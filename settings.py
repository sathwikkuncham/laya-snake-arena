"""Portable local configuration. Secrets are read only into the server process."""
import json
import os
import re
from copy import deepcopy
from pathlib import Path

from providers import DEFAULT_ENGINES


DEFAULTS = {"width": 24, "height": 16, "initial_length": 6, "seed": 7, "fps": 8,
            "guarded": True, "prompt": "compact", "warmup_moves": 3,
            "max_recorded_moves": 10000, "comparison_limit": 300,
            "comparison_max_moves": 1000, "comparison_stop": "moves", "endurance_observation": "board", "solo_engine": "laya", "plugins": [],
            "engines": DEFAULT_ENGINES, "jev_settings": None, "jev_model": "jev-latest"}


def validate_config(config):
    if config["comparison_stop"] not in ("moves", "endurance") or config["endurance_observation"] not in ("board", "planner"):
        raise ValueError("Invalid comparison termination or endurance input setting")
    for key, low, high in (("width", 4, 64), ("height", 4, 64), ("seed", 0, 999999),
                           ("initial_length", 2, 4095), ("warmup_moves", 0, 20),
                           ("max_recorded_moves", 1, 10000), ("comparison_limit", 1, 10000),
                           ("comparison_max_moves", 1, 10000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    if config["width"] % 2 and config["height"] % 2:
        raise ValueError("At least one board dimension must be even")
    if config["initial_length"] >= config["width"] * config["height"]:
        raise ValueError("initial_length must be smaller than the board")
    if config["comparison_limit"] > config["comparison_max_moves"]:
        raise ValueError("comparison_limit exceeds comparison_max_moves")
    if type(config["guarded"]) is not bool or config["prompt"] not in ("compact", "detailed"):
        raise ValueError("guarded must be boolean and prompt must be compact or detailed")
    if type(config["fps"]) not in (int, float) or config["fps"] not in (0, 2, 4, 8, 12, 20):
        raise ValueError("fps must be 0, 2, 4, 8, 12, or 20")
    engines = config["engines"]
    if not isinstance(engines, dict) or not 1 <= len(engines) <= 4:
        raise ValueError("Configure between one and four engines")
    for engine_id, spec in engines.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", engine_id) or engine_id in ("all", "both"):
            raise ValueError("Engine IDs must be short lowercase identifiers; all and both are reserved")
        if not isinstance(spec, dict) or not isinstance(spec.get("provider"), str):
            raise ValueError("Every engine needs a provider")
        if not isinstance(spec.get("options", {}), dict):
            raise ValueError("Engine options must be an object")
        for key in ("label", "caption"):
            if key in spec and (not isinstance(spec[key], str) or not 1 <= len(spec[key]) <= 80):
                raise ValueError(f"Engine {key} must be 1–80 characters")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", spec.get("color", "#c9ef7d")):
            raise ValueError("Engine color must be a six-digit hex color")
    if config["solo_engine"] not in engines:
        raise ValueError("solo_engine must name a configured engine")
    if not isinstance(config["plugins"], list) or any(not isinstance(p, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", p) for p in config["plugins"]):
        raise ValueError("plugins must contain local Python module names")
    return config


def load_config(root):
    root = Path(root)
    dotenv = root / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key in {"TYPESAFE_API_KEY", "LAYA_EXECUTABLE", "LAYA_MODEL", "LAYA_DEVICE", "LAYA_PORT", "JEV_MODEL", "VERDICT_CONFIG"}:
                os.environ.setdefault(key, value)
    config = deepcopy(DEFAULTS)
    config.update(json.loads((root / "config.example.json").read_text(encoding="utf-8-sig")))
    path = root / "config.json"
    if path.is_file():
        config.update(json.loads(path.read_text(encoding="utf-8-sig")))
    for key, env in {"executable":"LAYA_EXECUTABLE", "model":"LAYA_MODEL", "device":"LAYA_DEVICE", "port":"LAYA_PORT", "jev_model":"JEV_MODEL", "jev_settings":"VERDICT_CONFIG"}.items():
        if os.environ.get(env):
            config[key] = os.environ[env]
    for key in ("executable", "model", "jev_settings"):
        if config.get(key):
            candidate = Path(config[key]).expanduser()
            config[key] = str(candidate if candidate.is_absolute() else (root / candidate).resolve())
    validate_config(config)
    for engine in config.get("engines", {}).values():
        if not isinstance(engine, dict) or not isinstance(engine.get("options", {}), dict):
            continue
        if engine.get("provider") in ("ggmlc", "typesafe"):
            for key in (("executable", "model") if engine["provider"] == "ggmlc" else ("settings_path",)):
                if engine.get("options", {}).get(key):
                    candidate = Path(engine["options"][key]).expanduser()
                    engine["options"][key] = str(candidate if candidate.is_absolute() else (root / candidate).resolve())
    config["port"] = int(config["port"])
    if not 1024 <= config["port"] <= 65535:
        raise ValueError("Port must be between 1024 and 65535")
    return validate_config(config)
