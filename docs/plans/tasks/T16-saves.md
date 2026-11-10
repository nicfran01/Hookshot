# T16 · Saves: per-game data folder, save and continue

**Milestone:** M5 · **Depends on:** T13 · **Machine:** Mac driving the Deck

## Context
Upstream keeps per-user data under `~/.local/share/hookshot` on Linux (`docs/saves.md`, `readme.md` "Where
the files go"). A second game built from the same runtime must not share that folder. Raiders' save layout
is unknown until the game writes one. `nn::fs` is 25 of 28 imports implemented and `nn::account` 10 of 19
(`work/imports_raiders.txt`).

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §10; `docs/plans/03-architecture.md` §3
- `docs/saves.md`; `host/nn_fs.c` (mount names, save data paths, the `--user` argument), `host/hos_paths.h`,
  the account functions (`grep -n "2nn7account" host/*.c`)
- `docs/plans/reports/M3-trace.md` (`nn::fs`, `nn::account` rows)

## Scope
1. The user-data root comes from the game config's `DATA_DIR` (generated `hos_game_data_dir`, T06):
   `~/.local/share/raiders-recomp` on Linux, honouring `XDG_DATA_HOME` exactly as upstream does for its own
   folder. Ocarina's stays `hookshot`.
2. The save round trip works: create save data, write, commit, quit, start, load.
3. The three uncovered `nn::fs` imports and any `nn::account` call the trace marked wrong.

## Non-goals
- Importing saves from a console or emulator (`scripts/oot_saves.py` is Ocarina-only; a Raiders equivalent
  is a possible later task). Cloud saves. Multiple user profiles beyond what upstream provides.

## Steps
1. Find every place the Linux data folder name is built (`grep -rn "hookshot" host/hos_paths.h host/nn_fs.c
   host/hos_main.c host/posix builder/linux | grep -i "share\|XDG\|user"`). Replace the literal with the
   generated data-dir string through one helper; keep upstream's one-time migration of an old `user` folder
   working for Ocarina only.
   - Pitfall: `tests/test_utf8_paths.py` and others read these files by text; keep function shapes.
2. List the uncovered `nn::fs` imports: `grep "^    .*2nn2fs" work/imports_raiders.txt`. Implement those the
   trace shows are called.
3. Save round trip with scripted input: extend `games/raiders/scripts/new_game.txt` into `save_and_quit.txt`
   (play to the first save point or autosave), then a second run that continues. `--user` points both runs at
   `~/raiders/work/runs/<name>/user` so tests never touch the real saves.
   - If the game only autosaves, find the trigger from the log (`HOS_TRACE=1` shows
     `nn::fs::Commit`/`CommitSaveData`).
4. Record the save layout (file names and sizes only).
5. Durability: a commit must be atomic on the host (write to a temporary name, then rename), as upstream
   does: confirm by reading `nn_fs.c`'s commit; if it is not, report it as an upstream issue rather than
   redesigning here.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py paths fs save
scripts/deck/run.sh save1 400 --args "--user $HOME/raiders/work/runs/save1/user" -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/save_and_quit.txt)"
ssh $DECK_HOST 'find ~/raiders/work/runs/save1/user -type f | head -20'        # save files exist
scripts/deck/run.sh save2 200 --args "--user $HOME/raiders/work/runs/save1/user" -- HOS_INPUT_SCRIPT="<continue script>"
scripts/deck/fetch.sh save2 && ls work/runs/save2/shots | tail -1              # shows the continued game (describe it)
ssh $DECK_HOST 'ls ~/.local/share/raiders-recomp 2>/dev/null; ls ~/.local/share/hookshot 2>/dev/null'  # default runs use the former only
```

## Report
`docs/plans/reports/T16-saves.md`: where data lives, the save layout (names and sizes), functions
implemented, the commit-atomicity finding, and how to back up a save.
