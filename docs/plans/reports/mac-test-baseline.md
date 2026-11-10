# Mac test baseline (T02, 2026-11-10)

The game-free suite on the development Mac, and the lifter's differential tests against Raiders. Later tasks compare
against this file: a check listed below as failing or skipped on the Mac is not a regression there; anything else that
fails is.

Source: branch `task/T02-mac-dev-checks` at `d9dfabd` (upstream `78e1112` + T01). Every number below is **verified**
(the command was run on this Mac on this date) unless it says otherwise.

## Setup

`scripts/dev/mac_setup.sh` (new): makes `.venv` if missing, installs only the missing pinned packages
(`lz4 numpy capstone "unicorn>=2.1,<2.2" zstandard`), checks `clang++`, builds `liba64emit` with
`third_party/a64-kit/lift/build_emit.py` (rebuilt only when its sources change), prints the versions and says which
optional test tools are missing. It never reads the game.

| | Run 1 | Run 2 |
|---|---|---|
| What it did | installed `unicorn>=2.1,<2.2` (the planning venv lacked it), built `liba64emit.so` | nothing |
| Time | 5.3 s | 0.2 s |
| Files in `.venv` and `liba64emit.so*` | | identical to after run 1 (mtime, size and path of every file hashed: `cd65437e1ed6ad83` both times) |

The Unicorn pitfall in the task did not apply: PyPI has `unicorn-2.1.4-cp37-abi3-macosx_11_0_arm64.whl`, which installs
on Python 3.14. The Homebrew `python@3.12` fallback was not needed (the script prints it if pip ever fails).

### Tool versions

| Tool | Version |
|---|---|
| macOS | 27.2.1, arm64, Apple M2 (`sysctl -n machdep.cpu.brand_string`) |
| Python (`.venv`) | 3.14.7 (Homebrew `python@3.14`) |
| lz4 / numpy / capstone / unicorn / zstandard | 4.4.5 / 2.5.4 / 5.0.9 / 2.1.4 / 0.25.0 |
| clang / clang++ | Apple clang 17.0.0 (clang-1700.6.4.2) |
| liba64emit | built from source sha1 `f7a5a193bfd6babe931a43fcacb3ed270995d9f3` |
| Homebrew, installed in step 2 | spirv-tools 1.4.363.0 (`spirv-val` = SPIRV-Tools v2026.4), glslang 16.6.0, vulkan-headers 1.4.363.0, spirv-headers 1.4.363.0 (glslang's dependency) |

## Game-free suite

`tests/run_all.py` reports the Mac as `linux` (**verified**: `OS = "windows" if WINDOWS else "linux"`,
`tests/run_all.py` line 31). So the Linux skips (`RUN_ALL_SKIP`) apply on the Mac, and macOS has no skip key of its own.
`run_all.py` is unchanged: the task allowed a `(raiders)` skip there, but skips now live in each test's
`RUN_ALL_SKIP`, keyed by `linux`/`windows` only, so a Mac-only skip would need a new OS value. Nothing was skipped
that way: the Mac failures are listed below instead.

| Run | Command | Passed | Failed | Skipped | Wall time |
|---|---|---|---|---|---|
| Baseline | `.venv/bin/python -I -B tests/run_all.py --jobs 4` | 278 | 9 | 43 | 626 s |
| With Homebrew tools | the same, with `HOOKSHOT_VULKAN_HEADERS=/opt/homebrew/include` and `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include` | 312 | 9 | 9 | 782 s |

330 checks in both runs. **The reference for later tasks is the second row.** To reproduce it: run
`scripts/dev/mac_setup.sh`, then `brew install spirv-tools glslang vulkan-headers`, export the two variables, and run
the command. `run_all.py` only finds the headers through those variables or a CPM cache, not through Homebrew's
prefix.

What the Homebrew tools fixed: 34 checks that were skipped for `vulkan_headers` (23), `spirv_headers` + `spirv_val`
(8), `spirv_headers` (2) or `glslang` + `spirv_val` (1) now run, and all 34 pass. The 9 failures are the same set in
both runs.

### Every non-passing check (run with Homebrew tools)

Classes: (a) needs a tool the Mac lacks, (b) assumes Linux or Windows, (c) a real failure.

| Check | Result | Class | Reason |
|---|---|---|---|
| `tests/test_program_cache_reader.py` | TIMEOUT 600 s | a | Its fixture is built with `-fsanitize=address`. The ASan runtime of Apple clang 17 on macOS 27.2.1 hangs at start, before `main` (**verified**: an empty `int main(){return 0;}` built with `-fsanitize=address` is stopped by a 15 s alarm, while the plain and UBSan builds exit at once; `sample` shows it spinning in `__asan::InitializeShadowMemory` → `get_dyld_hdr` → `malloc`). The hung child outlives the runner's timeout and was killed by hand. |
| `tests/test_seed_reader.py` | FAIL 301 s | a | Same ASan hang; the test's own 300 s timeout. |
| `tests/test_mem_gate.py` | FAIL | b | `nx2/build.py` reads free memory from `/proc/meminfo` (Windows: `GlobalMemoryStatusEx`); macOS has neither, so it reads `None`. |
| `tests/test_mem_gate_children.py` | FAIL | b | `nx2/build.py` reads `/proc/<pid>/statm` and `/proc/<pid>/task/*/children`. |
| `tests/test_low_memory_notice.py` | FAIL | b | The fixture includes `<sys/sysinfo.h>` (Linux only). |
| `tests/test_prof_symbols.py` | FAIL | b | The fixture includes `<link.h>` and builds a Linux PIE ELF. |
| `tests/test_hookshot_launch.py` | FAIL | b | The macOS temp folder `/var/folders/...` is a symlink to `/private/var/...`; the test compares a resolved path with an unresolved one. Passes with `TMPDIR` set to a path without a symlink (**verified**). |
| `tests/test_linux_update.py` | FAIL (5 errors) | b | The same symlink: "the update would write through a symbolic link: /var/folders/...". Passes with `TMPDIR` set to a path without a symlink (**verified**). |
| `tests/test_appimage_source_headers.py` | FAIL | b | The same symlink: `Path.resolve()` leaves the unresolved temp root, so the missing header is not found. Passes with `TMPDIR` set to a path without a symlink (**verified**). |
| `nx2/test_insn.py` | skip | b | `RUN_ALL_SKIP` on both OSes: needs the game's modules and Unicorn. Run by hand below. |
| `nx2/test_leaf.py` | skip | b | The same. Run by hand below. |
| `nx2/test_dll.py` | skip | b | Needs a full Windows game build (`work/build/hookshot_game.dll`). |
| `nx2/test_bc_storage_views.py` | skip | b | Needs a Windows Vulkan device. |
| `tests/test_present_aspect_vulkan.py` | skip | a | Needs a Vulkan 1.3 device (none on this Mac). |
| `tests/test_builder_dlss_update.py` | skip | b | Windows Builder, .NET 8 fixture. |
| `tests/test_fs_path_utf8.py` | skip | b | Native Windows filesystem conversion APIs. |
| `tests/test_log_batch.py` | skip | b | The Windows log writer (SRW locks). |
| `tests/test_precompile_compute_guard.py` | skip | b | Windows structured exceptions. |

**No class (c) failure.** Every check not in this table passed.

Not tried (outside T02): Homebrew's `llvm` might have a working ASan runtime for the two class (a) checks
(**unknown**).

## Lifter differential tests on Raiders (step 3)

Run with `OOT_WORK=$PWD/work` and `OOT_DUMP` set as in `CLAUDE.md`. Logs are in `work/t02_*.txt` (not committed).

| Command | Result |
|---|---|
| `python -I nx2/census.py --nx2` | Passed, 6 s. Words per module: rtld 2,512, main 16,598,728, subsdk0 135,452, sdk 2,224,428. Untranslated: 460,368 `udf` words and 6 words that are not instructions; no other mnemonic is untranslated. |
| `python -I nx2/test_insn.py --per 6 --states 12` | **Cannot run on the Mac.** It sampled 3,614 encodings in 737 forms, then the harness build failed: `clang: error: unsupported option '-mcx16' for target 'arm64-apple-darwin27.2.0'`. 0 cases run. |
| `python -I nx2/test_leaf.py --count 500 --states 4` | **Cannot run on the Mac.** It picked and lifted 500 self-contained functions (14,876 instructions, 3 s), then failed to build the harness on the same `-mcx16` error. 0 cases run. |

The acceptance criterion for `test_insn.py` ("all pass", or the failing forms listed) **is not met**: no form could be
tested, so there are no results to list.

### Why, and what it means for the Deck

As a diagnostic only, both tests were run again with a `clang` wrapper first on `PATH` that adds `-arch x86_64`
(Rosetta is running on this Mac). No source was changed. Both then fail on the next line:

- `third_party/a64-kit/tests/insn_test.py` lines 151 and 170: the harness has `#include <windows.h>` and maps its memory
  with `VirtualAlloc`, with no `#ifdef`.
- `nx2/test_leaf.py` line 222 (`#include <windows.h>`) and lines 269-270 (`VirtualAlloc`): the same.

So both harnesses are **Windows only as written**, not just unable to build on arm64 (**verified** by the source lines
and the x86-64 build error). They cannot build on Linux either. The task's fallback ("mark the test Deck only, T08 runs
it there") does not hold:

- T06 step 5 and T08 step 2 (`nx2/test_leaf.py --count 1000 --states 4 --calls` on the Deck) would fail the same way on
  SteamOS (**inferred** from the source; not run on the Deck).
- Running them needs a POSIX path in both harnesses (`mmap` with `MAP_FIXED_NOREPLACE` in place of `VirtualAlloc`) plus
  an x86-64 host. That is new work for the plan: `insn_test.py` is under `third_party/`, which CONTRIBUTING.md says not
  to modify, so it would need a wrapper in `nx2/` or a change upstream. It is a candidate generic fix for T25.
  Recommendation: revise T06 and T08 before they run. Done the same day: new task T08a
  (`docs/plans/tasks/T08a-lifter-tests-linux.md`, change log in `05-roadmap.md`).

## Deviations

- `nx2/test_insn.py` and `nx2/test_leaf.py` are marked **"Windows only (as written)"**, not "Deck only". The reason is
  above.
- `tests/run_all.py` is unchanged (no Mac skip key exists; see "Game-free suite").
