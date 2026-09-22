"""Uncapped, matched-configuration Snake runs with independent model decisions."""
import copy
import hashlib
import json
import statistics
import threading
import time
from collections import deque
from pathlib import Path

from providers import EngineRegistry
from upstream.game import SnakeGame
from upstream.policy import LayaPolicy


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    at = (len(values) - 1) * p
    low = int(at)
    return round(values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (at - low), 2)


class Comparison:
    def __init__(self, solo, config):
        self.solo = solo
        self.config = config
        self.registry = getattr(solo, "registry", None) or EngineRegistry(config)
        self.solo_id = getattr(solo, "engine_id", config.get("solo_engine", "laya"))
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.threads = []
        self.clients = []
        self.active = False
        self.pausing = False
        self.run_id = 0
        self.mode = "both"
        self.seed = int(config.get("seed", 7))
        self.limit = config.get("comparison_limit", 300)
        self.max_moves = config.get("comparison_max_moves", 1000)
        self.stop_condition = config.get("comparison_stop", "moves")
        self.observation = config.get("endurance_observation", "board")
        self.guarded = False if self.stop_condition == "endurance" else config.get("guarded", True)
        self.retention = config.get("max_recorded_moves", 10000)
        self.latency_window = 2048
        self.lanes = {}
        self._reset()

    def _reset(self):
        self.run_id += 1
        self.lanes = {}
        for name in self.registry.engines:
            self.lanes[name] = {
                "game": SnakeGame(self.config.get("width", 24), self.config.get("height", 16), self.seed, self.config.get("initial_length", 6)),
                "state": "ready", "error": None, "last": None,
                "interventions": 0, "input_tokens": 0, "output_tokens": 0,
                "latencies": deque(maxlen=self.latency_window), "frames": deque(maxlen=self.retention), "elapsed": 0.0,
                "segment_start": None, "recent": deque(maxlen=120),
                "model": self.registry.public(name)["model"],
            }
        initial = next(iter(self.lanes.values()))["game"].snapshot()
        self.initial_hash = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()

    def selected(self):
        return tuple(self.registry.engines) if self.mode == "both" else (self.mode,)

    def command(self, data):
        action = data.get("action")
        with self.lock:
            if action == "pause":
                self.stop.set()
                self.pausing = self.active
            elif action == "configure":
                if self.active:
                    raise ValueError("Pause and wait for current requests before changing the comparison.")
                mode = data.get("mode", self.mode)
                seed = data.get("seed", self.seed)
                limit = data.get("limit", self.limit)
                guarded = data.get("guarded", self.guarded)
                stop_condition = data.get("stop_condition", self.stop_condition)
                observation = data.get("observation", self.observation)
                if mode not in (*self.registry.engines, "both"):
                    raise ValueError("Select a configured engine or all engines")
                if type(seed) is not int or not 0 <= seed <= 999999:
                    raise ValueError("Seed must be an integer from 0 to 999999")
                if stop_condition not in ("moves", "endurance"):
                    raise ValueError("Choose a move budget or endurance")
                if observation not in ("board", "planner"):
                    raise ValueError("Choose board-only or planner-assisted input")
                if stop_condition == "moves" and (type(limit) is not int or not 1 <= limit <= self.max_moves):
                    raise ValueError(f"Move limit must be from 1 to {self.max_moves}")
                if stop_condition == "endurance":
                    limit = self.limit  # Retain the last budget for a later return to budget mode.
                    guarded = False
                if type(guarded) is not bool:
                    raise ValueError("Shield must be true or false")
                self.mode, self.seed, self.limit, self.guarded = mode, seed, limit, guarded
                self.stop_condition, self.observation = stop_condition, observation
                self._reset()
            elif action == "reset":
                if self.active:
                    raise ValueError("Pause and wait for current requests before resetting.")
                self._reset()
            elif action == "start":
                if self.active:
                    raise ValueError("Comparison is already running")
                names = [n for n in self.selected() if self.lanes[n]["state"] not in ("finished", "game_over", "error")]
                if not names:
                    raise ValueError("This run is complete. Choose New comparison.")
                if self.solo_id in names and (not self.solo.ready or self.solo.error):
                    raise ValueError(self.solo.error or "The solo engine is still loading")
                # Only acquire credentials for an explicit JEV run; no requests on page load.
                clients = {}
                try:
                    for name in names:
                        if name != self.solo_id:
                            clients[name] = self.registry.create(name)
                except Exception:
                    for client in clients.values():
                        client.close()
                    raise
                self.solo.command({"action": "pause"})
                self.stop = threading.Event()
                self.active = True
                self.pausing = False
                self.remaining = len(names)
                self.clients = list(clients.values())
                barrier = threading.Barrier(len(names))
                self.threads = []
                for name in names:
                    self.lanes[name]["state"] = "preparing"
                    client = clients.get(name, self.solo.backend)
                    t = threading.Thread(target=self._worker, args=(name, client, barrier), daemon=True)
                    self.threads.append(t)
                    t.start()
            else:
                raise ValueError("Unknown comparison action")
        return self.snapshot()

    def _worker(self, name, client, barrier):
        lane = self.lanes[name]
        try:
            # Let a pending solo inference finish before the matched start barrier.
            if name == self.solo_id:
                while self.solo.busy:
                    if self.stop.wait(.01):
                        barrier.abort()
                        return
            barrier.wait(timeout=30)
            with self.lock:
                lane["segment_start"] = time.perf_counter()
                lane["state"] = "running"
            policy = self._policy(client)
            while not self.stop.is_set():
                with self.lock:
                    if self._budget_reached(lane) or not lane["game"].alive or lane["game"].won:
                        break
                    game = copy.deepcopy(lane["game"])
                before = game.snapshot()
                decision = policy.decide(game)
                game.step(decision.executed)
                if self.guarded and (not game.alive or not game.cycle_order_valid()):
                    raise RuntimeError("Cycle safety invariant failed")
                now = time.perf_counter()
                with self.lock:
                    lane["game"] = game
                    lane["last"] = decision.to_dict()
                    lane["latencies"].append(decision.inference_ms)
                    lane["recent"].append(now)
                    lane["interventions"] += int(decision.intervened)
                    lane["input_tokens"] += decision.input_tokens
                    lane["output_tokens"] += decision.output_tokens
                    lane["model"] = getattr(client, "reported_model", None) or lane["model"]
                    lane["frames"].append({"before": before, "decision": lane["last"], "after": game.snapshot()})
        except threading.BrokenBarrierError:
            if not self.stop.is_set():
                with self.lock:
                    lane["error"] = "Could not synchronize the comparison start. Try a new run."
        except Exception as exc:
            # Backend errors are already sanitized; never include key, headers, or body.
            with self.lock:
                lane["error"] = str(exc)
            if lane["state"] == "preparing":
                barrier.abort()
        finally:
            ended_at = time.perf_counter()  # Resource teardown is not survival time.
            if name != self.solo_id:
                try:
                    client.close()
                except Exception:
                    pass
            with self.lock:
                if lane["segment_start"] is not None:
                    lane["elapsed"] += ended_at - lane["segment_start"]
                    lane["segment_start"] = None
                lane["state"] = "error" if lane["error"] else "game_over" if not lane["game"].alive else "finished" if self._budget_reached(lane) or lane["game"].won else "paused"
                self.remaining -= 1
                if self.remaining == 0:
                    self.active = self.pausing = False

    def _budget_reached(self, lane):
        return self.stop_condition == "moves" and lane["game"].ticks >= self.limit

    def _policy(self, client):
        if self.stop_condition == "endurance" and self.observation == "board":
            from board_policy import BoardPolicy
            return BoardPolicy(client)
        return LayaPolicy(client, guarded=self.guarded, prompt=self.config.get("prompt", "compact"))

    def snapshot(self):
        with self.lock:
            lanes = {}
            now = time.perf_counter()
            for name, lane in self.lanes.items():
                elapsed = lane["elapsed"] + (now - lane["segment_start"] if lane["segment_start"] is not None else 0)
                recent = [t for t in lane["recent"] if now - t < 5]
                rate = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 1 else 0
                latencies = lane["latencies"]
                lanes[name] = {
                    "selected": name in self.selected(), "state": lane["state"],
                    "engine": self.registry.public(name),
                    "error": lane["error"], "game": lane["game"].snapshot(),
                    "termination_reason": "provider_error" if lane["error"] else lane["game"].death_reason if not lane["game"].alive else "board_filled" if lane["game"].won else "move_limit" if self._budget_reached(lane) else None,
                    "last": copy.deepcopy(lane["last"]), "model": lane["model"],
                    "interventions": lane["interventions"],
                    "elapsed_s": round(elapsed, 3),
                    "average_rate": round(lane["game"].ticks / elapsed, 2) if elapsed > 0 else 0,
                    "recent_rate": round(rate, 2),
                    "median_ms": round(statistics.median(latencies), 2) if latencies else None,
                    "p95_ms": percentile(latencies, .95),
                    "input_tokens": lane["input_tokens"], "output_tokens": lane["output_tokens"],
                    "retained_frames": len(lane["frames"]),
                    "latency_samples": len(latencies),
                }
            return {"mode": self.mode, "seed": self.seed, "limit": self.limit,
                    "stop_condition": self.stop_condition, "observation": self.observation,
                    "retention_limit": self.retention, "latency_window": self.latency_window,
                    "guarded": self.guarded, "active": self.active, "pausing": self.pausing,
                    "run_id": self.run_id, "initial_state_sha256": self.initial_hash,
                    "lanes": lanes, "hardware": self.solo.hardware,
                    "solo_engine": self.solo_id, "max_moves": self.max_moves,
                    "engines": [self.registry.public(n) for n in self.registry.engines],
                    "solo_ready": self.solo.ready and not self.solo.error}

    def export(self):
        with self.lock:
            return {"format": "laya-snake-arena-compare-v2", "summary": self.snapshot(), "prompt": "raw-board-v1" if self.stop_condition == "endurance" and self.observation == "board" else self.config.get("prompt", "compact"),
                    "method": "Same board, initial body, seed, input policy, and termination setting. Endurance has no move/time limit and never overrides the model's move. Each lane ends independently on collision, a full board, or a provider error; user pause remains available. Score and move counters are cumulative; only the last retention_limit frames and latency_window timings remain in memory. Paths may diverge. API wall latency includes network; the solo model is resident. Pauses excluded from elapsed time; connection setup included in a provider's first decision. Built-in providers use no automatic retries or result cache.",
                    "frames": {n: list(self.lanes[n]["frames"]) for n in self.selected()}}

    def close(self):
        self.stop.set()
        for client in self.clients:
            try:
                client.close()
            except Exception:
                pass
        for thread in self.threads:
            thread.join(timeout=2)
