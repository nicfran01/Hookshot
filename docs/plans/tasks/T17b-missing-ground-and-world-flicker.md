# T17b · Draws left out after the gear menu: the missing ground and the world flicker

**Milestone:** M6 (rendering) · **Depends on:** T17a · **Machine:** Mac driving the Deck; the user at the Deck to
reproduce and for the final check

## Context
- **The ground goes missing after the gear menu.**
  - In T17a's user check (`check3`, 2026-11-13), the user left the gear menu in the hub, after a level, and the ground
    under the player was gone.
  - T13 saw the same once (`M4-first-frame.md`, item 12: "the floor went invisible under you").
- **It is draws left out, not lighting** (verified, `work/runs/check3/hookshot_log.txt`):
  - from present 8880 (271 s into the capture), every 120-present frame line reads `skips a frame by vk_draw.cpp line:
    6525:` with 36-107 draws a frame, where it read `(0 skipped)` before;
  - line 6525 (at commit `a4d4b73`) is the indexed draw's `ib = gpu_buffer_bind(d.ibuf, …); if (!ib) SKIP_HERE();`: the
    index buffer lies in no imported pool;
  - just before, the import summary changed to `imports: 48 live (2000 MB), 0 retired still imported (0 MB), 2 retired
    given back (112 MB)`.
- **The world flicker the user saw comes with that state** (verified, the capture's one-frame events outside the HUD
  blocks, 3+ blocks, per 30 s):
  - 33-116 per 30 s until 270 s, then 183, 221, 179, 180;
  - frames 8930 and 11032 show the deck missing and black rectangles where geometry should be.
- **What is not known.**
  - Which of these happened:
    - a pool the game still draws from was given back;
    - the game finalized a pool and made a new one over the same memory that was never imported;
    - the import was refused (inferred candidates; 2,000 MB were imported at the time).
  - Whether any world flicker before 270 s, in the level, is new with T17a's copies as submitted. There is no
    comparison run in a level: T17a measured only the hub route, where its copies cut world events 336 → 53 per 1,000.
- **Not this task:**
  - the slow motion back in the hub, T17's game-work level (~2,200 uniform updates a frame, 18-22 fps; T22);
  - the gear-menu lighting change (`BLOCKER-T17a-2026-11-13.md`), unless it turns out to be this cause.

## Read first
- `CLAUDE.md`.
- `docs/plans/reports/T17a-ui-rendering.md`: step 6 (`check3`), What is left. Also T17a's copies as submitted
  (`gpu/vk/as_submitted_policy.h`), so a fix here does not undo them.
- `docs/plans/reports/BLOCKER-T17a-2026-11-13.md`.
- `docs/plans/reports/M4-first-frame.md`, item 12.
- `gpu/vk/vk_memory.cpp`:
  - the pool imports: `pool_lookup`, `pool_of`, `memory_pool_created`, the background imports (`bg_main`);
  - the retire and give-back policy, and where the `imports: … live … retired given back` line is logged;
  - `gpu_buffer_bind`.
- `docs/texel-buffer-ownership.md` (upstream's notes on import replacement and give-back under memory pressure).
- `host/nvn_native.c`: `nvnMemoryPoolInitialize` / `nvnMemoryPoolFinalize`, and what they tell the renderer.
- `scripts/framelog.py` (`--regions`) and `docs/development.md` "Pictures and frames".

## Scope
1. **A repeatable case.**
   - Hub → a level → back to the hub → gear menu (PLUS, then B) several times.
   - Script it if the route to a level can be scripted (`HOS_INPUT_SCRIPT`, or steered with `HOS_INPUT_LIVE`).
   - Otherwise the user plays it with the logging below on, as in T17a's `check3`, on
     `--args "--user /home/deck/raiders/work/t17_user_play"`.
2. **A measure for the world.**
   - Add to `scripts/framelog.py` a count of one-frame events outside the HUD regions, by size and per 30 s (or per 1,000
     frames from a start time), with its test.
   - T17a's scratch version excluded rows 7-8 columns 0-4, row 8 columns 13-15 and rows 0-1 columns 12-15.
3. **The cause.**
   - Log, under a switch, each skipped indexed draw: index-buffer address and size, program key, present.
   - Log the pool table around it: live imports' ranges, imports retired and given back (range, when, why).
   - Log the game's pool initialize and finalize calls (range, present).
   - From that, say which case it is (Context), with the log lines.
4. **The fix,** clearly located:
   - marked `(raiders)`;
   - generic where it is not Raiders-specific (an upstream PR candidate for T25);
   - with a game-free test in `tests/` (the import and retire bookkeeping can be driven without a GPU, as
     `tests/test_texel_buffer_ownership.py` does).
5. **The world flicker after the fix.**
   - Re-measure on the same case.
   - In a level, A/B T17a's copies (`RX_VK_UB_SNAPSHOT=0 RX_VK_SB_SNAPSHOT=0` against the default) to settle whether
     any remaining world flicker is theirs.
6. **User check at the Deck:** a 10-minute windowed session with sound (hub, a level, back, the gear menu several times),
   Steam quit if the gyro is needed.

## Non-goals
- Frame rate and the game-work level (T22), memory budgets (T20) beyond what the fix needs, shader caches (T21).
- The gear-menu lighting change (`BLOCKER-T17a-2026-11-13.md`), unless it is this cause.
- The gameplay hang in `cffdbb02c4dfbd39` (T13's problem 7).
- Ocarina-only code paths.

## Files to touch
- **`gpu/vk/vk_memory.cpp`, `gpu/vk/vk_draw.cpp`** (the skip diagnostics and the fix), `gpu/vk/vk_internal.h` if an
  export is needed. Edits marked `(raiders)`; a game-free test for each fix.
- **`host/nvn_native.c`:** logging of pool initialize and finalize under a switch, if the renderer's side is not enough.
- **`scripts/framelog.py`:** the world measure, with `tests/test_framelog_regions.py` extended (or a new test).
- **`games/raiders/scripts/`:** a route to a level and back, if one can be scripted.
- **`docs/plans/reports/T17b-missing-ground.md`.**

## Acceptance criteria
```bash
# the repeatable case (scripted, or the user's session with the same switches)
scripts/deck/run.sh ground1 900 --window --sound --args "--user /home/deck/raiders/work/t17_user_play" -- \
  HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAMELOG=framelog && scripts/deck/fetch.sh ground1
grep -c "skips a frame by vk_draw.cpp line" work/runs/ground1/hookshot_log.txt        # 0 for the index-buffer site
grep -ci "device lost" work/runs/ground1/hookshot_log.txt                             # 0
.venv/bin/python -I scripts/framelog.py work/runs/ground1/framelog --regions 60       # plus the new world measure
.venv/bin/python -I -B tests/run_all.py
```
- **No draw is left out for an index buffer in no pool** across the case: the hub, a level, back and at least five gear-menu
  round trips. Name any other skip line that remains and its cause.
- **The world measure after the gear menu is within 1.5x of before it,** in the same scene.
- **T17a's criteria still hold** on its route (`ui1`'s command): HUD bottom left at most twice the higher control region,
  no 36+ block event at the water warning or the wipe.
- **The test suite:** the same 9 failures as T17a's final run (`331 passed` with header paths set), plus the new tests
  passing.
- **User check:** the ground stays visible after the gear menu, no world flicker in normal play, and nothing that worked in
  T17a broken (UI, ink, save and continue).

## Report
`docs/plans/reports/T17b-missing-ground.md`:
- the case and the measure;
- the cause, with the log lines;
- the fix and the counts before and after;
- the level A/B of T17a's copies;
- what is left;
- the upstream PR candidates (T25).
