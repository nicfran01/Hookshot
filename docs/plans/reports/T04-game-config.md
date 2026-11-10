# T04 · Per-game configuration layer (2026-11-10)

`make_game.py --check` now takes the version pin, the game's title and its language list from the game the dump is,
through `nx2/game.py` and `games/<id>/game.py`. Ocarina selects to upstream's values, and its sentences are unchanged
byte for byte.

Every claim is **verified** (the command or file named) unless marked otherwise.

## Files

| File | What |
|---|---|
| `games/__init__.py` (new) | the package; docstring only |
| `games/oot/game.py` (new) | upstream's game, upstream's values |
| `games/raiders/game.py` (new) | Splatoon Raiders, base game |
| `nx2/game.py` (new) | `select(exefs=None)`, `check_build(cfg, build_id)`, `by_id(id)`, `all_ids()`, `program_id(exefs)`, `pinned(cfg)` |
| `nx2/npdm.py` (new) | `npdm()`, moved out of `nx2/dump.py` unchanged (decision below) |
| `nx2/dump.py` | the function replaced by `from npdm import npdm`, `(raiders)`-marked; `dump.py --dump` prints the same output before and after on the dump |
| `nx2/make_game.py` | `select_game()`; `check_supported_build`, `check`, `folder_language` and the `language.txt` writer go through the game; 21 lines added, 8 removed, all `(raiders)`-marked |
| `tests/test_game_config.py` (new) | 9 checks, standard library only |

## Fields

Each `games/<id>/game.py` has the 16 fields of `03-architecture.md` §3. Fields not used yet name the task that will
use them in a comment.

| Field | Type | `oot` | `raiders` | Used by |
|---|---|---|---|---|
| `ID` | str | `oot` | `raiders` | T04 |
| `TITLE` | str | `Hookshot` | `Raiders Recomp` | T04 (the check's sentences) |
| `PROGRAM_ID` | int | `0x0400486024DEC000` | `0x0400380020056000` | T04 (`select`) |
| `BUILDS` | dict, 40-digit lower-case hex → version | `e0f3ccfa…3348`: `update v131072` | `abb30e2f…a4f5`: `1.0.0 (base)` | T04 |
| `MODULES` | tuple | rtld, main, subsdk0, sdk | rtld, main, subsdk0, sdk | T06 |
| `SDK` | str | `22.2.8` | `21.4.4` | (record) |
| `LANGUAGES` | list of (code, name) | upstream's 16 | 13 (below) | T04 (`language.txt`), T05 |
| `ROMFS_MIN_FILES` | int or None | None | 46,000 | T05 |
| `ROMFS_MIN_BYTES` | int or None | None | 13,600,000,000 | T05 |
| `ZS_DICTIONARY` | str or None | `Pack/ZsDic.pack.zs` | None | T05 |
| `DATA_DIR` | str | `hookshot` | `raiders-recomp` | T16 |
| `EXE` | str | `hookshot` | `hookshot` | T24 |
| `LIFT_PATCHES` | str or None | `games.oot.patches` | `games.raiders.patches` | T06 (modules not written yet) |
| `SKIP_PROGRAMS` | tuple | `53509044401d78d2` | () | T07 |
| `VISUAL_WORKAROUNDS` | (fog, exposure) or None | (0.08, 1.0) | None | T07 |
| `PERF_FILES` | tuple | hot_funcs.txt, hot_order.txt, hookshot_pieces.prof, hookshot.res | hot_funcs.txt, hot_order.txt, raiders_pieces.prof | T22 |

## Decisions

- **Languages: all 13 of Raiders' codes kept.** Each of `ja, en-US, es-419, fr-CA, en-GB, es, fr, de, it, nl, ko,
  zh-Hans, zh-Hant` is in the runtime's table (`host/nn_applet.c`, `languages[]`, 16 codes). None was dropped or
  corrected. The runtime's `pt-BR`, `pl` and `ru` are not among the game's (the region-language mapping is from planning,
  `02-gap-analysis.md` §1). `tests/test_game_config.py` checks every game's codes against that table, so a later edit
  to either side is caught.
- **The build check compares the first 8 hex digits**, as upstream always has (`bid.startswith("e0f3ccfa")`).
  `BUILDS` keeps the full 40-digit ids, but `tests/test_make_game_cache.py` makes NSO headers with only those 4 bytes
  set, so a 40-digit comparison would have failed upstream's test.
- **`select()` when there is no `main.npdm`:** it matches main's build id against every game's `BUILDS`, else falls
  back to upstream's game (`oot`). So an exefs of a bare `main` (upstream's test fixtures) is checked against Ocarina
  with upstream's sentence, as before. An npdm with an unknown program id stops: `program id %016X is not a supported
  game (supported: oot, raiders)`. In `make_game.py` that becomes an `@@error` line, so builders show it.
- **The npdm reader was moved, not imported or copied** (the user's choice). `dump.py` imports numpy and a64-kit's
  `nso` (lz4) at load. Importing it would have made `--check` and every test of the layer need two packages upstream's
  CI does not install (`source-regressions.yml` installs only `zstandard`, and runs `--strict`). `nx2/npdm.py` holds the
  function byte for byte. It keeps upstream's `open(path, "rb").read()`, which leaves the file for the collector to
  close (a `ResourceWarning` under `-W error`); it was left unchanged on purpose.
- **`make_game.BUILD_ID` and `make_game.LANGUAGES` stay Ocarina's.** `builder/linux/hookshot_builder.py` imports both
  (its line 29) and the builders are out of scope until T24. `tests/test_game_config.py` checks that `games/oot` equals
  them.
- **`folder_language()` (`--update`)** accepts a code from any game's list: the folder's own game wrote it.
- **Ocarina's `VISUAL_WORKAROUNDS` is (0.08, 1.0), not the plan's (0.25, 0.65).** Upstream changed `oot_visual()`
  (`gpu/vk/vk_shader.cpp` lines 944-948): off unless `RX_VK_OOT_VISUAL=1`, with fog 0.08 and exposure 1.0.
- **`ROMFS_MIN_*` for Ocarina are None:** upstream has no such floor; T05 decides.

## Tests

`tests/test_game_config.py` (9 checks, about 0.1 s): every game has the 16 fields with the right types, 40-digit build
ids, unique program ids and language codes; the codes are the runtime's; Ocarina equals `make_game.BUILD_ID` and
`LANGUAGES`; `select()` by a synthetic `main.npdm` (0x400 bytes), by `HOOKSHOT_GAME`, by build id without an npdm, and
the two errors; `check_build`'s four sentences; and `make_game.check()`'s `@@check` and `@@error` lines (with the
compiler probes stubbed). It passes under a Python with no numpy (Homebrew's `python3`), the way CI runs.

No upstream test had to change. The checks that read `make_game.py` by text or run it pass:
`run_all.py make_game builder cpu_target dump` → 12 passed. The one failure there,
`tests/test_builder_dlss_update.py`, is a .NET fixture on upstream's Linux skip list; naming "builder" runs it anyway,
and it does not read `make_game.py`.

## Acceptance

| Command | Result |
|---|---|
| `make_game.py --check --exefs "$OOT_DUMP/exefs"` | `@@check ok This is the version Raiders Recomp supports (build abb30e2f).` |
| the same on `work/t04/exefs`, `main`'s byte 64 changed to `x` | `@@check bad This is build 78b30e2f. Raiders Recomp supports build abb30e2f.` (then `rm -rf work/t04`) |
| `HOOKSHOT_GAME=nope make_game.py --check ...` | `@@error HOOKSHOT_GAME=nope is not a supported game (supported: oot, raiders)`, exit 1 |
| `run_all.py test_game_config test_builder_status` | 2 passed |
| `run_all.py` (whole suite, with the baseline's Homebrew header variables) | 313 passed, 9 failed, 9 skipped in 716 s: the baseline's 312 and the new check; the 9 failures are the baseline's, the same names (`mac-test-baseline.md`). No worse |

## Upstream PR

The shape would fit an upstream PR (`T25` candidate 3): plain-data modules, one loader, and the selected game's
values only where the build already used constants; no upstream test changed. Two things to settle with the maintainer
first, in an issue, as T25 plans: whether they want a `games/` folder at all, and the npdm move. The move is a refactor
of `dump.py` they may prefer done another way (lazy imports in `dump.py` would do as well).
