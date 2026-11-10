# T04 · Per-game configuration layer and version pin

**Milestone:** M1 · **Depends on:** T02 · **Machine:** Mac

## Context
Upstream pins one game in code: `nx2/make_game.py:44` `BUILD_ID = "e0f3ccfa"`, the language list at `:55`,
performance file names at `:1305`. Raiders' main build id is `abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5`, so
`--check` rejects it today. This task adds the per-game layer designed in
`docs/plans/03-architecture.md` §3 and makes the version check use it. Later tasks (T05-T07, T16, T24) add
fields; this one creates the mechanism and the identity fields.

## Read first
- `CLAUDE.md`; `docs/plans/03-architecture.md` §3; `docs/plans/02-gap-analysis.md` §1, §13
- `nx2/make_game.py` lines 1-60, `build_id` (`:291`), `check_modules` (`:300`), `check_supported_build`
  (`:311`), `check` (`:378`), the `--language` handling in `parse_args` (`:1174`) and `main` (`:1199`)
- `nx2/kit.py`; `tests/test_builder_status.py`
- For the model only: `refs/Recompia/recomp/games/pkp/config.py`

## Scope
1. `games/__init__.py`, `games/oot/game.py`, `games/raiders/game.py` with the fields `ID`, `TITLE`,
   `PROGRAM_ID`, `BUILDS`, `MODULES`, `SDK`, `LANGUAGES`, `ROMFS_MIN_FILES`, `ROMFS_MIN_BYTES`,
   `ZS_DICTIONARY`, `DATA_DIR`, `EXE`, `LIFT_PATCHES`, `SKIP_PROGRAMS`, `VISUAL_WORKAROUNDS`, `PERF_FILES`
   (values in `03-architecture.md` §3; fields not yet consumed are still defined, with a comment naming the
   task that will use them).
2. `nx2/game.py`: `select(exefs=None)`, `check_build(cfg, build_id)`, `by_id(id)`, `all_ids()`.
3. `make_game.py`: `--check`, `check_supported_build` and the language list go through `nx2/game.py`.
4. Tests.

## Non-goals
- No lift, host or renderer changes (T06, T07). No renaming of binaries. No builder-UI string changes
  (`builder/` keeps its Ocarina text; it is not used by this project until T24).

## Interfaces
```python
# nx2/game.py
def program_id(exefs) -> int            # from exefs/main.npdm (reuse dump.py's npdm() reader, do not copy it)
def select(exefs=None):                 # HOOKSHOT_GAME=<id> wins; else match PROGRAM_ID; else SystemExit with
                                        # "program id %016X is not a supported game (supported: oot, raiders)"
def check_build(cfg, main_build_id):    # -> (True, "This is the version <TITLE> supports (build abb30e2f).")
                                        #    (False, "This is build 12345678. <TITLE> supports build abb30e2f.")
```
- The `@@check ok|bad <text>` protocol on stdout is unchanged (`make_game.py` docstring): builders parse it.
- For Ocarina the texts must stay byte-identical to today's (`tests/test_builder_status.py:31-34` asserts
  them): `games/oot/game.py` sets `TITLE = "Hookshot"`.

## Steps
1. Write the two game modules. For Raiders' `LANGUAGES`, check each code against the language table the
   runtime accepts (`grep -n "en-US" host/*.c nx2/make_game.py`, and the `language.txt` writer in
   `make_game.py`); drop or correct codes the runtime does not know and say so in the report.
2. `nx2/game.py`: import game modules by path with `importlib` so `python -I` works (the script folder is not
   on `sys.path` under `-I`; follow how `make_game.py:45` inserts paths).
3. `make_game.py`: replace the three uses of `BUILD_ID` and the `LANGUAGES` constant with the selected
   config. Keep a module-level `BUILD_ID` name defined (as the Ocarina value) if any test imports it
   (`grep -rn "BUILD_ID\|make_game\.LANGUAGES" tests builder`).
4. Tests: `tests/test_game_config.py`: every `games/*/game.py` has all fields with the right types; build ids
   are 40 lower-case hex digits; `select()` picks by a synthetic `main.npdm` (write 0x400 bytes with the
   program id where `dump.py`'s reader looks) and by `HOOKSHOT_GAME`; `check_build` texts. No dump needed.
5. Run the full game-free suite.

## Pitfalls
- Tests cut functions out of `make_game.py` by text (`AGENTS.md`). After editing, run
  `python -I -B tests/run_all.py make_game builder` first, then the whole suite.
- `PROGRAM_ID` for Ocarina is `0x0400486024DEC000` (`readme.md`); its full build id is
  `e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348` (`docs/design.md` §9).
- Do not print the dump's path or any game text in `@@` lines beyond what upstream prints.

## Acceptance criteria
```bash
.venv/bin/python -I nx2/make_game.py --check --exefs "$OOT_DUMP/exefs"
#   @@check ok This is the version Raiders Recomp supports (build abb30e2f).
mkdir -p work/t04 && cp -R "$OOT_DUMP/exefs" work/t04/exefs && printf 'x' | dd of=work/t04/exefs/main bs=1 seek=64 conv=notrunc 2>/dev/null
.venv/bin/python -I nx2/make_game.py --check --exefs work/t04/exefs    # @@check bad … (then: rm -rf work/t04)
HOOKSHOT_GAME=nope .venv/bin/python -I nx2/make_game.py --check --exefs "$OOT_DUMP/exefs"   # a clear error naming the ids
.venv/bin/python -I -B tests/run_all.py test_game_config test_builder_status
.venv/bin/python -I -B tests/run_all.py     # no worse than docs/plans/reports/mac-test-baseline.md
```
(The copy in `work/t04` is a temporary derived file under the ignored `work/` folder; delete it afterwards.
The original dump is never touched.)

## Report
`docs/plans/reports/T04-game-config.md`: the final field list, the language-code decisions, tests added, and
whether this shape looks acceptable for an upstream PR (it is a candidate; note any upstream test that had
to change).
