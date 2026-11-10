# T11 · NVN2 procs the game calls that the native layer lacks

**Milestone:** M3 · **Depends on:** T09 · **Machine:** Mac driving the Deck

## Context
`host/nvn_native.c` implements 427 NVN procs by name; Raiders' `main` names 734 (`work/nvn_missing.txt` has
the 325 without one). Procs the layer lacks log their first call and return 0. The M3 trace lists which of
them Raiders calls before its first present. Hookshot's own game needed 14 at this stage
(`docs/design.md` §5: DLSS parameter procs, window acquire timeout, HDR metadata,
`nvnProgramBuilderGetShaders`, …) and later `nvnCommandBufferPushComputeConstants`, `nvnQueueWaitSync`,
`SetCopyImageStride` (§9).

## Read first
- `CLAUDE.md`; `docs/plans/reports/M3-trace.md` (NVN sections); `docs/plans/02-gap-analysis.md` §5
- `host/nvn_native.c`: the `NV(name)` macro and argument accessors (`P`, `U32`, `U64`, `GP`, `RET`), the
  `impls[]` table (from line ~2688), the `devinfo[]` table and its comment, one builder family end to end
  (for example `nvnSamplerBuilder*`) and one command-buffer recording proc with its op in
  `gpu/render/rx_nvn.h`
- `gpu/render/nvn_api.h` (signatures and enums), `gpu/vk/VULKAN.md`
- `docs/design.md` §4 (the replay's rules)

## Scope
Implement, in `host/nvn_native.c` (or a new `host/nvn_native_raiders.c` if the additions are many and
self-contained: prefer the new file to keep merges easy; `impls[]` then needs one registration hook), every
NVN proc the trace marked **blocking** or **wrong answer** before the first present, in this order:
1. Builders and state objects (setters that fill a struct the layer already has: cheap and safe).
2. Getters whose 0 answer is wrong (sizes, alignments, counts): return what the real driver would; when the
   value comes from the device, read it the way `devinfo[]` was produced (run the `sdk`'s own function under
   Unicorn on the Mac; `nx2/` has the harness the comment refers to: find it with
   `grep -rn "nvnDeviceGetInteger" nx2`).
3. Command-buffer procs that only set state the replay already models.
4. Command-buffer procs that need a new op: add the op to `gpu/render/rx_nvn.h` and its replay in
   `gpu/vk/vk_replay.cpp`/`vk_draw.cpp` only if the trace shows the game cannot draw its first frame without
   it; otherwise record it for T13.

## Non-goals
- DLSS evaluation. Accept and store `nvnDlss*` parameters so the game proceeds; what the picture needs is
  T13's concern.
- No speculative implementations of procs the trace did not see.
- No changes to the replay's ordering rules.

## Steps
1. From `M3-trace.md`, make the work list (name, class, what it must do). Show it to the user before
   implementing if it has more than about 25 entries: that is more than one session.
2. Check the device limits: Raiders' SDK is NVN 21.4.4 and `devinfo[]` came from Mario Kart World's 21.4.0
   driver. Re-run the extraction against Raiders' `sdk` on the Mac and diff the table. Any difference goes
   into a per-game override (`games/raiders/game.py` → generated C), not into the shared table.
3. Implement in small batches; each batch: `python -I -B tests/run_all.py nvn` on the Mac, then
   `scripts/deck/sync.sh && scripts/deck/build.sh && scripts/deck/run.sh nvnN 120 -- HOS_NVN_STRICT=1`.
   - Pitfall: adding an `NV()` does not relift (the procs are resolved by name at run time), so iterations
     are a host-only rebuild: minutes.
   - Pitfall: structs live in guest memory at the game's addresses and sizes. A builder struct that is too
     large for the game's allocation corrupts memory: check the game's allocation size from the matching
     `Get…Size`-style proc or the lifted caller before defining a layout.
4. Tests: upstream tests cut `NV()` functions out of `nvn_native.c` by text
   (`grep -rln nvn_native tests | head`). Add one test per non-trivial proc in the same style.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py nvn
scripts/deck/run.sh nvnN 180 -- HOS_NVN_STRICT=1 HOS_NO_MOVIES=1 && scripts/deck/fetch.sh nvnN
grep -n "PresentTexture\|present" work/runs/nvnN/hookshot_log.txt | head -3     # a first present is reached under STRICT,
                                                                               # or the report names the proc that stops it
.venv/bin/python -I scripts/trace_report.py work/runs/nvnN/hookshot_log.txt | sed -n '/NVN procs called without/,/^$/p'
.venv/bin/python -I -B tests/run_all.py
```

## Report
`docs/plans/reports/T11-nvn2.md`: procs implemented (name, what it does, test), the `devinfo` diff, procs
deferred with the reason, new ops added to the stream (if any), and upstream PR candidates.
