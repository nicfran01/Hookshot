# T09a · Built-in font stand-in (`nn::pl::GetBuiltInFontData`) (2026-11-10)

Claims are **verified** (Capstone disassembly of `work/sa/image/image.bin` at base `0x80000000`, a log line or a command)
unless marked **inferred** or **unknown**. Addresses and offsets only: no disassembly, no game strings.

## Research (written before implementing)

### Who calls it

| What | Finding | |
|---|---|---|
| Call sites in `main` | One function, `0x836e69c0`, calls the font functions: the `Ounce` overload once (`0x836e6f14`) and the `Nx` overload twice (`0x836e6eb8`, `0x836e6ef8`). It is the only caller of either. Its PLT stubs are `0x83f71390` (Ounce) and `0x83f71380` (Nx); their GOT slots point at the `sdk` definitions `0x854ca2b0` and `0x854ca670` | verified |
| What `0x836e69c0` is | A callback `(u64 *out_size, const char *name, ?, ctx *)` → data pointer. Its parent (`0x836e6544`-`0x836e6558`, frame `0x836e655c` in the crash backtrace) passes it to the font-container loader `0x8082f9d0`. That loader checks the container's magic `0x58504346` and its version (`>= 0x08000001`), then builds the container's fonts through `0x8082fb60` or `0x80830540` | verified |
| Font type (2nd argument) | Picked by **name**: the callback compares the requested font name with 6 constants and passes type 0-5. In order, the six names are the system fonts of the public shared-font enum: standard, Chinese simplified, Chinese simplified extension, Chinese traditional, Korean, Nintendo extension. Any other name is loaded from the game's own files through `ctx` (vtable `+0x30`), without `nn::pl` | verified (the mapping); inferred (the order matches the public enum) |
| Which types this game requests | **unknown** before the fix: the stub logs only its first call. After the fix the HLE logs each type once (see Deck run) | |
| 3rd argument (`bool`) | `0` at all three call sites (`mov w2, wzr`) | verified |
| Result checked? | Ounce: no, it is called once and the result is ignored. Nx: yes, it polls (`tbnz w0, #0`), sleeping in between (`nn::os::ConvertToTimeSpan`, `nn::os::SleepThread`), until bit 0 is set | verified |
| Ounce or Nx | A byte at `[ctx]` picks Nx when it is 1. Nx mode also needs `RequestLoadNxFont`: its only caller, `0x83ebed68`, gives it a 0x1300000-byte buffer (align 0x1000) when a config byte at `[x1+0x1e]` is 1. No trace has called `RequestLoadNxFont`, and the crashing call was the Ounce one, so this game runs in Ounce mode | verified (the code); inferred (the mode) |

### The struct (from the SDK's own implementations)

Both `sdk` implementations (`0x854ca2b0` Ounce, `0x854ca670` Nx) work the same way. They ask the `pl` service for an
"available" byte and a u64 (vtable `+0x60` and `+0x20`), then write the struct only when the byte is 1. The value returned
in `w0` is that byte.

| Offset | Size | Meaning | |
|---|---|---|---|
| `+0x00` | 1 | Low byte of the service's u64 | verified written; meaning **unknown**; not read by the game's caller (verified) |
| `+0x01` | 1 | Bit 8 of the service's u64 | the same |
| `+0x02`-`+0x07` | 6 | not written | verified |
| `+0x08` | 8 | **Data pointer**: shared-memory base (Ounce) or the `RequestLoadNxFont` buffer (Nx), plus the u64's high 32 bits | verified; the caller returns it (`ldr x0, [sp, #0x18]`) |
| `+0x10` | 8 | **Size** (a u32 from the service, zero-extended) | verified; the caller stores it through `out_size` |
| Total | 0x18 | | verified (nothing past `+0x10` is written) |

Return type: `bool` ("available"). When the byte is not 1, the struct is left as it was: the game's caller then reads
uninitialised stack. That is the null read of every run so far.

### Format the consumer expects

- `0x80830540` calls the callback at `0x80830890` and keeps the pointer in `x21` and the size in a table.
- It checks that the font name ends in a 6-character extension (`0x808309c0`-`0x808309d4`).
- At `0x808309d8` it reads the first 4 bytes at the pointer and accepts `0x00010000` (TrueType), `ttcf` (TrueType
  collection) or `OTTO` (CFF OpenType) as kind 0. Any other value is kind 2: the obfuscated system container
  (**inferred**). A second extension check (`0x80830a0c` onward) does the same.
- So a **plain font file** is a valid answer. The crash is this read: `x21` is the stale field (`CRASH: … read 0`,
  `lr 0x808309d0`) (verified by the addresses; M2-boot.md has the backtrace).
- Where kind 0 data goes next (likely the 24 imported `nn::fontll::ScalableFontEngine` functions) was not followed: the
  signature check is enough to pick the rung (**inferred**: kind 0 is used as is).

### `RequestLoadNxFont(void *, size_t)` (`sdk` `0x854ca570`)

It makes a 0x1300000-byte transfer memory over the game's buffer, sends it to the `pl` service (vtable `+0x70`), stores the
buffer as the Nx base (`0x85e87d20`), and returns nothing. A failure result aborts (verified).

## Decision: rung 1

The consumer takes a whole font file by its sfnt signature, so `nn_pl_font.c` serves the embedded OFL TrueType file:
`third_party/fonts/libertinus/LibertinusSans-Regular.ttf`, 424,224 bytes, starting `00 01 00 00`.

- Both overloads, every type: write `+0x00`/`+0x01` as 0 and the pointer and size at `+0x08`/`+0x10` (the whole 0x18-byte
  struct is written), then return `true`.
- `RequestLoadNxFont`: nothing to load, logged once. If a game does use the Nx mode, its Nx answers point at the same copy,
  not into its buffer (the pointer is all the caller uses: verified for this caller).
- The copy is made once, in `hos_sys_alloc` memory (zeroed, page-aligned, never freed), and reused.
- `HOS_BUILTIN_FONT=<.ttf/.otf path>` replaces it, from the environment only.

## Implementation

| File | What |
|---|---|
| `host/nn_pl_font.c` (new) | The three `HLE()`s. Both overloads fill the whole 0x18-byte struct (`+0x00`-`+0x07` zero, pointer, size) and answer `true`; each overload and type is logged once. `RequestLoadNxFont` logs once and touches nothing. The font is copied once (under a lock) into `hos_sys_alloc` memory, page-aligned, never moved or freed. `HOS_BUILTIN_FONT` is read with `getenv` only; an unreadable file falls back to the included font, with a log line |
| `nx2/host_font.py` (new) | Writes `gen/host_font.c` (`hos_builtin_font`, `hos_builtin_font_size`) from `LibertinusSans-Regular.ttf`, as `nx2/ui_fonts.py` does for the renderer. It rewrites the file only when it changes |
| `nx2/build.py` | `import host_font` and one line that adds the generated file to the runtime's sources, marked `(raiders)`. It is on the shared standalone path, so Linux and Windows both get it. `host/*.c` files are found by `os.listdir`, so `nn_pl_font.c` itself needs no line |
| `third_party/fonts/PROVENANCE.md` | The runtime's use is added, marked `(raiders)`. The AppImage already ships `third_party/fonts` whole (`scripts/linux/appimage.sh:59`) |
| `tests/test_nn_pl_font.py` (new) | Compiles `nn_pl_font.c` and the generated font with stand-in helpers (`-Wall -Werror`), in the style of `tests/test_audio_in.py`. 9 checks: the generated size; the TrueType signature; an unchanged file is not rewritten; the struct is filled, nothing past `+0x18` is touched and `true` comes back; one copy for every overload and type; logs once each; a null struct; `RequestLoadNxFont` leaves the buffer alone; the served bytes equal the file's; `HOS_BUILTIN_FONT` served, and the fallback; `build.py` and `PROVENANCE.md` wired |
| `docs/plans/tasks/T25-upstream-prs.md` | Candidate 10: this stand-in |

## Deck run

| Step | Result |
|---|---|
| `scripts/deck/build.sh` | **241 s** in all: lift 230 s (`3:50.74`, peak RSS 5.2 GB), compile `4s, 0 failed`, link `451 MB`. The lift now says `276 import stubs` (T08: 279: the three `nn::pl` names are now `HLE`s). Only the changed objects recompiled: the lifted code's objects were reused, against the task's estimate of a 45-minute relift (verified: `work/t09a_build.log`) |
| `scripts/deck/run.sh font1 180 -- HOS_NO_MOVIES=1 HOS_TRACE=1 HOS_HOSTCALL_STATS=1 HOS_STATS_AFTER=100 HOS_LOG_SYNC=1` | Ran to the time limit (`Killed … stopped at the time limit`); 37 screenshots; 38,070-line log |
| `scripts/deck/fetch.sh font1` | 39 files to `work/runs/font1/` |

What the log says about the font (verified):

- `pl: built-in fonts answered with the included font (424224 bytes, signature 00010000)`
- `pl: GetBuiltInFontData(Ounce, type 0, 0) -> the stand-in font (lr 0x836e6f18)`: **one** request, Ounce overload,
  type 0 (standard), from the caller the research found. No Nx call and no `RequestLoadNxFont`, which confirms the
  Ounce-mode inference.

## Where the boot is now

- **Past the old stop.** There is no `CRASH` line (the old stop was line 819). The first present is at line **5953**,
  then about 60 fps (`vi: … frames presented (60.0 fps …)`) until the time limit.
- **Text.** The screenshots from frame 3,000 to 11,100 (kept in `work/runs/font1/shots/`) show the same interactive menu,
  waiting for input in a headless run. Every text element on it is **readable**, and no missing-glyph boxes were seen.
  Which glyphs come from the stand-in and which from the game's own fonts (the container mixes both) is **unknown**.
- **Coverage of the stand-in** (by design): Libertinus Sans covers Latin, Greek and Cyrillic. It has no CJK, Korean
  or system button symbols (types 1-5). Only type 0 was requested in this run (English, `oe: language en-US`).
- **The new trace** (`M3-trace.md`, regenerated and re-annotated): 20 generated stubs called, **0 blocking**, 5 wrong
  answers (T18 ×2, T10 Part B ×1, T13 ×2), 0 unimplemented NVN procs. There are 3.0 `WaitEvent` calls per present, and
  `nvnTextureReadTexels` runs 12,178 times by 100 s: a CPU texture read-back before gameplay, a lead for T17.
- `nn::pl::GetBuiltInFontData` is now implemented here (owner T09a), so it no longer shows as a stub.

## Upstream

`nn_pl_font.c` is generic: no game id check, and the struct layout is the SDK's own. It is added to T25's list as
candidate 10. The same answer works for any Switch 2 SDK game that draws text with the system fonts (**inferred**: checked
on this game only).

## Deviations

1. **The first Deck build failed.** `scripts/deck/sync.sh` sends only what `git ls-files` lists, so the three new
   untracked files did not reach the Deck. The build stopped at `ModuleNotFoundError: No module named 'host_font'` after
   240 s, and its lift had run without the new `HLE()`s. Fix: the new files were staged by path (`git add`), then the
   same build ran again. No script was changed.
2. **The relift cost 241 s, not ~45 min.** The lifted code's objects were reused. Only the stubs file, the hooks and the
   runtime were rebuilt (verified: `compiled in 4s`).
3. **`scripts/trace_report.py` §5 ratio.** For a run that outlives its count table, the generated "WaitEvent per present"
   (2.72) mixes two time bases. `M3-trace.md` gives the consistent 3.00 from the 100 s table, by hand. The script is
   T09's and is left unchanged here.
4. **`work/standalone_stubbed.txt` regenerated** (`spikes/standalone_summary.py`): 276 names, no `nn::pl` entry. This
   keeps the report's "of the N stubbed imports" true.
5. **Grep count.** The acceptance `grep -c "GetBuiltInFontData"` prints **1**, not 0. The match is the runtime's own new
   log line (`pl: GetBuiltInFontData(Ounce, type 0, 0) -> the stand-in font`), not a stub line. The criterion's stated
   aim ("0 'unimplemented import' lines for it") holds: `grep -c "unimplemented import.*GetBuiltInFontData"` prints 0.

## Acceptance criteria

| Command | Result |
|---|---|
| `.venv/bin/python -I -B tests/run_all.py test_nn_pl_font` | `1 passed, 0 failed, 0 skipped`. **Met** |
| `scripts/deck/build.sh && scripts/deck/run.sh font1 180 -- … && scripts/deck/fetch.sh font1` | Build `/home/deck/raiders/work/sa/build/hookshot` (241 s); run to the time limit; 39 files fetched. **Met** (second attempt: Deviation 1) |
| `grep -c "GetBuiltInFontData" work/runs/font1/hookshot_log.txt` | `1`: the HLE's own log line; `unimplemented import` lines for it: `0`. **Met in intent** (Deviation 5) |
| `grep -n "CRASH" work/runs/font1/hookshot_log.txt \| head -3` | no lines. **Met** |
| `.venv/bin/python -I scripts/trace_report.py work/runs/font1/hookshot_log.txt \| head -12` | `end: no crash or fatal error logged (time limit or exit); first present: line 5953`. **Met: past line 819** |
| `.venv/bin/python -I -B tests/run_all.py` | With `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`: **321 passed, 9 failed, 9 skipped** of 339 in 771 s (before: 320 / 9 / 9 of 338). The new check passes. The 9 failures are exactly the baseline's 9 (`mac-test-baseline.md`). **Met** |
| `git status --porcelain \| grep -c 'work/'` | `0`. **Met** |
