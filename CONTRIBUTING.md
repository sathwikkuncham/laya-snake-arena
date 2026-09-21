# Contributing

Bug reports, documentation fixes, accessibility improvements, and provider
adapters are welcome. Discuss substantial changes in an issue first.

## Local development

Use Python 3.11+ and Node.js only for JavaScript syntax checks. The core app has
no third-party Python dependencies. Configure model paths in ignored `config.json`
and credentials in ignored `.env` when needed. The deterministic example provider
in `docs/EXTENDING.md` enables development without a GPU or paid API.

```sh
python -m unittest discover -s tests -v
python -m compileall -q app.py backend.py compare.py jev_backend.py providers.py settings.py plugins tests
node --check static/app.js
node --check static/compare.js
node --check static/draw.js
```

For UI changes, check Solo and Compare, start/pause/reset, narrow screens,
keyboard access, and visible errors. Use actual inference for a manual integration
check when appropriate; CI must remain offline and credential-free.

## Pull requests

- Keep changes focused and explain the user-visible result.
- Add meaningful regression tests for changes to provider contracts or threading.
- Preserve original-source notices and mark modifications to vendored code.
- Update configuration/extension docs when changing the public interface.
- Do not commit secrets, private settings, personal paths, downloaded binaries,
  model weights, logs, or large videos.
- Use the provider registry instead of hard-coding another model into the UI.
- Keep local and remote latency definitions explicit. Do not fabricate model
  probabilities, silently replay predictions, or imply the safety planner is AI.

Contributions are licensed under the repository's Apache-2.0 license. No CLA is
required. See `CODE_OF_CONDUCT.md` for community expectations.
