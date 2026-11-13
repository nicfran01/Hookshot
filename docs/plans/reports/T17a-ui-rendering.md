# T17a · UI and overlay rendering   (2026-11-13)

**Short answer.**
- **The UI flicker and the two overlay faults were one cause, and it is fixed.**
  - **The cause.** On the Deck the buffer pools have no VRAM mirrors (integrated GPU). The GPU therefore read uniform
    and storage buffers from guest memory when it executed, not as they were at the submission. By then the game's
    threads had already written later frames' data into them.
  - **The UI class.** Raiders' 2D layer is the most rewritten data in a frame. It came out with another frame's
    constants or text data for one frame in two: flat shapes, a counter partly drawn, another string's letters in the
    button prompts.
  - **The overlay class.** The water warning dropping out and the respawn wipe at the wrong size are the same layer
    reading the same way.
  - **The fix.** Uniform buffers, and single read-only storage buffers the CPU wrote in the last 3 frames, are copied
    into the recording's stream as submitted. Memory the GPU writes is left in place. This is upstream's design rule 2,
    applied where mirrors do not already apply it.
- **The measure** (one-frame jumps per 1,000 frames, from 60 s):

  | Region | Before (`ui0`) | After (`ui1`) |
  |---|---|---|
  | HUD bottom left | 483.3 | **4.4** |
  | Bottom-right button prompts | 266.6 | **2.1** |
  | Control regions | 54.8 / 25.3 | 16.0 / 4.2 |

  Large events (36+ blocks): **17 → 0**, over 10 respawn wipes and 17 water-warning spans in `ui1`.
- **The gear-menu brightness:** within 3% in all three final-build pairs (−0.09%, −1.34%, −0.23%). But the menu still
  leaves a lighting change behind at times (−3.2% in two earlier runs; one washed-out run under an A/B switch). Its
  cause is **not found**: `BLOCKER-T17a-2026-11-13.md`.
- **Your check at the Deck** (`check3`, step 6): the UI flicker is gone and the scene no longer brightens after the menu.
  But once, after the menu, the ground went missing: 36-107 draws a frame left out for an index buffer in no imported pool
  (upstream's code, T13's item 12). The world flicker you saw comes with that state.

Claims are **verified** (run, command, log line or file:line named) unless marked **inferred** or **unknown**. Runs are in
`work/runs/<name>/` (Mac) and `~/raiders/work/runs/<name>/` (Deck). Every run is windowed, handheld
(`HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720`), with `RX_VK_FRAMELOG=framelog`, on a fresh copy of your save
(`--user-from ~/raiders/work/t17_user_seed`). Your save is still `d9dfb4bb…` after all runs. `journalctl -k`: 0
`gfx_`/timeout lines since 2026-11-12 22:00. No run lost the device (`grep -ci "device lost"`: 0 in every run named here).

## The measure (step 1)

- **`scripts/framelog.py --regions <s>`** (`--region NAME=R0-R1,C0-C1` adds or replaces one).
  - It uses the script's own event rule (`jumps()`, the same test as before, now one function).
  - From `<s>` seconds after the first record, it counts the eligible triplets in which a region has at least one block
    that jumps, per 1,000.
  - It then lists every event of 36+ blocks after `<s>`.
  - Without `--regions`, the output is unchanged: `tests/test_framelog_integrity.py` passes, and the new test checks a
    plain run's lines.
- **The default regions** are T17's: `hud_bottom_left` rows 7-8 columns 0-4, `counter_top_right` 0-1/12-15,
  `control_bottom_centre` 7-8/6-10 and `control_middle` 3-4/6-10.
- **One region added in this report** with `--region hud_bottom_right=8-8,13-15`: the button prompts. In standing-still
  runs it was the region that still flickered after the first fix (below).
- **`tests/test_framelog_regions.py`:** synthetic captures only (painted blocks). It covers region parsing, the jump
  rule, the counts, the start time, the large-event list, unchanged plain output and a bad region's error.
- **T17's baseline reproduced exactly** on `work/runs/play1/framelog` (docked, from 60 s): 464.9 / 28.2 / 45.5 / 23.2 per
  1,000, and the same 9 large events at 117.46-298.64 s (verified).
- **Routes.**
  - `games/raiders/scripts/area1_loop.txt` (T17). It falls into the water and respawns 2-10 times a run.
  - **New: `games/raiders/scripts/gear_menu.txt`.** Title to hub (ZL+ZR at 30, 35, 40 s), then nothing until PLUS at
    80 s and B at 92 s; B closes the menu (verified in shots). The player stands still, so any jump outside the menu's
    own fade is a fault.

## Runs

| Run | Build | Route, s | Switches beyond the common ones | For |
|---|---|---|---|---|
| `t17a_dump1` | main | area1, 140, headless | `RX_VK_DUMP=2700+8` | a dump of 8 frames (below: of little use) |
| `ui0` | main | area1, 330 | `RX_VK_PASS_TRACE=1` | the handheld baseline: the acceptance command on the old build |
| `mir1` | main | area1, 200 | `RX_VK_MIRROR=1` | A/B: pools mirrored |
| `ubs1` | main | area1, 200 | `RX_VK_UB_SNAPSHOT=1` | A/B: uniform buffers copied (upstream's experiment switch) |
| `gear1` | uniform fix | gear, 130 | shots every 30 | brightness; first standing-still flicker reading |
| `fix2`, `fix3`, `fix4` | intermediate | area1, 200 | — | the vertex-stream and copy-source steps (dropped, below) |
| `gear2`, `gear3`, `gear4` | intermediate | gear, 120 | `RX_VK_AS_SUBMITTED_LOG=1`; `gear3` an A/B switch | finding the prompts' input |
| `ui1` | **final** | area1, 330 | — | **acceptance** |
| `gear5`, `gear7`, `gear8` | **final** | gear, 120 | (`gear5` shots every 30) | brightness pairs, standing-still flicker |
| `gear6` | **final** | gear, 120 | `RX_VK_UB_SNAPSHOT=0 RX_VK_SB_SNAPSHOT=0` | the old behaviour on the same build |

## The UI class (step 2)

**What the bad frames look like.** From `play1` and `ui0` frame captures, triplets around HUD-region jumps (verified by
eye):
- the HUD's parts drawn as flat white or black ovals and squares;
- the counter partly drawn;
- an in-world marker as a flat square.

In the standing-still runs, the button prompts show another string's letters for one frame.

**A draw left out? No.** Every `vk: a frame:` line in `play1` and `ui0` reads `0.0 draws left out (not ready), 0.00 waits for
shaders or pipelines` (verified). Pipelines are ready, so this is not T21's area. The `RX_VK_PIPE_SKIP=0` run was not
made: the log already answers its question (a deviation, below).

**A/B, `area1_loop`, from 60 s:**

| Run | HUD bottom left | Counter | Bottom centre | Middle | Bottom-right prompts | 36+ events | ub updates a frame, fps |
|---|---|---|---|---|---|---|---|
| `ui0` (default) | **483.3** | 40.9 | 54.8 | 25.3 | **266.6** | 17 | 2,121, 19.7 |
| `mir1` (`RX_VK_MIRROR=1`) | **2.8** | 4.5 | 18.9 | 7.6 | **1.1** | 0 | 979, 27.6 |
| `ubs1` (`RX_VK_UB_SNAPSHOT=1`) | 27.3 | 4.5 | 24.2 | 10.6 | 98.5 | 1 | 2,037, 19.8 |

- **Mirroring the pools removes the class** (verified). So the GPU read pool memory at the wrong time.
- **The cause in code** (verified):
  - With mirrors off, `gpu_buffer_bind` returns the imported pool's own buffer: `gpu/vk/vk_memory.cpp`, the
    `!mirror_on()` branch.
  - `mirror_on()` is on only for discrete GPUs, and the Deck logs `vk: VRAM mirror of buffer pools off`.
  - The replay records synchronously, but the GPU executes later. The game has by then written later frames' data
    into the same memory (inferred, from the A/B and from upstream's own comment on the same race before mirrors,
    beside `gpu_buffer_bind`).
- **Uniform buffers carry most of it** (`ubs1`, verified), but not all: the prompts stayed at 98.5.
- **Not mirrors as the fix** (verified, `mir1` against `ui1`'s level):
  - They cost 42-43 mirrors (768 MB), 9.6 MB synced and **55.8 MB written back a frame**.
  - VRAM in use went from 1.5 to 2.4 GB.
  - At the same 979-update level, 27.6 fps against 39.9-43.2 fps for the final fix (`ui1`, `fix4`).
  - On a 16 GB shared-memory machine that is T20's and T22's budget.

**Finding the rest: standing still in the hub (`gear_menu.txt`, from 45 s), where every region but the prompts reads 0:**

| Run | Copied as submitted | Bottom-right prompts |
|---|---|---|
| `gear6` (old behaviour) | nothing | 215.7 (and HUD bottom left 382.3) |
| `gear1` | uniform buffers | 88.0 |
| `gear2` | + vertex streams the CPU wrote in the last 3 frames | 61.3 (0.6 streams a frame copied) |
| `gear3` | + those streams even on GPU-written pages (an A/B switch) | 63.3 |
| `gear4` | + index buffers (0 copied) + read-only storage buffers (12.8 a frame) | **0.0** |
| `gear5`, `gear7`, `gear8` | the final fix: uniform + read-only storage | **0.0, 0.0, 0.0** |

- **The prompts' input is a single read-only storage buffer** the CPU rewrites every frame (verified).
  - In `gear4` the only new copies were storage buffers; index buffers copied 0.
  - Vertex streams made no difference (`gear2`/`gear3`).
  - Buffer-to-buffer copies were never used by the game in `fix4` (0 copy sources a frame).
- **Those three steps were reverted.** The vertex-stream, index-buffer and copy-source copies had no observed effect, so
  only the two located causes remain.

## The overlay class (step 3)

**The same cause.** In every large event of `ui0` (verified by eye on the triplets), the water-warning border is missing
or the wipe is wrong, **and in the same frame** HUD parts are flat black or white. The border and the wipe are drawn by the
same 2D layer:
- the warning border missing for one frame, or there for one frame;
- the wipe's circle the wrong size for the sequence, with the outside not fully black.

| Run | Wipes | Warning spans | 36+ events after 60 s |
|---|---|---|---|
| `ui0` | 4 | 7 | **17**: all at the warning or a wipe (117.1-123.8, 126.8, 178.4, 188.1, 236.1-236.5, 290.6 s) |
| `mir1` | 2 | 6 | 0 |
| `ubs1` | 1 | 4 | 1: a white 3D splash missing for one frame at 130.5 s. The warning border and the HUD are intact (verified by eye): a 3D effect, not the overlay |
| `ui1` (final) | **10** | **17** | **0** |

- Wipes and warning spans were found with a scratch scan of the capture (dark borders; the warning's olive border).
- **`RX_VK_PASS_TRACE=1` logged nothing** (`ui0`: 0 `passes of frame` lines). It logs only at the flash detector's or the
  frame log's dark-frame trap, and neither fired. Not needed once the A/B named the cause.
- **`RX_VK_EVENT_WAITS=0` was not run.** The overlays turned out not to be ordering between queues.

## The gear-menu brightness (step 4)

**The measure.** Mean luma of the frame capture over 65-74 s (before PLUS) and 95-108 s (after B), the same view with no
input in between, plus the count of 20x20 blocks that changed by more than 3 levels:

| Run | Build | Before | After | Change | Blocks changed |
|---|---|---|---|---|---|
| `gear1` | uniform fix | 140.57 | 136.01 | −3.25% | 62 |
| `gear2` | intermediate | 140.47 | 140.47 | +0.00% | 49 |
| `gear3` | intermediate + A/B switch copying GPU-written vertex data | 140.29 | 202.92 | **+44.65%** | 144 |
| `gear4` | intermediate (storage fix in) | 140.52 | 136.09 | −3.15% | 62 |
| `gear6` | final, copies off | 140.49 | 140.30 | −0.14% | 6 |
| `gear5` | **final** | 140.56 | 140.43 | **−0.09%** | 3 |
| `gear7` | **final** | 142.32 | 140.42 | **−1.34%** | 34 |
| `gear8` | **final** | 140.59 | 140.27 | **−0.23%** | 7 |

- **What changes** (verified by eye, `gear1` shots at presents 2130 and 2850, and its block map):
  - the sky blocks do not move at all, so it is not exposure and not the camera;
  - the sunlit surfaces lose their warm direct light, as if in shadow: the tower front, the deck, the characters.
- **`gear3`'s after-picture is washed out over the whole frame:** your V7. But that run had a switch that copied
  GPU-written data, which can be stale, so the run proves nothing about the cause (inferred).
- **It is intermittent, and in both directions.**
  - It happened under two different builds (`gear1`, `gear4`) and not in four others, `gear6`'s old behaviour among them.
  - So the copies neither cause nor cure it (inferred from 8 runs).
- **The area-reload check was not made:** the cause was not located, and a route into a level was out of time.
- **Next step:** a dump of the lighting passes before and after the menu in a run that shows the change, comparing which
  textures (shadow map, light buffers) the lit passes sample. The `t17a_dump1` dumps were 320x180 thumbnails, and a dump
  turns the queue-order waits off (`sync_waits_on()` is false while `dump_on()`, `gpu/vk/vk_replay.cpp`), so a run that
  dumps may not show it. `BLOCKER-T17a-2026-11-13.md`.

## The fix (step 5)

**`gpu/vk/as_submitted_policy.h`** (new, header-only, the decisions):
- `switch_on(env, mirrors_on)`:
  - **`RX_VK_UB_SNAPSHOT`** (upstream's switch, which was off): now on by default exactly when pools are not mirrored;
    `=0` never.
  - **`RX_VK_SB_SNAPSHOT`** (new): the same rule.
- `copy_uniform` copies any uniform buffer whose memory the GPU never wrote.
- `copy_storage` copies a single read-only storage buffer the CPU wrote in the last 3 frames, up to 4 MB, never
  GPU-written.
- `GenRing` gives the memory generation as a frame began, a few frames back.

**`gpu/vk/vk_draw.cpp`** (raiders):
- `uniform_range` decides from the policy, before it binds the pool.
- The storage descriptors ask `storage_as_submitted` first. A copy comes from `memory_read_as_submitted` (guest memory
  with the submission's capture pages over it) and is made once per recording (`RecordingRes::sb_copies`, cleared with
  the recording).
- Every 600 frames, one `vk: a frame: as submitted:` line counts the copies. `RX_VK_AS_SUBMITTED_LOG` names the first
  storage ranges left in place.

**`gpu/vk/vk_memory.cpp`** (raiders):
- `memory_stamp_gpu` records every GPU buffer write in a page bitmap: 16 MB of lazily zeroed memory over the 512 GB
  window, never cleared.
- `memory_gpu_written` answers from that bitmap, so a copy never holds the CPU's bytes from before a GPU write.
- `memory_mirrors_on` and `memory_generation_before` are exported. `vk_internal.h` declares all three.

**The cost in `ui1`** (verified, the log line) and the frame rate:
- Each frame copied 3,936 uniform buffers (4.60 MB) and 13.4 storage buffers (0.38 MB).
- 389.5 storage buffers were left on GPU-written pages, and 286.2 were over 4 MB.
- At the slow game-work level the frame rate is unchanged: `ui0` 19.7 fps at 2,121 updates, `ubs1` 19.8 at 2,037,
  `fix3` 19.7 at 2,041 (verified).
- In the final build's runs the fast level gave 39.9 fps (`ui1`).

**Tests:**
- **`tests/test_as_submitted.py`** (new) compiles the header against its cases: the switches, both decisions, the
  ring. It checks by text that both binding sites ask the policy before binding the pool, that the copies are read as
  submitted and kept per recording, that every GPU write records its pages, and that the exports sit outside the
  anonymous namespaces.
- **`tests/parallel_rb_refresh_test.cpp`** compiles a cut of `build_descriptors`, which now names `storage_as_submitted`.
  The fixture gained a stub that binds in place, since that world is about mirrors. Upstream's text is unchanged.

**Upstream PR candidate (T25): yes, generic.**
- Any integrated GPU runs without mirrors: the Deck, other handhelds, laptops' iGPUs.
- Discrete GPUs keep their behaviour: the switches follow `mirror_on()`.
- The PR would add the two switches' rows to `docs/development.md`. They are not added here: not in this task's
  files.

## Acceptance criteria

| Command | Output | Met? |
|---|---|---|
| `scripts/deck/run.sh ui1 330 --window --user-from /home/deck/raiders/work/t17_user_seed -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh ui1` | `stopped at the time limit`; `fetch: …/work/runs/ui1 (48 files)` | Met |
| `.venv/bin/python -I scripts/framelog.py work/runs/ui1/framelog --regions 60` | `13032 frames`; `regions from 60.0 s: 10491 eligible triplets`; HUD bottom left `46, 4.4 per 1,000`; counter `54, 5.1`; bottom centre `168, 16.0`; middle `44, 4.2`; `events of 36+ blocks from 60.0 s: 0` | **Met:** 4.4 is at most twice the higher control (2 × 16.0 = 32.0) |
| 36+ events at the water warning or the wipe | 0, over 10 wipes and 17 warning spans | **Met.** No large event remains, of any class |
| `grep -ci "device lost" work/runs/ui1/hookshot_log.txt` | `0` | Met |
| Gear-menu pair within 3% | Final build: −0.09% (`gear5`), −1.34% (`gear7`), −0.23% (`gear8`) | **Met in 3 of 3 final-build pairs.** The underlying change is not explained; it reached −3.25%/−3.15% in two intermediate runs (above, and the blocker) |
| `.venv/bin/python -I -B tests/run_all.py` (header paths set, `--jobs 4`) | `331 passed, 9 failed, 9 skipped in 841 s` | **Met:** the same 9 failures as T17, plus the 2 new tests passing |
| User check at the Deck | UI flicker gone; no brighter scene after the menu; the ground went missing once after the menu, with world flicker from then on | **Partly met:** the missing ground (draws left out, step 6) is open |

`ui1` settled at the fast game-work level (979 updates a frame, 39.9 fps), where `ui0` was at the slow one (2,121). The
same criterion also held at the slow level in an intermediate build: `fix3` gave 38.0 against 2 × 26.3 = 52.6.

**The test suite.** The first full run on this branch gave `330 passed, 10 failed, 9 skipped in 838 s`:
- the 9 known failures (`mac-test-baseline.md`; `test_program_cache_reader.py` the ASan timeout);
- `tests/test_parallel_rb_refresh.py`, broken by this change and fixed in its fixture (above).

The final run: **`331 passed, 9 failed, 9 skipped in 841 s`**. The 9 are the known ones: 8 FAIL plus the `test_program_cache_reader.py` TIMEOUT, as in T17. 331 = T17's 329 + `test_framelog_regions.py` + `test_as_submitted.py`. **Met.**

## Step 6: your check at the Deck (`check3`, 2026-11-13)

`scripts/deck/run.sh check3 900 --window --sound --args "--user /home/deck/raiders/work/t17_user_play" -- HOS_HANDHELD=1
HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAMELOG=framelog`. You played the hub, a level and back,
then closed the game at 437 s. Steam was quit; 0 device losses.

**Your verdict:**

| Check | Result |
|---|---|
| UI flicker | **Gone** |
| Brightness after the gear menu | **No change**, over several PLUS round trips |
| The ground | **Gone under you once** after leaving the gear menu, back in the hub |
| World flicker | A new-looking flicker in the world while the camera or the character moves |
| Speed | Faster at the start and in the level, slow motion back in the hub |

**What the log and the capture show:**
- **Slow motion: the game-work level** (T17's bistable level, T22; verified).
  - Hub ~33-40 fps at ~1,100 uniform updates a frame.
  - Level 30-35 fps at ~1,400.
  - Back in the hub **18-22 fps at ~2,200**.
  - Game time follows frames (T17 step 4). Not this change.
- **The missing ground: draws left out** (verified).
  - From present 8880 (271 s), every frame line reads `skips a frame by vk_draw.cpp line: 6525:`, 36-107 draws a frame,
    where it read `(0 skipped)` before.
  - That line is upstream's index-buffer bind (`gpu_buffer_bind(d.ibuf, …)`): the draw's index buffer is in no imported
    pool.
  - Just before it, `imports: 48 live (2000 MB), … 2 retired given back (112 MB)`. Inferred: a pool the game still draws
    from, or one made again over the same memory, is no longer imported.
  - This is T13's item 12 ("the floor went invisible under you"). The copies in this task do not take part: the skip is
    before them.
- **The world flicker comes with that state** (verified, the capture's one-frame events outside the HUD blocks, 3+
  blocks, per 30 s):
  - 33, 48, 37, 116, 92, 63, 33, 21, 51 until 270 s;
  - **183, 221, 179, 180** from 270 s, when the skips start.
  - The frames show the missing deck and black rectangles where geometry should be (frames 8930, 11032).
- **On the scripted route, this change made the world calmer, not worse** (frames with a world event, per 1,000):
  - `ui0` 336 → `ui1` 53 (mirrors: 48).
  - In the level, before 270 s, no comparison run exists: whether any of your world flicker there is new is **unknown**.

## Deviations

- **`RX_VK_PIPE_SKIP=0` was not run.** The log's `0.0 draws left out (not ready)` in every frame line of `play1` and
  `ui0` answers the step's question directly.
- **Dumps (`RX_VK_DUMP=<present>+3`) were tried once** (`t17a_dump1`, 8 frames). They were not the tool here:
  - each step is a 320x180 thumbnail, too small for HUD detail;
  - dumping turns off the queue-order waits, so a dumped frame is not an ordinary frame.

  The A/B runs located the cause instead.
- **Three intermediate copies** (vertex streams, index buffers, buffer-copy sources) were built and measured, then
  removed: no effect was seen. Only the two causes with evidence are in the commit.

## What is left

1. **The gear-menu lighting change** (cause unknown): `BLOCKER-T17a-2026-11-13.md`. You saw no brightness change in `check3`.
2. **Draws left out for want of an imported pool** after the gear menu, back in the hub (`check3`, above): the missing ground,
   and the world flicker that comes with it. Next: log the skipped draws' index-buffer addresses against the pool list and
   the game's pool finalize/initialize calls (`nvnMemoryPoolFinalize`, `memory_pool_created`) around 271 s.
3. **`docs/development.md` rows** for `RX_VK_UB_SNAPSHOT` (its new default) and `RX_VK_SB_SNAPSHOT`, with the upstream
   PR (T25).
4. **For T22:** mirrors are no option on the Deck at their cost (above). The copies' CPU cost showed no frame-rate change
   at the same level, but was not profiled.
