# Add or replace a decision engine

The game and original prompt policy do not depend on a particular inference
library. The provider registry connects a typed-decision backend to that policy.

## 1. Add another instance of a built-in provider

Copy `config.example.json` to the ignored `config.json`. Its `engines` object is
replaced as a whole when overridden, so include every engine you want to keep.
For example, these entries compare two Laya checkpoints without editing Python:

```json
{
  "solo_engine": "multilingual",
  "engines": {
    "multilingual": {
      "provider": "ggmlc",
      "label": "Laya Multilingual",
      "caption": "Local CUDA",
      "color": "#c9ef7d",
      "options": {"model": "models/laya_multilingual_f16.gguf"}
    },
    "english": {
      "provider": "ggmlc",
      "label": "Laya English",
      "caption": "Local CUDA",
      "color": "#91cfe3",
      "options": {"model": "models/laya_english_f16.gguf"}
    }
  }
}
```

Both use the top-level `executable` and `device` unless overridden in their
options. Model and executable paths can be relative to the app directory.
Multiple local engines occupy GPU memory concurrently. Choose models that fit
your hardware; this configuration is an example, not a measured benchmark.

For `typesafe`, options may override `model` and `settings_path` (an existing
Verdict settings JSON). API keys stay in environment variables or private
settings, never in the engine's public label or model metadata.

## 2. Define a backend

A backend implements this interface:

```python
class MyBackend:
    reported_model = "my-model-version"  # public metadata, no credentials
    hardware = "Local CPU"              # optional descriptive metadata

    def predict(self, state, questions):
        # Perform a fresh inference here. Return the typed result described below.
        raise NotImplementedError

    def close(self):
        # Release connections, processes, and device resources. Be idempotent.
        pass
```

`state` is the original policy's text and `questions` is a dictionary of typed
questions. Snake currently submits one `choice` and two `noul` questions per move.
The policy must be able to read this response contract:

```json
{
  "model": "my-model-version",
  "answers": {
    "move": {
      "type": "choice",
      "probabilities": {"UP": 0.1, "DOWN": 0.6, "LEFT": 0.1, "RIGHT": 0.2}
    },
    "risk": {"type": "noul", "noul": 0.9},
    "food": {"type": "noul", "noul": 0.8}
  },
  "usage": {"input_tokens": 154, "output_tokens": 0}
}
```

The values above illustrate the schema, not a real model response. Return actual
measurements from your implementation. Choice labels must match the request;
probabilities must be finite and between zero and one, with choice probabilities
summing to one within rounding tolerance. Usage counts must be nonnegative
integers. Invalid output stops the run before it can drive a move.

Do not pass LLM-written confidence numbers off as calibrated probabilities. If
you implement a generative-model adapter, document how probabilities are derived,
its token generation cost, and the different semantics in the engine caption.

## 3. Register a local factory

Create `plugins/my_provider.py`:

```python
from my_inference_package import MyBackend

def register(registry):
    registry.register(
        "my-provider",
        lambda options, config: MyBackend(**options),
    )
```

Then configure it:

```json
{
  "plugins": ["plugins.my_provider"],
  "solo_engine": "custom",
  "engines": {
    "custom": {
      "provider": "my-provider",
      "label": "My model",
      "caption": "Custom local engine",
      "color": "#c9ef7d",
      "options": {"model": "my-model"}
    }
  }
}
```

Only locally configured plugin modules are imported. Plugins run as normal Python
code with your user's permissions; use code you trust. There is no browser API
for installing or loading plugins. A plugin must never put credentials into its
public metadata or log them. Unexpected custom-provider errors are sanitized
before reaching the UI.

## 4. Try the included non-AI example

Use `plugins.planner_example`, provider `planner-example`, with a label and caption
that explicitly say **deterministic / not AI**. For example:

```json
{
  "plugins": ["plugins.planner_example"],
  "solo_engine": "baseline",
  "prompt": "compact",
  "engines": {
    "baseline": {
      "provider": "planner-example",
      "label": "Planner baseline (not AI)",
      "caption": "Deterministic rules",
      "color": "#c9ef7d",
      "options": {}
    }
  }
}
```

This runs without a model file, GPU, or API key. It demonstrates integration and
tests the plumbing; its speed and behavior are not model benchmark results.

## Lifecycle and timing

- The configured solo engine is initialized once and shared with comparison runs.
  Solo play pauses while it is used in a comparison.
- Other engines initialize before the synchronized run start and close at pause
  or completion. Resume initializes those engines again.
- Each lane performs sequential requests independently, with no artificial pace
  delay. One finished lane does not throttle the remaining lanes.
- Built-in local warmup is configurable; remote APIs are not called on startup.
- A pending request may finish before a pause takes effect.
- Request timing wraps `predict`, including serialization, validation, and any
  network travel. Model initialization is outside the run timer.
- Custom providers own their timeout/cancellation semantics. Avoid retries and
  caching in comparisons unless clearly documented.

## Verification before contributing

Add offline tests for malformed responses, timeouts/errors, resource cleanup,
and credential handling. Run `python -m unittest discover -s tests -v`. The suite
includes a three-provider comparison proving that no controller changes are
needed. Real provider checks are manual and must never run in CI with a user's
credentials. Document hardware, model versions, prompt style, and limitations.
