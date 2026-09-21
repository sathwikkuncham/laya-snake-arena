# Publishing this repository and its videos

The public repository is
[sathwikkuncham/laya-snake-arena](https://github.com/sathwikkuncham/laya-snake-arena).
This guide describes the release process for maintainers.

## Source repository

1. Run the offline checks and review the proposed source changes.
2. Merge the reviewed source changes and wait for GitHub Actions CI to pass.
3. Keep `.gitignore` in place. It excludes `config.json`, `.env`, downloaded
   weights/executables, logs, caches, private game history, and large videos.
4. Include the existing Apache-2.0 LICENSE and NOTICE files, including upstream
   attribution. Do not bundle the separate model weights or ggmlc binaries.

The public examples use relative paths and blank credentials. The source package
does not contain the author's personal Downloads path or Verdict settings file.

## Video assets

Create a release and attach `laya-solo.mp4`, `laya-vs-jev.mp4`, and optionally
the media ZIP containing posters, timestamps, and run traces. The MP4s are small
enough to distribute separately without adding video history to Git.

Suggested titles:

- **Laya Snake on Windows — local RTX 4070 SUPER, real-time demo**
- **Laya vs TypeSafe JEV — live local/cloud Snake comparison**

Suggested description:

> Real local Laya predictions and live TypeSafe JEV API calls drive the original
> laya-mlx Snake policy. Each move asks three typed questions. The comparison uses
> the same starting board, seed, safety setting, and move budget. JEV timings
> include internet latency. A deterministic planner provides features, and the
> visible cycle safety shield can override unsafe proposals. This capture plays
> at original wall-clock speed; screenshot capture and UI sampling skip some
> fast game updates. Results are from one run, not a universal model benchmark.

Add links to the repository, original laya-mlx project, ggmlc, and TypeSafe.
For full methodology and measured results, link `docs/RECORDINGS.md`.
