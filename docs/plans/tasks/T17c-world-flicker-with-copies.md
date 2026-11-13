# T17c · World flicker with T17a's copies as submitted

**Milestone:** M6 (rendering) · **Depends on:** T17b · **Machine:** Mac driving the Deck; the user at the Deck to play the
level case and for the final check

## Context
- **What is left after T17b** (`docs/plans/reports/T17b-missing-ground.md`, What is left, item 1):
  - T17b fixed the missing ground: draws left out for pools past the 8192th, 0 skips in `ground1`.
  - A world flicker remains while the camera moves (stick or gyro), worst in the level (Blanch Seaway):
    - 178.7-229.6 world events of 3+ blocks per 1,000 frames in `ground1`'s level spans;
    - 30-117 in the hub.
  - It shows no missing geometry: lighting or shading differs for one frame, or the 3D view jumps for one frame. Example:
    `ui2` frame 5547, 43 blocks, during a water-warning span, with the warning and the HUD intact.
- **T17a's copies take part in it** (inferred; T17b's A/B, `abl0` with `RX_VK_UB_SNAPSHOT=0 RX_VK_SB_SNAPSHOT=0`):
  - Copies off: world 30.1 against 43.7 per 1,000 in the hub, 169.1 against 229.6/178.7 in the level's first stretch.
  - The user saw "much less world/3D model/character flicker" with the copies off, in the hub and the level, and no
    jumping with the gyro. Some object flicker on a few objects remained in the hub.
  - The UI flicker came back with the copies off (HUD bottom left 23.3 → 321.5): the copies must stay for the 2D layer.
  - The two sessions were not the same play and ran at different game-work levels, so the numbers only agree in
    direction.
- **What the copies leave read late** (verified, `vk: a frame: as submitted:` lines in `ground1` and `ui2`):
  - every uniform buffer is copied: 2,350-4,626 a frame, 0 left in GPU-written memory;
  - 5-16 read-only storage buffers copied a frame;
  - 226-455 storage buffers a frame left in place on GPU-written pages, and 130-346 left in place because they are over
    4 MB;
  - vertex streams and index buffers are never copied.
- **A candidate mechanism** (inferred, T17b; not tested):
  - A draw's uniform buffers (the camera, object constants) come as they were at the submission.
  - Its other inputs (large or GPU-page storage buffers, vertex streams) are read from guest memory when the GPU gets
    there, after the game has written later frames' data.
  - While the camera moves, objects whose transforms or skinning come from late data and a camera from copied data
    disagree by a frame.
  - Two details may matter:
    - `memory_gpu_written`'s page bitmap (`gpu/vk/vk_memory.cpp`, `memory_stamp_gpu`) is never cleared. A page the GPU
      wrote once excludes every later CPU-written buffer on it from the copies.
    - The 4 MB storage limit.
- **A reference that reads everything as submitted:** `RX_VK_MIRROR=1`.
  - The pools' VRAM mirrors are synced at each submission's start.
  - T17a's `mir1` on the hub route: world calm, UI fixed.
  - But 768 MB of mirrors, 55.8 MB written back a frame, and 27.6 fps against ~40: not a fix on the Deck. It is the
    yardstick: if the level's world is calm with mirrors, the cause is partial as-submitted reads.
- **T17a's lesson** (`T17a-ui-rendering.md`, `gear3`): copying data the GPU writes gives stale data (a washed-out frame).
  Whatever is copied must not be GPU-written in the same frame's work.

## Read first
- `CLAUDE.md`.
- `docs/plans/reports/T17b-missing-ground.md`: the world measure, the A/B, What is left.
- `docs/plans/reports/T17a-ui-rendering.md`: the fix (step 5), the `mir1`/`ubs1` A/B, the reverted vertex-stream and
  index-buffer copies (`gear2`-`gear4`) and why they were dropped.
- `gpu/vk/as_submitted_policy.h`, its test `tests/test_as_submitted.py`.
- `gpu/vk/vk_draw.cpp`: `uniform_range`, `storage_as_submitted`, `as_submitted_count`; the vertex-stream and index-buffer
  bindings (`gpu_buffer_bind` callers).
- `gpu/vk/vk_memory.cpp`: `memory_stamp_gpu`, `memory_gpu_written`, `memory_read_as_submitted`, the captures
  (`take_capture`), `mirror_on`, `mirror_sync`.
- `docs/design.md` rule 2 (nothing the replay reads comes from live guest memory).
- `scripts/framelog.py` (`--regions`, `--span`).

## Scope
1. **A repeatable case in a level.**
   - Script the route from the hub into Blanch Seaway if it can be done: map, raid, then a camera sweep with the right
     stick, standing still (`HOS_INPUT_SCRIPT`, or steered with `HOS_INPUT_LIVE`; T17b's `ground1` reached the map at
     ~104 s and the level at ~117 s).
   - Otherwise a fixed set of instructions the user plays the same way each run, with the frame log on. Then compare
     only spans of the same activity.
   - Add a scripted camera sweep in the hub (the `gear_menu.txt` start, then RLEFT/RRIGHT presses) as the cheap
     repeatable case.
2. **Calibrate the measure.**
   - Count how much of a level span's world events are the game's own one-frame effects: the radar sweep, the reticle,
     splashes.
   - Use a span standing still with no input, plus by-eye checks of the largest events.
   - Report world numbers with that floor in mind.
3. **The A/B ladder, on the same case,** each run naming its switches:
   - (a) the default (T17a's copies);
   - (b) copies off;
   - (c) `RX_VK_MIRROR=1` (everything as submitted);
   - (d) and on: the copies plus each late input in turn:
     - storage buffers over 4 MB the CPU wrote lately;
     - storage buffers on pages the GPU wrote, but not in the frames before (a page bitmap that ages);
     - vertex streams the CPU wrote lately.

   Say which input closes the gap to (c), with its log line counts.
4. **The fix**, clearly located:
   - in `as_submitted_policy.h` (the decision) and `vk_draw.cpp` / `vk_memory.cpp` (the copies), marked `(raiders)`;
   - generic, as T17a's: an upstream PR candidate;
   - with the policy's cases in `tests/test_as_submitted.py`;
   - with its cost a frame (copies, MB) and the frame rate at the same game-work level, against the default.
5. **User check at the Deck:** a 10-minute windowed session with sound: hub, Blanch Seaway, back, the gear menu, with
   the stick and the gyro. Steam quit for the gyro.

## Non-goals
- Frame rate and the game-work level (T22), memory budgets (T20): mirrors are the yardstick, not the fix, unless their
  cost can be made Deck-sized within this task.
- The gear-menu lighting change (`BLOCKER-T17a-2026-11-13.md`), unless it turns out to be this cause.
- Draws left out (T17b), shader caches (T21), Ocarina-only code paths.

## Files to touch
- **`gpu/vk/as_submitted_policy.h`, `gpu/vk/vk_draw.cpp`, `gpu/vk/vk_memory.cpp`**, `gpu/vk/vk_internal.h` if an export is
  needed. Edits marked `(raiders)`.
- **`tests/test_as_submitted.py`**, and any test that cuts a changed function by text.
- **`games/raiders/scripts/`:** the level route and the hub camera sweep, if they can be scripted.
- **`scripts/framelog.py`:** only if the calibration needs a new output, with `tests/test_framelog_regions.py`.
- **`docs/plans/reports/T17c-world-flicker.md`.**

## Acceptance criteria
```bash
# the level case on the final build (scripted, or the user's session with the same switches)
scripts/deck/run.sh flick1 600 --window --sound --args "--user /home/deck/raiders/work/t17_user_play" -- \
  HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh flick1
.venv/bin/python -I scripts/framelog.py work/runs/flick1/framelog --regions 60 --span <level span> --span <hub span>
grep -c "skips a frame by vk_draw.cpp line" work/runs/flick1/hookshot_log.txt         # 0
grep -ci "device lost" work/runs/flick1/hookshot_log.txt                              # 0
# T17a's route
scripts/deck/run.sh ui3 330 --window --user-from /home/deck/raiders/work/t17_user_seed -- \
  HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 \
  RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh ui3
.venv/bin/python -I scripts/framelog.py work/runs/ui3/framelog --regions 60
.venv/bin/python -I -B tests/run_all.py
```
- **The world in the level case:**
  - with the fix, at most the copies-off run's events per 1,000 on the same spans, and within 1.25x of the mirrors run
    (c);
  - at most 1.5x the standing-still floor of step 2 while the camera sweeps.
- **The UI stays fixed:** HUD bottom left at most twice the higher control region, in `flick1` and `ui3`.
- **No 36+ block event at the water warning or the wipe** in `ui3`, of any class: T17b's `ui2` had one world-class event
  there.
- **No draw left out** (0 skip lines) and no device lost in every run named.
- **The test suite:** T17b's final run (`332 passed, 9 failed, 9 skipped`, the same 9 failures) plus any new tests
  passing.
- **User check:** no world, model or character flicker with the stick or the gyro in the hub or the level; the UI, ink,
  save and continue as in T17b; the ground still there after the gear menu.

## Report
`docs/plans/reports/T17c-world-flicker.md`:
- the case and the measure's floor;
- the A/B ladder with each run's switches and counts;
- the input that causes it, with the log lines;
- the fix, its cost and the counts before and after;
- what is left;
- the upstream PR candidates (T25).
