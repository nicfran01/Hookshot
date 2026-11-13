# T17 · Gameplay correctness and first Deck measurements (Gate 2, first reading)   (2026-11-12)

**Short answer.**
- **Ink: the path is the occlusion counts, and it is correct now.**
  - With real counts (the default) health stays at 100/100 on the player's own ink. With the old fixed 4096
    (`RX_VK_OCC_REAL=0`) it drains: 88, 76, 65, 54, 51 over the same route.
  - The write-back is not on the path. With mirrors forced on and the write-back turned off, health still stays at 100.
  - The counts reach guest memory a median ~21 ms after the replay queues them. That is under one frame (34-48 ms here)
    for most reports, but not all of them.
- **Picture:** 9 large one-frame flashes in 5,384 frames of play (1.7 per 1,000), all in two places:
  - the water-warning overlay;
  - the respawn iris wipe.

  There are no whole-picture dark frames.
- **Game speed follows the frame count.**
  - Below its target the game runs in slow motion: the same 3 s walk at 10.9 fps went visibly less far than at 18.8 fps.
  - Hookshot's "Game speed = Real time" is Ocarina's and does nothing for Raiders.
- **Frame rate.**
  - Handheld runs at **29.5 fps** (1% low 24.6), with 61.8% of frames over 33.4 ms.
  - Docked ran at **20.7 fps** in one run and **49.5 fps** in another.
  - A run settles at one of several levels, which follow how many uniform-buffer updates the game issues per frame
    (830 to 2,150). The limit is the replay's thread, not the GPU: the GPU takes ~9-10 ms a frame in every run.
- **Memory:** about 5.7 GB resident, plus ~2.8-2.9 GB GTT and 0.9 GB VRAM in use on the GPU. That is high for a 16 GB
  machine (T20).
- **Your checks at the Deck (`check1`, `check2`, windowed, the Deck's own controls): ink and continue passed.**
  - **Ink:** all four behaviours work.
  - **Continue:** the second boot brought you to the results screen of the level you had closed the game in.
  - **New problems you saw:** every 2D UI element over 3D flickers; the scene is brighter after the gear menu; and
    **the gyro did not move the aim until you quit the Steam client in Desktop Mode**; then it worked again (below).

Claims are **verified** (run, command, file:line or log line named) unless marked **inferred** or **unknown**. Runs are
in `work/runs/<name>/` on the Mac and `~/raiders/work/runs/<name>/` on the Deck. Logs, screenshots, frame captures and
saves are game output and are not committed.

## Branch, build, runs

- **The branch.** `task/T17-gameplay-correctness` sits on `main` at `97433a6`, which now has T15 and T16 (merged on your
  instruction; see `BLOCKER-T17-2026-11-12.md`).
- **The build.** The final Deck build gives `build (lift): 190 s`, exit 0.
- **The start state.** Every run starts from the same copy of your save, `d9dfb4bb…`.
  - `run.sh --user-from ~/raiders/work/t17_user_seed` copies it into the run's own `user/` folder, so the game's
    writes stay there.
  - Your save had the same md5 after all runs. No GPU reset was logged (`journalctl -k`: 0 `gfx_`/timeout lines since
    20:50).
- **The route, `games/raiders/scripts/area1_loop.txt`** (155 presses, 2,482 characters, wall clock). It has no game
  data:
  - ZL+ZR at 30, 35 and 40 s (title to hub);
  - then, every 12 s from 90 s to 317 s, the same cycle:
    1. ZR 2 s (ink ahead);
    2. ZL+LUP 1.5 s (swim);
    3. LUP 1.2 s;
    4. RRIGHT 0.25 s;
    5. ZR+LLEFT 1.5 s;
    6. ZL+LDOWN 1.5 s;
    7. LDOWN 1.2 s;
    8. RLEFT 0.25 s.
  - **Where it plays:** the hub, the first area with free control after a post-prologue save (T15). It inks the deck,
    swims in that ink and walks out of it.
  - **It drifts:** in most runs the player falls off the deck into the water once or twice (the water warning, then a respawn
    with an iris wipe). That is the game's own behaviour, and it gives the flash check a transition to look at.

| Run | Profile | Switches beyond the route (all with `--user-from`) | Purpose |
|---|---|---|---|
| `play1` | docked, windowed 1280x720 | acceptance switches + `RX_VK_FRAMELOG`, `RX_VK_OCC_LAG=200`, `--rss` | acceptance; flashes; docked measurement |
| `meas_hh` | handheld, windowed | `RX_VK_FRAME_LOG`, `HOS_THREAD_TIMES=10`, `RX_VK_PASS_TIMING=1`, `RX_VK_OCC_LAG=200`, `--rss` | handheld measurement |
| `meas_dk` | docked, windowed | the same | docked measurement |
| `occ_on` / `occ_off` | handheld, headless | shots every 150 presents; `occ_off` adds `RX_VK_OCC_REAL=0` | ink A/B |
| `mirror_wb` / `mirror_nowb` | handheld, headless | `RX_VK_MIRROR=1`; `mirror_nowb` adds `RX_VK_NO_WRITEBACK=1` | write-back check |
| `speed_a` / `speed_b` | handheld, headless | one 3 s walk at 100 s; `speed_b` adds `HOS_FRAME_SLEEP_MS=40` | game speed |
| `play1_t17a` | docked, headless | as `play1` | the first try; it showed the frame-log gap below |

No run had a device loss (`grep -ci "device lost"`: 0 in all 9).

## Changes

1. **`scripts/deck/run.sh`** (with `tests/test_deck_scripts.py`):
   - A relative `RX_VK_FRAME_LOG`, `RX_VK_FRAMELOG` or `HOS_PRESENT_TRACE` file now goes in the run's folder. Before,
     it went in the executable's folder, which `fetch.sh` never reads.
   - `run.sh` makes `RX_VK_FRAMELOG`'s `.go` file, so the capture covers the whole run.
   - `--rss`: every 5 s, the game's `VmRSS`/`VmHWM` and the GPU's `mem_info_vram_used`/`mem_info_gtt_used` go to
     `rss.txt`, with the peaks on its last line. A run stopped at its time limit had no memory figure before.
   - `--user-from <dir>`: the run plays on a fresh copy of a user folder. The task's play runs therefore never touch
     your save.
   - The new test case runs the Deck side on a stand-in executable. It passes on the Deck (10 of 10, Linux); on the Mac
     it is skipped (no `/proc`).
2. **`gpu/vk/vk_replay.cpp` (raiders): `RX_VK_FRAME_LOG` now works in headless runs.**
   - `do_present` returned before `present_out` when offscreen, so the CSV stayed empty in every scripted Deck run
     (verified: `play1_t17a` had no `frames.csv`).
   - The CSV writer is now one function, `frame_time_log()`, called from `present_out` and from the offscreen present.
   - New `tests/test_frame_log_offscreen.py` checks both calls as text and compiles the function into a three-present
     driver.
   - `RX_VK_FRAMELOG` (the 320x180 capture) still needs a real swapchain, so the acceptance run is windowed.
   - **A candidate upstream fix:** generic, one change.
3. **`gpu/vk/vk_occlusion.cpp` and `.h` (raiders): `RX_VK_OCC_LAG=<n>`.** Every n reports, it logs how long after the
   replay queued them the collector wrote their words: the median, the 95th percentile and the longest.
4. **`games/raiders/scripts/area1_loop.txt`**: the route.

## Step 3: ink

### The mechanism (verified)

- **No buffer write-backs on the Deck.**
  - The Deck's GPU is integrated (`vk: device 0: … RADV VANGOGH …, type 1`), so `vk: VRAM mirror of buffer pools off`.
  - Every frame reads `mirrors 0 (0 MB): … 0.00 MB written back` (`occ_on`).
  - The GPU writes the game's pools in place.
- **Ink state comes from samples-passed counts** (T13 session 5; `gpu/vk/vk_occlusion.cpp`):
  - each frame the game counts pixels per paint unit with occlusion queries;
  - `play1` wrote **1.83 million** reports in 330 s (9,149 lines of 200), about 250 per frame;
  - none was given up.

### A/B (step 3 as changed by you: occlusion counts instead of the write-back)

Health read from the screenshots at the same presents (1800-6300, every 450), handheld, the same route and save:

| Run | Counts | Mirrors / write-back | Health over the run |
|---|---|---|---|
| `occ_off` | fixed 4096 (`RX_VK_OCC_REAL=0`) | off | **88, 76, 65, 54, 51**, then 89, 99, 76: drains on the deck, low-health edges on screen |
| `occ_on` | real (default) | off | **100** throughout, except the water warning |
| `mirror_wb` | real | on, write-back on (2.4-55.8 MB written back a frame) | **100**, except the water warning |
| `mirror_nowb` | real | on, write-back off (0.00 MB a frame) | **100**, except the water warning |

- **Ink physics break only when the counts are wrong** (verified). The write-back does not carry the ink state
  (verified): with mirrors on and no write-back, the result is unchanged.
- **The camera read-back buffers** from T13 session 4 are written by compute programs. In `mirror_nowb` their GPU
  writes stay in the mirror, and nothing visible changed in the screenshots. What they feed is still **unknown**.

### Lag (verified at the collector; the game's side inferred)

| Run | fps | Median delay | 95th percentile | Longest |
|---|---|---|---|---|
| `play1` | 20.7 | 20.5 ms (median of the 200-report windows' medians) | 38.2 ms (median window) | 96.5 ms (at load) |
| `occ_on` | 20.4 | 21.1 ms | — | — |
| `mirror_wb` | 24.5 | 7.0 ms | — | — |
| `mirror_nowb` | 34.3 | 12.6 ms | — | — |

- In `play1`, 40.4% of the windows had a 95th percentile over one frame (43.7 ms).
- **What this means for the game** (inferred):
  - Raiders' reader waits for the report's timestamp word (T13 session 5), so a late count is read late, never wrong.
  - Most counts are there by the game's next frame; some come a frame later still. On the console, results are ready
    within the frame they were drawn in.
  - A one-frame lag in the ink under the player is unlikely to show while walking. It may show at ink edges.
- **Not done:** `HOS_TRACE` timestamps at the game's read (`0x811eb380`). The delay above runs from the replay's queue
  to the write.
- **Unknown until your check:** whether the player's state changes on the frame the ink lands.

## Step 2: picture stability (`play1`, whole run, 7,319 frames captured)

- **Raw counts.** `scripts/framelog.py` reports `events: 5323 on the game's frames, 0 on made frames`.
- **What an event is.** The script counts any one 20x20 block that jumps against both neighbours. Most are particles
  and ink spray, so the events are given by size from 60 s on (5,384 triplets; boot and the title left out):

  | Event size (blocks of 144) | Brighter | Darker | Per 1,000 frames |
  |---|---|---|---|
  | 1-2 | 1,301 | 1,756 | 568 |
  | 3-9 | 967 | 580 | 287 |
  | 10-35 | 33 | 19 | 9.7 |
  | **36-144 (a quarter of the picture or more)** | **3** | **6** | **1.7** |
  | Whole-picture dark frames (mean brightness under 60% of both neighbours') | — | — | **0** |

- **The 9 large events, looked at frame by frame** (before, frame, after):
  - **117.5 s, 118.0 s and 234.0 s: the low-health / water warning overlay.**
    - It drops out for one frame, or shows for one frame where its neighbours have none.
    - The HUD's bottom left turns into flat white shapes on the same frame.
  - **134.2 s, 188.5 s and 298.5 s: the respawn iris wipe.**
    - The middle frame's circle is the wrong size for the sequence, or the area outside it shows the scene dimly
      instead of black.
    - So the overlay and the scene are a frame out of step (inferred).
- **Not a dark-frame problem:** there is none of Hookshot's dark-frame class (`docs/design.md` §11).
- **`RX_VK_FLASH`** with shots every frame was not run. The frame log covered the whole run instead.

## Step 4: game speed

- **Game time follows frames** (verified, `speed_a`/`speed_b`):
  - the same `LUP/3000` at 100 s, from the same save;
  - at 18.8 fps the robot ahead grew from ~50 to ~130 px wide on screen;
  - at 10.9 fps (`HOS_FRAME_SLEEP_MS=40`), from ~50 to ~70 px.
  - The distance ratio is roughly the frame-rate ratio (inferred from the screen sizes). This is T13's problem 10
    ("animations play slowly").
- **"Game speed = Real time" and `HOS_FPS_LOG` do nothing for Raiders** (verified).
  - Both need Ocarina's graphics module (`host/nn_vi.c`, `realtime_step`; `if (!mod) return;`).
  - That module is found when `GetSystemTick` returns to `0x8348c770` (`host/hos_thread.c:1007`). No call in Raiders'
    lifted code returns there: the nearby call returns to `0x8348c778`, checked in `work/sa/gen`.
  - The hook is not gated on the game id, against CLAUDE.md's rule. Here it is harmless by address. Gating it on
    `hos_game_is("oot")` is a one-line follow-up for T22.
- **Raiders' frame-rate target is unknown.**
  - It presents with interval 1 (`vi: … frames presented (… interval 1)` in every run), so it asks for every display
    refresh (inferred: a 60 fps target).
  - A Raiders real-time step needs its own frame-time hook, which is T22's.

## Step 5: measurements (windowed, Desktop Mode, 1280x720 window)

From 60 s on (boot and the title left out):

| | Handheld `meas_hh` | Docked `meas_dk` | Docked `play1` (frame capture on) |
|---|---|---|---|
| Frames | 7,694 | 12,905 | 5,388 |
| Mean frame time (fps) | 33.9 ms (**29.5 fps**) | 20.2 ms (**49.5 fps**) | 48.3 ms (**20.7 fps**) |
| Median | 34.2 ms | 20.0 ms | 45.4 ms |
| 1% low (99th percentile frame) | **24.6 fps** (40.6 ms) | **37.4 fps** (26.7 ms) | **14.8 fps** (67.6 ms) |
| Frames over 33.4 ms | 61.8% | 0.4% | 99.0% |
| Game uniform-buffer updates a frame | ~1,360 | ~830 | ~2,130 |
| Draws / passes a frame | ~1,250 / 84 | ~1,110 / 83 | ~1,330 / 83 |
| GPU time a frame (`RX_VK_PASS_TIMING`, median of the 600-present lines) | 9.2 ms | 9.3 ms | 9.4 ms |
| Presentation Thread (the replay) | 69% of a core | 85% | 71% |
| sead::MainThread | 25% | 34% | 18% |
| All threads (per 10 s interval) | ~2.3 cores of 8 | ~2.8 | ~1.9 |
| Peak RSS (VmHWM) | 5.71 GB | 5.78 GB | 5.78 GB |
| GPU memory (whole GPU, peak) | VRAM 889 MB, GTT 2,800 MB | VRAM 889 MB, GTT 2,910 MB | VRAM 887 MB, GTT 2,812 MB |
| `vk: status:` | slowest 61.2 ms; VRAM 1.5 of 5.1 GB | slowest 54.0 ms; VRAM 1.5 of 5.0 GB | slowest 73.6 ms; VRAM 1.5 of 5.1 GB |

The acceptance command's own figure for `play1` is the whole run, boot included: `frames 7322  mean 43.7 ms  over 33.4
ms: 83.3%`.

**The bistable frame rate** (verified, `vk: N presents` lines; the cause is unknown):

| Run | ub updates a frame | fps |
|---|---|---|
| `meas_dk` | 830 | 47-53 |
| `mirror_nowb` | 1,190 | 30-37 |
| `meas_hh` | 1,360 | 27-33 |
| `mirror_wb` | 1,445 | 23-26 |
| `occ_off` | 2,215 | 19-21 |
| `play1`, `occ_on`, `speed_a` | 2,130 | 19-21 |

- **Within a run the level is flat.** Every run settles at one level within the first minute and holds it.
- **The level is not the frame rate's effect.**
  - `speed_b`, slowed to 10.9 fps by a sleep, stayed at 2,069 a frame.
  - Docked and handheld each reached both fast and slow levels.
- **So the A/B runs' frame rates cannot be compared with each other.** Only their ink results can.
- **What it points at** (inferred): something chosen at start-up (a quality or level-of-detail state, or the game's
  performance controller fed by the replay's fake GPU timestamps, `docs/design.md` §4.4) decides how much the game
  draws per frame.
  - The replay's CPU time per frame then follows it: about 34 ms at the 2,130 level and 17 ms at the 830 level
    (Presentation Thread share × frame time).

## Step 6: visual differences (headless and windowed screenshots; your console comparison still to do)

| # | Where | What | Suspected | Severity |
|---|---|---|---|---|
| V1 | HUD, health bar and ink tank, the counter | Flat white squares, black or white ovals and solid shapes in place of HUD parts. The counter is sometimes partly drawn (`8`, `5` for `285`). In most runs, in many shots | T13's UI flat-box class (problem 4): UI layout drawing (inferred) | Medium: often visible |
| V2 | Water-warning overlay | Drops out or appears for one frame (play1 117.5, 118.0, 234.0 s) | The overlay pass out of step with the scene: present ordering or event waits (`docs/design.md` §4.1, inferred) | Medium |
| V3 | Respawn iris wipe | One frame with the wrong circle, or the scene showing outside it (134.2, 188.5, 298.5 s) | As V2 | Low-medium |
| V4 | Docked hub (T15) | **Not reproduced.** T15's docked hub was magenta; `play1_t17a` (headless), `play1` and `meas_dk` (windowed) all draw it correctly. The compute program T15 named (`20ce8fa19e5349c2`, a network left out on AMD) never ran (0 log lines) | Unknown; T15 used `HOS_INPUT_FRAME_CLOCK=1` and an earlier build | Open, watch |
| V5 | Hub nets | Present in shots; the flicker T13 saw (problem 13) was not looked for frame by frame | Unknown | Low |
| V6 | **Every 2D UI element drawn over 3D** (your check, `check1`) | Flickers and glitches all through play: V1 seen live, constant rather than occasional | V1's class; T13's problem 4 and item 11 | **High:** always visible |
| V7 | **After the gear menu (+)** (your check, `check1`) | The scene is brighter than before the menu | T13's item 12 reproduced: state the menu's rendering leaves behind (exposure, a render target or a texture the 3D reuses; unknown) | Medium |
| — | Colours, shadows, fog, missing objects | Need the console side by side | Your check | — |

T13's open items 10-14 (`M4-first-frame.md`) still stand. Item 10 is now explained: the game runs per frame (step 4).

## Gate 2, first reading

- **Handheld:** the Deck is **just short of a stable 30 fps** in the hub: 29.5 fps mean, a 34.2 ms median, and a 1% low
  of 24.6 fps.
- **Docked:** between 20.7 and 49.5 fps, depending on the per-run state above.
- **What limits it:**
  - the replay's thread (Presentation Thread, 69-85% of a core, ~17-34 ms of CPU a frame), together with the
    per-run level of game work that it replays;
  - not the GPU (9-10 ms a frame);
  - not memory for now. But 5.7 GB resident plus 2.8-2.9 GB GTT is a large share of 16 GB (T20).
- **Why it matters beyond smoothness:** game time follows frames, so 20 fps plays at about a third of normal speed if
  the target is 60 (inferred).
- **For M7 (T22):**
  - find what sets the per-run level (it alone is worth 20 → 49 fps);
  - cut the replay's per-frame descriptor and update cost (T13's note: ~30 ms of descriptors at the slow points);
  - give Raiders a real-time step of its own.

## Acceptance criteria

| Command | Output | Met? |
|---|---|---|
| `scripts/deck/run.sh play1 330 --window --rss --user-from /home/deck/raiders/work/t17_user_seed -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" RX_VK_FRAME_LOG=frames.csv HOS_THREAD_TIMES=10 RX_VK_FRAMELOG=framelog RX_VK_OCC_LAG=200 HOS_WINDOW_SIZE=1280x720 && scripts/deck/fetch.sh play1` | `stopped at the time limit`, `24 screenshots`, `# rss: 64 samples …`, `fetch: … (31 files)` | Met; the switches added are explained below |
| `.venv/bin/python -I scripts/framelog.py work/runs/play1/framelog 2>/dev/null \| tail -5` | Five of the largest events (`frame 5543 (game) darker 66 blocks …`); the counts are in step 2 | Met |
| `awk … work/runs/play1/frames.csv` | `frames 7322  mean 43.7 ms  over 33.4 ms: 83.3%` | Met (a measurement) |
| `grep -ci "device lost" work/runs/play1/hookshot_log.txt` | `0` | Met |
| `.venv/bin/python -I -B tests/run_all.py` | Header paths unset: `296 passed, 9 failed, 42 skipped`. Set (`HOOKSHOT_VULKAN_HEADERS`/`HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`, `--jobs 4`, as T13): **`329 passed, 9 failed, 9 skipped in 810 s`** | Met: the 9 failures are the same files as T13's final run (`diff` of the names: none). The 3 extra passes are T15's and T16's tests and `test_frame_log_offscreen.py` |
| Your checks: the four ink behaviours; start, play, save, quit, continue on the Deck's controls | Ink: all four work. Continue: the second boot resumed at the results screen of the level you quit in | **Met** (`check1`, `check2`; below) |

**Why the acceptance run has more switches than the task's command.**
- **`--window`:** `RX_VK_FRAMELOG` needs a real swapchain (it is taken in `present_image`).
- **`RX_VK_FRAMELOG=framelog`:** without it the `framelog.py` line has no file to read.
- **`--user-from`:** keeps your save out of reach.
- **`--rss`:** the memory figure.
- **`RX_VK_OCC_LAG`:** the ink lag.
- **`HOS_WINDOW_SIZE`:** the Deck's window.

None of them loosens a criterion. The task's command as written, run headless (`play1_t17a`, before the frame-log fix),
produced no `frames.csv` and no `framelog`.

## Your checks at the Deck (done 2026-11-12)

**The runs.** Windowed, handheld profile, the Deck's own controls, on `~/raiders/work/t17_user_play` (a persistent copy of
your save; yours stayed `d9dfb4bb…`):
- `check1`: `run.sh check1 1800 --window --args "--user /home/deck/raiders/work/t17_user_play" -- HOS_HANDHELD=1
  HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAME_LOG=frames.csv`;
- `check2`: the same, with `--sound` and `HOS_MOTION_DEBUG=1`.

| Check | Result |
|---|---|
| Ink: swim in own ink, walk in enemy ink, climb an inked wall, ink stays | **All four work** (your check, in the hub and in a level) |
| Start, play, save, quit | `check1`: you closed the window (`display: window closed, exiting`, exit 0). The game had written `save.dat` at 22:11:07, 5,962 B (verified) |
| Continue | `check2`: **the game resumed at the results screen of the level you closed it in** (your check). Raiders does not drop you back into a level |
| Sound | `check1` was muted by `run.sh`'s default (`HOS_AUDIO=0`; my command left out `--sound`). With `--sound` in `check2`, the sound present before is there. The missing effects are T18's |
| Gyro | Did not move the aim in `check1` or `check2` while the Steam client ran. **It works again once Steam is quit in Desktop Mode** (your check, during `check2`) |

**Frame rate in your play** (`check1`, 417 s after boot): 41.1 fps mean, 1% low 17.1 fps, 24.2% of frames over 33.4 ms.
Peak resident set 6.69 GB (`run.sh`: the run ended by itself, so `peak_rss_kb.txt` exists).
- Unlike the scripted runs, the level of game work changed **within** the run: ~22 fps at 2,132 updates a frame, then
  ~59 fps at 1,768 for the rest.
- So the level follows the area or state the game is in, not only the start-up. That is a lead for T22.

**The gyro: the Steam client blanks it in Desktop Mode too (verified by your check; the mechanism is inferred).**
- `check2` had the same launch as T15's working `gyro_a` (Desktop Mode, over SSH, windowed, handheld, `HOS_MOTION_DEBUG=1`).
  The log reads `"Steam Deck Controller" connected (SDL), with a gyroscope` and `motion controls from "Steam Deck
  Controller"`, as in `gyro_a`.
- **But no readings arrived:** `check2` has one `hid: motion:` line, all zeros (`accel (-0.00, +0.00, -0.00) G`; a
  working sensor reads about 1 G of gravity). `gyro_a` had 344 lines that followed the tilt.
- **The Steam client was running** in this Desktop Mode session from 15:49 (`steam -steamdeck`). When you quit it, the
  gyro moved the aim again (your check).
- **So T15's Gaming Mode finding applies to Desktop Mode whenever Steam runs** (inferred): Steam holding the Deck's
  controller leaves the game's SDL view of it without sensor data.
- **For now:** quit Steam before a Desktop Mode run that needs the gyro.
- **For T24:** the shipped launch needs T15's plan B (Steam Input's gyro on the right stick), or the `--raw-deck-pad` lead
  (`steam_launch.sh`), in both modes. Nothing in the code was changed here.

## Decisions

- **Step 3 was replaced** by the occlusion-count A/B plus a mirror check (your instruction). The write-back A/B is moot
  on an integrated GPU.
- **Measurements are windowed,** as you play. Headless runs give no swapchain frame capture.
- **No performance change** (T22) and no memory change (T20) was made. The bistable level is recorded for T22.
- **A gap in the plan:** no task from T18 to T25 fixes rendering correctness. That covers V1/V6 (the UI flicker), V2/V3
  (the overlay out of step) and V7 (the brightness after the gear menu). T18-T19 are audio and movies, T20-T22
  memory, caches and CPU, T23 a soak, T24 packaging, T25 upstream PRs. A new task covers them:
  `docs/plans/tasks/T17a-ui-and-overlay-rendering.md` (written at your request).
- **A measure for the UI flicker** (`play1` frame capture, from 60 s; a scratch script over `scripts/framelog.py`'s
  blocks):
  - **The HUD's bottom left** (block rows 7-8, columns 0-4 of the 16x9 grid) has a one-frame jump in **465 of every
    1,000 frames**, and the counter at the top right in 28.
  - The same-sized regions with no HUD have 23-46 (bottom centre 45.5, middle 23.2).
  - This is T17a's baseline.
