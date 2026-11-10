# T05 · Ingestion fixes: optional zstd dictionary, romfs sanity

**Milestone:** M1 · **Depends on:** T04 · **Machine:** Mac

## Context
Raiders' romfs has no `Pack/ZsDic.pack.zs`; its `.zs` files are plain zstd. Upstream opens that file
unconditionally in three places, so the shader census (and later the in-game menu font and button prompts)
fail on Raiders. `spikes/shader_census_nodict.py` showed the census works once the requirement is removed
(22,042 programs, 26,960 stages). Also, a romfs copied to the Deck by hand can be incomplete, which shows up
as an unexplained crash much later.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §1, §6; `spikes/README.md`
- `nx2/shader_census.py` (`dictionaries`, `unpack`, `main`), `nx2/prompt_assets.py` (its `ZsDic` use),
  `gpu/vk/vk_game_font.h` (its `ZsDic` use), `host/prompts.c` (how a missing font is handled)
- `nx2/make_game.py` `stand_in_damaged_files` (`:317`), `shader_census_cmd` (`:1028`), the census call at `:1483`

## Scope
1. `nx2/shader_census.py`: a missing dictionary file means "no dictionaries", with one printed line.
2. `nx2/prompt_assets.py` and `gpu/vk/vk_game_font.h`: the same tolerance. Behaviour with a dictionary
   present is unchanged.
3. `nx2/romfs_check.py` (new): file-count and byte-count floor from the game config; ignores `*.part` and
   dotfiles; called by `make_game.py` before the build and available as a command.
4. Tests for each.

## Non-goals
- No change to the census's output format (`HKSEED01`). No walk of new archive kinds (that is T12 if needed).
- Do not make the in-game font work for Raiders here: only make its absence harmless (fallback to the
  bundled Libertinus font is upstream's documented behaviour, `readme.md` "In-game menu").

## Interfaces
```python
# nx2/shader_census.py
def dictionaries(romfs, zs):   # [] when Pack/ZsDic.pack.zs does not exist; prints "no Pack/ZsDic.pack.zs: plain zstd only"

# nx2/romfs_check.py
def summary(romfs) -> (files: int, size: int)          # skips *.part, .DS_Store, other dotfiles
def check(cfg, romfs) -> (ok: bool, text: str)         # against cfg.ROMFS_MIN_FILES / ROMFS_MIN_BYTES; 0 disables
#   python -I nx2/romfs_check.py <romfs>               prints files, GiB, and ok / what is missing
```

## Steps
1. Census: guard the `open()` in `dictionaries`. `unpack` already tries plain zstd first and raises
   "no dictionary fits" otherwise: keep that.
2. `prompt_assets.py`: read how it uses the dictionary; make the dictionary optional the same way. If the
   asset it wants does not exist in Raiders' romfs at all, it must return "nothing to do" (the caller in
   `make_game.py:1485` already treats prompts as optional; confirm).
3. `vk_game_font.h`: find the path that reads `ZsDic.pack.zs` at run time; when the file is missing, try
   plain zstd, and on any failure fall back to the bundled font without logging an error per frame.
   - Pitfall: 17 tests read `gpu/vk/vk_menu.cpp` by text and some read `vk_game_font.h`
     (`grep -rln vk_game_font tests`). Keep function names and shapes; add, do not reshape.
4. `romfs_check.py` + the call in `make_game.py` (a failed check is an `@@error` naming the counts found and
   expected, and saying "copy the romfs again"). The Raiders floors are in `games/raiders/game.py`
   (46,340 files / 12.69 GiB observed; floors 46,000 and 13,600,000,000 bytes: recompute the byte floor from
   `summary()` on the real dump and set it 0.5% below).
5. Tests: `tests/test_shader_census_nodict.py` (a temp romfs with one tiny zstd file and no `Pack/`:
   `dictionaries` returns `[]`, `unpack` round-trips), `tests/test_romfs_check.py` (temp trees: ok, too few
   files, `.part` ignored).
6. Delete `spikes/shader_census_nodict.py` and its row in `spikes/README.md` (superseded), or leave a one-line
   note pointing here.

## Acceptance criteria
```bash
.venv/bin/python -I nx2/shader_census.py "$OOT_DUMP/romfs" --out work/raiders_shaders.bin | tail -5
#   "22042 programs from 26960 stages" and "wrote work/raiders_shaders.bin 239 MB"
.venv/bin/python -I nx2/romfs_check.py "$OOT_DUMP/romfs"          # files 46340 (the .part ignored), ok
.venv/bin/python -I -B tests/run_all.py test_shader_census_nodict test_romfs_check vk_game_font prompt
.venv/bin/python -I -B tests/run_all.py                            # no worse than the baseline
git status --porcelain | grep -c 'work/'                          # 0 (the .bin stays ignored)
```

## Report
`docs/plans/reports/T05-ingest.md`: what changed in each of the three dictionary readers, what Raiders' romfs
offers for the menu font and prompts (found or fallback), the final romfs floors, and a ready-to-send upstream
PR description for the dictionary fix (branch from `upstream/main`; the user opens the PR; see T25).
