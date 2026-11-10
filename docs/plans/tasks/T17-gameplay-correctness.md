# T17 · Gameplay correctness pass and first Deck measurements (Gate 2, first reading)

**Milestone:** M5 (exit) · **Depends on:** T15, T16 · **Machine:** Mac driving the Deck; the user at the
Deck for play checks

## Context
With input and saves working, the first playable area is reachable. This task checks that gameplay is
correct, not only that it draws: picture stability (Hookshot's flash and dark-frame classes,
`docs/design.md` §10-§11), game speed, and above all **ink behaviour**. In this series the game logic tests
which ink the player stands in using data the GPU drew; if the CPU sees that data late or not at all, movement
breaks even when the picture is right (`00-overview.md` risk 2). The task also takes the first honest frame
rate and memory numbers on the Deck, which decide how much of M7 is needed.

## Read first
- `CLAUDE.md`; `docs/plans/reports/M4-first-frame.md`, `M3-trace.md` (read-back candidates)
- `docs/design.md` §4, §10, §11
- `docs/development.md` "Pictures and frames", "Time and profiles", and the write-back switches
  (`RX_VK_NO_WRITEBACK`, `RX_VK_WB_DIFF`, `RX_VK_MIRROR`)
- `gpu/vk/vk_memory.cpp` header comments on write-back; `docs/dump-readback.md`

## Scope
1. A repeatable gameplay run (scripted input) of about five minutes in the first area.
2. Picture checks: flash detector, frame log, a manual review of screenshots.
3. Ink behaviour checks with the user.
4. Measurements: fps, frame-time distribution, RSS, GPU memory, thread load.
5. Fix correctness bugs that are small and clearly located; list the rest with evidence.

## Non-goals
- Performance tuning (T22) and memory tuning (T20): measure only.
- Audio (T18), movies (T19).

## Steps
1. Scripted route: extend the input script to move, turn, shoot, and enter ink (`games/raiders/scripts/
   area1_loop.txt`).
2. Picture stability: `RX_VK_FLASH=1` with `RX_VK_SHOTS` and `RX_VK_SHOT_EVERY=1` for a short window;
   `RX_VK_FRAMELOG=<file>` + `python -I scripts/framelog.py <file>` for the whole run (it finds flashes and
   dark frames). Record counts per 1,000 frames.
3. Ink read-back. First establish the mechanism with evidence:
   - From the M3 trace and a gameplay trace, list NVN calls that copy GPU results to CPU-visible memory
     (texture-to-buffer copies, buffer maps of pools the GPU writes) and how often per frame.
   - Run A/B: default versus `RX_VK_NO_WRITEBACK=1`. If ink physics break only in B, the write-back is the
     path. Then measure lag: does the player's state change on the same frame ink lands, or frames later?
     (User observation plus `HOS_TRACE` timestamps around the read.)
   - If physics are wrong in the default configuration, find which pool or format is not written back
     (`RX_VK_WB_DIFF=0` as a second A/B) and fix in `gpu/vk/vk_memory.cpp`, or record a blocker.
   User checks at the Deck: swim in own ink (fast, hidden), walk in enemy ink (slow, damage), climb an inked
   wall, ink coverage persists when looking away and back.
4. Game speed: with fps below 60, `Game speed = Real time` should keep normal speed (`readme.md`); confirm
   with a stopwatch against an in-game timer or animation. Record what Raiders' own frame-rate target is
   (`HOS_FPS_LOG`).
5. Measurements over the scripted run: `RX_VK_FRAME_LOG=<csv>` (mean, 1% low, share of frames over 33.3 ms),
   `HOS_THREAD_TIMES=10`, RSS (`/proc/<pid>/status` sampled by `run.sh`; add `--rss` sampling if missing),
   the `vk: status:` line, `RX_VK_PASS_TIMING=1` for GPU time per pass. One run in handheld profile, one
   docked profile for comparison.
6. Triage every visual difference from the console (user's comparison): missing objects, wrong colours,
   shadows, fog, UI. One line each: where, suspected pass or program key, severity.

## Acceptance criteria
```bash
scripts/deck/run.sh play1 330 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" RX_VK_FRAME_LOG=frames.csv HOS_THREAD_TIMES=10 \
  && scripts/deck/fetch.sh play1
.venv/bin/python -I scripts/framelog.py work/runs/play1/framelog 2>/dev/null | tail -5     # flash / dark-frame counts
awk -F, 'NR>1{n++; s+=$3; if($3>33.4)o++} END{printf "frames %d  mean %.1f ms  over 33.4 ms: %.1f%%\n", n, s/n, 100*o/n}' work/runs/play1/frames.csv
grep -ci "device lost" work/runs/play1/hookshot_log.txt                                    # 0
.venv/bin/python -I -B tests/run_all.py
```
User checks: the four ink behaviours above; start, play, save, quit, continue on the Deck's own controls.

## Report
`docs/plans/reports/M5-gameplay.md`: ink mechanism and A/B results; flash and dark-frame rates; game-speed
check; the measurement table (fps mean and 1% low, frame-time share over 33.4 ms, CPU per thread, GPU ms,
RSS, GPU memory) for handheld and docked profiles; the visual-difference list; a plain statement for Gate 2:
how far the Deck is from a stable 30 fps and what limits it (CPU thread, GPU, memory).
