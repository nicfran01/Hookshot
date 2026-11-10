# T02 · Mac development environment and test baseline

**Milestone:** M0 · **Depends on:** T01 · **Machine:** Mac

## Context
The Mac is where code is written. Upstream supports Windows and Linux; nobody has said its tools or tests run
on macOS. Planning showed that `nx2/dump.py`, `nx2/imports.py`, `nx2/lift.py` (coverage) and
`third_party/a64-kit/lift/build_emit.py` do run on an Apple M2 with Python 3.14
(`spikes/README.md`). This task establishes which game-free tests pass on the Mac, so later tasks can tell a
regression from a platform skip.

## Read first
- `CLAUDE.md`, `AGENTS.md`
- `CONTRIBUTING.md` sections "Testing" and "Game-free checks"
- `tests/run_all.py` docstring and its `ARGS` / skip list / `find_tools`

## Scope
1. A documented, repeatable Mac setup.
2. A baseline of `tests/run_all.py` on macOS.
3. The Unicorn-based lifter tests run once against the Raiders image.

## Non-goals
- Do not fix upstream tests that fail only because of macOS (record them). Do not try to compile the game.
- Do not change `tests/run_all.py` except, if needed, a `(raiders)`-marked skip reason for "needs Linux or
  Windows" that leaves Linux and Windows behaviour identical.

## Files to touch
- `scripts/dev/mac_setup.sh` (new), `docs/plans/reports/mac-test-baseline.md` (new)

## Steps
1. `scripts/dev/mac_setup.sh`: creates `.venv`, installs `lz4 numpy capstone "unicorn>=2.1,<2.2"
   zstandard`, checks `clang++` exists, builds `liba64emit` via
   `python -I third_party/a64-kit/lift/build_emit.py`, prints the versions. Idempotent.
   - Pitfall: Unicorn 2.1 may have no wheel for the installed Python on arm64 macOS. If `pip` cannot install
     it, record that and create the venv with an older Python from Homebrew (`python@3.12`) instead; do not
     drop the version pin.
2. Run `.venv/bin/python -I -B tests/run_all.py --jobs 4` and save the summary table. Classify each failure:
   (a) needs a tool the Mac lacks (Vulkan/SPIR-V headers, glslang, spirv-val, dotnet, a Windows or Linux
   header), (b) assumes Linux or Windows, (c) a real failure. For (a), try `brew install spirv-tools glslang
   vulkan-headers` and re-run once; record what that fixed.
3. With `OOT_WORK` and `OOT_DUMP` set (see `CLAUDE.md`), run the lifter's differential tests on Raiders:
   `python -I nx2/census.py --nx2`, `python -I nx2/test_insn.py --per 6 --states 12`,
   `python -I nx2/test_leaf.py --count 500 --states 4`.
   - These compare lifted C against Unicorn. `test_leaf.py` compiles C natively: on an arm64 Mac the lifted
     C targets x86-64 conventions in places (`a64.h`); if it cannot build here, record why and mark the test
     "Deck only" (T08 runs it there).
4. Write the report.

## Acceptance criteria
```bash
scripts/dev/mac_setup.sh && scripts/dev/mac_setup.sh        # second run changes nothing
.venv/bin/python -I -B tests/run_all.py --jobs 4 | tail -40  # summary shown; every failure is listed in the report
.venv/bin/python -I nx2/test_insn.py --per 6 --states 12     # "all pass", or the failing forms listed in the report
```

## Report
`docs/plans/reports/mac-test-baseline.md`: tool versions; counts of passed / skipped / failed; a table of
every non-passing check with its class (a/b/c) and one line of reason; the results of step 3 (forms tested,
cases, failures). Later tasks compare against this file.
