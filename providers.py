"""Backend extension contract and local, configuration-driven engine registry."""
import importlib
import math
from pathlib import Path
from typing import Protocol

from backend import LayaBackend
from jev_backend import JevBackend


class DecisionBackend(Protocol):
    def predict(self, state, questions) -> dict: ...
    def close(self) -> None: ...


DEFAULT_ENGINES = {
    "laya": {"provider": "ggmlc", "label": "Laya", "caption": "Local GPU", "color": "#c9ef7d", "options": {}},
    "jev": {"provider": "typesafe", "label": "JEV", "caption": "TypeSafe cloud", "color": "#91cfe3", "options": {}},
}


def validate_response(result, questions):
    """Fail closed: no game move may execute using malformed model output."""
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise ValueError("Engine response must contain an answers object")
    usage = result.get("usage", {})
    if not isinstance(usage, dict):
        raise ValueError("Engine response must contain a usage object")
    for name in ("input_tokens", "output_tokens"):
        value = usage.get(name, 0 if name == "output_tokens" else None)
        if type(value) is not int or value < 0:
            raise ValueError("Engine response must report nonnegative token usage")
    for qid, question in questions.items():
        answer = result["answers"].get(qid)
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise ValueError("Engine response question types must match the request")
        if question["type"] == "choice":
            probs = answer.get("probabilities", {})
            if not isinstance(probs, dict) or set(probs) != set(question["criteria"]):
                raise ValueError("Engine response choice labels must match the request")
            values = list(probs.values())
        elif question["type"] == "noul":
            values = [answer.get("noul")]
        else:
            raise ValueError("Snake currently uses choice and noul questions only")
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError("Engine response contains invalid probabilities")
        if question["type"] == "choice" and abs(sum(values) - 1) > .02:
            raise ValueError("Engine choice probabilities must sum to one")
    return result


class CheckedBackend:
    def __init__(self, backend, trusted_errors=False):
        self._backend = backend
        self._trusted_errors = trusted_errors
        self._closed = False

    def predict(self, state, questions):
        try:
            response = self._backend.predict(state, questions)
        except Exception:
            if self._trusted_errors:
                raise
            raise RuntimeError("Custom engine request failed. Check the provider implementation; no move was executed.") from None
        return validate_response(response, questions)

    @property
    def reported_model(self):
        return getattr(self._backend, "reported_model", None)

    @property
    def hardware(self):
        return getattr(self._backend, "hardware", "External decision engine")

    def close(self):
        if not self._closed:
            self._closed = True
            self._backend.close()


def ggmlc_factory(options, config):
    executable = options.get("executable", config["executable"])
    model = options.get("model", config["model"])
    for label, path in (("executable", executable), ("model", model)):
        if not Path(path).is_file():
            raise RuntimeError(f"Missing {label}. Set its path in config.json or the corresponding environment variable.")
    return LayaBackend(executable, model, options.get("device", config.get("device", "cuda")))


def typesafe_factory(options, config):
    return JevBackend(options.get("settings_path", config.get("jev_settings")), options.get("model", config.get("jev_model", "jev-latest")))


class EngineRegistry:
    """Plugins register local Python factories; options never go to the browser."""
    def __init__(self, config):
        self.config = config
        self.factories = {"ggmlc": ggmlc_factory, "typesafe": typesafe_factory}
        for module_name in config.get("plugins", []):
            try:
                importlib.import_module(module_name).register(self)
            except Exception:
                raise ValueError(f"Could not register configured plugin {module_name}") from None
        self.engines = config.get("engines", DEFAULT_ENGINES)
        for engine in self.engines.values():
            if engine["provider"] not in self.factories:
                raise ValueError(f"Unknown provider: {engine['provider']}")

    def register(self, provider_name, factory):
        if provider_name in self.factories:
            raise ValueError("Provider already registered")
        if not callable(factory):
            raise ValueError("Provider factory must be callable")
        self.factories[provider_name] = factory

    def create(self, engine_id):
        engine = self.engines[engine_id]
        provider = engine["provider"]
        try:
            backend = self.factories[provider](dict(engine.get("options", {})), self.config)
        except Exception:
            if provider in ("ggmlc", "typesafe"):
                raise
            raise RuntimeError("Custom engine could not initialize. Check its local configuration.") from None
        if not callable(getattr(backend, "predict", None)) or not callable(getattr(backend, "close", None)):
            raise ValueError("A backend must implement predict(state, questions) and close()")
        return CheckedBackend(backend, trusted_errors=provider in ("ggmlc", "typesafe"))

    def public(self, engine_id):
        engine = self.engines[engine_id]
        provider, options = engine["provider"], engine.get("options", {})
        model = options.get("model", self.config.get("model", "") if provider == "ggmlc" else self.config.get("jev_model", "jev-latest") if provider == "typesafe" else engine_id)
        if provider == "ggmlc":
            model = Path(model).name
        return {"id": engine_id, "label": engine.get("label", engine_id),
                "caption": engine.get("caption", provider), "color": engine.get("color", "#c9ef7d"),
                "provider": provider, "model": model}
