# T06 · Game-neutral lift driver; first full standalone lift of Raiders

**Milestone:** M2 · **Depends on:** T04 · **Machine:** Mac

## Context
`nx2/lift.py --standalone` installs Ocarina's lift-time patches for every game: `lift.py:162-167` imports
`oot_wide`, `oot_jitter`, `oot_occlusion` and calls `install(L, img)`; `lift.py:186-188` passes
`main_build == oot_patches.LIFE_BUILD_ID` to `chunks.edit_c` (`chunks.py:302` imports `oot_patches`). Those
patches insert C at addresses found in Ocarina's `main`. On Raiders they must not run. Planning verified
only the non-standalone discovery and coverage pass (258,115 functions, 100% translated,
`spikes/README.md`); the standalone lift with `--write` has not been run.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §2; `docs/plans/03-architecture.md` §3
- `nx2/lift.py` (all 204 lines), `nx2/chunks.py` `edit_c` and its callers, `nx2/standalone.py` docstring and
  `hle_set`, `gen_stubs`, `write_image_c`, `nvn_exports`
- The first 40 lines of each of `nx2/oot_wide.py`, `oot_jitter.py`, `oot_occlusion.py`, `oot_patches.py`:
  what each `install` hooks and whether it checks the build id itself
- `docs/design.md` §7 (testing)

## Scope
1. `games/oot/patches.py` and `games/raiders/patches.py`, each exposing `install(L, img)` and
   `edit_c(gen, stats, meta)` hooks; Ocarina's wraps the existing `oot_*` modules unchanged, Raiders' does
   nothing.
2. `lift.py` and `chunks.py` call the selected game's hooks instead of importing `oot_*` directly.
3. Run the full standalone lift for Raiders on the Mac and record the numbers.
4. `standalone.py`/`build.py`: write `hos_game_id`, `hos_game_title`, `hos_game_data_dir` into the generated
   `hos_image.c` beside the existing image base and build id (consumed by T07).

## Non-goals
- No compile or link (T08, on the Deck). No changes to the `oot_*.py` files themselves. No new lift patches
  for Raiders.

## Interfaces
```python
# games/<id>/patches.py
def install(L, img): ...                       # before discovery; add hooks to the lifter
def edit_c(gen, stats, meta, whole): ...       # after the C is written; Ocarina's forwards to chunks.edit_c's
                                               # existing behaviour, gated on its build id as today
```
Generated C (`work/sa/gen/hos_image.c`), new lines:
```c
const char hos_game_id[] = "raiders";
const char hos_game_title[] = "Raiders Recomp";
const char hos_game_data_dir[] = "raiders-recomp";
```

## Steps
1. Read the four `oot_*` modules and write down, for the report, what each patches and how it is gated today.
2. Add the patch modules and the two call sites. With Ocarina selected the lift must behave exactly as
   before: the same modules installed in the same order, the same `edit_c` argument.
   - Pitfall: there is no Ocarina dump to diff against. Protect equivalence with a test that monkeypatches
     the `oot_*` modules and asserts the call order and arguments (`tests/test_lift_game_patches.py`).
   - Pitfall: `tests/test_lift_cache.py` and `tests/test_oot_*.py` read `lift.py` and the `oot_*` files by
     text. Run them first after editing.
3. Emit the game identity into `hos_image.c`. Find where `mkw_image_base` and `mkw_main_build_id` are written
   (`build.py:521` and `standalone.write_image_c`) and add the three strings in the same place.
4. Run, with `OOT_WORK` and `OOT_DUMP` set:
   `.venv/bin/python -I -u nx2/lift.py --standalone --write 2>&1 | tee work/lift_standalone.log`.
   Expected lines (compare with the planning numbers): "standalone: 528 HLE functions in host/, 279 OS-facing
   imports stubbed", the discovery and coverage table, "standalone: hos_image.c …", "nvn2_exports.c (22 sdk
   NVN functions …)", "wrote N code files".
   - This writes about 1.2 GB of lifted C to `work/sa/gen` on the Mac. It is game code: it stays there.
   - If discovery differs from the non-standalone numbers (258,115 functions), explain why (hooked functions
     are not lifted).
5. Do not run `nx2/test_insn.py` or `nx2/test_leaf.py` here: T02 found both harnesses Windows only and the
   Mac arm64 (`docs/plans/reports/mac-test-baseline.md`). T08a ports them to Linux and runs them on the Deck.
   (Revised 2026-11-10.)

## Acceptance criteria
```bash
.venv/bin/python -I -u nx2/lift.py --standalone --write 2>&1 | tail -15     # ends "done (…s)", no traceback
grep -c "oot_" work/lift_standalone.log                                     # 0: no Ocarina patch ran
grep -n 'hos_game_id\|hos_game_title\|hos_game_data_dir' work/sa/gen/hos_image.c
ls work/sa/gen | wc -l && du -sh work/sa/gen
.venv/bin/python -I -B tests/run_all.py test_lift test_oot test_game_config
.venv/bin/python -I -B tests/run_all.py                                     # no worse than the baseline
git status --porcelain | grep -c 'work/'                                    # 0
```

## Report
`docs/plans/reports/T06-lift.md`: what each Ocarina patch module does and how it is now reached; the
standalone lift's numbers for Raiders (functions, chunks, size of C, HLE and stub counts, NVN exports,
polls, time); anything in the lift log that looks like a warning.
