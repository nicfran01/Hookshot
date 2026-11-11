# T05 · Ingestion fixes: optional zstd dictionary, romfs floor (2026-11-10)

The three readers of `Pack/ZsDic.pack.zs` now treat a missing file as "no dictionary, plain zstd". With the file present
they behave as before. A new `nx2/romfs_check.py` compares a romfs against the game's file and byte floors, and
`make_game.py` runs it before the lift.

Every claim is **verified** (the command or file named) unless marked otherwise.

## Files

| File | What |
|---|---|
| `nx2/shader_census.py` | `dictionaries()`: no `Pack/ZsDic.pack.zs` → prints `no Pack/ZsDic.pack.zs: plain zstd only`, returns `[]`. `unpack()` unchanged |
| `nx2/prompt_assets.py` | `zs_dictionary()` → `None` with one line when the pack is missing; `read_zs(…, None)` reads plain zstd; `main()` returns early ("nothing to do") when the game has no `Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs` |
| `gpu/vk/vk_game_font.h` | `Reader` gains `bool plain`. `open()`: no pack → plain mode when `Font2/Scalable` is a folder, else `false`; a pack that is there but does not read still fails. `read()`: in plain mode, decompresses with no dictionary. No function renamed or reshaped |
| `nx2/romfs_check.py` (new) | `summary(romfs)`, `check(cfg, romfs)`, and the command |
| `nx2/make_game.py` | `import romfs_check`; `check_romfs(exefs, romfs)` (new function); one call right after `check_supported_build(exefs)` in `main()`, before the lift. 12 lines added, all `(raiders)`-marked |
| `games/raiders/game.py` | the byte floor recomputed; comments |
| `games/oot/game.py` | the `ZS_DICTIONARY` comment corrected (no reader uses the field; see Decisions) |
| `tests/test_shader_census_nodict.py` (new) | no pack: `[]` plus the one line; `unpack` round-trips a plain frame and passes non-zstd data through; with a pack (a synthetic SARC) the dictionaries are read and nothing is printed; the whole census as a subprocess on a romfs with one tiny `.zs` → `0 programs from 0 stages`, an empty `HKSEED01` file |
| `tests/test_romfs_check.py` (new) | 10 checks: `*.part`, `.DS_Store`, dotfiles and dot folders skipped; ok; too few files; too few bytes; a `.part` does not make up the count; floors 0/None skip the check; missing folder; the command (`HOOKSHOT_GAME=raiders`); the games' floors; `make_game.main` calls it between the build check and the lift |
| `tests/test_prompt_assets_nodict.py` (new) | `zs_dictionary` → `None` plus the one line; `read_zs(None)` round-trips; the command on a romfs without the font exits 0, says "nothing to do", writes no `--out` folder. Needs no fontTools |
| `tests/test_game_font.cpp` | 3 blocks added, none changed: no pack and a font in `Font2/Scalable` → opens and returns the font's bytes; the same with a font that has no Latin letters → not used; no pack and no `Font2/Scalable` → `!open()` |
| `spikes/shader_census_nodict.py` | deleted (superseded); its row in `spikes/README.md` is kept as the planning record, marked "removed by T05" |

## The three dictionary readers

| Reader | Before | Now, with the pack | Now, without the pack |
|---|---|---|---|
| `shader_census.dictionaries` | `open()` raised `FileNotFoundError`; the census stopped | unchanged | `[]` plus one printed line; `unpack()` already tried plain zstd first |
| `prompt_assets.zs_dictionary` / `read_zs` | `open()` raised; `make_game` printed "the button prompts … were not made" | unchanged | `None` plus one line on stderr; plain frames |
| `vk_game_font.h` `Reader::open` / `read` | `open()` returned false → the bundled Libertinus font | unchanged (the 23 earlier `CHECK`s of `test_game_font.cpp` still pass) | plain mode if `Font2/Scalable/` is a folder; else `false` → Libertinus, as before |

On the font reader's logging: `vk_imgui.cpp` `game_font()` opens the reader once (`static bool opened`) and `load_fonts()`
logs one line for the fallback. Neither was changed and there is no logging per frame (read in the source).

## What Raiders' romfs offers

| Asset upstream reads | In Raiders' romfs | Result |
|---|---|---|
| `Pack/ZsDic.pack.zs` | absent (`ls romfs/Pack`: 5 entries, none of them this one) | the plain-zstd path in all three readers |
| Menu font, `Font2/Scalable/*.bfotf.zs` | no `Font2/` folder. The fonts are in `Font/`: 4 `*.bfarc.zs` archives (a different container from upstream's `.bfotf.zs`) | **fallback**: the bundled Libertinus font (**inferred** from the code path: `open()` returns false because `Font2/Scalable` is not there; not run on the Deck yet) |
| Prompt icon font, `Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs` | absent | **fallback**: `prompt_assets.py` on the dump printed `prompts: nothing to do: …` and exited 0, with no output folder. With no `prompts/` folder in the game folder, `host/prompts.c` serves nothing and the game shows its own icons (read in `host/prompts.c`, `setup_state` 3) |
| Prompt textures and layouts, `UI/Layout2Archive/Common…` | no `UI/Layout2Archive/` (Raiders has `UI/LayoutArchive/`) | not reached: the tool stops before them |

Reading Raiders' `.bfarc` fonts is out of scope (the task's non-goals). If it is ever wanted, it is a new reader and
not part of this fix.

## romfs floors

`summary()` on the dump's romfs: **46,338 files, 13,627,981,317 bytes (12.69 GiB)**, in 0.23 s on the Mac.

| | Files | Bytes |
|---|---|---|
| All entries (`find romfs -type f`) | 46,340 | |
| Skipped | 2: `.DS_Store` at the top and one `*.part` in `Effect/` (2,048 bytes; the complete file of the same name is there too, 876,601 bytes) | |
| Counted | **46,338** | **13,627,981,317** |
| Floor (`games/raiders/game.py`) | **46,000** (as planned; 0.73% below) | **13,559,000,000** (0.5% below, rounded down; the planned 13,600,000,000 was only 0.2% below) |
| Ocarina (`games/oot/game.py`) | None (no check, as upstream) | None |

A failed check in `make_game.py` is `@@error The romfs at <dir> is incomplete: it has N files (Raiders Recomp expects at
least 46000) and B bytes, G GiB (… expects at least …). Copy the romfs again.` (only the parts that are short are named).

## Decisions

- **The readers look for the file; they do not read `ZS_DICTIONARY`.** `shader_census.py` and `prompt_assets.py` are
  given only a romfs, and the fix is generic, so it can go upstream unchanged. `ZS_DICTIONARY` stays in both configs as
  a record, and its comments now say so. A later task can drop the field or start reading it.
- **The font reader's plain mode needs `Font2/Scalable/`.** That keeps upstream's check "a folder with nothing → `!open()`"
  as it is, and `open()` still means "fonts may be readable here". It uses `std::filesystem` (`exists`, `is_directory`
  with `std::error_code`, so nothing throws). The game builds as C++20 (`nx2/build.py` lines 842, 893).
- **`check_romfs` runs on every build path** (`--romfs`, `--nup`, `--update`), after the build check, so the game is
  known. It checks `<out>/romfs`, the folder the game will run from. A game with no floors returns before reading the
  folder, so upstream's flows and fixtures are untouched.
- **The prompts tool tests for the font before the dictionary**, so for Raiders it prints only one line.

## Acceptance criteria

| Command | Result |
|---|---|
| `shader_census.py "$OOT_DUMP/romfs" --out work/raiders_shaders.bin \| tail -5` | first line `no Pack/ZsDic.pack.zs: plain zstd only`; `22042 programs from 26960 stages`; `wrote work/raiders_shaders.bin 239 MB` (251,529,184 bytes); 0 lines with "skipped"; 2.33 s wall. **Met** |
| `romfs_check.py "$OOT_DUMP/romfs"` | `files 46338, 12.69 GiB (13627981317 bytes): ok`, exit 0. **Met except the number:** the task expected "files 46340 (the .part ignored)", but 46,340 is the count with both the `.part` and `.DS_Store` included. Leaving them out, as the interface says to, gives 46,338 |
| `run_all.py test_shader_census_nodict test_romfs_check vk_game_font prompt` | 6 passed, 0 failed, 0 skipped. `vk_game_font` matches no test file: the font test is `tests/test_game_font.py`, run separately as `run_all.py game_font`: 1 passed |
| `run_all.py` (full, with Homebrew tools as in the baseline's reference row) | 316 passed, 9 failed, 9 skipped, 776 s (334 checks; the baseline's reference row: 312 / 9 / 9 of 330). The 4 new checks are T04's `test_game_config` and T05's three new tests, all passing. The 9 failures are exactly the baseline's 9 (the two ASan hangs, `test_mem_gate`, `test_mem_gate_children`, `test_low_memory_notice`, `test_prof_symbols` and the three temp-symlink ones). **Met: no worse than the baseline** |
| `git status --porcelain \| grep -c 'work/'` | `0` (`work/` ignored by `.gitignore:3`) |

## Upstream PR (ready to send; the user opens it, T25)

Branch from `upstream/main`, e.g. `fix/zsdic-optional`. Leave out the `(raiders)` markers, `nx2/romfs_check.py`,
`make_game.py`, `games/` and `tests/test_romfs_check.py`. Include the three readers, `tests/test_shader_census_nodict.py`,
`tests/test_prompt_assets_nodict.py` and the added blocks of `tests/test_game_font.cpp`.

> **Title:** fix: read games without Pack/ZsDic.pack.zs (plain zstd)
>
> Some games built on the same engine ship no `Pack/ZsDic.pack.zs`: their `.zs` files are plain zstd frames. Three
> readers open that file unconditionally, so on those games the shader census stops with `FileNotFoundError`, the
> button-prompt tool fails, and the menu font reader gives up even where a font is present.
>
> - `nx2/shader_census.py` `dictionaries()`: a missing pack means no dictionaries, with one printed line. `unpack()`
>   already tries a plain frame first.
> - `nx2/prompt_assets.py`: `zs_dictionary()` returns `None` when the pack is missing, and `read_zs()` then reads plain
>   frames. A game with no `Font2/Scalable/External…bfotf.zs` has nothing to redraw: the tool says so and exits 0.
> - `gpu/vk/vk_game_font.h` `Reader`: with no pack and a `Font2/Scalable/` folder, fonts are read as plain frames.
>   Otherwise nothing changes, including the fallback to Libertinus.
>
> Nothing changes for a game that has the pack. All earlier checks of `test_game_font.cpp` are unchanged and pass.
>
> Tests: `tests/test_shader_census_nodict.py` and `tests/test_prompt_assets_nodict.py` (new, synthetic files, standard
> library plus `zstandard`), and three added blocks in `tests/test_game_font.cpp`. No game files are read.
