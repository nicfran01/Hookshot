# T17c · World flicker with T17a's copies as submitted   (2026-11-14)

**Short answer.**
- **The cause is found and fixed in the hub, on a repeatable case.**
  - **What the bad frames are** (verified, `sw_m1`/`sw_j1` frame captures, horizontal shift per frame):
    - while the camera pans steadily (~10 px a frame), one frame shows the camera of **two frames before**, and the next
      catches up by two steps (`+10 +10 -10 +20`);
    - sometimes only the sky band moves, not the ground;
    - the HUD is intact.
  - **Which input** (verified):
    - the **uniform** copies carry it: copying only uniform buffers gives it, copying only storage buffers does not
      (`sw_g1`/`sw_g2`);
    - none of the task's step (d) inputs. Big storage buffers, an ageing GPU-write record and vertex streams copied
      nothing that mattered and changed nothing (table below).
  - **The cause** (verified by the fix's A/B):
    - The game's queues wait for events **the CPU signals**. The game writes the frame's constants *after* it submits
      the work, then signals.
    - When the replay finds such a wait unmet, the queue stops, and upstream takes a fresh capture when it resumes
      (`vk_replay.cpp` `resume_queue`, `memory_capture_now`).
    - When the wait is **already met** as the replay reaches it, nothing is captured. The copies after the wait then take
      the bytes from the submit-time capture, written before the CPU's update: the double-buffered constants of two
      frames before.
    - Whether the wait is met depends on timing, so the stale frame comes and goes: ~1 frame in 50-100 while the
      camera turns.
  - **The fix** (`as_submitted_policy.h` `capture_at_met_wait`, called in `vk_replay.cpp`'s met-wait branch):
    - at a met wait on a CPU-signalled event, take the same capture the resume path takes, when the pools are not
      mirrored;
    - the draws after it build their descriptors again;
    - `RX_VK_MET_CAPTURE=0` turns it off.
- **Measure, hub sweep, final build** (world events of 9-35 blocks per 1,000 frames while the camera sweeps: the flicker's
  signature, below): fix **0.0, 0.0** (`fx1`, `fx2`) against **19.7** with it off (`fx0`); copies off 0.0, mirrors 0.0.
  The UI stays fixed: HUD bottom left 16.9 and 11.4 (copies off: 348.2).
- **Cost:** 0.8-0.94 extra captures a frame (3,781-5,570 per run), ~0.48 ms each on the replay thread, ~44 pages
  (0.2 MB). The frame rate at the same game-work level is unchanged within run noise.
- **The level case (`flick1`, your session, 265 s):**
  - Blanch Seaway reads **76.0** world events of 3+ blocks per 1,000 (9-35 blocks: **5.4**).
  - T17b's runs, before the fix: copies on (`ground1`) 229.6 and 178.7 (53.1 and 42.6); copies off (`abl0`) 169.1 (52.7).
  - 0 skip lines, 0 device losses.
  - **Your verdict:** "This is a very significant improvement. in this current state, i completely accept the way the game
    looks right now."
- **Not done:** no scripted route into the level (Deviations).

Claims are **verified** (run, command, log line or file:line named) unless marked **inferred** or **unknown**. Runs are in
`work/runs/<name>/` (Mac) and `~/raiders/work/runs/<name>/` (Deck): game output, never committed. Every run used a fresh
copy of your save (`--user-from …/t17_user_seed`); your save is still `d9dfb4bb…` after all runs (checked). Every run named
here: **0 skip lines, 0 device losses** (`grep -c "skips a frame by vk_draw.cpp line"`, `grep -ci "device lost"`).

## The case and the measure's floor (scope 1-2)

**The case: `games/raiders/scripts/hub_sweep.txt`** (new).
- `gear_menu.txt`'s start: title to hub with ZL+ZR at 30, 35, 40 s.
- No input until 75 s: a still span.
- Then RLEFT/2500 and RRIGHT/2500 every 3 s until 165 s: the camera sweeps, the player stands still.
- No input to the end: a second still span.
- Runs: 200 s, windowed, handheld (`HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720`), `RX_VK_FRAMELOG=framelog
  RX_VK_SHOT_EVERY=300`, fresh save.
- Spans: still 50-73 s, sweep 78-163 s, still 168-195 s (`--span`). The frame log's first record is within ~2 s of the
  script's clock (inferred: the 10-s bins rise in 70-80 s).

**The floor** (verified, `scripts/framelog.py --regions 78 --span …`; no change to the script was needed):
- **Standing still:** 0.0-5.4 world events of 3+ blocks per 1,000 in every mode (copies off: 16-36, its own UI-class
  spill into world blocks).
- **While the camera sweeps, the measure counts the motion itself.** A smoothly panning textured scene makes blocks that
  peak against both neighbours. In every mode, mirrors included, the sweep reads 55-100 per 1,000 of 3+ blocks,
  almost all of 3-8 blocks: mirrors `fxm` 72.9 of 3-8 and 0.0 of 9-35; copies off `fxb` 64.2 and 0.0.
- **The flicker's signature is the 9-35-block class.**
  - With T17a's copies it reads 11.7-22.5 per 1,000 in every run (`sw_a`, `sw_d*`, `sw_e1`, `sw_f*`, `sw_g1`, `fx0`).
  - It reads 0.0 with copies off, with mirrors, and with the fix.
  - By eye and by shift (below), those frames are the stale-camera frames.
- **The level's own one-frame effects** (radar sweep, reticle, splashes) are **not calibrated**: no level run was made
  (Deviations). In `ui3`'s level route, 9-35-block world events are 3.1 per 1,000, with 0 of 36+.

## The A/B ladder (scope 3)

All on the hub sweep, from experiment builds of this branch. Each experiment switch was off unless named, so the
default behaviour of every build equals T17a's unless the row says otherwise.

| Run | Switches (beyond the case's) | Sweep, 3+ | Sweep, 9-35 | Still | HUD BL | ub/frame, fps |
|---|---|---|---|---|---|---|
| `sw_a` | (a) default, T17a's copies | 157.0 | 15.7 | 5.4 / 0.0 | 35.0 | 1504, 30.6 |
| `sw_b` | (b) `RX_VK_UB_SNAPSHOT=0 RX_VK_SB_SNAPSHOT=0` | 86.9 | **0.0** | 36.3 / 3.7 | 337.9 | 2134, 24.7 |
| `sw_c` | (c) `RX_VK_MIRROR=1` | 99.6 | **0.0** | 0.0 / 0.0 | 22.3 | 2071, 23.2 |
| `sw_d1` | (d) big storage: `RX_VK_SB_BIG_MB=64` | 131.2 | 11.7 | 0.0 / 0.0 | 29.6 | 2134, 23.5 |
| `sw_d2` | (d) ageing GPU record: `RX_VK_GPU_WRITTEN_AGE=8` | 128.1 | 12.6 | 0.0 / 0.0 | 21.7 | 2134, 23.3 |
| `sw_d3` | (d) vertex streams: `RX_VK_VB_SNAPSHOT_MB=16` | 147.0 | 22.5 | 2.3 / 0.0 | 36.1 | 979, 39.6 |
| `sw_e1` | every pool captured: `RX_VK_CAPTURE_POOL_MB=1024` | 147.3 | 17.5 | 0.0 / 0.0 | 26.4 | 2134, 23.4 |
| `sw_f2` | mixed CPU/GPU pages ≤ 1 MB copied: `RX_VK_SB_MIXED_MB=1` | 101.5 | 12.3 | 0.0 / 0.0 | 21.6 | 2071, 24.0 |
| `sw_f3` | the same ≤ 4 MB: `RX_VK_SB_MIXED_MB=4` | 143.8 | 21.5 | 2.2 / 0.0 | 25.5 | 2134, 22.5 |
| `sw_g1` | uniform copies only: `RX_VK_SB_SNAPSHOT=0` | 146.8 | **20.2** | 3.4 / 0.0 | 36.9 | 979, 43.2 |
| `sw_g2` | storage copies only: `RX_VK_UB_SNAPSHOT=0` | 61.3 | **0.0** | 20.3 / 3.8 | 150.2 | 1504, 36.9 |
| `sw_i1` | reads as of their own submission's capture (per-page capture history) | 114.9 | 12.5 | 1.8 / 0.0 | 43.6 | 1504, 32.7 |
| `sw_j1` | `sw_i1` + inline uniform updates written into the captures once done | 119.6 | 11.8 | 1.7 / 0.0 | 34.2 | 1357, 40.4 |
| `sw_l1` | `sw_i1` + pages kept when their capture is given up | 177.1 | 18.4 | 0.0 / 0.0 | 29.4 | 2134, 24.0 |
| `sw_n1` | **a capture at a met CPU-event wait**: `RX_VK_MET_CAPTURE=1` | 75.3 | **0.0** | 2.1 / 0.0 | 20.1 | 2134, 22.8 |

Diagnostic-only runs (logging, not measured for the flicker): `sw_f0`, `sw_f1`, `sw_h0`-`sw_h3`, `sw_k1`, `sw_m1`.
`sw_m1` hashed every live uniform read under a lock and ran perturbed (321.7), so it is used only for its log result.

**What each step showed** (verified, the runs' log lines):
- **(d) The task's three late inputs never carried it.** Their copies had no effect, and their log lines show why:
  - **Big storage (`sw_d1`):** `0.0 copied` with a 64 MB limit.
    - The over-4 MB bindings (155.5-355.7 a frame) are mostly one 53 MB range, `+0x3567e80`, 0 GPU-written pages.
    - The CPU's write watch saw it written only around boot (`sw_f0` log, `CPU-written lately yes … present 936`). In
      the sweep, its late-input count reads 0.0 a frame.
    - T17b's "the CPU wrote lately" for these was the page generations, which GPU stamps also bump (`memory_stamp_gpu`
      calls `memory_stamp`).
  - **Ageing GPU record (`sw_d2`):** `0.0 storage buffers copied on pages the GPU wrote before`. The storage ranges left on
    GPU-written pages are written by the GPU every frame, so an 8-frame age never releases them.
    - They are three ranges and a ring of small records (`sw_f1`, `RX_VK_LOG_WRITTEN=1`).
    - The 2.3 MB `0x7fcdb5d000 +0x247740` is written by programs `8e895bab2bdea870` (c0+0x30) and `86086be3dea4414b`,
      and read by many vertex-stage programs (`RX_VK_WATCH_RANGE`). It is most of the 349-376 bindings a frame left on
      GPU-written pages (inferred: `sw_f2` copied every smaller one, and those counts did not drop).
    - The ring in `0x10287xxxxx` holds 0x10-0x200-byte records, some written by `ab081c00720b1468` and
      `5cccf8dd72de67b7`.
    - Copying them anyway: `sw_f2` 1.0 a frame (0.02 MB), `sw_f3` 5.3 a frame (9.92 MB). No effect.
  - **Vertex streams (`sw_d3`):** `1.0-1.2 vertex streams the CPU wrote lately, all copied (0.00 MB)`. No effect.
- **The uniform copies alone carry it** (`sw_g1` against `sw_g2`).
- **Reads as of their submission (`sw_h*`, `sw_i1`).**
  - Pages read as submitted, per ~20,000 reads: ~20,350 from the submission's own capture or one before, **4-5 from a
    later capture**, 4-5 from guest memory stamped after the submission, ~5,500 live and not stamped since.
  - The later-capture reads were one uniform page, `0x7fcd9ff000`, about once a frame, 2-9 generations ahead.
  - The fix for that (`sw_i1`) took them to 0 with no change to the flicker.
- **Inline uniform updates (`sw_j1`).** They are written to guest memory on the GPU with no stamp
  (`vk_replay.cpp` `gpu_write`). But `0 page copies written` over 7,001,057 updates: no updated page ever has a capture.
- **Pages whose capture was given up (`sw_k1`, `sw_l1`).**
  - ~3,200 per 20,000 reads, from ~400 distinct pages.
  - Keeping them took that to ~550, with 2.6 M reads served from the kept pages, and no change to the flicker.
- **Live reads are stable** (`sw_m1`). `0` live uniform reads came back with bytes changed while the page's stamp was
  unchanged. So the copies took their capture data faithfully, and the stale bytes were already in the capture.
- **The frames themselves** (`shift.py`, scratch: 1-D cross-correlation of column means, sky rows 10-60 and ground rows
  110-140):
  - In all 12 9+-block events of `sw_j1`'s sweep, the neighbours show the same view (shift 0, mean |diff| 1.6-3.1), and
    the odd frame is a camera step off (±9-14 px, mean |diff| ~22).
  - Timelines show the pattern `+10 +10 -10 +20`: one frame two steps back, then a catch-up.
  - In 3 of 12, the sky band moves and the ground band does not.
- **A capture at a met CPU-event wait closes it** (`sw_n1`: 9-35 0.0, 3+ 75.3, HUD 20.1).
  - `waits met 20127 (3799 on a CPU event, 3799 captures there)`.
  - The steps of rows `sw_d*`-`sw_l1` were reverted (Deviations): they had no effect on the flicker.

**The input that causes it: the bytes the game writes after its submit, up to a CPU-signalled event, read by the copies
from the submit's capture when the wait is already met.**
- Log lines (verified, `fx0`, the fix off): `waits met 20127 (3784 on a CPU event, 0 captures there), … captures at a CPU
  event's wait 1493`.
- Only the 1,493 waits that stopped a queue got a fresh capture. The 3,784 met ones read the old one.
- **Why mirrors and copies-off were calm** (inferred for mirrors):
  - Copies off: the GPU reads guest memory when it executes, after the CPU's write, every time.
  - Mirrors: the pools are synced at the recording's first use of each pool. How that avoids the stale bytes is
    **unknown**, and not needed for the fix.

## The fix (scope 4)

**`gpu/vk/as_submitted_policy.h`** (raiders, T17c), the decision:
- `capture_at_met_wait(env, mirrors_on)`: `RX_VK_MET_CAPTURE` as T17a's switches:
  - unset: on exactly when the pools are not mirrored;
  - `0`: never; anything else: always.

**`gpu/vk/vk_replay.cpp`** (raiders, T17c), the capture: in `NOP_WAIT_EVENT`'s met branch,
1. when the event is one the CPU signalled (`cpu_events`, under `ev_cpu_mu`) and the policy says so, it calls
   `memory_capture_now(rec_value_now, completed())`, the resume path's call;
2. it then bumps `ub_gen`, so no later draw reuses the descriptors (and the stream copies) of a draw before the wait;
3. it is skipped in a parallel replay's dry pass (its segments, those before the wait too, are recorded after it) and by
   workers;
4. `log_order_stats` counts the met CPU-event waits and the captures taken there.

**Cost** (verified, final build):

| | `fx0` (off) | `fx1` (fix) | `fx2` (fix) | `ui3` (fix) |
|---|---|---|---|---|
| Met waits on a CPU event, captures there | 3,784, 0 | 5,570, 5,570 | 3,781, 3,781 | 5,481, 5,481 |
| A capture (`vk: capture: a submit`) | 0.48 ms, 49 pages, 0.2 MB | ~0.5 ms | 0.48 ms, 44 pages, 0.2 MB | — |
| ub updates a frame, fps | 2134, 23.6 | 1441, 31.0 | 2134, 22.6 | — |

- About 0.8-0.94 extra captures a frame: ~0.4-0.45 ms a frame on the replay thread, ~0.2 MB copied.
- At the same game-work level (2134), 22.6 fps (`fx2`) against 23.6 (`fx0`) and 22.5-23.5 in the experiment builds'
  default runs: within run noise (inferred; T17's bistable level makes single runs unreliable for fps).
- No new memory.

**Counts before and after** (hub sweep, final build, same switches):

| Run | Switches | Sweep 3+ | Sweep 9-35 | HUD BL | ub, fps |
|---|---|---|---|---|---|
| `fx0` | `RX_VK_MET_CAPTURE=0` (T17a) | 127.7 | 19.7 | 25.9 | 2134, 23.6 |
| `fx1` | default (fix) | 86.2 | **0.0** | 16.9 | 1441, 31.0 |
| `fx2` | default (fix) | 55.6 | **0.0** | 11.4 | 2134, 22.6 |
| `fxb` | copies off | 82.1 | 0.0 | 348.2 | 2134, 23.2 |
| `fxm` | `RX_VK_MIRROR=1` | 97.0 | 0.0 | 15.4 | 2134, 22.2 |

**Tests** (`tests/test_as_submitted.py`, extended):
- the policy's cases for `capture_at_met_wait`: unset with and without mirrors, `0`, `1`;
- by text, on `vk_replay.cpp`:
  - the met branch asks the policy with `RX_VK_MET_CAPTURE` and `memory_mirrors_on()`;
  - only for a CPU-signalled event, under `ev_cpu_mu`;
  - it captures for `rec_value_now`, not in a dry pass, and bumps `ub_gen`;
  - workers break out before the wait is evaluated;
  - `resume_queue` still takes its own capture.

Other tests that cut `vk_replay.cpp` by text pass unchanged (`test_bank_gen.py`, `test_parallel_dry_marks.py`,
`test_wb_diff_cpu_writes.py`, `test_same_bind.py`).

**Upstream PR candidate (T25): yes, generic.**
- Any game without mirrors (integrated GPUs) whose work waits for CPU-signalled events gets those frames' constants
  late in its copies.
- With T17a's copies, it is part of the same PR.
- With mirrors (discrete GPUs) the policy leaves it off. Whether mirrors need it is **unknown**.

## Acceptance criteria

| Command or criterion | Output | Met? |
|---|---|---|
| `scripts/deck/run.sh flick1 600 --window --sound --args "--user /home/deck/raiders/work/t17_user_play" -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh flick1` | `run flick1: exited with 0` (you closed the game at 265 s); `29 screenshots`; `peak resident set 6829180 kB`; `fetch: …/work/runs/flick1 (34 files)` | Met (265 s, not 600: your session) |
| `.venv/bin/python -I scripts/framelog.py work/runs/flick1/framelog --regions 60 --span 108-200 --span 45-78 --span 232-265` | `8892 frames`; `regions from 60.0 s: 6389 eligible triplets`; HUD bottom left `144, 22.5 per 1,000`; counter `257, 40.2`; bottom centre `80, 12.5`; middle `205, 32.1`; `events of 36+ blocks from 60.0 s: 0`; `world span 108-200 s: … 210 with 3+ blocks, 76.0 per 1,000`; `45-78 s: … 56 …, 41.2`; `232-265 s: … 27 …, 38.7` | Ran. Spans from the screenshots (by eye): hub 41-78 s, map ~84 s, loading ~96 s, Blanch Seaway ~108-200 s, its menu ~210 s, hub again ~230-265 s |
| `grep -c "skips a frame by vk_draw.cpp line"` / `grep -ci "device lost"` on `flick1` | `0` / `0` | Met |
| World in the level case: ≤ copies-off, ≤ 1.25x mirrors, ≤ 1.5x the still floor | **Level (`flick1`, 108-200 s): 76.0** of 3+ blocks (9-35: 5.4, from two `--regions` counts). Copies off, T17b's `abl0` level 120-160 s: 169.1 (52.7). No mirrors run in the level. **Hub sweep stand-in** (final build): fix 86.2 / 55.6, copies off 82.1, mirrors 97.0 (1.25x = 121.3), still floor 0.0 | **≤ copies off: met in the level** (76.0 against 169.1; different plays, so the direction only). **≤ 1.25x mirrors:** level **unknown** (no mirrors run there); hub met. Hub ≤ copies off: met by `fx2` (55.6), not by `fx1` (86.2 against 82.1, 1.05x; the two runs differ by game-work level, 1441 against 2134). **≤ 1.5x the still floor: not met as written, and cannot be:** the floor is 0.0, and camera motion alone gives 55-100 of 3+ blocks in every mode, mirrors included (scope 2). With the flicker's own class (9-35 blocks), the fix reads 0.0 in the hub sweeps and 5.4 in the level, against 42.6-53.1 before (`ground1`) and 52.7 copies off (`abl0`) |
| `scripts/deck/run.sh ui3 330 --window --user-from /home/deck/raiders/work/t17_user_seed -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh ui3` | `run ui3: stopped at the time limit`; `fetch: …/work/runs/ui3 (28 files)` | Met |
| `.venv/bin/python -I scripts/framelog.py work/runs/ui3/framelog --regions 60` | `6953 frames`; `regions from 60.0 s: 5109 eligible triplets`; HUD bottom left `44, 8.6 per 1,000`; counter `30, 5.9`; bottom centre `108, 21.1`; middle `41, 8.0`; `events of 36+ blocks from 60.0 s: 0`; world 1-2 58.5, 3-8 14.1, 9-35 3.1, 36-144 0.0 per 1,000 | **UI met:** 8.6 ≤ 2 × 21.1. **No 36+ event at the water warning or the wipe: met** (0 of any class; T17b's `ui2` had 1) |
| `grep -c "skips a frame by vk_draw.cpp line"` / `grep -ci "device lost"`, every run named | `0` / `0` in all 30 runs (`sw_*`, `fx*`, `ui3`) | Met |
| `.venv/bin/python -I -B tests/run_all.py` (`HOOKSHOT_VULKAN_HEADERS`/`HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`, `--jobs 4`) | `332 passed, 9 failed, 9 skipped in 823 s (linux, 4 at once)` | **Met:** the same 9 as T17b (8 FAIL plus the `test_program_cache_reader.py` TIMEOUT, all in `mac-test-baseline.md`); `test_as_submitted.py` passes with its new cases |
| UI stays fixed in `flick1` and `ui3` | `flick1`: HUD bottom left 22.5 ≤ 2 × 32.1; `ui3` above; the hub sweeps 11.4-16.9 against copies-off 348.2 | Met |
| User check (10 minutes, windowed, sound, hub, Blanch Seaway, back, gear menu, stick and gyro, Steam quit) | `flick1`, 265 s, windowed, with sound: hub, Blanch Seaway, back to the hub. Your words: "This is a very significant improvement. in this current state, i completely accept the way the game looks right now." | **Met by your acceptance.** Not checked one by one: the session was 265 s, not 10 minutes, and whether the gear menu and the gyro were used is **unknown**. The ground is visible in the hub after the level (screenshot at present 8400, by eye) |

## Your session (`flick1`, 2026-11-14)

The final build, the acceptance command, your play: hub, map, Blanch Seaway, back to the hub, closed at 265 s.

| Span | `flick1` (fix) | `ground1` (T17b, copies on) | `abl0` (T17b, copies off) |
|---|---|---|---|
| Level, 3+ blocks per 1,000 | **76.0** (108-200 s) | 229.6 (117-144 s), 178.7 (226-239 s) | 169.1 (120-160 s) |
| Level, 9-35 blocks per 1,000 | **5.4** | 53.1, 42.6 | 52.7 |
| Hub, 3+ blocks per 1,000 | 41.2 (45-78 s), 38.7 (232-265 s) | 43.7 (37-92 s) | 30.1 (37-100 s) |
| Hub, 9-35 blocks per 1,000 | **0.0**, 4.3 | 9.6 | 1.5 |

- The sessions are different plays at different game-work levels, so they agree in direction only.
- In the level, copies off (`abl0`) also read 52.7 of 9-35 blocks. Part of the level's large events are the game's own
  effects, or copies-off faults of their own (inferred; not calibrated, Deviations).
- `waits met 43693 (8219 on a CPU event, 8219 captures there)`.

## Deviations

- **The fix is in `gpu/vk/vk_replay.cpp`**, not in the task's files (`vk_draw.cpp`, `vk_memory.cpp`). The decision is in
  `as_submitted_policy.h` as the task asked. The cause turned out to be when a capture is taken, not what is copied.
  `vk_draw.cpp`, `vk_memory.cpp` and `vk_internal.h` are unchanged in the commit.
- **The task's candidate mechanism was wrong** (it was marked inferred, not tested): the late inputs of step (d) do not
  carry the flicker.
- **Step (d)'s inputs, and four more steps, were built, measured and reverted:**
  - the experiment switches `RX_VK_SB_BIG_MB`, `RX_VK_GPU_WRITTEN_AGE`, `RX_VK_VB_SNAPSHOT_MB`, `RX_VK_SB_MIXED_MB`;
  - a CPU-only write-age record;
  - reads as of their own submission (a per-page capture history);
  - inline updates written into the captures;
  - pages kept when their capture is given up;
  - the as-of and live-change diagnostics.

  None changed the flicker. They are in no commit, as T17a's dropped copies.
- **No scripted route into the level.**
  - The hub's spawn faces the robot that opens the map (verified, `ground1` and `gear5` screenshots by eye), so a
    steered route looks possible (inferred).
  - It was not attempted: the hub sweep reproduced the flicker (T17b's direction, 1.8x) and found the cause.
  - The level case is your session, with the fixed instructions above.
- **The calibration of the level's own effects** (radar, reticle, splashes) was not made: no level run.

## What is left

1. **A mirrors run in the level**, if the 1.25x-of-mirrors criterion is wanted there (only the hub has one).
2. **Mirrors without the fix.** Why `RX_VK_MIRROR=1` showed no stale frames is **unknown**. The policy leaves the capture
   off with mirrors. A discrete-GPU check belongs with the upstream PR.
3. **The parallel replay** (`RX_VK_PARALLEL`, off by default) takes no capture at a met wait. Its dry pass runs before
   the segments are recorded, so a capture there would reach draws before the wait too. **Unknown** whether it shows the
   flicker.
4. **`docs/development.md` rows** for `RX_VK_MET_CAPTURE`, with T17a's and T17b's switches, in the upstream PR (T25).
5. **A scripted level route** (map from the hub's robot), if a later task needs repeatable level runs.

## Upstream PR candidates (T25)

- **The capture at a met CPU-event wait** (`vk_replay.cpp`, `as_submitted_policy.h` `capture_at_met_wait`,
  `tests/test_as_submitted.py`): generic, with T17a's copies.
- **Not upstream:** `games/raiders/scripts/hub_sweep.txt` (Raiders' route).
