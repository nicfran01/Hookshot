# T09a · Built-in font stand-in (`nn::pl::GetBuiltInFontData`)

**Milestone:** M3 · **Depends on:** T09 **merged into `main`** (this task needs `scripts/trace_report.py` and
`docs/plans/reports/M3-trace.md`; the merge is the user's action) · **Machine:** Mac driving the Deck

Added 2026-11-10 from `docs/plans/reports/BLOCKER-T10-2026-11-10.md`.

## Context
Every run so far stops at the same place: log line 819, a null read on `sead::MainThread` right after the
generated stub for `nn::pl::GetBuiltInFontData(BuiltInFontDataOunce*, BuiltInFontTypeOunce, bool)` logs its
first call (`M2-boot.md` "The stopping point"; `M3-trace.md` §1 row 3) **[verified there]**. No submit and no
present happen before it. The caller (at guest `0x836e6f14`) passes a struct on its own stack, ignores the
result, returns the struct's pointer field and stores its size field **[verified by disassembly in M2;
which field is which is inferred]**. So a failure result does not help: the game needs a pointer to font data.

This is the only blocking call the trace found, and no task owned `nn::pl`. The console's built-in font is
system data and cannot be shipped or read from the dump. The repository already carries fonts under the SIL
Open Font License (`third_party/fonts/libertinus/`, `OFL.txt`), and the build already embeds them into the
renderer (`nx2/ui_fonts.py` → a generated C++ file). The runtime answers the older
`nn::pl::GetSharedFont*` with an empty font marked loaded (`host/nn_applet.c:347-354`).

What format the game expects is **unknown**: the struct's full layout, the enum's values, and whether the
consumer wants a plain TrueType/OpenType file or a container. `main` imports 24
`nn::fontll::ScalableFontEngine` functions (`grep 2nn6fontll work/imports_raiders.txt`), which is the likely
consumer **[inferred]**.

## Read first
- `CLAUDE.md`; `docs/plans/reports/BLOCKER-T10-2026-11-10.md`; `docs/plans/reports/M2-boot.md` ("The
  stopping point"); `docs/plans/reports/M3-trace.md` §1
- `host/nn_applet.c:340-360` (the shared-font answer and `hos_sys_alloc`); `host/hos.h` (the `HLE`, `RET`,
  argument and guest-pointer helpers)
- `nx2/ui_fonts.py`; `nx2/build.py:870-885` (how the generated font file joins the build);
  `third_party/fonts/PROVENANCE.md`
- `nx2/standalone.py` docstring (an `HLE()` is picked up at lift time)
- `grep "2nn2pl" work/standalone_stubbed.txt` (three names: the `Ounce` and `Nx` overloads of
  `GetBuiltInFontData`, and `RequestLoadNxFont`)

## Scope
1. **Research (on the Mac, no Deck needed):** the layout of `BuiltInFontDataOunce` as the game uses it, the
   font-type values the game passes, and what the consumer does with the pointer and size.
2. `host/nn_pl_font.c` (new): `HLE()` for both `GetBuiltInFontData` overloads and `RequestLoadNxFont`,
   serving a stand-in font in guest memory.
3. A Deck run showing the boot goes past the old stop, and a regenerated trace report.

## Non-goals
- Shipping, extracting or downloading the console's fonts, from anywhere. No firmware files.
- Correct glyphs for every language or the system's button symbols: a stand-in may show missing-glyph boxes
  for characters it lacks. Record what is missing; do not source more fonts in this task.
- Any other stub the new trace reveals (those go to their owners: see T10's "Ownership" table).
- Changing `host/nn_applet.c`'s shared-font answer.

## Interfaces
```c
/* host/nn_pl_font.c (generic: no game id check) */
HLE(_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb)  /* fills the struct */
HLE(_ZN2nn2pl18GetBuiltInFontDataEPNS0_17BuiltInFontDataNxENS0_17BuiltInFontTypeNxEb)
HLE(_ZN2nn2pl17RequestLoadNxFontEPvm)
```
- Font bytes: a generated C file of the build's own, made the way `nx2/ui_fonts.py` makes the renderer's
  (extend that script with a C output for the host, or add `nx2/host_font.py` beside it). One regular face is
  enough. Copied once into guest memory from `hos_sys_alloc`, page-aligned, and reused for every call.
- Optional override, only if it costs a few lines: `HOS_BUILTIN_FONT=<path to a .ttf or .otf>` read from the
  environment (path values are not accepted from `hookshot_env.txt`: `readme.md` "Switches for testing").
  Whatever file the user points it at is theirs to supply; the code only reads a font file.

## Steps
1. Research, with Capstone on `work/sa/image/image.bin` (base `0x80000000`), as M2 did:
   - The caller at `0x836e6f14`: every field of the struct it reads after the call, and their offsets.
   - Up the backtrace (`0x836e655c`, `0x8082fb24`, `0x808309d0`): where the pointer and size go. Follow until
     a call into `nn::fontll` (or another parser) takes them; note the function and which argument.
   - The second argument: which enum values are passed, from how many call sites
     (`grep` the lifted C on the Deck for the stub's symbol, or search the image for `bl` to its PLT entry).
   - The third argument (`bool`) and whether any caller checks the result.
   - If `sdk` contains a real implementation of the `Nx` overload's consumers, compare its struct handling.
   Write the findings into the report **before** implementing: fields (offset, size, meaning, verified or
   inferred), expected format, font types requested. Do not paste disassembly; offsets and one-line
   descriptions only.
2. Decide the answer by this ladder and say which rung was used:
   1. The consumer is a scalable font engine taking a whole font file → serve the embedded OFL TrueType file
      for every requested type (pointer, size, and any other field the game reads).
   2. The consumer needs a container or table the stand-in cannot satisfy → serve a minimal valid answer the
      engine skips (the empty-font approach the runtime uses for shared fonts), if the research shows the
      game tolerates it.
   3. Neither → stop and write a blocker report with the research.
3. Implement. Pitfalls:
   - An `HLE()` changes the lift key: expect a full relift on the Deck (T08 measured the lift at 2,544 s).
     Get all three functions in before the first Deck build.
   - Write every field the research found the game reads, and zero the rest of the struct: the caller's
     struct is uninitialised stack.
   - The font must stay mapped and unmoved for the process's life.
   - Add the new file to the host sources in `nx2/build.py` for Linux and Windows; keep
     `third_party/fonts`' licence note true (`PROVENANCE.md` lists where the fonts are used: add the runtime).
4. Test without the game: `tests/test_nn_pl_font.py` in upstream's style (cut the `HLE` out by text, compile
   with stub helpers, call it, assert the struct's pointer is non-null, the size equals the embedded file's,
   and the bytes start with a TrueType/OpenType signature).
5. Deck: `scripts/deck/sync.sh && scripts/deck/build.sh`, then
   `scripts/deck/run.sh font1 180 -- HOS_NO_MOVIES=1 HOS_TRACE=1 HOS_HOSTCALL_STATS=1 HOS_STATS_AFTER=100 HOS_LOG_SYNC=1`
   (T09's trace switches) and `scripts/deck/fetch.sh font1`.
6. Regenerate the trace report from the new log:
   `python -I scripts/trace_report.py work/runs/font1/hookshot_log.txt --md docs/plans/reports/M3-trace.md`.
   Classify the new rows as T09 did (safe / wrong answer / blocking) and set each Owner cell from T10's
   "Ownership" table. Change row 3's owner from T10 to T09a and its class to implemented.
7. If the game now renders text before the next stop, describe what it looks like (from a screenshot kept in
   `work/`): readable, boxes, nothing.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py test_nn_pl_font
scripts/deck/build.sh && scripts/deck/run.sh font1 180 -- HOS_NO_MOVIES=1 HOS_TRACE=1 HOS_HOSTCALL_STATS=1 HOS_STATS_AFTER=100 HOS_LOG_SYNC=1 \
  && scripts/deck/fetch.sh font1
grep -c "GetBuiltInFontData" work/runs/font1/hookshot_log.txt        # 0 "unimplemented import" lines for it
grep -n "CRASH" work/runs/font1/hookshot_log.txt | head -3           # none, or a different backtrace from 0x808309d0 0x8082fb24 0x836e655c
.venv/bin/python -I scripts/trace_report.py work/runs/font1/hookshot_log.txt | head -12   # "end:" is past the old line 819 stop
.venv/bin/python -I -B tests/run_all.py                              # no worse than the baseline
git status --porcelain | grep -c 'work/'                             # 0
```
The task is complete when the boot passes the font call. Reaching a present is not required.

## Report
`docs/plans/reports/T09a-font.md`: the research table (struct fields, format, types requested, consumer),
the rung used and why, what text looks like, where the boot stops now (first lines of the new trace summary),
and whether `nn_pl_font.c` is an upstream candidate (it is generic: add it to T25's list if so).
`docs/plans/reports/M3-trace.md` regenerated and re-annotated.
