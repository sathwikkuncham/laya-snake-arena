# Security policy

Security fixes target the latest release and `main`.

Report suspected vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/sathwikkuncham/laya-snake-arena/security/advisories/new).
Include affected versions and minimal reproduction steps. Do not include API
keys, unredacted settings, or real private data. Do not open a public issue with
an exploitable vulnerability or credential.

## Boundaries

- The server binds to loopback only. Host and Origin checks plus a per-process
  control token restrict browser-issued state changes. It is not a public service.
- Keys are read server-side from `.env`, process environment, or private Verdict
  settings. They are excluded from UI state and exported game traces.
- TypeSafe traffic uses verified HTTPS to `api.typesafe.ai`; no arbitrary base
  URL is accepted by the built-in adapter.
- Downloads of model files and executables are explicit user setup steps.
- Python plugins are trusted local code, not sandboxed extensions. Review them
  before enabling them. The browser cannot install plugins or modify configuration.
- Third-party models, binaries, and services have independent security and
  licensing considerations. Keep your downloaded runtime and GPU drivers updated.

If a key is accidentally shared, revoke it at its provider before replacing it.
Do not expose this server to a LAN or the internet without designing and testing
an appropriate authentication and deployment layer.
