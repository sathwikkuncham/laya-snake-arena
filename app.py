"""Local Windows port of the Laya Snake demonstration; Python standard library only."""
import argparse
import copy
import json
import logging
import math
import secrets
import threading
import time
import urllib.request
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from providers import EngineRegistry
from compare import Comparison
from settings import load_config
from upstream.game import SnakeGame
from upstream.policy import LayaPolicy

ROOT = Path(__file__).resolve().parent
APP_ID = "laya-snake-arena-v1"


class Session:
    def __init__(self, config):
        self.config = config
        self.registry = EngineRegistry(config)
        self.engine_id = config.get("solo_engine", "laya")
        self.engine = self.registry.public(self.engine_id)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = threading.Event()
        self.backend = None
        self.ready = False
        self.error = None
        self.loading = "Preparing the selected engine…"
        self.running = False
        self.step_requested = False
        self.busy = False
        self.epoch = 0
        self.guarded = config.get("guarded", True)
        self.fps = float(config.get("fps", 8))
        self.seed = int(config.get("seed", 7))
        self.best = 0
        self.hardware = "Connecting to CUDA…"
        self._new_game()
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    def _new_game(self):
        self.game = SnakeGame(int(self.config.get("width", 24)), int(self.config.get("height", 16)), self.seed, self.config.get("initial_length", 6))
        self.last = None
        self.interventions = 0
        self.samples = deque(maxlen=50)
        self.completed = deque(maxlen=60)
        self.recording = deque(maxlen=self.config.get("max_recorded_moves", 10000))
        self.total_frames = 0
        self.started_at = time.time()
        self.running = False
        self.step_requested = False
        self.epoch += 1

    def _loop(self):
        try:
            self.backend = self.registry.create(self.engine_id)
            with self.lock:
                self.hardware = self.backend.hardware
                self.loading = "Warming up local decisions…"
            warm = SnakeGame(self.config.get("width", 24), self.config.get("height", 16), self.seed + 1000, self.config.get("initial_length", 6))
            policy = LayaPolicy(self.backend, prompt=self.config.get("prompt", "compact"))
            warmups = self.config.get("warmup_moves", 3) if self.engine["provider"] == "ggmlc" else 0
            for _ in range(warmups):
                if self.closed.is_set():
                    return
                if warm.won:
                    break
                warm.step(policy.decide(warm).executed)
            with self.lock:
                self.ready = True
                self.loading = ""
            while not self.closed.is_set():
                with self.lock:
                    work = self.ready and not self.error and (self.running or self.step_requested) and self.game.alive and not self.game.won
                    if work:
                        self.step_requested = False
                        self.busy = True
                        epoch = self.epoch
                        game = copy.deepcopy(self.game)
                        guarded = self.guarded
                if not work:
                    self.wake.wait(0.2)
                    self.wake.clear()
                    continue
                start = time.perf_counter()
                try:
                    decision = LayaPolicy(self.backend, guarded=guarded, prompt=self.config.get("prompt", "compact")).decide(game)
                    before = game.snapshot()
                    game.step(decision.executed)
                    if guarded and (not game.alive or not game.cycle_order_valid()):
                        raise RuntimeError("The safety planner invariant failed; game paused.")
                    now = time.perf_counter()
                    with self.lock:
                        if epoch == self.epoch and not self.closed.is_set():
                            self.game = game
                            self.last = decision.to_dict()
                            self.interventions += int(decision.intervened)
                            self.samples.append(decision.inference_ms)
                            self.completed.append(now)
                            self.best = max(self.best, game.score)
                            self.total_frames += 1
                            self.recording.append({"step": game.ticks, "at": time.time(), "before": before, "decision": self.last, "after": game.snapshot(), "guarded": guarded})
                            if not game.alive or game.won:
                                self.running = False
                        self.busy = False
                        delay = max(0, 1 / self.fps - (now - start)) if self.fps else 0
                except Exception as exc:
                    logging.exception("Prediction failed")
                    with self.lock:
                        self.error = str(exc)
                        self.running = self.busy = False
                    continue
                self.wake.wait(delay)
                self.wake.clear()
        except Exception as exc:
            logging.exception("Runtime initialization failed")
            with self.lock:
                self.error = str(exc)
                self.loading = ""
        finally:
            if self.backend:
                self.backend.close()

    def snapshot(self):
        with self.lock:
            timestamps = [t for t in self.completed if time.perf_counter() - t < 3]
            rate = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0
            return {
                "app": APP_ID, "ready": self.ready, "loading": self.loading,
                "error": self.error, "running": self.running, "busy": self.busy,
                "guarded": self.guarded, "fps": self.fps, "hardware": self.hardware,
                "model": (self.backend.reported_model if self.backend else None) or self.engine["model"], "engine": self.engine, "game": self.game.snapshot(),
                "last": copy.deepcopy(self.last), "interventions": self.interventions,
                "best": self.best, "rate": round(rate, 2),
                "mean_ms": round(sum(self.samples) / len(self.samples), 2) if self.samples else None,
                "recorded": len(self.recording), "epoch": self.epoch,
            }

    def command(self, data):
        action = data.get("action")
        with self.lock:
            if action == "reset":
                seed = data.get("seed", self.seed + 1)
                if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 999999:
                    raise ValueError("Seed must be an integer from 0 to 999999")
                self.seed = seed
                self._new_game()
            elif action == "shield":
                if not isinstance(data.get("enabled"), bool):
                    raise ValueError("Shield must be true or false")
                self.guarded = data["enabled"]
                self._new_game()  # A new valid cycle is required when re-enabling protection.
            elif action == "speed":
                fps = data.get("fps")
                if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps not in (0, 2, 4, 8, 12, 20):
                    raise ValueError("Unsupported speed")
                self.fps = float(fps)
            elif action == "pause":
                self.running = self.step_requested = False
                self.epoch += 1  # Discard a pending move rather than moving after pause.
            elif action in ("start", "step"):
                if not self.ready or self.error:
                    raise ValueError(self.error or "Model is still loading")
                if not self.game.alive or self.game.won:
                    raise ValueError("Start a new game first")
                if action == "start":
                    self.running = True
                else:
                    if self.running or self.busy or self.step_requested:
                        raise ValueError("Pause and wait for the current decision first")
                    self.step_requested = True
            else:
                raise ValueError("Unknown action")
            self.wake.set()
        return self.snapshot()

    def export(self):
        with self.lock:
            return {"format": APP_ID, "model": (self.backend.reported_model if self.backend else None) or self.engine["model"],
                    "backend": self.engine["provider"], "engine": self.engine, "prompt": self.config.get("prompt", "compact"), "hardware": self.hardware,
                    "source": "https://github.com/mizorewww/laya-mlx",
                    "note": "Real model outputs over planner features. Safety shield may change the executed move. Each prediction corresponds to the before board.",
                    "started_at": self.started_at, "total_frames": self.total_frames,
                    "retained_frames": len(self.recording), "frames": list(self.recording)}

    def close(self):
        self.closed.set()
        self.wake.set()
        if self.backend:
            self.backend.close()
        self.worker.join(timeout=3)


def run(config, open_browser=False):
    port = int(config.get("port", 8765))
    token = secrets.token_urlsafe(32)
    url = f"http://127.0.0.1:{port}"
    # Reopening the launcher reuses this app only, never starts a second GPU worker.
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
            existing = json.load(response)
        if existing.get("app") == APP_ID:
            if open_browser:
                webbrowser.open(url)
            return
    except Exception:
        pass
    session = None

    class Handler(BaseHTTPRequestHandler):
        def local_request(self):
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                self.send({"error": "Local access only"}, 403)
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed}:
                self.send({"error": "Cross-origin requests are not allowed"}, 403)
                return False
            return True

        def log_message(self, fmt, *args):
            pass

        def send(self, value, status=200, kind="application/json; charset=utf-8", filename=None):
            body = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            if not self.local_request():
                return
            path = urlparse(self.path).path
            if path == "/api/health":
                return self.send({"app": APP_ID})
            if path == "/api/state":
                return self.send(session.snapshot())
            if path == "/api/compare/state":
                return self.send(comparison.snapshot())
            if path == "/api/compare/recording":
                return self.send(comparison.export(), filename="laya-jev-comparison.json")
            if path == "/api/recording":
                return self.send(session.export(), filename="laya-snake-recording.json")
            files = {"/": ("index.html", "text/html; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "application/javascript; charset=utf-8"), "/draw.js": ("draw.js", "application/javascript; charset=utf-8"), "/compare.js": ("compare.js", "application/javascript; charset=utf-8")}
            if path in files:
                name, mime = files[path]
                content = (ROOT / "static" / name).read_bytes()
                if name == "index.html":
                    content = content.replace(b"__APP_TOKEN__", token.encode())
                return self.send(content, kind=mime)
            return self.send({"error": "Not found"}, 404)

        def do_POST(self):
            if not self.local_request():
                return
            if self.headers.get("X-App-Token") != token:
                return self.send({"error": "Reload this app to reconnect"}, 403)
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length < 4096:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                if self.path == "/api/shutdown":
                    self.send({"ok": True})
                    threading.Thread(target=server.shutdown, daemon=True).start()
                    return
                if self.path == "/api/compare/control":
                    return self.send(comparison.command(data))
                if self.path != "/api/control":
                    return self.send({"error": "Not found"}, 404)
                if comparison.active and data.get("action") in ("start", "step"):
                    raise ValueError("Pause the comparison before playing in Solo mode.")
                self.send(session.command(data))
            except (ValueError, TypeError, RuntimeError) as exc:
                self.send({"error": str(exc)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    session = Session(config)
    comparison = Comparison(session, config)
    try:
        if open_browser:
            webbrowser.open(url)
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        comparison.close()
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    log_dir = ROOT / "runtime"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(filename=log_dir / "app.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(load_config(ROOT), args.open)
    except Exception as exc:
        logging.exception("App failed")
        if args.open and __import__("os").name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"{exc}\n\nSee runtime/app.log in the app folder.", "Laya Snake could not start", 0x10)
        raise
