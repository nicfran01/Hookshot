# Tasks

One file per implementation task, each sized for one Opus session. Order and dependencies:
`../05-roadmap.md`. How to run a session: `../06-handoff-guide.md`.

| Task | Milestone | Machine | Summary |
|---|---|---|---|
| [T01](T01-fork-setup.md) | M0 | Mac | Make this directory the fork; merge ignores; disable release workflows |
| [T02](T02-mac-dev-checks.md) | M0 | Mac | Mac setup; game-free test baseline; lifter differential tests |
| [T03](T03-deck-build-environment.md) | M0 | Deck | Build container, dependencies, `scripts/deck/*`, game-free renderer build |
| [T04](T04-game-config-layer.md) | M1 | Mac | `games/<id>/game.py`, `nx2/game.py`, version check through it |
| [T05](T05-ingest-fixes.md) | M1 | Mac | Optional zstd dictionary; romfs sanity check |
| [T06](T06-lift-gating.md) | M2 | Mac | Game-neutral lift driver; first standalone lift of Raiders |
| [T07](T07-host-gating.md) | M2 | Mac | Gate Ocarina-specific runtime and renderer code |
| [T08](T08-first-build-and-boot.md) | M2 | Deck | First build; boot to `nnMain` |
| [T09](T09-trace-report.md) | M3 | Deck | Trace harness; report of every stub and NVN proc called |
| [T10](T10-offline-stubs.md) | M3 | Deck | Offline answers: network, ldn, nfp, friends, swkbd |
| [T11](T11-nvn2-gaps.md) | M3 | Deck | NVN2 procs the game needs |
| [T12](T12-shader-census-on-deck.md) | M3 | Deck | Translate every shader on RADV; pass rate |
| [T13](T13-first-frame.md) | M4 | Deck | First frame and title screen (Gate 1) |
| [T14](T14-geometry-stage.md) | M4/M5 | Deck | Geometry-stage support (conditional) |
| [T15](T15-input-and-gyro.md) | M5 | Deck | Handheld pad, scripted input, gyro |
| [T16](T16-saves.md) | M5 | Deck | Per-game data folder; save and continue |
| [T17](T17-gameplay-correctness.md) | M5 | Deck | Ink behaviour, picture stability, first measurements (Gate 2 reading) |
| [T18](T18-audio.md) | M6 | Deck | Audio |
| [T19](T19-movies.md) | M6 | Deck | `nn::movie` to VP9 |
| [T20](T20-deck-memory.md) | M7 | Deck | Memory budget and Deck profile |
| [T21](T21-shader-and-pipeline-caches.md) | M7 | Deck | Shader preparation, pipeline caches, Steam pre-caching |
| [T22](T22-cpu-performance.md) | M7 | Deck | Threads, hot list, PGO, frame cap (Gate 2 verdict) |
| [T23](T23-stability-soak.md) | M7 | Deck | Hour-long soak, GPU hangs, suspend/resume |
| [T24](T24-packaging.md) | M8 | Mac + Deck | AppImage, launcher, Gaming Mode |
| [T25](T25-upstream-prs.md) | M8 | Mac | Prepare generic fixes for upstream |
