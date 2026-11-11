# T06 · Game-neutral lift driver; first full standalone lift of Raiders (2026-11-10)

`nx2/lift.py` and `nx2/chunks.py` now reach a game's lift-time patches through the per-game layer
(`games/<id>/patches.py`, loaded by `nx2/game.py patches(cfg)`). Ocarina's hooks call upstream's `oot_*` modules
unchanged, in upstream's order. Raiders' hooks do nothing. The generated `hos_image.c` carries the game's id, title and
data folder. The first full standalone lift of Raiders ran on the Mac: 74 code files, 1.34 GiB of C, 110 s.

Every claim is **verified** (the command, file or log line named) unless marked otherwise. The lift log is
`work/lift_standalone.log` (not committed).

## Files

| File | What |
|---|---|
| `games/oot/patches.py` (new) | `install(L, img)`: `oot_wide`, `oot_jitter`, `oot_occlusion`, in that order. `supported(meta, standalone)`: lift.py's old gate. `edit_c(gen, stats, supported, whole)`: `oot_patches.apply(gen, protect_hearts=supported, required=supported and whole)`. The `oot_*` modules are imported inside each hook, as before |
| `games/raiders/patches.py` (new) | the same three hooks, doing nothing (`supported` is False) |
| `nx2/game.py` | `patches(cfg)`: loads `cfg.LIFT_PATCHES` (`games.<id>.patches`) by path, once. `None` gives do-nothing hooks; a name outside `games/` or a missing file stops with `SystemExit` |
| `nx2/lift.py` | selects the game (`_game.select(a.exefs)`, printed as `game: <id> (<module>)`); `patches.install(L, img)` where the three imports were; `chunks.edit_c(..., patches.supported(meta, a.standalone), ..., patches=patches)`; `write_image_c(..., game=cfg)`. Imports no `oot_*` module now. 20 lines changed |
| `nx2/chunks.py` | `edit_c(gen, stats, supported, whole=True, patches=None)`: runs the game's `edit_c`, then `group_marks` (every game). With `patches=None` it uses Ocarina's, so upstream's callers and `tests/test_mark_groups.py` behave as before |
| `nx2/standalone.py` | `c_string(s)` (new); `write_image_c(..., game=None)` writes `hos_game_id`, `hos_game_title`, `hos_game_data_dir` right after `hos_main_build_id`. With `game=None` it selects the game from the exefs |
| `nx2/make_game.py` | `lift_key` also hashes `games/` (1 line; see Decisions) |
| `games/oot/game.py`, `games/raiders/game.py` | the `LIFT_PATCHES` comments ("not written yet" dropped) |
| `tests/test_lift_game_patches.py` (new) | 10 checks, no game files (below) |

## The Ocarina patch modules and how they are reached now

Read in each module's docstring and `install`/`apply`. Addresses are offsets into Ocarina's `main` (`MAIN = 0x80020000`).

| Module | What it patches | How it was gated | Reached now |
|---|---|---|---|
| `oot_wide.py` | Widescreen and ultrawide: C after a set of `main` instructions (`SITES`), so the picture follows the window's shape, 16:9 cameras take its ratio, the HUD stays in the middle 16:9, and the save picture is cut to the middle. Reads host globals that stay 0 in a 16:9 window | Installed in every `--standalone` lift. **Checks each site's instruction word itself** and leaves out sites that differ ("widescreen: main+… holds …: left out") | `games/oot/patches.install`, 1st |
| `oot_jitter.py` | DLSS and FSR camera jitter: C after the projection loads in the view's uniform-buffer fill (`main+0x6bc520`) | The same: every standalone lift, word checked per site | `install`, 2nd |
| `oot_occlusion.py` | Occlusion Off: 6 `ldrb w8, [x0]` sites read 0 when `hos_occlusion_off` is set | The same: every standalone lift, word checked per site | `install`, 3rd |
| `oot_patches.py` (`apply`) | Edits of the written C, matched by exact text: the dynamic-resolution branch, text speed, the fixed path's scale, the movie's frame count, the frame's time at step divides, and the output-size edits (`OUT_EDITS`, 8). With `protect_hearts` also the menu focus and tick hooks, heart protection, flight, flight rotation, the mouse camera and the free camera. It also runs `oot_native_resolution.apply` first | Ran on **every** lift, standalone or not, for every game (`chunks.edit_c`). `protect_hearts` and `required` only for the standalone whole lift of `LIFE_BUILD_ID` (`e0f3ccfa…3348`). The other edits ran anyway, matched by text, and printed `oot_patches: WARNING` for every place they did not find | `games/oot/patches.edit_c`, from `chunks.edit_c`, with `supported` from `games/oot/patches.supported` |

On Raiders, before this change: the three `install`s would each have printed a "left out" line for every site (**inferred**:
their word checks would fail, since the game's code is different). `oot_patches.apply` would then have printed at least
its 4 always-on WARNING lines, the step-divide WARNING, and the output-size WARNING (**inferred** from `apply`'s code;
not run on the unpatched driver). After the change, the log has 0 lines containing `oot_` (below).

`oot_patches.LIFE_BUILD_ID` equals `games/oot/game.py`'s pinned build; a test checks this.

## The standalone lift of Raiders

`.venv/bin/python -I -u nx2/lift.py --standalone --write` with `OOT_WORK=$PWD/work`, `OOT_DUMP` as in `CLAUDE.md`,
under `/usr/bin/time -l`, Apple M2.

| | Value | Planning / expected |
|---|---|---|
| Game selected | `raiders (games.raiders.patches)` | |
| HLE functions in `host/` | 528 | 528 |
| OS-facing imports stubbed | 279 | 279 |
| `host/` HLE names no module has (unused) | 4: `nn::os::SystemEvent` constructor and destructor, `nn::audio::GetTrueRawAudioInputDevice`, `nn::audio::SetVoiceBiquadFilterParameter` | |
| Image | rtld `0x80000000+0x20000`, main `0x80020000+0x4e30000`, subsdk0 `0x84e50000+0xe0000`, sdk `0x84f30000+0x1060000`; 258,033 entries, 0 trampolines, 0 unresolved non-weak imports | same layout |
| Extra entries from ADR / ADRP+ADD | 10,523 code addresses outside 247,176 unwind-covered functions, 71 of them new | |
| Functions discovered | **257,308** (main 212,252, sdk 43,521, subsdk0 1,491, rtld 44) | 258,115 non-standalone |
| Instructions | 18,384,908; untranslated 0; translated 100.0000% | 18,409,608 |
| Undefined encodings reached (UDF, trap as on hardware) | 14,582 sites, 16 distinct words | |
| Jump tables | 987 (926 bounded, 22 bounded by the function, 1 ADR table); BR without a table 0; PLT stubs 9,969 | 987, 0 |
| Chunks | 57 (`code_000`–`code_056`), 9 of them split into 2–6 parts: **74 code files**; boundaries from sizes, saved to `work/image/chunks.txt` | Hookshot's game: 57 chunks |
| Size of C | `code_*.c` 1,443,224,033 bytes (1.34 GiB); `work/sa/gen` 84 files, 1.4 GB (`du -sh`) | ~1.2 GB (inferred in planning) |
| `hos_image.c` | thread hooks `0x85dccc48`, `0x85dccc50`; the three identity strings (below) | |
| Import stubs (`a64_stubs.c`) | 279 | |
| NVN exports (`nvn2_exports.c`) | 22 sdk NVN functions routed to `host/nvn2.c` | 22 |
| Page marks | 157,467 groups share one mark, for 725,195 of 1,212,685 stores through a base register | |
| Interrupt polls | 585,606 loop headers in 96,568 functions | |
| Time | 110 s wall (discovery 30 s); 157 s user, 21 s sys; peak RSS 5.0 GiB (5,379,375,104 bytes) | discovery-only pass: 37 s |

**Why 807 fewer functions:** 258,115 − 257,308 = 807 = 528 + 279, the HLE'd plus the stubbed. A comparison of
`work/image/functions.json` (the planning pass) with `work/sa/image/functions.json` gives 807 entry points gone, 0 new,
all 807 in `sdk`, and the set gone **equals** the 807 `hooks` addresses in `work/sa/image/image.json`. Hooked functions
are not lifted: the host or a stub replaces them. The 24,700 fewer instructions are their bodies.

`hos_image.c` lines 13-15:

```c
const char hos_game_id[] = "raiders";   /* (raiders) games/<id>/game.py */
const char hos_game_title[] = "Raiders Recomp";
const char hos_game_data_dir[] = "raiders-recomp";
```

### Lines in the log that read like warnings

None is an error, and none stopped the lift. Each is upstream's normal report:

- `host/ defines 4 imp_ functions for symbols no module has (unused)`: HLE functions written for other games' SDKs.
  Harmless (they are not hooked).
- `jump tables whose table register is reused before the br: 1`, and in the lifter's report `4 rejected (target outside)`,
  `br to a code constant: 1`, `br with adr candidates: 40`. The coverage table still has `BR without a table 0`. Whether
  the 4 rejected tables' branches are reached at run time is **unknown** (T08a/T09).
- `indirect BR 32154 of 43556` (the lifter's report) and the table's `BR(not table)` 42,567: these are branches
  dispatched through the run-time lookup, as upstream does for every game. Not a fault.
- `unhandled words 16 (14582 sites)`: the UDF/unallocated words above, which trap as on the hardware.
- No line with `WARNING`, `Error`, `Traceback`, `left out` or `oot_` (`grep -c "oot_"` gives 0).

## Decisions

- **The hooks are `install(L, img)`, `supported(meta, standalone)` and `edit_c(gen, stats, supported, whole)`, not the
  task's `edit_c(gen, stats, meta, whole)`.** `tests/test_mark_groups.py` calls `chunks.edit_c(d, st, True)` and
  `chunks.edit_c(d, Counter(), supported, whole)`, passing `supported` itself, so `chunks.edit_c` keeps that argument.
  The build gate moved into Ocarina's `supported()`, comparing against `oot_patches.LIFE_BUILD_ID` as before.
- **`chunks.edit_c` with no `patches` uses Ocarina's.** Upstream's only caller is `lift.py`, and the tests pass none.
  Defaulting to upstream's game keeps them, and `git merge upstream/main`, unchanged.
- **`group_marks` stays in `chunks.edit_c` for every game.** It is the lifter's page-mark grouping, not a game patch.
- **`games/` is now in the lift key** (`make_game.lift_key`). The lift reads `games/<id>/game.py` (the identity in
  `hos_image.c`) and `games/<id>/patches.py`. Without this line, an edit there would reuse a stale lift.
  `lift_key`'s own docstring says "one it reads must be" in the key.
- **`build.py` was not changed.** The task's `build.py:521` (now `:553`, `write_info`) writes `mkw_info.c` for the
  emulator build, not `hos_image.c`. The standalone build's `hos_image.c` comes only from `standalone.write_image_c`.
- **Strings are written with `c_string()`**, which octal-escapes anything outside printable ASCII and also `"` and `\`.
  The three current values are plain ASCII.

## Tests

`tests/test_lift_game_patches.py`, 10 checks, about 0.1 s. The `oot_*` modules are replaced in `sys.modules` by stand-ins
that record their calls:

- Every game's `LIFT_PATCHES` loads, has the three hooks, and loads once. `None` gives do-nothing hooks; bad names stop.
- Ocarina: `install` calls `oot_wide`, `oot_jitter`, `oot_occlusion` in that order with `(L, img)`. `supported` is True
  only for a standalone lift of `LIFE_BUILD_ID`, which equals the pinned build. `edit_c` calls `oot_patches.apply(gen,
  protect_hearts=s, required=s and w)` for all four (s, w).
- Raiders: no stand-in is called, and `supported` is False.
- `chunks.edit_c` with no patches or Ocarina's calls `apply`; with Raiders' it does not; `group_marks` runs once in all
  three cases.
- `lift.py` and `chunks.py` import no `oot_*` module; `lift.py` installs before `L.discover(` and passes the game's gate.
- `write_image_c` writes the three strings for Raiders (given, and selected from a synthetic `main.npdm`) and for Ocarina,
  after `hos_main_build_id`.
- A change to `games/raiders/patches.py` changes `make_game.lift_key`.

## Acceptance criteria

| Command | Result |
|---|---|
| `lift.py --standalone --write \| tail -15` | ends `done (110s)`; no traceback. **Met** |
| `grep -c "oot_" work/lift_standalone.log` | `0`. **Met** |
| `grep -n 'hos_game_id\|…' work/sa/gen/hos_image.c` | lines 13, 14, 15, as above. **Met** |
| `ls work/sa/gen \| wc -l && du -sh work/sa/gen` | `84`, `1.4G` |
| `run_all.py test_lift test_oot test_game_config` | 9 passed, 0 failed, 0 skipped. **Met.** `test_mark_groups` (which reads `chunks.edit_c` and `lift.py`) run separately: passed |
| `run_all.py` (full, with Homebrew tools as in the baseline's reference row) | 314 passed, 9 failed, 9 skipped, 794 s (332 checks; the baseline's reference row is 312 / 9 / 9 of 330). The 2 new checks are T04's `test_game_config` and `test_lift_game_patches`, both passing. The 9 failures are exactly the baseline's 9 (the two ASan hangs, `test_mem_gate`, `test_mem_gate_children`, `test_low_memory_notice`, `test_prof_symbols` and the three temp-symlink ones). **Met: no worse than the baseline** |
| `git status --porcelain \| grep -c 'work/'` | `0` |

Not run, as the task says: `nx2/test_insn.py` and `nx2/test_leaf.py` (Windows-only harnesses; T08a).
