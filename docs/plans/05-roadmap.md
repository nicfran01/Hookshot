# 05 · Roadmap

Each milestone has one testable exit criterion. Tasks are sized for one Opus session each; a session that
finds more than it can finish writes a blocker report (`06-handoff-guide.md`) instead of stretching.
At a few hours a week, expect one or two tasks a week: 27 tasks is roughly four to six months, with wide
error bars on M4, M5 and M7 **[inferred]**.

The original suggested M0 (reproduce a Hookshot build of its own game) is replaced by a toolchain-only M0,
because the user does not have that game.

## Order and dependencies

```mermaid
flowchart LR
    T01[T01 fork] --> T02[T02 Mac checks]
    T01 --> T03[T03 Deck env]
    T02 --> T04[T04 game config]
    T04 --> T05[T05 ingest fixes]
    T04 --> T06[T06 lift gating]
    T04 --> T07[T07 host gating]
    T03 --> T08[T08 first build + boot]
    T05 --> T08
    T06 --> T08
    T07 --> T08
    T03 --> T08a[T08a lifter tests on Linux]
    T06 --> T08a
    T08a --> T13
    T08 --> T09[T09 trace report]
    T08 --> T12[T12 shader census on Deck]
    T09 --> T09a[T09a built-in font stand-in]
    T09a --> T10[T10 offline guard, then answers as traced]
    T09a --> T11[T11 device limits, then NVN2 procs as traced]
    T09a --> T13[T13 first frame]
    T10 --> T13
    T11 --> T13
    T13 -.->|a trace shows their calls| T10
    T13 -.->|a trace shows a missing proc| T11
    T12 --> T13
    T13 --> T14[T14 geometry stage, conditional]
    T13 --> T15[T15 input + gyro]
    T13 --> T16[T16 saves]
    T15 --> T17[T17 gameplay correctness]
    T16 --> T17
    T17 --> T18[T18 audio]
    T17 --> T19[T19 movies]
    T17 --> T20[T20 memory]
    T17 --> T21[T21 shader caches]
    T17 --> T22[T22 CPU performance]
    T20 --> T23[T23 stability soak]
    T21 --> T23
    T22 --> T23
    T23 --> T24[T24 packaging]
    T24 --> T25[T25 upstream PRs]
```

De-risking is front-loaded: T12 (do the shaders translate on RADV at all?) and T09 (what does the game call
that the runtime lacks?) run as soon as a binary exists, before any effort goes into the picture. Frame rate
and memory are first measured in T13 and T17, not left to M7.

**The trace is a loop, not one pass.** The first trace stopped at the first blocking call (the built-in
font), long before any submit, so it could not list what comes after. From T09a on, each task that gets the
boot further regenerates `reports/M3-trace.md` from its own run. T10's answers (Part B) and T11's procs are
done when a trace shows their calls, which may be as late as T13 or T15; the dotted arrows above are those
returns. Owners by namespace: the "Ownership of traced calls" table in `tasks/T10-offline-stubs.md`.

## Milestones

### M0 · Toolchain proven without a game
- **Tasks:** T01, T02, T03.
- **Exit:** on the Mac, `python -I -B tests/run_all.py` finishes with every failure explained in
  `docs/plans/reports/mac-test-baseline.md`. On the Deck, `scripts/deck/setup.sh` ends by building
  `hookshot_vk.so` with `RX_VK_ONLY=1` and prints a RADV driver line that includes `VK_EXT_mesh_shader`.
- **Risk retired:** the build host. If the Deck cannot build the renderer, stop and choose another host
  before touching game code.

### M1 · Ingest and version-check the Raiders dump
- **Tasks:** T04, T05.
- **Exit:** `python -I nx2/make_game.py --check --exefs <dump>/exefs` prints
  `@@check ok …` for build `abb30e2f`, and `@@check bad …` for a folder whose `main` differs;
  `python -I nx2/shader_census.py <romfs> --out work/raiders_shaders.bin` reports 22,042 programs.

### M2 · Lift, link, reach `nnMain`
- **Tasks:** T06, T07, T08, T08a (T08a is not part of the exit; it must be done before T13).
- **Exit:** on the Deck, `work/sa/build/hookshot` exists and a `HOS_TRACE=1` run logs the boot sequence
  through `nnMain` and reaches `nvnBootstrapLoader` (Hookshot's stage S2, `docs/design.md` §6), or stops at a
  named unimplemented call recorded in `docs/plans/reports/M2-boot.md`.

### M3 · Trace everything up to the first crash or hang
- **Tasks:** T09, T09a, T10 (Part A; Part B if triggered), T11 (device limits; procs if triggered), T12.
- **Exit:** the boot passes the built-in font call (T09a); the offline guard is in place and a run shows no
  non-loopback socket (T10 Part A); `docs/plans/reports/M3-trace.md`, regenerated from the latest run, lists
  every stub and NVN proc the game called with a class and an owner; `docs/plans/reports/M3-shaders.md` gives
  the translate/lower pass rate for all stages on RADV.
- **Moved to M4:** "no blocking entry remains before the first `nvnQueuePresentTexture`". The first trace
  showed that blocking calls are found one at a time as the boot advances, so clearing them all is part of
  T13's loop, with T10 Part B and T11 run when their calls appear.
- **Risk retired:** 5 (shader gaps). Risks 6 (unknown calls) and 7 (online dependency at boot) are only
  retired at the M4 exit.

### M4 · First frame and title screen  — **Gate 1**
- **Tasks:** T13 (with T10 Part B and T11 as their calls appear), then T14 only if T13's log shows "dropped
  stages" on something visible.
- **Exit:** `scripts/deck/run.sh title 180` leaves a screenshot in `work/runs/title/shots/` that shows the
  title screen, and the log has no "device lost". The user confirms the picture against the console.
- **Gate:** if this needs more than about six sessions beyond T13's first, write a re-plan before continuing.
  Sessions spent in T10 Part B and T11 count towards the six. Each `HLE()` added costs a relift of about 45
  minutes on the Deck (T08: 2,544 s), which is the main cost of this loop.

### M5 · In game and controllable  — **Gate 2 (first measurement)**
- **Tasks:** T15, T16, T17.
- **Exit:** from the Deck's own controls the user starts a new game, reaches the first playable area, moves,
  aims with gyro or the documented fallback, saves, quits and continues from the save. T17's report records
  average fps and RSS in that area and confirms ink behaviour (swimming in own ink, slowed in enemy ink).

### M6 · Audio and movies
- **Tasks:** T18, T19.
- **Exit:** music and effects play without crackle for ten minutes in the first area; one of the
  `UI/Movie/Gadget_*.webm` clips plays in its menu at normal speed.

### M7 · Deck stability and performance  — **Gate 2 (verdict)**
- **Tasks:** T20, T21, T22, T23.
- **Exit:** a one-hour session in Gaming Mode with no crash, no `gfx_` timeout in `journalctl -k`, RSS + GPU
  memory ≤ 12.5 GB, the frame rate held at the chosen cap (target 30 fps or better) for 95% of frames in
  `RX_VK_FRAME_LOG`, and no new pipeline compiles on a second visit to an area.
- **Gate:** below a stable 30 fps after T22 → record what was tried and decide with the user whether to
  continue (upstream performance work may land in the meantime).

### M8 · Packaging and a Gaming Mode launch
- **Tasks:** T24, T25.
- **Exit:** on a Deck with no build container, the fork's AppImage builds the game from the dump with one
  command and the non-Steam shortcut starts it from Gaming Mode with saves in
  `~/.local/share/raiders-recomp`. Generic fixes are open as PRs upstream, or listed with the reason they
  are not.

## Standing activities

- **Upstream merge** at the start of every milestone (`03-architecture.md` §6).
- **Reports** live in `docs/plans/reports/` (names, counts, timings, decisions; never game data, never
  screenshots).
- **Plan revisions:** when a blocker report changes the plan, the planner (this role) edits the affected task
  files and notes the change at the bottom of this file.

## Open questions for the user

1. **GitHub fork:** created under which account, and public or private? (Needed by T01. A fork of a public
   GPL repo is normally public; that is fine because it never contains game data.)
2. **Deck details:** LCD or OLED, free space on internal storage and SD card, and are you willing to enable
   SSH on it? (T03.)
3. **Performance data in git:** hot-function lists, link order and PGO profiles hold addresses and counters,
   not code. Keep them local (default, strictest reading of the constraint) or commit them so a fresh clone
   builds fast?
4. **Renaming:** is it acceptable that binaries and switches keep upstream's names (`hookshot`, `HOS_`,
   `RX_`) internally, with only the window title, data folder and AppImage named for this project?
5. **Console comparison:** can you provide console screenshots or footage of the title screen and first area
   for the accuracy checks in T13 and T17? (They stay on your machines.)

## Change log

- 2026-11-10: first version.
- 2026-11-10 (after T01): `windows-builder.yml` is guarded to upstream's repository instead of renamed, because
  `tests/test_recomplauncher_json.py` reads it (`reports/BLOCKER-T01-2026-11-10.md`; T01 and `03-architecture.md`
  §7 edited).
- 2026-11-10 (after T02): new task **T08a**. `nx2/test_insn.py` and `nx2/test_leaf.py` have Windows-only harnesses
  (`windows.h`, `VirtualAlloc`, SEH) and cannot run on the arm64 Mac, so T06 no longer runs them and T08 no longer
  defers to the Deck. T08a adds a Linux path (no edit to `third_party/`) and runs them on the Deck before T13.
  Also T25 candidate 9 and `02-gap-analysis.md` §2 (`reports/mac-test-baseline.md`).
- 2026-11-10 (after T09, `reports/BLOCKER-T10-2026-11-10.md`): new task **T09a** (built-in font stand-in). Every run
  stops at `nn::pl::GetBuiltInFontData`, which no task owned, and the trace saw no call in T10's namespaces. T10 is
  split: Part A (offline guard: source check, Discord presence off, run-time socket check) is unconditional and moved
  ahead of the answers; Part B (the offline answers) runs only when a trace shows its calls, and its acceptance
  requires a trace that ends past the font call. T11 likewise does its device-limits check now and its procs when
  traced. T13 depends on T09a and owns the stop-by-stop loop; an ownership table for traced calls is in T10.
  M3's "no blocking entry before the first present" moved to M4. T09 must be merged into `main` before T09a.
  Also `02-gap-analysis.md` §3 (`nn::pl` row) and `tasks/README.md`.
