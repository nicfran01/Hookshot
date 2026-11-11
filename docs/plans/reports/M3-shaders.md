# M3 · Shader translation on the Deck: pass rate, failure classes, time (T12, 2026-11-11)

**Short answer.** Raiders' shaders translate almost completely on the Deck. **21,648 of the census's 22,042 programs**
were prepared in **77 s at 533 MB**, about 98 % of the programs. The remaining 394 programs, all in the `Sample`
archive, had to be left out (below).

| Result | Count |
|---|---|
| Stages that did not lower | 1 |
| Programs that did not translate | 20 neural networks, left out by design on a GPU without cooperative matrices |
| Driver failures | 0, for 3,015 compute pipelines and 75,650 graphics stage libraries |
| GPU timeouts | 0 |
| Warm second start | about 1 s |

**What was left out.** The full census cannot be prepared on the Deck. **394 programs in the `Sample` archive** have
100 KB to 997 KB of code each. Four of them in flight take 11-13 GB, and SteamOS's `earlyoom` killed every full run
(`BLOCKER-T12-2026-11-11.md`). By your choice (option 1 there), this report measures the census without those 394
programs and treats them as one failure class of their own. A 180 s play run to the menu drew none of them.

**What the census misses.** The game built **11 programs the census does not have** (20 stages). Most come from the
UI `Layout` archives, which the census does not walk.

**Effect on M4.** Nothing here blocks M4.

Claims are **verified** (command, file:line or log line named) unless marked **inferred** or **unknown**. Logs and dumps
stay on the Deck under `~/raiders/work/`, and `work/runs/shaders1/` is on the Mac. Program and stage keys are listed;
no shader code, instruction words or game text.

## Setup

| | |
|---|---|
| Build | The T11 build of the standalone game, `~/raiders/work/sa/build/hookshot` (07:46), renderer `hookshot_vk.so`. The renderer sources are the same as on `main` |
| Device | `AMD Custom GPU 0405 (RADV VANGOGH), Vulkan 1.4, driver 0x6801063`; mesh shaders yes, pipeline libraries yes, matrix multiplies in software (no cooperative matrices) |
| System | SteamOS 3.9.5 (build 20261023.100), kernel 7.2.7-valve2, glibc 2.43; 14.8 GB RAM, 8.4 GB swap (zram + file) |
| Workers | 4 (`hardware_concurrency()/2`, `vk_draw.cpp:7350`). There is no switch, and `taskset` has no effect (blocker §3) |
| Cold start | Before `shaders1`: the program and pipeline caches beside the executable moved aside, and the Mesa cache pointed at an empty folder (`MESA_SHADER_CACHE_DIR=~/raiders/work/t12_mesa_cache`) |

**Census, verified by `~/raiders/work/t12_census.log`:** `nx2/shader_census.py` in the container, 22,042 programs from
26,960 stages, 239 MB, 4.9 s.

**Filtered census:** `scripts/census_filter.py --max-kb 100` (new, with `tests/test_census_filter.py`) kept **21,648
programs and 26,595 stages**. It left out 394 programs (234 vertex+fragment, 160 vertex+fragment+geometry) and the 365
stages only they use. That copy was put beside the executable as `hookshot_shaders.bin`.

The tool's renderer keys (`--keys`) match the renderer's `code_key`: the 3 failing large-program stage keys the killed
runs logged are all in its list (verified).

## Runs

| Run | What | Wall time | Peak RSS | Result |
|---|---|---|---|---|
| `shaders1` | cold `--prepare-shaders`, filtered census | **77.0 s** (`prepared … in 77.0 s`; 08:21:48-08:23:06 with start-up) | **532,976 kB** | `@@done shaders`, exit 0 |
| `shaders2` | the same again, caches warm | **≈ 1 s** (08:23:56-08:23:57) | 254,112 kB | nothing translated: the program cache read (38,102 keys), 3,015 compute pipelines from the pipeline cache in 235 ms |
| `shaders3` | the same, `RX_VK_GPL=1`: the driver's stage libraries for every kept program | 162.5 s (`warmed … in 162.5 s`); whole run 08:24:10-08:26:53 | 373,808 kB | exit 0, 0 driver faults |
| `seed1` | 180 s play run, `RX_VK_PRECOMPILE=1 RX_VK_SEED_CHECK=1 HOS_NO_MOVIES=1` | 180 s (time limit) | not measured (section 7) | 10,726 frames presented, 60 fps at the end, no crash |
| `seed2` | 60 s, the same with `RX_VK_DUMP_STAGES` | 60 s | not measured | 44 stages dumped, used to find where the missed stages come from |

On-disk sizes after these runs:

| File | Size |
|---|---|
| `hookshot_programs.bin` | **2,828,784,997 bytes** (2.76 GB) |
| `hookshot_programs.idx` | 816,816 bytes |
| `mkw_vk_pipelines.bin` | 1.6 MB, and 98 MB with the stage libraries |
| Mesa cache | 19 MB, and 287 MB after `shaders3` |

**Why `shaders3` exists.** Graphics stage libraries are opt-in upstream (`RX_VK_GPL`, `vk_draw.cpp:1506`: "off until the
driver step is safe"). So a default preparation builds no graphics pipeline in the driver; they are built in play from
the pipeline-state notes (T21). `shaders3` measures the driver step anyway.

## 1. Totals and pass rates per step (filtered census)

| Step | In | Passed | Failed | Rate | Source |
|---|---|---|---|---|---|
| Lower (Ampere → Maxwell), stages | 26,595 | 26,594 | **1** | 99.996 % | 1 `does not lower` line; the log cap of 400 was not reached (`vk_shader.cpp:271`); 1 file in `lowfail/` |
| Translate (IR → SPIR-V), programs | 21,648 | 21,627 | 21 | 99.90 % | `prepared 21648 shader programs (38102 new, 21 failed, …)` |
| (the same, networks left out by design) | 21,628 | 21,627 | 1 | 99.995 % | the 20 networks below are not a translation failure |
| Compute pipelines in the driver | 3,015 | 3,015 | 0 | 100 % | `3015 compute pipelines; 3015 compute variants` |
| Graphics stage libraries in the driver (`RX_VK_GPL=1`) | 37,825 variants × 2 | 75,650 | 0 | 100 % | `warmed 75650 stage libraries of 37825 kept shader program variants`; 0 `driver faulted` lines |

How the 21 failures split (**verified** by arithmetic on the log lines):

- 21,648 programs = 21,350 graphics + 298 compute.
- 38,102 kept = 37,825 graphics variants (`shaders3`'s count) + 277 compute programs.
- 298 − 277 = 21 = 20 networks + 1 compute program that does not lower.
- **Every graphics program translated.** The log cap of 30 "not translated" lines was not reached (20 lines, all networks).

Over the **whole** census (22,042 programs), the 394 left out are unmeasured. Before their kills, the full runs logged 3
lowering failures among them (below); how many more they hold is **unknown**.

## 2. Failure classes

| # | Class | Count | Stage kind | Opcode / message | Archive | Instruction (Mesa NAK `sm70_encode.rs` @ `9b0a38c`, and the lowering) |
|---|---|---|---|---|---|---|
| 1 | **Large programs** | **394 programs** | 234 vertex+fragment, 160 +geometry | not a failure message: each takes ~25 s and several GB to translate; 4 at once are killed by `earlyoom` | `Sample` (all 394; no other archive has a program over 66 KB) | n/a |
| 2 | Networks left out | 20 programs | compute | `a network left out on this card` (`vk_shader.cpp:1569`) | the networks (NDSR); which archive per key was not looked up | n/a: by design, no cooperative matrices on RADV |
| 3 | IMAD, constant-buffer addend | 1 stage (filtered); 1 more in class 1 | compute (`048439bbb2371e35`, Sample program 4704); fragment (`20a0a678e82aff5a`, class 1) | `native multiply wide addend mode (op 0x624)` | Sample | **IMAD**: NAK `OpIMad` uses base 0x024 (`:1751-1771`) with form 3 in bits 9-11 (`:674`), which is src2 from a constant buffer (`:665-669`). The lowering takes 0x424/0x624 only as "IMAD.MOV.U32" or a plain low multiply (`lower_to_maxwell.h:863-878`) |
| 4 | CALL linkage | 2 stages, both in class 1 | fragment (`c6161150ded1ceb6`, `1d1e403c35ffbc9c`) | `native call linkage mode (op 0x944)` | Sample | **CALL (relative)**: NAK encodes no CALL (its control-flow neighbours are BSYNC 0x941, BREAK 0x942, BSSY 0x945, BRA 0x947, EXIT 0x94d). The lowering decodes 0x944 as a relative call and refuses a link register set up other than the way it knows (`lower_to_maxwell.h:3355-3363`). This is the class Hookshot's own game still has (`docs/design.md` §9) |

There is no fifth class.

- **Classes 3 and 4, offline:** `nx2/lower_test.py ~/raiders/work/lowfail_all 0` in the container (`EMSDK=~/raiders/deps/emsdk`)
  printed "4 programs, 0 lower, 4 fail; 2 native call linkage mode (op 0x944); 2 native multiply wide addend mode (op 0x624)".
  This is the same as the run's log. `lowfail_all` holds the filtered run's dump plus the 3 from the killed full runs.
- **Large programs, measured:** `f1936ba0dc85d369` took 23.8-24.3 s, and `85f16f6a706a99e9` (part 1) took 27.8 s.
  During `shaders1m` the resident set grew from 0.4 to 11 GB in 35 s with the 4 workers in that block. Where the memory
  goes inside the recompiler is **unknown** (blocker §2).

## 3. Task and mesh stages

- **Task stages:** none (census; verified in `02-gap-analysis.md` §6).
- **Mesh:** one program, fragment+mesh, translated in the preparation ("mesh program a393e5bb1df886f9, NVN stage 7: 1
  storage buffers"). It is the program's key, not a stage key.
- RADV's task/mesh programs are built without the driver's optimizer by default on AMD ("task and mesh programs built
  without the driver's optimizer (AMD; RX_VK_MESH_OPT=1: with it)").
- The Deck's known task-shader hang (`04-steam-deck.md` §1) cannot occur: there is no task stage.

## 4. Dropped geometry stages

- **160 programs have a geometry stage**, all in `Sample`, and **all 160 are among the 394 large programs** (the filter's
  stage kinds: `0+1+2: 160`).
- The preparation never builds a geometry stage: `seed_translate` uses stages 0 and 1 only (`vk_shader.cpp:2503-2545`).
  So "dropped stages" can only show in play (`program_pick`, `vk_shader.cpp:2171`).
- In `seed1`, 180 s to the menu: **0 "dropped stages" lines**.
- So the geometry question (T14) and the large-program question are the same programs. Whether gameplay draws them is
  **unknown** (the run stopped at the menu).

## 5. The census against what the game creates (`seed1`, 180 s)

- **11 graphics programs were translated in play**, all in the first ~25 s of the boot (log lines 1401-7398).
- **None of their 20 stages is in the census** (no `+` in any `vk: in play:` line).
- **None is one of the 394 left out** (checked against the 365 left-out renderer keys).
- **No compute or mesh program was translated in play.**
- There were no lowering or translation failures in play.

Where the 20 stages are, by searching romfs files (one level of zstd, then nested zstd frames) for 128-byte or 96-byte
pieces of each stage's code from the `RX_VK_DUMP_STAGES` dump (`~/raiders/work/t12_probe/find_stages*.py`; paths and
keys only):

| Found in | Stages | Keys |
|---|---|---|
| `Layout/*.Nin_Ounce_NVN2.blarc.zs` (UI layouts), code from +0x80 | 8 | `060cad753e25a1c9` `1026b193aa3b18e6` `193f4950a9b80890` `1f39463f89d8bb35` `5c15c6a6f94d6d8f` `b7c081f363c10a4f` `e8b01166031624a8` `eedca169c3bbbadd` (each in 23-169 layout files) |
| the same, but only from +0x400: the first bytes in memory differ from the file's | 2 | `ca94d4e48cedb9f3` `ff6f6525c000e8c1` (213 files each) |
| `Lib/sead/primitive_renderer/primitive_drawer_nvn2_shader.bin` (also in the agl and Sample archives) | 1 | `a84cb47cd9e13867` |
| `Lib/agl/agl_resource…{debug,release}.sarc.zs` | 1 | `fa5a3dbc2dbaaa81` |
| not found in any romfs file | 8 | `01f357deb5376ed2` `3c732f8da740e661` `3ceaa32a8482811f` `672a21e7a9507552` `843cabd3ed54dd81` `b90da3d934b08717` `ccd977d058a301a7` `d675bf6c4d0704c6` |

**Archive kinds the census misses:**

1. **`Layout/*.blarc.zs`:** the census walks `Shader`, `Layout2Shader`, `Lib`, `Movie` and `Effect`
   (`nx2/shader_census.py:218`); Raiders' layouts are in `Layout/`, which it does not walk. This is the main source.
2. **`Lib/sead/primitive_renderer/primitive_drawer_nvn2_shader.bin`:** a standalone shader file. `Lib/` is walked, but
   this file kind is not one the census reads (**inferred**: no stage of it is in the census).
3. **The `release` agl and gsys archives:** the census reads them but gets **0 programs** from each (census log), while it
   gets 5,167 and 51 from the `debug` ones. Two missed stages are in agl and sead files whose code the census holds
   under other keys. So the census likely takes the debug archives' control sections where the game uses the release
   ones (**inferred**).

The 10 stages whose bytes differ at the start, or are not found at all, are **inferred** to be changed or put together
by the game when it loads them. Their origin is **unknown**.

This is a lower bound: 180 s reaches the title menu, not gameplay.

## 6. Times and memory

| | Value |
|---|---|
| Census | 4.9 s, 734 MB |
| Cold preparation, filtered census, 4 workers | **77.0 s**, **533 MB** peak. Compute programs first (298, with 3,015 texture variants), then 21,350 graphics programs × 3 attribute variants |
| Warm start of the same | **≈ 1 s**, 254 MB |
| Driver stage libraries for every graphics variant (opt-in) | 162.5 s, 374 MB; the Mesa cache grows to 287 MB |
| The 394 large programs | not prepared: killed at 7.5-13.2 GB after 74-108 s (blocker §2) |

The plan's expectation of "tens of minutes" (`04-steam-deck.md` §3) was **wrong for the filtered census**: 77 s.

**Resumability:**

- The preparation is resumable: `hookshot_prepared.bin` records what it was made for.
- The driver's part is keyed on `pipelineCacheUUID`, vendor, device and driver version (`warmed_stamp`, `vk_draw.cpp:7096`).
- `shaders3` showed a change of settings redoing only the driver's part ("the shaders are prepared, but their driver's
  part was made for another driver or other settings: made again").
- After a Mesa update, only that part is made again (**verified** by reading; not run with a real driver update).

## 7. Notes

- **Peak RSS of time-limited runs.** `run.sh` records the peak resident set through `getrusage(RUSAGE_CHILDREN)`.
  `timeout` does not reap a game it kills at the time limit, so that figure leaves the game out: `seed1` gave 11 MB.
  `run.sh` now drops the figure for such runs and says so.
- **The program cache is 2.76 GB on disk** for 38,102 records. It is not read in whole at the start (254 MB resident in
  `shaders2`), but its size matters for T20 (disk and memory) and T24 (packaging) (**inferred**).
- **GPU:** `journalctl -k -b | grep -cE "gfx_|amdgpu.*timeout"` = **4**. All 4 date from before T12 and none is a
  timeout: "ring gfx_0.0.0/gfx_0.1.0 uses VM inv eng …" ×2 at boot (2026-11-10 15:39) and ×2 at the S3 resume
  (2026-11-11 07:09). Since 08:00, 0 lines match `amdgpu.*(timeout|reset|fault|hang)`.
- **`/tmp`** (tmpfs) held T08a's 5.4 GB instruction-test leftover, which caused the first kill. It was moved to
  `~/raiders/work/t12_moved_tmp/` (blocker §6).

## 8. Does any class block M4? Recommendations

| Class | Blocks M4? | Recommendation |
|---|---|---|
| 1. Large `Sample` programs (394, with all 160 geometry ones) | **No**: none drawn up to the menu | **Fix, in a new task with T14.** First learn whether gameplay draws them (a play run past the menu with `RX_VK_SEED_CHECK=1`, the keys checked against `~/raiders/work/t12_census/left_out_renderer_keys.txt`). If they are drawn: find the recompiler's memory use, measure one on one worker (needs a worker switch). If not: the preparation (T21) skips programs over a size, as here. Until then, **T21/T24 must not prepare the unfiltered census on a Deck**: it is killed every time |
| 2. Networks (20) | No | **Defer** to T13 (the NDSR/DLSS fallback, `02-gap-analysis.md` §6) |
| 3. IMAD with a constant-buffer addend (0x624) | No: one compute program, not dispatched in `seed1` | **Defer**: a lowering case to add (T14 or a lowering task). `RX_VK_SKIP_CODE` is not needed: the dispatch is already left out when the program does not translate (`vk_draw.cpp` "dispatches of program … are left out") |
| 4. CALL linkage (0x944) | No: only in class 1 | **Defer** with class 1. Hookshot upstream has the same open class (`docs/design.md` §9): watch upstream first |
| Census misses (`Layout`, sead primitive drawer, agl/gsys release) | No: 11 programs translated in play without a failure | **Defer to T21**: extend the census (an upstream candidate for the release-archive part, since agl and gsys are shared engine libraries) |

## Deviations

1. **The census was filtered** (`scripts/census_filter.py --max-kb 100`): the full census cannot finish on the Deck
   (`BLOCKER-T12-2026-11-11.md`). Option 1 there was your choice. The 394 programs are class 1 above, not part of the
   pass rate.
2. **A third preparation run with `RX_VK_GPL=1`** measures the driver step for graphics programs, which a default
   preparation does not build.
3. **`run.sh`'s time limit:** 7200 s for the preparation runs instead of the task's 3600, so a cold run would be timed
   whole. It finished in 77 s.
4. **Opcode names:** NAK was read from a shallow git clone of Mesa (`9b0a38c`, in the session's scratchpad, not in the
   repository). GitLab's web front end refused automated fetches.

## Acceptance criteria (real output)

| Command | Output |
|---|---|
| `scripts/deck/fetch.sh shaders1` | `fetch: …/work/runs/shaders1 (3 files)` |
| `grep -c "" work/runs/shaders1/hookshot_log.txt` | `473` |
| `grep -iE "prepared\|translated\|failed" … \| tail -20` | 19 `not translated: a network left out on this card` lines, then `vk: prepared 21648 shader programs (38102 new, 21 failed, 3015 compute pipelines; 3015 compute variants, 234 programs with texture variants, 33 at the limit) in 77.0 s` |
| `ssh $DECK_HOST 'ls ~/raiders/work/lowfail \| wc -l'` | `1` (`5_048439bbb2371e35.bin`, class 3) |
| `ssh $DECK_HOST 'journalctl -k -b \| grep -cE "gfx_\|amdgpu.*timeout"'` | `4`: all explained in section 7, none a timeout |

| `.venv/bin/python -I -B tests/run_all.py` (Mac, with `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`) | **322 passed, 9 failed, 9 skipped** of 340 in 728 s (T09a: 321 / 9 / 9 of 339). The new `test_census_filter` passes, and so does `test_deck_scripts`. The 9 failures are exactly `mac-test-baseline.md`'s 9 (8 FAIL and the `test_program_cache_reader` TIMEOUT) |

All are run against the filtered census (Deviation 1). On the full census the first command fetched a killed run's log
and no `prepared` line was printed (blocker §2).

## Deck state left behind

- **`~/raiders/work/sa/build/`** now has:
  - the filtered census as `hookshot_shaders.bin`, which a preparation can finish;
  - the prepared program cache (2.76 GB) and pipeline caches from `shaders1`-`shaders3` and `seed1`;
  - `hookshot_prepared.bin`.

  A normal run without `RX_VK_PRECOMPILE=1` does not prepare. The play runs' older caches from T09-T11 are in
  `~/raiders/work/t12_precaches/play/`.
- **The full census** is in `~/raiders/work/t12_census/hookshot_shaders.bin`, with the filtered copy, `left_out.tsv` and
  `left_out_renderer_keys.txt`.
- **Safe to discard** (all game-derived, under `~/raiders/work/`): `t12_precaches/killed{1,2,3}/`, `runs/shaders1m/`,
  `runs/seed2/`, `t12_stages/` (44 dumped stages), `lowfail_all/`, `t12_probe/`, `t12_mem*.csv`. `t12_moved_tmp/` is
  T08a's leftover.
- **The Deck's `src/`** is this branch, which lacks T11's commit `a3f1c10`; the binary is still T11's.
