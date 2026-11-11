# T11 · NVN2 procs and device limits (2026-11-11)

**Short answer.**
- **The proc work (scope 1-4) is not triggered.** No trace has shown an NVN proc called without an implementation:
  `M3-trace.md` §2 is empty for `trace1`, `font1` and `offline1`, and for this task's `nvn1` run.
- **`nvn1` ran under `HOS_NVN_STRICT=1`** and presented with no stop for 180 s.
- **Step 2 (device limits) is done.** I ran this game's own driver function for every id and compared it with the
  shared table. One id is a real difference and is now a per-game override: `0x31`, 5 in the table and 0 in Raiders'
  driver, which the game does not ask for. The rest either match or differ for documented reasons.

Claims are **verified** (command, file:line, log line, or Unicorn/Capstone on `work/sa/image/image.bin`) unless marked
**inferred** or **unknown**. Names, ids, counts and offsets only.

## Branch base

From `main` at `374154a` (T09a merged; T11 depends on T09a only). `task/T10-offline-stubs` is not on `main`, and T11 does
not need it. This is why this branch's Deck build has `276 import stubs` (T10's has 273): `host/nn_offline.c` is not here.

## Trigger check (scope 1-4)

| Trace | §2 "NVN procs called without an implementation" | "end:" line |
|---|---|---|
| `font1` (T09a) | none | `end: no crash or fatal error logged (time limit or exit); first present: line 5953` |
| `offline1` (T10) | none | `end: no crash or fatal error logged (time limit or exit); first present: line 5041` |
| `nvn1` (this task, `HOS_NVN_STRICT=1`) | none | `end: no crash or fatal error logged (time limit or exit); first present: line 5389` |

**Not triggered.** No proc was implemented and none was deferred, and no op was added to the stream (by the task's rule,
"never implement a proc no trace has seen"). The session that first meets a missing proc runs scope 1-4 then (most likely
T13).

## Device limits (step 2)

### Method

The harness named in `host/nvn_native.c`'s comment above `devinfo[]` is not in the repository: the task's
`grep -rn "nvnDeviceGetInteger" nx2` finds nothing. The method was rebuilt as `spikes/nvn_devinfo.py` (Unicorn 2.1, the
standalone lift's image):

1. In NVN2, `nvnDeviceGetInteger` has no exported name. The only copy of the name is in `main` (the game's own list).
   So the spike finds it the way the game does: `sdk`'s exported `nvnBootstrapLoader("nvnDeviceGetProcAddress")` →
   `sdk+0x659450`, then `nvnDeviceGetProcAddress(NULL, "nvnDeviceGetInteger")` → **`sdk+0x659410`** (MKW's 21.4.0 driver:
   `sdk+0x65b680`, from the comment).
2. While resolving, the driver calls `nn::os` (a mutex, a TLS slot). In the spike those calls answer 0, an `svc` answers
   0, and the current thread's TLS pointer and handle are set. The CPU model is `MAX`, for pointer authentication.
3. Each id 0x00-0xCF is asked of a zeroed device. Reads of the device are recorded.

Run time: under a second (`.venv/bin/python -I spikes/nvn_devinfo.py`).

### Diff (208 ids: 173 the same)

| Id | Name (`gpu/render/nvn_api.h`) | Table | Raiders' driver | Decision |
|---|---|---|---|---|
| `0x01` | API minor version | 40 | 39 | **Keep 40.** Deliberate upstream: Ocarina needs at least 40, and MKW's driver said 39 too (the comment above `devinfo[]`). Raiders boots and presents with 40 (verified: `font1`, `offline1`, `nvn1`). Saying 39 would be a change nobody has tested |
| `0x31` | `GLSLC_MIN_SUPPORTED_GPU_CODE_MINOR_VERSION` | 5 | **0** | **Per-game override: 0.** A constant in the driver: the id's case is `mov w0, wzr`, with no device read (verified: `sdk` `0x8558dbd0`) |
| 17 ids: `0x17`, `0x18`, `0x2b`, `0x2d`, `0x37`, `0x38`, `0x3a`, `0x3d`-`0x41`, `0x62`, `0x7d`, `0x87`, `0x99`, `0x9a` | | as in the table | 0 with a zeroed device | **Keep the table.** These read the device (offsets `0x28`-`0x9f8`), so the zeroed run does not give the hardware's answer. The original extraction kept a value for them the same way. Raiders' real values are **unknown** |
| `0xc0`-`0xcf` (16) | | not in the table | 0, no error | **No change.** The game never asks for them (below); the runtime still stops on an id past the table |

### What the game asks for (verified: `devinfo1`, 60 s, `HOS_NVN_DEVINFO_LOG=1`)

17 distinct ids: `0x00`, `0x01`, `0x04` (130,204 calls), `0x0f`, `0x10`, `0x11`, `0x12`, `0x14`, `0x18`, `0x19`, `0x1a`,
`0x2a`, `0x39` (258 calls), `0x51`, `0x55`, `0x5a`, `0x5b`.
- Every one of them answers the same as Raiders' driver except `0x01` (deliberate) and `0x18`. `0x18` is a device-state
  id: 256 from the table, and the hardware value is **unknown**.
- `0x31` is not asked for, so its override changes nothing observable today (**verified** for the first 60 s). It is
  there because the task requires that any driver difference go into a per-game override, not into the shared table.
- `devinfo1` ran on T10's Deck build, before this branch's. The logging is the same code on both.

### The override

| File | Change |
|---|---|
| `games/raiders/game.py` | `NVN_DEVICE_INFO = {0x31: 0}`, with its source and the two non-overrides explained |
| `nx2/standalone.py` | `nvn_device_info_c(game)` (new, `(raiders)`) writes `const int hos_game_nvn_devinfo[][2] = {{0x31, 0}, {-1, 0}};` into `gen/hos_image.c` from `write_image_c`. A game without the field (Ocarina) gets `{{-1, 0}}`. An id outside 0..0xFF or a value that is not a 32-bit int stops the lift |
| `host/hos_game.h` | `extern const int hos_game_nvn_devinfo[][2];` |
| `host/nvn_native.c` `NV(nvnDeviceGetInteger)` | After the bounds check, an id in the game's table answers the game's value. The `HOS_NVN_DEVINFO_LOG` line shows the answer given. Marked `(raiders)`; the shared `devinfo[]` is unchanged |

Verified on the Deck: the build's `gen/hos_image.c` line 16 is `const int hos_game_nvn_devinfo[][2] = {{0x31, 0}, {-1, 0}};`.

## Tests

`tests/test_nvn_device_info.py` (new, 16 checks, upstream style: the real `devinfo[]` and `NV(nvnDeviceGetInteger)` cut
out of `nvn_native.c` by text) covers:
- the generator's line for Raiders, for a game with no field, and for id order;
- 5 bad overrides that stop the lift;
- the wiring in `standalone.py` and `hos_game.h`;
- the compiled function, fed the generator's own output: `0x31` → 0, and `0x00`/`0x01`/`0x2e`/`0x04` → 231/40/201/256
  from the table;
- with no overrides, `0x31` → 5 as before, and an id past the table still stops (exit 86).

## Procs implemented, deferred, new ops

None of each (not triggered: see above).

## Upstream candidates

- `spikes/nvn_devinfo.py` reproduces the extraction that `nvn_native.c`'s comment describes and that upstream does not
  ship. It belongs with T25's #6 (NVN procs) or as its own small PR: any game's `sdk` can be checked against `devinfo[]`.
- The per-game override only makes sense with T25's #3 (the per-game config). It is kept in the fork otherwise.

## Deviations

1. **No harness to re-run.** `spikes/nvn_devinfo.py` rebuilds the method (above). It is a spike: game data in, numbers
   out, no test of its own (like `spikes/standalone_summary.py`).
2. **`0x01` is not overridden to the driver's 39** (above). The task's "any difference goes into a per-game override"
   is applied to the measured difference (`0x31`), not to upstream's deliberate value.
3. **The acceptance `sed` range** (`/NVN procs called without/,/^$/`) stops at the blank line right after the heading,
   so it prints only the heading. The section's table, printed with `awk '/NVN procs called without/,/### 3/'`, is
   `| | none | | | | | | |`.
4. **The run name** is `nvn1` for the task's `nvnN`.

## Acceptance criteria

| Command | Result |
|---|---|
| `.venv/bin/python -I -B tests/run_all.py nvn` | `6 passed, 0 failed, 0 skipped` (5 upstream NVN tests and the new one). **Met** |
| `scripts/deck/run.sh nvn1 180 -- HOS_NVN_STRICT=1 HOS_NO_MOVIES=1 && scripts/deck/fetch.sh nvn1` | Built first with `scripts/deck/sync.sh && scripts/deck/build.sh` (253 s: lift 244 s, `compiled in 6s, 0 failed`, `linked … 451 MB`). The run went to the time limit with 37 screenshots, and 39 files were fetched. **Met** |
| `grep -n "PresentTexture\|present" work/runs/nvn1/hookshot_log.txt \| head -3` | `12: … vk: no window: presents render offscreen (1920x1080)`, `1377: [hos Presentation Thread] vk: present texture … 3840x2160 format 0x25: rendered`, `1398: … rendered`. **Met: a first present under STRICT**. The log has no FATAL, CRASH or "is not implemented" line (`grep -c`: 0) |
| `.venv/bin/python -I scripts/trace_report.py work/runs/nvn1/hookshot_log.txt \| sed -n '/NVN procs called without/,/^$/p'` | `### 2. NVN procs called without an implementation` (the range ends at the blank line after the heading: Deviation 3). The table: `\| \| none \| …`. **Met: none** |
| `.venv/bin/python -I -B tests/run_all.py` | With `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`: **322 passed, 9 failed, 9 skipped** of 340 in 722 s (`main` with T09a: 321 / 9 / 9 of 339; the new check passes). The 9 failures are exactly the baseline's 9 (`mac-test-baseline.md`). **Met** |
| `git status --porcelain \| grep -c 'work/'` (`06-handoff-guide.md` §6) | `0` |
