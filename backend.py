"""Persistent, local ggmlc Laya process. No simulated predictions."""
import json
import queue
import subprocess
import threading
import time
from collections import deque


class LayaBackend:
    def __init__(self, executable, model, device="cuda"):
        self.lock = threading.Lock()
        self.messages = queue.Queue()
        self.stderr = deque(maxlen=30)
        self.sequence = 0
        self.closed = False
        args = [str(executable), "daemon", str(model), "--device", device]
        if device.startswith("cuda"):
            args.append("--cuda-graph")
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._stdout, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()
        try:
            greeting = self._receive(60)
            if greeting.get("status") != "ready":
                raise RuntimeError(f"Unexpected Laya startup response: {greeting}")
        except Exception:
            self.close()
            raise

    def _stdout(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                self.stderr.append(line.strip())
        self.messages.put(None)

    def _stderr(self):
        for line in self.process.stderr:
            self.stderr.append(line.strip())

    def _receive(self, timeout):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("Laya took too long to respond. Restart the app. " + " ".join(self.stderr)[-1200:])
        if value is None:
            raise RuntimeError("Laya process stopped. " + " ".join(self.stderr)[-1200:])
        if value.get("error"):
            raise RuntimeError(str(value["error"]))
        return value

    def predict(self, state, questions):
        with self.lock:
            if self.closed:
                raise RuntimeError("Laya is closed")
            self.sequence += 1
            request_id = str(self.sequence)
            self.process.stdin.write(json.dumps({"id": request_id, "state": state, "questions": questions}, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            result = self._receive(30)
            if str(result.get("id")) != request_id:
                raise RuntimeError("Laya response ID did not match the pending decision")
            if not isinstance(result.get("answers"), dict):
                raise RuntimeError("Laya did not return answers")
            return result

    @property
    def hardware(self):
        for line in self.stderr:
            if "Device 0:" in line:
                return line.split("Device 0:", 1)[1].split(", compute")[0].strip()
        return "CUDA device"

    def close(self):
        self.closed = True
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
