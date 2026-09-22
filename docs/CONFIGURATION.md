# Configuration guide

## Files and precedence

Start with `config.example.json`. Optional `config.json` overrides its values.
Recognized environment variables override both. An optional `.env` file sets
recognized variables only when they are not already present in the process.
Restart the app after configuration changes.

Both `config.json` and `.env` are ignored by Git. Do not put keys in JavaScript,
screenshots, exported data, or public documentation.

## Typical setup

```powershell
Copy-Item config.example.json config.json
Copy-Item .env.example .env
```

Edit `config.json`:

```json
{
  "executable": "D:/AI/laya/laya.exe",
  "model": "D:/AI/models/laya_multilingual_f16.gguf",
  "device": "cuda",
  "port": 8765,
  "width": 24,
  "height": 16,
  "seed": 7,
  "fps": 8,
  "jev_settings": null,
  "jev_model": "jev-latest"
}
```

Use forward slashes in JSON, or escape Windows backslashes as `\\`.
The app resolves relative file paths against its own directory, not the terminal's
working directory. It does not download binaries or weights automatically.

| Setting | Meaning |
|---|---|
| `executable` | Path to the separately downloaded ggmlc `laya.exe` |
| `model` | Path to the compatible GGUF checkpoint |
| `device` | `cuda` is the tested Windows setting; backend-dependent alternatives require separate validation |
| `port` | Local HTTP port, 1024–65535; default 8765 |
| `width`, `height` | Board dimensions, at least 4; at least one must be even for the cycle planner |
| `seed` | Initial food-placement seed |
| `fps` | Solo target moves/s; 0 removes pacing. Comparisons always run uncapped |
| `jev_settings` | Optional existing Verdict settings JSON containing `apiKey` |
| `jev_model` | TypeSafe model alias or supported version; default `jev-latest` |
| `initial_length` | Starting snake length; at least 2 and smaller than the board |
| `guarded` | Default safety shield state, boolean |
| `prompt` | Original policy prompt style: `compact` or `detailed` |
| `warmup_moves` | Local ggmlc warmup moves (0–20); remote providers are not warmed at startup |
| `max_recorded_moves` | Solo recording retention (1–10,000); larger boards use more memory |
| `comparison_limit` | Default moves per engine |
| `comparison_max_moves` | Maximum selectable comparison moves (1–10,000) |
| `comparison_stop` | `moves` for a fixed budget, or `endurance` for collision/full-board termination without a move/time cap |
| `endurance_observation` | `board` for board and rules only; `planner` retains assisted descriptions. Endurance always disables move overrides |
| `solo_engine` | ID of the engine used by the solo view |
| `engines` | One to four engine definitions; see the extension guide |
| `plugins` | Trusted local Python modules exposing `register(registry)` |

The default game begins with six segments. Board dimensions range from 4 to 64,
with at least one even dimension. Model, backend, board size, and shield can all
affect performance. Published recordings use a 24 × 16 board and FP16 multilingual
weights. Multilingual is the original demo author's default for this workload;
it is not a claim that this checkpoint is best for every English task.

See [EXTENDING.md](EXTENDING.md) for adding engines. The top-level configuration
merge is shallow: an `engines` value in `config.json` replaces the whole example
mapping. Built-in provider options override their top-level fallback settings.
For example, `engines.english.options.model` selects a second checkpoint while
the other local engine can continue using the top-level `model` value.

## Environment variables

| Variable | Overrides |
|---|---|
| `LAYA_EXECUTABLE` | `executable` |
| `LAYA_MODEL` | `model` |
| `LAYA_DEVICE` | `device` |
| `LAYA_PORT` | `port` |
| `JEV_MODEL` | `jev_model` |
| `VERDICT_CONFIG` | `jev_settings` |
| `TYPESAFE_API_KEY` | Direct TypeSafe credential; takes priority over the Verdict key |

The optional `.env` parser accepts `KEY=value` with optional matching quotes.
It does not evaluate shell expressions or expand other variables.

For an existing Verdict setup, set `jev_settings` or `VERDICT_CONFIG` to your
private settings file. No credential needs to be copied. Otherwise, set
`TYPESAFE_API_KEY` in `.env` or your process environment. The client sends it only
to `api.typesafe.ai` over verified HTTPS. No JEV request occurs merely by opening
the app or selecting a panel.

For the double-click launcher, install Python with PATH integration. It prefers
`.venv/Scripts/pythonw.exe` when present. You may set the Windows environment
variable `LAYA_SNAKE_PYTHON` to another `pythonw.exe`. This launcher-only variable
is read by Windows Script Host, so it belongs in the process/user environment,
not the app's `.env` file.

## Troubleshooting

- **Missing executable/model:** check `config.json` and confirm the file exists.
- **Python not found:** install Python 3.11+ and enable Add to PATH, then reopen
  your terminal. `python app.py --open` also bypasses the VBS launcher.
- **CUDA startup failure:** verify the executable build supports your GPU and
  your NVIDIA driver. The recorded test used the v0.9.1 `sm89` Windows build.
- **Port in use:** change `port` and restart. Reopening the same app normally
  reuses its existing instance.
- **JEV authentication failure:** update the local key and restart. The error
  display intentionally does not echo keys or request headers.
- **JEV timeout/rate limit:** the run stops without silently retrying. Start a
  new comparison after resolving the connection or account limit.
- **A lane finishes first:** expected. Each advances independently to its move
  budget or, in endurance mode, a collision or full board. Errors are reported
  separately from Snake deaths and do not stop another running lane.
- **App stays running after closing a tab:** use Quit app to unload the model.

The app binds only to `127.0.0.1`. Do not expose this development server directly
to the public internet. Diagnostic logs are local under `runtime/`.
