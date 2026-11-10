# T23 · Deck stability: GPU hangs, long sessions, suspend and resume

**Milestone:** M7 (exit) · **Depends on:** T20, T21, T22 · **Machine:** the user plays at the Deck; Mac for
analysis

## Context
Known upstream problems on AMD hardware: device loss on some Radeon cards (issues #708, #614), Linux AMD
problems (#604, #528), and a Steam Deck GPU reset in a long-running task shader (#817, `gfx_0.0.0 timeout`
in `journalctl -k`). Raiders has no task shaders in its archives (`spikes/shader_stage_kinds.py`), so the
exact #817 case does not apply, but nothing has yet been run for an hour. Handheld-specific events also need
checking: suspend/resume, the Steam overlay, switching to Desktop Mode, low battery TDP changes.

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §1, §6; reports `T20-memory.md`, `T21-shader-caches.md`,
  `T22-performance.md`
- `docs/development.md` "The GPU" (`RX_VK_HANG_DUMP` is Windows-only: note it), `RX_VK_SKIP_CODE`,
  `RX_VK_MESH_NOCULL`, `RX_VK_VALIDATION`, `RX_VK_CHECKPOINTS`
- `docs/swapchain-recovery.md`; `gpu/vk/vk_hangdump.cpp` header; `readme.md` "If something goes wrong"

## Scope
1. A soak protocol and a script that collects evidence for a session.
2. Three sessions: one hour of normal play from Gaming Mode; a scripted loop left running for an hour;
   an event test (suspend/resume ×5, overlay ×5, quick-access TDP change, controller sleep/wake).
3. Root cause or workaround for every crash, hang, GPU reset or leak found, or a blocker report.

## Non-goals
- New features. Performance tuning beyond undoing a setting that causes instability.

## Steps
1. `scripts/deck/soak.sh <name> <minutes>` (new): starts sampling (reuse `mem_report.sh`), follows
   `journalctl -k -f` filtered to `amdgpu|gfx_|drm|Out of memory|oom` into
   `work/runs/<name>/kernel.log`, records the game's exit status and the last 200 log lines, battery and
   temperature at start and end. It does not start the game when the user launches from Gaming Mode
   (`--attach` finds the running process).
2. Session A (user, Gaming Mode, one hour, normal play including area changes and a save). Afterwards:
   crashes, visual glitches noticed with the time they happened, `kernel.log`, memory trend (a leak shows as
   a steady RSS or GTT climb: compare the first and last ten minutes).
3. Session B (scripted, one hour): the T17 loop repeated; same evidence. Deterministic input makes any
   failure reproducible.
4. Session C (events): after each suspend/resume, does the picture return, does audio resume, does input
   work, does the swapchain recover (`docs/swapchain-recovery.md`)? Overlay open/close; change TDP limit;
   let the controller idle.
5. For each failure:
   - GPU reset (`gfx_… timeout`, "device lost"): the last program key before it ("its code:" lines; enable
     `RX_VK_CHECKPOINTS` only if it applies to AMD: check). Reproduce with session B. Try
     `RX_VK_SKIP_CODE=<key>` to confirm the program, then decide: fix, simplify, or ship the skip in
     `deck_env.txt` if the effect is minor. Report upstream if generic.
   - Crash in lifted code: the guest address from the fault line (`nx2/fault.py` maps addresses to
     functions); note the function's module and offset only.
   - Leak: which counter grows (texture cache, pipelines, pools, guest heap).
   - Suspend/resume failure: where the swapchain or audio device is recreated; fix in `host/posix/` or
     `gpu/vk/vk_main.cpp`.
6. Re-run the failed session after each fix.

## Acceptance criteria
```bash
bash -n scripts/deck/soak.sh
scripts/deck/fetch.sh soakA && scripts/deck/fetch.sh soakB && scripts/deck/fetch.sh soakC
grep -cE "gfx_|timeout|GPU reset|device lost" work/runs/soak{A,B}/kernel.log work/runs/soak{A,B}/hookshot_log.txt   # all 0
tail -1 work/runs/soakB/exit_status                                                                                # normal exit at the time limit
#   memory: last-ten-minutes mean RSS within 3% of first-ten-minutes mean (after the first area is loaded)
```
User confirmation: one hour in Gaming Mode without a crash; suspend and resume returns to a working game.
This is the M7 exit together with T22's frame-rate criterion.

## Report
`docs/plans/reports/M7-stability.md`: the three sessions' results, each failure with cause and fix or
workaround, switches added to `deck_env.txt` with the reason, remaining known issues for the README.
