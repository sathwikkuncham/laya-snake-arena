"""Direct TypeSafe JEV client. Read the existing Verdict key only on the server."""
import http.client
import json
import math
import os
import ssl
from pathlib import Path


class JevBackend:
    def __init__(self, settings_path, model="jev-latest"):
        self.model = model
        self.reported_model = model
        saved = {}
        path = Path(settings_path) if settings_path else None
        if path and path.is_file():
            saved = json.loads(path.read_text(encoding="utf-8-sig"))
        self._key = os.environ.get("TYPESAFE_API_KEY") or saved.get("apiKey")
        if not isinstance(self._key, str) or not self._key.strip():
            raise RuntimeError("Set TYPESAFE_API_KEY in .env or point jev_settings to your Verdict settings file.")
        self._key = self._key.strip()
        if "\r" in self._key or "\n" in self._key:
            raise RuntimeError("The saved TypeSafe key has an invalid format.")
        self._connection = None

    def predict(self, state, questions):
        if self._connection is None:
            self._connection = http.client.HTTPSConnection("api.typesafe.ai", timeout=20, context=ssl.create_default_context())
        body = json.dumps({"model": self.model, "state": state, "questions": questions}, ensure_ascii=False).encode("utf-8")
        try:
            self._connection.request("POST", "/v1/systemone", body=body, headers={
                "Authorization": "Bearer " + self._key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Laya-Snake-Windows/1.0",
            })
            response = self._connection.getresponse()
            raw = response.read(2_000_000)
            if response.status != 200:
                messages = {401: "The saved TypeSafe key was rejected.", 402: "TypeSafe reports insufficient credits.", 403: "TypeSafe denied this request.", 422: "TypeSafe rejected the question schema.", 429: "TypeSafe rate limit reached. Wait before starting another run.", 529: "TypeSafe is overloaded. Try again later."}
                raise RuntimeError(messages.get(response.status, f"TypeSafe returned HTTP {response.status}."))
            result = json.loads(raw)
            answers = result.get("answers", {})
            for qid, question in questions.items():
                answer = answers.get(qid, {})
                if answer.get("type") != question["type"]:
                    raise ValueError("JEV returned an unexpected answer type")
                if question["type"] == "choice":
                    probabilities = answer.get("probabilities", {})
                    if set(probabilities) != set(question["criteria"]):
                        raise ValueError("JEV returned unexpected direction labels")
                    values = list(probabilities.values())
                    if not self._valid(values) or abs(sum(values) - 1) > .02:
                        raise ValueError("JEV returned an invalid probability distribution")
                elif not self._valid([answer.get("noul")]):
                    raise ValueError("JEV returned an invalid probability")
            usage = result.get("usage")
            if not isinstance(usage, dict) or not isinstance(usage.get("input_tokens"), int):
                raise ValueError("JEV response is missing token usage")
            self.reported_model = str(result.get("model", self.model))
            return result
        except (OSError, http.client.HTTPException):
            self.close()
            raise RuntimeError("Could not reach TypeSafe. Check your connection and try a new run.") from None

    @staticmethod
    def _valid(values):
        return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1 for v in values)

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None
