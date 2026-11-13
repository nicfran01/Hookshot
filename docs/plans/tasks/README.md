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
| [T08a](T08a-lifter-tests-linux.md) | M2 | Mac + Deck | Linux path for the lifter's differential tests; run them on Raiders (added after T02) |
| [T09](T09-trace-report.md) | M3 | Deck | Trace harness; report of every stub and NVN proc called |
| [T09a](T09a-builtin-font-stand-in.md) | M3 | Deck | Built-in font stand-in: the call every run stops at |
| [T10](T10-offline-stubs.md) | M3 | Deck | Offline guard now; offline answers when a trace shows the calls |
| [T11](T11-nvn2-gaps.md) | M3 | Deck | Device-limits check now; NVN2 procs when a trace shows them missing |
| [T12](T12-shader-census-on-deck.md) | M3 | Deck | Translate every shader on RADV; pass rate |
| [T13](T13-first-frame.md) | M4 | Deck | First frame and title screen (Gate 1) |
| [T14](T14-geometry-stage.md) | M4/M5 | Deck | Geometry-stage support (conditional) |
| [T15](T15-input-and-gyro.md) | M5 | Deck | Handheld pad, scripted input, gyro |
| [T16](T16-saves.md) | M5 | Deck | Per-game data folder; save and continue |
| [T17](T17-gameplay-correctness.md) | M5 | Deck | Ink behaviour, picture stability, first measurements (Gate 2 reading) |
| [T17a](T17a-ui-and-overlay-rendering.md) | M6 | Deck | UI flicker, overlays out of step, brightness after the gear menu (added after T17) |
| [T17b](T17b-missing-ground-and-world-flicker.md) | M6 | Deck | Draws left out after the gear menu: the missing ground and the world flicker (added after T17a) |
| [T17c](T17c-world-flicker-with-copies.md) | M6 | Deck | World flicker while the camera moves, with T17a's copies as submitted (added after T17b) |
| [T18](T18-audio.md) | M6 | Deck | Audio |
| [T19](T19-movies.md) | M6 | Deck | `nn::movie` to VP9 |
| [T20](T20-deck-memory.md) | M7 | Deck | Memory budget and Deck profile |
| [T21](T21-shader-and-pipeline-caches.md) | M7 | Deck | Shader preparation, pipeline caches, Steam pre-caching |
| [T22](T22-cpu-performance.md) | M7 | Deck | Threads, hot list, PGO, frame cap (Gate 2 verdict) |
| [T23](T23-stability-soak.md) | M7 | Deck | Hour-long soak, GPU hangs, suspend/resume |
| [T24](T24-packaging.md) | M8 | Mac + Deck | AppImage, launcher, Gaming Mode |
| [T25](T25-upstream-prs.md) | M8 | Mac | Prepare generic fixes for upstream |
