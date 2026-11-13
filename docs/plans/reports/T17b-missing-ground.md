# T17b · Draws left out after the gear menu: the missing ground and the world flicker   (2026-11-13)

**Short answer.**
- **The missing ground is fixed.**
  - **The cause:** the renderer read at most the host's first 8192 memory pools, and Raiders has more live:
    - `memory_sync` read the list into `list(8192)`, and `host->gpu_pools` writes at most the list's length.
    - Raiders keeps **~8,823 pools live in the hub** and **9,515 after a level**.
    - The pools past the 8192nd (the highest addresses, `0x7fff…` first) left the renderer's pool table while the game still
      drew from them.
    - A draw there works only while a per-thread lookup cache still holds its pool. From its first miss, `pool_lookup`
      finds no pool, and an indexed draw whose index buffer lies there is left out every frame (`check3`, from present 8880).
  - **None of the task's three candidates.** The table loses pools that are neither given back, made again over the same
    memory, nor refused an import (below).
  - **The fix** (`gpu/vk/vk_memory.cpp`, `read_pool_list`): when the host fills the list, it is asked again with a list twice
    as long, up to 1,048,576 pools. Both readers of the host's pools use it. Generic: an upstream PR candidate (T25).
- **Counts** (verified):

  | Run | Build | Table entries | Live pools that left the table | Skip lines |
  |---|---|---|---|---|
  | `check3` (T17a) | before | not logged | not logged | 26: from present 8880, 36-107 draws a frame at the index-buffer site |
  | `pool1` | before, diagnostics | 8192, stuck from present 3514 | **639** | 0 (hub only) |
  | `pool2` | the fix | 8,821 | **0** | 0 |
  | `ground1` | the fix | up to 9,515 live (host log) | **0** until present 6587, where the table log reached its cap | **0** (hub, a level twice, back, the gear menu) |

  You saw the ground stay visible after the gear menu in `ground1`, from boot and after the levels.
- **The world flicker.**
  - **The flicker that came with the missing ground is gone.** `check3` showed missing deck and black rectangles, at 324.3
    world events per 1,000 frames after 270 s. In `ground1`, the world after each gear menu is calmer than before it:
    66.7 → 15.4 and 117.4 → 41.1 per 1,000.
  - **A smaller world flicker remains, worst in the level** (178.7-229.6 per 1,000 in Blanch Seaway, while the camera
    moves).
  - **T17a's copies have a part in it** (inferred, from the A/B and your eye). With them off (`abl0`) the world read lower
    in both scenes (hub 30.1 against 43.7; the level's first stretch 169.1 against 229.6 and 178.7), and you saw "much less
    world, 3D model and character flicker" and no jumping with the gyro. The UI flicker came back, as expected.
  - Not fixed here: it is a design change to T17a's copies, not draws left out (What is left, item 1).
  - On T17a's scripted route (`ui2`), one 36+ block event of this world class falls in a water-warning span. The overlay
    is intact, but T17a's criterion "no 36+ block event at the water warning" is **not met by the letter** (Acceptance
    criteria). The HUD criterion holds.

Claims are **verified** (run, command, log line or file:line named) unless marked **inferred** or **unknown**. Runs are in
`work/runs/<name>/` (Mac) and `~/raiders/work/runs/<name>/` (Deck): game output, never committed. Your save stayed
`d9dfb4bb…` (checked before the runs). Every scripted run used a fresh copy of it (`--user-from …/t17_user_seed`); your
sessions used `--user /home/deck/raiders/work/t17_user_play`. 0 device losses in every run named here.

**Branch.** `task/T17b-missing-ground-and-world-flicker` was cut from T17a's tip (`184c480`), not from `main`, as you chose:
`main` holds neither T17a's copies nor this task's file.

## The case and the measure (scope 1-2)

**The case.**
- **Not scripted.** No route from the hub into a level exists, so you played it:
  - `ground1`, the acceptance command (below);
  - `abl0`, the A/B (step 5).
- **Two headless hub runs** for the diagnosis: `pool1` (before the fix) and `pool2` (after). Route: title → hub (ZL+ZR at
  30, 35, 40 s), then five gear-menu round trips (PLUS at 80, 100, 118, 136, 154 s; B 10-12 s after each), 200 s.
- **`ground1`'s timeline** (inferred, from its screenshots every 300 presents and its frame lines):

  | Time | What |
  |---|---|
  | 37-92 s | hub; gear menu ~69-71 s |
  | ~104 s | map |
  | 117-144 s | Blanch Seaway |
  | ~162 s | results |
  | 174-185 s | gear menu |
  | 202-217 s | hub |
  | 226-239 s | the level again |
  | ~255 s | results |
  | 261-467 s | hub, camera low over the deck (ground visible); gear menu ~296-300 s |

**The world measure: `scripts/framelog.py --regions <s>`** now also prints the world.
- **What counts.**
  - An event is a triplet's blocks that jump one way: the script's own rule (`jumps()`), each sign on its own, as in its
    event list.
  - Only blocks outside the HUD count (`WORLD_HUD`, T17a's scratch exclusion): rows 7-8 columns 0-4, row 8 columns 13-15,
    rows 0-1 columns 12-15.
- **What it prints.**
  - From `<s>`: events by size (1-2, 3-8, 9-35, 36+ blocks), per 1,000 eligible triplets.
  - Events of 3+ blocks per 30 s of the whole capture (`--world-bin`).
  - Per `--span A-B` (seconds after the first record): events of 3+ blocks per 1,000 eligible triplets.
- **Reproduces T17a's scratch figures exactly** on `check3` (verified):
  `world events of 3+ blocks per 30 s: 33 48 37 116 92 63 33 21 51 183 221 179 180 11 10`.
  - Counting a triplet once instead (either sign) gave lower early bins.
  - On `check3`: `world span 60-270 s: … 64.6 per 1,000`; `world span 270-390 s: … 324.3 per 1,000`.
- **`tests/test_framelog_regions.py`** (extended, synthetic captures only): the world mask, `--span` parsing, the counts by
  size, bin and span, the command's world lines, a bad span's error, and no world lines without `--regions`.

## The cause (scope 3)

**Diagnostics** (all off unless set; logging only):
- **`RX_VK_POOL_LOG=1`** (`gpu/vk/vk_memory.cpp`, `gpu/vk/vk_draw.cpp`):
  - each change of the renderer's pool table (`table -` / `table +`, with the entry count and nested entries);
  - each import made, refused, retired and given back, with the present;
  - for an indexed draw left out (`memory_explain_unbound`, the first 64, then 1 in 4096): the index buffer's address and
    size, the program key, the present, the table entries below and above it, how many entries hold it, any import over it,
    and the table and imports within 256 MB.
- **`HOS_POOL_LOG=1`** (`host/nvn_native.c`, `host/nvdrv.c`):
  - every `nvnMemoryPoolInitialize` / `nvnMemoryPoolFinalize` (range, flags, present);
  - every change those make to the GPU mappings that is not their own: an entry of another pool replaced or dropped, or a
    finalize that removes another pool's entry or none.

**What `pool1` showed** (verified, `work/runs/pool1/hookshot_log.txt`):
- The table rose to **`(8192 entries, 0 nested)`** at present 3514 and stayed there.
  - The game made 8,954 pools and finalized 133: **8,823 live** from present 3500.
  - Of the 767 `table -` lines, **639 were pools still live** (no finalize logged), the first at present 3514
    (`0x7fff969000`, `0x7fffa8d000`, …). 128 were real finalizes.
- **Ruled out** (verified):
  - **A given-back pool.** A retired import is always replaced by the import that took it in (`retire_pool` is only
    called from `pool_lookup` and `bg_drain`, after the new import is made). A lookup never misses for that reason.
  - **A refused import.** `check3` has 0 `not imported` lines. In `pool1`, `ground1` and `abl0` the pool log has 0
    `import … refused` lines.
  - **A pool made again over the same memory.** 0 `replaces`, `drops`, `removes another` or `no mapping starts` lines in
    `pool1`, `pool2`, `ground1` and `abl0`.
  - **Nested table entries.** `0 nested` in every table line of the four runs.
- **Why `pool1` itself left nothing out, and `check3` did from present 8880** (inferred). `gpu_buffer_bind` first tries a
  per-thread cache (`tl_pools`, by 64 KB page, cleared only when a pool leaves `imported`) and a bind memo. Only a miss in
  both reaches `pool_of` → `pool_lookup`, which checks the host's table first. A pool cut from the table keeps working until
  its slot is taken by another pool. After that, every lookup for it fails, and the draws stay left out: the onset in
  `check3` and its persistence.
- **Not observed:** a skip with the diagnostics on and the old build. `ground1` (with the fix) left nothing out, so the
  `memory_explain_unbound` line was never printed in a real case. The link from the cut pools to `check3`'s skips is
  **inferred**: the site (`gpu_buffer_bind` returns nothing only when `pool_lookup` does), the timing, and the cure.

## The fix (scope 4)

**`gpu/vk/vk_memory.cpp` (raiders):**
- **`read_pool_list(list, get)`** (line 581).
  - It asks for the pools with the list's length; while the host fills it, it doubles the list and asks again, up to
    `kPoolListMax` (2^20).
  - It returns the count, never below 0.
- **`host_pool_list(list)`** wraps it with `host->gpu_pools` and logs its first growths:
  `vk: 8196 pools: the list of the host's pools grown to 16384`.
- **Both readers use it:**
  - `memory_sync` (the renderer's pool table);
  - `refresh_pool_ranges_locked` (the capture's pool ranges, with `RX_VK_CAPTURE_POOL_MB`).
- **No extra call in the common case:** one call while the host has fewer pools than the list holds.
- The skip site is unchanged except for the diagnostic call. The indexed draw's `SKIP_HERE()` is now `vk_draw.cpp:6527`
  (it was 6525).

**Tests:**
- **`tests/test_pool_list_all.py`** (new). It cuts `read_pool_list` by text and drives it with a host of 0, 1, 8191, 8192,
  8193, 8823, 20000 and 70000 pools, checking each count and the last (highest) entry. It also checks:
  - an empty list starts at 8192;
  - a host that always fills the list stops at 2^20;
  - a negative answer gives 0;
  - by text, that `host->gpu_pools` is called only in `host_pool_list` and that both readers go through it.
- **`nx2/test_import_windows.py`.** It compiles a cut of `pool_lookup`, which now names the pool log. Its fixture gained
  one stub line (the log off). Upstream's checks are unchanged.

**Upstream PR candidate (T25): yes, generic.** Any game with more than 8192 live memory pools loses pools from the table
the same way. How many pools Ocarina keeps live is **unknown**. The PR: `read_pool_list` with its test.

## The world flicker after the fix (scope 5)

**Before and after the gear menu, `ground1`** (verified, `--span`). This criterion is met:

| Scene | Before the menu | After it |
|---|---|---|
| Hub, first visit (menu ~70 s) | 37-68 s: **66.7** per 1,000 | 74-92 s: **15.4** |
| Hub after the levels (menu ~298 s) | 262-293 s: **117.4** | 302-392 s: **41.1** |

`ground1` from 60 s: 3 events of 36+ blocks (263.6, 268.0, 305.0 s); world by size 1-2 98.8, 3-8 45.6, 9-35 11.3, 36+ 0.2
per 1,000. Per 30 s: `0 122 32 22 218 58 26 98 82 33 29 0 50 0 0 2`.

**The level A/B of T17a's copies** (`abl0`: the same switches as `ground1` plus `RX_VK_UB_SNAPSHOT=0 RX_VK_SB_SNAPSHOT=0`,
hub → Blanch Seaway, 246 s):

| Measure | Copies on (`ground1`) | Copies off (`abl0`) |
|---|---|---|
| HUD bottom left, from 60 s | 23.3 per 1,000 | **321.5** (the UI class back) |
| World, hub before the level | 37-92 s: 43.7 | 37-100 s: **30.1** |
| World, the level's first stretch | 117-144 s: 229.6; 226-239 s: 178.7 | 120-160 s: **169.1** |
| Your view | world flicker while the camera moves, also with the gyro | "much less world/3D model/character flicker", in the hub and the level; no jumping with the gyro; "some object flicker on a few objects" when moving the camera in the hub |

- **The copies take part in the remaining world flicker** (inferred). Your view is clear-cut; the measure agrees in
  direction but by only 1.1-1.45x, and the two sessions were not the same play.
  - The measure also counts the game's own one-frame effects (the radar sweep, the reticle, splashes): verified by eye on
    `ground1`'s largest level events.
  - Those frames show no missing geometry, only lighting or shading different for one frame while the camera turns.
  - The two sessions also ran at different game-work levels: `abl0`'s hub at ~2,070 uniform updates a frame and 19-24 fps,
    its level at ~1,140 and 45 fps; `ground1`'s level at ~770-1,250 and 32-41 fps. Rates per 1,000 frames are not
    normalised for that.
- **A candidate mechanism** (inferred, not tested). With the copies on, a draw's uniform buffers and lately written
  read-only storage buffers come as submitted. Its other inputs are still read from guest memory when the GPU gets there:
  - uniform buffers on any page the GPU ever wrote (`memory_gpu_written`'s bitmap is never cleared);
  - storage buffers over 4 MB, on GPU-written pages, or not read-only;
  - vertex streams.

  During camera motion, objects that take their transforms from the late data and a camera from the copied data could
  disagree by a frame. With the copies off, all of it is late together: the world agrees with itself, and the 2D layer
  breaks instead.

## Acceptance criteria

| Command or criterion | Output | Met? |
|---|---|---|
| `scripts/deck/run.sh ground1 900 --window --sound --args "--user /home/deck/raiders/work/t17_user_play" -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_FRAMELOG=framelog RX_VK_POOL_LOG=1 HOS_POOL_LOG=1 && scripts/deck/fetch.sh ground1` (the task's switches plus the two pool logs) | `run ground1: exited with 0` (you closed the game at ~467 s); `fetch: …/work/runs/ground1` | Met |
| `grep -c "skips a frame by vk_draw.cpp line" work/runs/ground1/hookshot_log.txt` | `0` | **Met:** no draw left out at any site, the index-buffer site included |
| `grep -ci "device lost" work/runs/ground1/hookshot_log.txt` | `0` | Met |
| `.venv/bin/python -I scripts/framelog.py work/runs/ground1/framelog --regions 60` | `14121 frames`; `regions from 60.0 s: 11394 eligible triplets`; HUD bottom left `266, 23.3 per 1,000`; counter `246, 21.6`; bottom centre `170, 14.9`; middle `243, 21.3`; `events of 36+ blocks from 60.0 s: 3`; world lines above | Ran |
| No draw left out for an index buffer in no pool across the case (hub, a level, back, 5+ gear-menu round trips) | 0 skip lines; 0 `indexed draw left out` lines; 0 live pools dropped | **Met.** Five or more round trips: by your account, not counted from the log (no input logging) |
| World after the gear menu within 1.5x of before, same scene | 15.4 against 66.7; 41.1 against 117.4 | **Met** |
| T17a's criteria on its route (`ui1`'s command, run as `ui2` on this build: `area1_loop.txt`, 330 s, windowed, fresh save) | `7122 frames`; from 60 s, `5212 eligible triplets`: HUD bottom left `39, 7.5 per 1,000`; counter `30, 5.8`; bottom centre `134, 25.7`; middle `56, 10.7`; `events of 36+ blocks from 60.0 s: 1`: `large frame 5547 (game) darker 43 blocks` at 240.30 s; 0 skip lines, 0 device losses | **HUD: met** (7.5 ≤ 2 × 25.7). **36+ events: not met by the letter.** The one event falls in a water-warning span, but by eye on its triplet the warning's border and the HUD are intact in all three frames; the 3D view jumps for one frame (the deck higher, water below). That is the world class (What is left, item 1), not T17a's overlay class. `ui1` had 0 |
| `.venv/bin/python -I -B tests/run_all.py` (header paths set, `--jobs 4`) | `332 passed, 9 failed, 9 skipped in 785 s` | **Met:** the same 9 failures as T17a (8 FAIL plus the `test_program_cache_reader.py` TIMEOUT); 332 = T17a's 331 + `test_pool_list_all.py` |
| User check | Ground visible after the menu; UI, ink, save and continue fine; **world flicker in normal play remains**, most in the level and while the camera moves | **Partly met:** the ground is fixed; "no world flicker in normal play" is **not** met (scope 5, What is left, item 1) |

**The test suite.** The first full run on this branch gave `331 passed, 10 failed`. The tenth was `nx2/test_import_windows.py`,
broken by the pool log in `pool_lookup`, and fixed in its fixture (above). The final run is the one in the table.

## Deviations

- **Branch base:** T17a's tip, not `main` (your choice, above).
- **`host/nvdrv.c`** is not in the task's files. You allowed it for a fix in the host's pool table. The diagnostics found
  no case for one, so it gained only the `HOS_POOL_LOG` logging (`pool_log_effect`); `hos_gpu_pools` is unchanged.
- **`nx2/test_import_windows.py`:** one stub line, to compile the new log lines in its cut of `pool_lookup`.
- **No scripted route into a level** (`games/raiders/scripts/` unchanged). You played `ground1` and `abl0`.
- **The pool logs were on in `ground1` and `abl0`** beyond the task's switches. They only log:
  - 0 lines from the draw-skip diagnostic;
  - the renderer's table and import lines: 13,435 in `abl0`; in `ground1` its 20,000-line cap, reached at present 6587
    (~148 s, the end of the first level visit);
  - the host's initialize/finalize lines (34,607 in `ground1`, under their 50,000 cap).
- **`ground1` past present 6587.** The renderer's table is no longer logged there. The host's log covers the whole run:
  - the game had more than 8192 pools live from present 3093 to the end (9,515 at most, at present 4862; 9,321 at the
    end);
  - 0 draws left out over the whole run.

  So the table held every pool after 6587 too: **inferred** from the fix (it reads until the host's list is not full)
  and the 0 skips.

## What is left

1. **The remaining world flicker with T17a's copies on** (a follow-up task: it is T17a's design, not draws left out).
   - Next: an A/B that copies the other inputs as submitted too, in a level with the gyro:
     - uniform buffers on GPU-written pages, deciding per frame rather than from a never-cleared bitmap;
     - vertex streams and storage buffers the CPU wrote lately.
   - Or narrow the copies to the 2D layer's programs.
   - Measure with `--span` on the same level, with the same play or a scripted camera sweep.
2. **A latent fault in the host's pool table, not seen in Raiders** (`host/nvdrv.c`).
   - `hos_gpu_pools` reports the GPU mappings, which are keyed by start. A pool made where a live pool starts replaces that
     pool's entry, and the first pool's finalize then removes the entry the second still needs.
   - Upstream already counts pools by range for its change tracking (`tracked`, `nvdrv.c`, the comment above
     `hos_gpu_track`), but not for this list.
   - `HOS_POOL_LOG` reports such a case. 0 in four Raiders runs, so not changed here. An upstream note or PR candidate if a
     game shows it.
3. **The slow game-work level** in the hub after a level (~2,200 uniform updates a frame, 20-22 fps in `ground1`): T22,
   unchanged.
4. **`docs/development.md` rows** for `RX_VK_POOL_LOG` and `HOS_POOL_LOG`, with T17a's two switches, in the upstream PR
   (T25).

## Upstream PR candidates (T25)

- **`read_pool_list`** (`gpu/vk/vk_memory.cpp`) with `tests/test_pool_list_all.py`: generic, one fix.
- **The pool-table diagnostics** (`RX_VK_POOL_LOG`, `HOS_POOL_LOG`): optional, with the fix or on their own.
- **Item 2's start-keyed table**, if confirmed in a game: report `tracked` ranges from `hos_gpu_pools`.
- **Not upstream:** the world measure's HUD regions are Raiders'.
