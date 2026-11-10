# T08a · Lifter differential tests on Linux; run them on Raiders

**Milestone:** M2 · **Depends on:** T03, T06 · **Machine:** Mac (edits) driving the Deck (runs)
· *(added 2026-11-10 after T02; see `docs/plans/reports/mac-test-baseline.md`)*

## Context
The only check that lifted C computes what the ARM64 code computes is the pair of differential tests that
compare it with Unicorn: `nx2/test_insn.py` (every instruction form the game uses) and `nx2/test_leaf.py`
(random whole functions, `--calls` for call trees). T02 found that **both harnesses are Windows only as
written**, so they cannot run on the Mac or on the Deck:

- `third_party/a64-kit/tests/insn_test.py` `build_harness`: `#include <windows.h>` (line 151) and
  `VirtualAlloc` for the guest memory (line 170).
- `nx2/test_leaf.py` `HARNESS`: `#include <windows.h>` (line 222), `VirtualAlloc` for the image and scratch
  (lines 269-270), and `__try` / `__except` with `GetExceptionCode()` to catch a fault in a lifted function
  (`run`, about line 263).

Both also add `-mcx16`, which only x86-64 accepts: fine on the Deck, not on the arm64 Mac. On Linux the Deck's
`deps/python` already has Unicorn and capstone (`scripts/linux/deps.sh` line 8).

## Read first
- `CLAUDE.md`, `AGENTS.md`; `docs/plans/reports/mac-test-baseline.md` ("Lifter differential tests")
- `nx2/test_insn.py` (all of it: it already monkeypatches `insn_test`), `third_party/a64-kit/tests/insn_test.py`
  `build_harness` and `main`
- `nx2/test_leaf.py` `HARNESS`, the function that writes and compiles it (`toolchain.find("clang")`, about
  line 334), and how it reads the harness's exit status and fault codes
- `third_party/PROVENANCE.md` and CONTRIBUTING.md "Do not modify `third_party/`"

## Scope
1. A POSIX path in `nx2/test_leaf.py`'s harness, behind `#ifdef _WIN32`, so the Windows text is unchanged.
2. A POSIX path for the instruction test **without editing `third_party/`**: `nx2/test_insn.py` wraps
   `insn_test.build_harness` (as it already wraps `sample`, `mem_regs` and `toolchain.native_target`).
3. Run both on the Deck against Raiders and record the results.

## Non-goals
- No change to `third_party/a64-kit/`. No change to what is sampled or compared. No arm64-Mac support (the
  harness is x86-64 by design: `-mcx16`, `a64.h`).
- No fixes to the lifter in this task: a failing form or function is recorded, with its mnemonic and count,
  for a follow-up task.

## Files to touch
- `nx2/test_leaf.py` (harness text only, `(raiders)`-marked), `nx2/test_insn.py` (a wrapper, `(raiders)`-marked),
  `tests/test_lifter_harness_posix.py` (new), `docs/plans/reports/T08a-lifter-tests.md` (new)

## Steps
1. `test_leaf.py` harness, POSIX side:
   - `#include <sys/mman.h>`, `<signal.h>`, `<setjmp.h>`; map with
     `mmap(A64_PTR(base), size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0)`
     and keep the same return codes (3, 4) when the address is not the one asked for.
   - `run`: a `SIGSEGV`/`SIGBUS`/`SIGILL`/`SIGFPE` handler that `siglongjmp`s back, installed once with
     `sigaction` (`SA_ONSTACK` and a `sigaltstack`, since a fault can be a stack overflow). Return a code the
     Python side already treats as "faulted"; map it the way the Windows path maps `GetExceptionCode()` (read the
     Python side first, and keep the meaning of each code the same).
   - Pitfall: `MAP_FIXED_NOREPLACE` needs Linux 4.17+ (SteamOS is far newer); glibc names it from 2.28. If the
     header lacks it, `#define MAP_FIXED_NOREPLACE 0x100000`.
2. `test_insn.py`: on non-Windows, wrap `insn_test.build_harness` so the `harness.c` it writes has the
   `windows.h` include and the `VirtualAlloc(...)` line replaced by the POSIX equivalents, before `clang`
   runs (for example by wrapping `subprocess.run` for that one call, or by rewriting the file between write
   and compile). Fail loudly if the expected Windows text is not found, so an upstream change cannot make the
   wrapper silently do nothing.
3. `tests/test_lifter_harness_posix.py`: game-free. It extracts both harness texts as the tests generate them
   (with a stub picked list) and checks that the Windows text is byte-identical to `upstream/main`'s and the
   POSIX text has no `windows.h`, `VirtualAlloc` or `__try`. If a C compiler is present, it compiles a tiny
   harness with an empty table on Linux. Mark it `RUN_ALL_SKIP` for `windows` only if it cannot run there.
4. On the Deck, in the container (`scripts/deck/*.sh`), with `OOT_WORK=~/raiders/work OOT_DUMP=~/raiders/dump`:
   `python -I nx2/census.py --nx2`, `python -I nx2/test_insn.py --per 6 --states 12`,
   `python -I nx2/test_leaf.py --count 1000 --states 4 --calls`. Logs to `~/raiders/work/`; fetch only the
   summary lines.
5. Write the report. These changes are a candidate upstream PR (T25): one fix, Linux support for the two
   differential tests.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py lifter_harness_posix          # passes on the Mac (game-free)
.venv/bin/python -I -B tests/run_all.py                               # no worse than mac-test-baseline.md
git diff upstream/main -- third_party/ | wc -l                        # 0
# on the Deck, through scripts/deck/*.sh:
python -I nx2/test_insn.py --per 6 --states 12                        # "all pass", or failing forms listed in the report
python -I nx2/test_leaf.py --count 1000 --states 4 --calls            # its summary line; failures listed in the report
```

## Report
`docs/plans/reports/T08a-lifter-tests.md`: forms and encodings tested, cases, passes and failures by mnemonic;
functions and call trees tested and the failures by kind; times on the Deck; the POSIX code paths added and how
the Windows text was shown unchanged. No instruction words, addresses of game code beyond module-relative counts,
or lifted C.
