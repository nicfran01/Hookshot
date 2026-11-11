# M2 · First Raiders build on the Deck; boot to NVN (T08, 2026-11-10)

**The milestone exit is met.** The first full build on the Steam Deck linked with no compile or link errors. The first
run, `boot1`, went through `_init_libc*`, `nnosInitialize`, `nninitStartup`, the three modules' `DT_INIT` and `nnMain`,
and initialised the native NVN device. No runtime change was needed for any of that. It then stopped on a null font
pointer: the game asked for `nn::pl`'s built-in font data, which only a generated stub answers. That stop is past the
milestone and is recorded for T09/T10.

Every claim is **verified** (the command, file or log line named) unless marked otherwise. Logs are in
`work/t08_build*.log` and `work/runs/boot1/` on the Mac, and `~/raiders/work/build.log` on the Deck (not committed).

## Branch base

T08 depends on T07, which was not on `main`. By the user's choice, `task/T07-host-gating` was merged into `main`
locally (`ae1f568`, `--no-ff`, not pushed), and this branch starts from it.

## Changes

| File | What | Why |
|---|---|---|
| `scripts/deck/build.sh` (lift mode) | `mkdir -p "$OOT_WORK/image"` before the lift | **Build stop 1.** In a new work folder the standalone lift stopped at `nx2/chunks.py:67` (`save`) with `FileNotFoundError: …/work/image/chunks.txt`, after 2:26. `make_game.py:1540` makes that folder before its lift; `build.sh` called `lift.py` directly. On the Mac it never showed, because `work/image` was there from planning's non-standalone lift |
| `scripts/deck/build.sh` (lift mode) | each of the 3 steps under `/usr/bin/time -v`, joined by `&&` | wall time and peak memory per step for this report; a failed step stops the next |
| `scripts/deck/run.sh` | the standalone game's image argument `work/image/image.bin` → `work/sa/image/image.bin` | T03 named the emulator lift's image, which the Deck does not have. The standalone lift writes `work/sa/image/image.bin`, and `make_game.py:1683` ships that file |
| `tests/test_deck_scripts.py` (new) | 3 checks: the run's image path (and that `make_game.py` ships the same), the build's 3 timed steps, that `work/image` is made before the lift, and `bash -n` on every `scripts/deck/*.sh` | |

No change to `host/`, `nx2/` or `gpu/`: the boot needed none.

**Upstream candidate (T25):** `nx2/chunks.py save` could make its folder itself (`os.makedirs(img_dir, exist_ok=True)`), so
`lift.py --standalone --write` works in an empty work folder. Hookshot's own flow always goes through `make_game.py`,
so upstream never meets it (**inferred**).

## Build on the Deck

`scripts/deck/build.sh` (sync, then in the `raiders-build` container: `make_game.py --check`, `lift.py --standalone --write`,
`build.py --standalone --jobs 4`), `HOOKSHOT_JOBS=4`, memory gate on, no hot list, no profile.

| Step | Wall time | Peak RSS (`/usr/bin/time -v`) |
|---|---|---|
| `make_game.py --check` | 0.23 s | 40 MB |
| `lift.py --standalone --write` | 2:58.6 (discovery 52 s; 74 code files written at 177 s) | 5.03 GiB (5,274,776 kB) |
| `build.py --standalone --jobs 4` | 39:24.9 (compile 2,362 s; link 2 s) | 1.68 GiB (1,759,760 kB): the largest single process, i.e. one compiler, not the sum of the 4 (**inferred** from how `time` reports a process tree) |
| Whole `build.sh`, sync included | **2,544 s (42.4 min)** | |

- `build.py`: `466 files, 4 jobs, -O1 -DA64_POLLING -DA64_WRITE_TRACK`; `compiled in 2362s, 0 failed`. The slowest file
  was `code_011_1.c` at 296 s (then `code_008.c` 267 s, `code_012.c` 254 s). CPU 393% (9,186 s user).
- The lift's numbers equal the Mac's (T06): 257,308 functions, 74 code files. The Deck's lift took 177 s against the
  M2's 110 s.
- No compiler was killed and no memory-gate wait was logged. `HOOKSHOT_JOBS=3` was not needed.

| File | Size |
|---|---|
| `~/raiders/work/sa/build/hookshot` | **473,160,408 bytes** (`linked … 451 MB`) |
| `~/raiders/work/sa/build/hookshot_vk.so` | 10,903,720 bytes |

## Boot

`scripts/deck/run.sh boot1 60 -- HOS_TRACE=1 HOS_NO_MOVIES=1`, then `scripts/deck/fetch.sh boot1`. Headless, muted, on the
SteamOS host. Log: 839 lines.

| Order | Log line | Result |
|---|---|---|
| 1 | `boot: image 95 MB at 0x80000000, 9809 MB of memory for the game`; `boot: 14798 MB of memory, 8422 MB of swap` | |
| 2 | `boot: _init_libc0`, `nnosInitialize`, `_init_libc1`, `nninitStartup`, `_init_libc2` | ran |
| 3 | `boot: main DT_INIT`, `subsdk0 DT_INIT`, `sdk DT_INIT` | ran |
| 4 | `boot: nnMain (0x80ff8be0)` (line 30) | reached |
| 5 | `nvn: native NVN layer: 427 procs`, `nvnDeviceGetProcAddress` ×3, `nvnDeviceBuilderSetDefaults`, `nvnDeviceInitialize` | **reached** |
| 6 | `nvn: native NVN device (flags 0): no Switch GPU emulation` (line 49) | **the milestone** |
| 7 | 348 NVN calls through 141 distinct procs: memory pools, queues, textures, samplers, windows, events, buffers, vertex state | **0** `nvn: … is not implemented` lines |
| 8 | `CRASH: exception 0xc0000005 (read 0, …)` on `sead::MainThread`, right after the stub `nn::pl::GetBuiltInFontData` (Ounce) logged its first call | **the stopping point** |

The acceptance grep (`nnMain\|nvnBootstrapLoader\|native NVN device`) gives lines 30 and 49. `nvnBootstrapLoader` itself
is not logged by name. The game reached the device through `nvnDeviceGetProcAddress`, which the bootstrap loader
returns (**inferred** from `host/nvn_native.c:3200`).

### The stopping point

- **What:** guest backtrace `lr 0x808309d0 0x8082fb24 0x836e655c 0x83ebf39c …`, a read at address 0. The stub
  `_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb` logged its first call just
  before, with `lr 0x836e6f18`.
- **Why (verified by disassembly of `work/sa/image/image.bin` with Capstone, on the Mac):** the function that calls it at
  `0x836e6f14` passes a struct on its own stack as the output, does not look at the result, then returns that struct's
  pointer field and stores its size field through its caller's pointer. The generated stub returns 0 and writes
  nothing, so the game gets a stale or null pointer to the system's built-in font (**inferred**: which field is which, from
  the order of the loads).
- **Not fixed here:** the call wants the console's built-in font data, which cannot be shipped. A fix needs a stand-in
  font served in that structure's layout (the runtime already answers the older `nn::pl::GetSharedFont*`:
  `host/nn_applet.c:349-354`), or a failure the game handles. That is bigger than a boot fix and comes after the
  milestone → **T10** (offline/system stubs), with T09's trace report.
- **After the crash the process did not exit:** `timeout` sent SIGTERM at 60 s and SIGKILL 15 s later
  (`run.sh` printed "Killed … stopped at the time limit"). Whether the crash handler waits on purpose (for a dump) or a
  thread keeps the process alive is **unknown** → T09.

### Threads and SVCs before the stop

35 `CreateThread`, 28 `StartThread`, 77 `QueryMemoryInfo`, 73 `AllocateMemoryPages`, 29 `AllocateAddressRegion`,
8 `FreeMemoryPages`, 2 `AllocateMemoryBlock`, 1 `SetMemoryHeapSize`. No unknown SVC, no `svcGetInfo` id the runtime
lacks, and no fault at a thread's start.

## SDK 21.4.4 against the runtime's SDK 22.2.8 tuning

| Point | Finding |
|---|---|
| TLS (`docs/design.md` §9: "the owner handle at TLR+0x110 too (SDK 22)") | 28 guest threads started with no fault at thread start (**verified** by the log). The SDK 22 layout works for SDK 21.4.4's thread entry, as far as this boot goes |
| NVN API version (231.40 reported) | accepted: `nvnDeviceInitialize` went on to 348 more NVN calls. No game-config value for the minor was needed |
| SVCs and `svcGetInfo` | nothing missing before the stop |
| SDK overloads | `nn::pl::GetBuiltInFontData` has two overloads in the imports, `…BuiltInFontDataNx…` and `…BuiltInFontDataOunce…` (`work/standalone_stubbed.txt`); the game calls the `Ounce` one. The runtime implements neither |

## Generated stubs seen (input to T09)

Each logged `[a64] unimplemented import` once, in this order:

| # | Symbol | Caller (`lr`) | Effect here |
|---|---|---|---|
| 1 | `_ZN2nn2ro12ProtectRelroEPKvS2_S2_S2_S2_` (`nn::ro::ProtectRelro`) | `0x80020168` (main's start) | none seen: the boot went on |
| 2 | `_ZN2nn3hid14InitializeJcmsEPvm` (`nn::hid::InitializeJcms`, the Joy-Con 2 mouse) | `0x83dc2dcc` | none seen (T15 plans "no mouse") |
| 3 | `_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb` (`nn::pl::GetBuiltInFontData`, Ounce) | `0x836e6f18` | **the crash** (above) |

## Acceptance criteria

| Command | Result |
|---|---|
| `scripts/deck/build.sh 2>&1 \| tail -5` | ends `/home/deck/raiders/work/sa/build/hookshot` (`build (lift): 2544 s` before it). **Met** |
| `ssh $DECK_HOST 'ls -la …/hookshot …/hookshot_vk.so'` | `473160408` and `10903720` bytes, both `-rwxr-xr-x`, 21:47. **Met** |
| `scripts/deck/run.sh boot1 60 -- HOS_TRACE=1 HOS_NO_MOVIES=1 && scripts/deck/fetch.sh boot1` | ran to the time limit; fetched 2 files. **Met** |
| `grep -n "nnMain\|nvnBootstrapLoader\|native NVN device" …/boot1/hookshot_log.txt` | `30: … boot: nnMain (0x80ff8be0)`, `49: … nvn: native NVN device (flags 0) …`. **Met: the boot reached NVN initialisation** |
| `run_all.py` (full) | 319 passed, 9 failed, 9 skipped, 812 s (337 checks; the baseline's reference row is 312 / 9 / 9 of 330). The 7 new checks are T04's to T08's tests, all passing (`test_deck_scripts` included). The 9 failures are exactly the baseline's 9. **Met: no worse than the baseline** |

`DECK_HOST=deck@steamdeck.local` throughout, since the default name does not resolve (T03).
