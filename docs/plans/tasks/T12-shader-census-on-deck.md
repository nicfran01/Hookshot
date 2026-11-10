# T12 · Translate every shader on the Deck: pass rate and failure classes

**Milestone:** M3 (early de-risk) · **Depends on:** T08 (a built game and renderer), T05 · **Machine:** Mac
driving the Deck

## Context
Raiders has 26,960 shader stages in 22,042 programs (`spikes/README.md`). Each must go Ampere → Maxwell
(`lower_to_maxwell.h`) → IR → SPIR-V (Eden's recompiler) → a RADV pipeline. Hookshot's own game still has a
few programs that do not lower (`docs/design.md` §9). Raiders' failure rate is unknown and is one of the two
risks that could change the plan (`00-overview.md` risk 5), so it is measured before effort goes into the
first frame. The same run measures shader preparation time on the Deck.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §6; `docs/plans/04-steam-deck.md` §1, §3
- `docs/design.md` §9 (S4 notes on lowering), §10 (precompile and cache files)
- `nx2/lower_test.py` docstring; `gpu/shadertool.cpp` header comment; `nx2/shader_census.py` docstring
- `gpu/vk/vk_shader.cpp`: `program_pick` (~2078), the "dropped stages" log (2087), the precompile entry
  (`grep -n "prepare\|precompile" gpu/vk/vk_shader.cpp gpu/vk/vk_main.cpp host/hos_main.c | head -40`)
- `docs/pipeline-cache-save-check.md`

## Scope
1. Run the shader preparation (`hookshot --prepare-shaders`) on the Deck against Raiders' census file.
2. Collect failures with `RX_VK_DUMP_FAILED=<dir>` (the dump is game data: it stays on the Deck under
   `~/raiders/work/lowfail`).
3. Classify failures offline with `nx2/lower_test.py`.
4. Report pass rate, classes, time, and memory.

## Non-goals
- No fixes to the lowering or the recompiler in this task, except a one-line fix if a single cause accounts
  for most failures and the fix is obvious. Fixes are planned from the report (new tasks or T14).
- No pipeline-state work (T21).

## Steps
1. Make sure the game folder has the census file: `make_game.py` writes `hookshot_shaders.bin`
   (`make_game.py:1483`). In a development build without `make_game.py`, run
   `python -I nx2/shader_census.py ~/raiders/dump/romfs --out <folder beside the executable>/hookshot_shaders.bin`
   in the container.
2. Run: `scripts/deck/run.sh shaders1 3600 -- RX_VK_DUMP_FAILED=$HOME/raiders/work/lowfail` with the
   executable's `--prepare-shaders` argument (extend `run.sh` with `--args "…"` if it cannot pass arguments
   yet). Watch `journalctl -k` for GPU timeouts during the run.
   - Pitfall: over SSH there is no display. `--prepare-shaders` must work headless
     (`HOS_HEADLESS`). If it needs a surface, run it from a Desktop Mode terminal and say so in the report.
   - Pitfall: memory. Pipeline compilation on 8 threads next to a 2.5 GB texture budget can swap. Record
     peak RSS; if the kernel kills it, re-run with fewer compile threads (find the switch with
     `grep -n "getenv(\"RX_VK.*THREAD\|JOBS" gpu/vk/*.cpp`).
3. From the log, count: stages lowered, stages failed to lower (by reason), programs translated, programs
   failed in the recompiler, pipelines created, pipelines failed in the driver. Count programs with task or
   mesh stages and with dropped geometry stages.
4. Offline classification on the Deck: `python -I nx2/lower_test.py ~/raiders/work/lowfail`. Group by the
   first unsupported opcode or message. For the top five classes, look up the opcode in Mesa NAK's encoding
   tables (public source) to name the instruction; do not paste shader disassembly into the report.
5. Compare the run-time program set with the census: are there programs the game creates that the census did
   not list? (This needs a short normal run from T08/T09: `grep "its code:"`-style lines; if the log does not
   print program keys by default, find the switch.) List the archive kinds the census misses.
6. Second run with the caches warm: time it.

## Acceptance criteria
```bash
scripts/deck/fetch.sh shaders1
grep -c "" work/runs/shaders1/hookshot_log.txt                      # the log exists
grep -iE "prepared|translated|failed" work/runs/shaders1/hookshot_log.txt | tail -20
ssh $DECK_HOST 'ls ~/raiders/work/lowfail | wc -l'                  # the number of failing programs (0 is a valid answer)
ssh $DECK_HOST 'journalctl -k -b | grep -cE "gfx_|amdgpu.*timeout"' # 0, or each line explained in the report
```

## Report
`docs/plans/reports/M3-shaders.md`: totals and pass rates per step (lower, translate, pipeline); a table of
failure classes (count, stage kind, opcode or message, which archive); programs with task/mesh stages;
programs with dropped geometry stages and their archive; first-run and warm-run times; peak memory; whether
any failure class blocks M4 (recommendation: fix now, defer, or skip via `RX_VK_SKIP_CODE`). Program keys
(hashes) may be listed; shader code may not.
