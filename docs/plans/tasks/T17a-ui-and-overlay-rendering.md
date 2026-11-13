# T17a · UI and overlay rendering: the 2D flicker, overlays out of step, brightness after the gear menu

**Milestone:** M6 (rendering) · **Depends on:** T17 · **Machine:** Mac driving the Deck; the user at the Deck for the
final check

## Context
- **The UI flickers in play.** Every 2D UI element drawn over the 3D flickers and glitches. HUD parts become flat white
  squares, black or white ovals, or solid shapes for a frame, and the counter is sometimes partly drawn.
  - The user saw it in every windowed session: T13's problem 4 and item 11, T17's V1/V6.
  - It is measurable: in T17's `play1` frame capture, the HUD's bottom left has a one-frame jump in **465 of every
    1,000 frames**, where screen regions with no HUD have 23-46 (`docs/plans/reports/M5-gameplay.md`, step 6 and
    Decisions).
- **Two full-screen overlays are a frame out of step with the scene** (T17's V2/V3: 9 large one-frame flashes in 5,384
  frames, all of them these two):
  - the water-warning overlay drops out, or appears, for one frame;
  - the respawn iris wipe shows a frame with the wrong circle, or the scene where black should be.
- **After the gear menu (+), the scene is brighter** than before it. This is T13's item 12, reproduced by the user in
  T17 (V7). Once, the floor also went invisible after a level and the menu (T13).
- **No other task covers rendering correctness.** T18-T25 are audio, movies, memory, caches, CPU, a soak, packaging
  and upstream PRs.
- **None of this is known to be one cause.**
  - The UI class looks like UI draws that sample the wrong or an unready texture, or draws left out for a frame
    (inferred).
  - The overlay class looks like ordering between the passes or queues that compose a frame (inferred,
    `docs/design.md` §4 rules 1 and 3).
  - The brightness looks like state the menu's rendering leaves behind: exposure, a render target or a texture the 3D
    reuses (inferred).

## Read first
- `CLAUDE.md`
- `docs/plans/reports/M5-gameplay.md`: step 2 (the flash classes, with times), step 6 (V1-V7), the UI baseline, and
  the bistable frame rate (A/B frame rates are not comparable between runs; compare pictures, not fps).
- `docs/plans/reports/M4-first-frame.md`: problems 3-5 and items 11-14, and the tools tried there.
- `docs/design.md` §4 rules 1, 3 and 5, and §10-§11 (the flash and dark-frame hunts, and what was ruled out there).
- `docs/development.md`:
  - "Pictures and frames": `RX_VK_FRAMELOG`, `RX_VK_FLASH`, `RX_VK_DUMP`, `RX_VK_DUMP_FILE`, `RX_VK_PASS_TRACE`,
    `RX_VK_PROBE`;
  - `RX_VK_PIPE_SKIP=0`;
  - the event-wait and queue switches named in `docs/design.md` §4.1 and §11 (`RX_VK_EVENT_WAITS=0`,
    `RX_VK_QUEUE_STATE`).
- `docs/ui-texture-upload.md`, `docs/texture-staging-publication.md`, `docs/sampler-admission.md` and
  `docs/texel-buffer-ownership.md`: what upstream already fixed in this area, so the same ground is not covered twice.
- `scripts/framelog.py` (the block grid and the event rule).

## Scope
1. **A repeatable measure for each class:**
   - the HUD flicker rate, per region, from a frame capture;
   - the overlay faults, from a run that falls into the water and respawns;
   - the brightness before and after the gear menu at a fixed view.
2. **For each class, the cause,** from dumps and traces of the bad frame against its neighbours.
3. **Fixes that are clearly located,** each marked `(raiders)`, gated on the game id if it is Raiders-specific, and kept
   generic (upstream PR candidates) where it is not.
4. **For what cannot be fixed in the task:** a blocker report with the evidence.

## Non-goals
- Frame rate (T22), memory (T20), shader caches (T21), audio and movies (T18, T19).
- The gameplay hang in `cffdbb02c4dfbd39` (T13's problem 7).
- The docked magenta hub (T15, not reproduced in T17), unless it comes back here.
- Colour or fog differences that need the console side by side, until the user names one.
- Ocarina-only code paths.

## Files to touch
- **`gpu/vk/`**, where the cause is found: likely `vk_replay.cpp`, `vk_draw.cpp` and `vk_texture.cpp`. Edits marked
  `(raiders)`, and a game-free test for each fix in `tests/`.
- **`scripts/framelog.py`:** a `--regions` option that counts one-frame jumps per block region (the measure below),
  with its test. Or a new `scripts/framelog_regions.py` with `tests/test_framelog_regions.py`.
- **`games/raiders/scripts/`:** new input scripts for the menu and water routes.
- **`docs/plans/reports/T17a-ui-rendering.md`.**

## Steps
1. **The measure.**
   - Add region counts to the frame-log analysis. A region is block rows and columns of `framelog.py`'s 16x9 grid of
     20x20 blocks, counted per 1,000 frames from a start time.
   - Reproduce T17's baseline on `work/runs/play1/framelog` (from 60 s): HUD bottom left (rows 7-8, columns 0-4)
     ~465 per 1,000; top-right counter (rows 0-1, columns 12-15) ~28; bottom centre (rows 7-8, columns 6-10) ~46;
     middle (rows 3-4, columns 6-10) ~23.
   - Use windowed runs: `RX_VK_FRAMELOG` needs a swapchain (`run.sh --window`).
   - Every run plays on a copy of the user's save (`run.sh --user-from ~/raiders/work/t17_user_seed`).
2. **The UI class.**
   - **Is it a draw left out?** One run with `RX_VK_PIPE_SKIP=0` against default. If the HUD rate drops to the
     controls' level, the cause is pipelines not ready (T21's area: record it and stop this class here).
   - **Otherwise, find the HUD's draws:** dump a bad frame and a good neighbour (`RX_VK_DUMP=<present>+3`). Find a
     frame number from the capture, or arm the dump live with `HOS_INPUT_LIVE` and `RX_VK_DUMP_FILE`. Compare:
     - which texture each HUD draw samples (handle, serial, format, whether `gpu_written`), its sampler, and its
       descriptor;
     - whether the texture's registration or upload reached the replay before the draw (`docs/design.md` §4 rule 3);
     - whether a texture or sampler pool slot was reused within the frame.
   - **A flat white or black shape** usually means a default or unready texture was bound. Check the texture-cache
     answer for those handles in the bad frame.
3. **The overlay class.**
   - A route that falls into the water and respawns: T17's `area1_loop.txt` does this by itself at about 117 s and
     134 s in `play1`. Run it with `RX_VK_PASS_TRACE=1` (it logs the passes at a flash).
   - Find the overlay's pass in the bad frame. Check:
     - which queue and command buffer it came from;
     - which event waits came before it;
     - whether its input (the scene, a mask) is this frame's or the last one's.
   - **A/B** `RX_VK_EVENT_WAITS=0` only to learn, never as the fix.
4. **The brightness.**
   - A script: stand still in the hub; at a fixed time take a dump; open the gear menu (`PLUS`); wait; close it (find
     the button: `B` or `PLUS`); take a dump at the same view.
   - Compare the mean brightness of the two pictures (same camera; no input in between), then the passes of the two
     frames. Exposure or auto-exposure buffers, render targets and textures that the menu wrote and the 3D reads.
   - Check whether the brightness comes back after an area reload (T13: "plays faster after an area reloads").
5. **Fix** what is clearly located, one change per cause, each with a game-free test. Re-measure after each change
   with the same route, and compare per-region counts, not fps.
6. **User check at the Deck:** a 10-minute windowed session with sound (`--sound`), in the hub, one level and the gear
   menu, with the Steam client quit if the gyro is needed (T17).

## Acceptance criteria
```bash
scripts/deck/run.sh ui1 330 --window --user-from /home/deck/raiders/work/t17_user_seed -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" \
  HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh ui1
.venv/bin/python -I scripts/framelog.py work/runs/ui1/framelog --regions 60     # (or the new script)
grep -ci "device lost" work/runs/ui1/hookshot_log.txt                            # 0
.venv/bin/python -I -B tests/run_all.py
```
- **The HUD bottom-left rate is at most twice the higher of the two control regions** in the same run (T17: 465
  against 46).
- **No one-frame event of 36+ blocks** at the water-warning overlay or the respawn wipe in `ui1`. Name each remaining
  large event and its class.
- **The gear-menu pair:** the mean brightness after the menu is within 3% of before, at the same view.
- **The test suite:** the same 9 failures as T17's final run (329 passed with header paths set), plus the new tests
  passing.
- **User check:** no visible UI flicker in normal play, no brighter scene after the gear menu, and nothing that worked
  in T17 broken (ink, save and continue).

## Report
`docs/plans/reports/T17a-ui-rendering.md`:
- the measure and its baseline;
- for each class: the cause found (or the evidence, if not found), the fix, and the per-region counts before and after;
- the gear-menu brightness before and after;
- what is left, with the next step;
- which fixes are upstream PR candidates (T25).
