# T16 · Saves: per-game data folder, save and continue (2026-11-12)

**Short answer.**
- **Data folder.** Raiders keeps its per-user data in its own folder: `~/.local/share/raiders-recomp`, or
  `$XDG_DATA_HOME/raiders-recomp` when that is set. Ocarina keeps `hookshot`.
- **Round trip works from an empty folder.**
  - `save1`: the game created its save, wrote it 4 times and was stopped.
  - `save2`: it loaded that save and continued in the hub, with no difficulty select, opening or customization.
- **One file.** The save is `save.dat` (4,667 B, then 4,907 B).
- **Nothing to implement in `nn::fs` or `nn::account`.**
- **Commit is not atomic, here or upstream.** Recorded as an upstream issue.
- **Deviations** (below): the `HOS_ENV_FILE` line cap is raised from 511 characters to 16 KiB, and `save1` ran 600 s
  instead of 400 s. You chose this as option 1 of `BLOCKER-T16-2026-11-12.md`.

Claims are **verified** (command, file:line or log line named) unless marked **inferred** or **unknown**. Runs are in
`work/runs/<name>/` on the Mac and `~/raiders/work/runs/` on the Deck. Logs, screenshots and saves are game output and
are not committed.

## Branch and build

- `task/T16-saves` was made from `main` at `2df50e1` (T15 is not merged, so its `nn::hid` changes are not here).
- The Deck build with every change below gives `build (lift): 189 s`, exit 0.
- Your save, `~/.local/share/raiders-recomp/save/5a3c9e1f0b7d24680000000000000001/save.dat` (md5 `d9dfb4bb…`, 5,554 B),
  had the same md5 before the runs and after every one. Every test run used its own `--user` folder.

## Where data lives

| | Linux |
|---|---|
| Raiders (`games/raiders/game.py` `DATA_DIR = "raiders-recomp"`) | `$XDG_DATA_HOME/raiders-recomp`, else `~/.local/share/raiders-recomp` |
| Ocarina (`DATA_DIR = "hookshot"`) | `$XDG_DATA_HOME/hookshot`, else `~/.local/share/hookshot` (unchanged) |
| `--user <dir>` | `<dir>` (wins over both) |
| Saves inside it | `save/<user id>/`, the user id being `5a3c9e1f0b7d24680000000000000001` (the runtime's one user) |

- **The code.**
  - `host/hos_main.c` `saves_dir()` now ends the folder with `hos_game_data_dir_name()`, a new one-line helper.
  - The helper returns the generated `hos_game_data_dir` (`gen/hos_image.c`, from `DATA_DIR`), or `"hookshot"` when it is
    empty. It is declared in `host/hos_game.h`.
  - The XDG rule is upstream's, unchanged: an absolute `XDG_DATA_HOME`, else `$HOME/.local/share`, else the folder beside
    the executable.
- **The `user/` move.** Upstream's one-time move of a `user/` folder beside the executable now runs only when
  `hos_game_is("oot")`. Raiders leaves such a folder alone and never takes its contents.
- **When it applies.** `saves_dir()` runs only when the game starts from a game folder with no arguments. The Deck
  scripts (`run.sh`, `steam_launch.sh`) pass `--user ~/.local/share/raiders-recomp` themselves, so their default runs
  were already in that folder.
- **On the Deck (verified):** `ls ~/.local/share/raiders-recomp` gives `save`, and `ls ~/.local/share/hookshot` finds
  nothing (exit 2).
- **Not changed** (not saves; inferred harmless here):
  - the updater's `~/.local/share/hookshot/builder` (`host/hos_update.c`, `builder/linux/`); `run.sh` turns update
    checks off;
  - DLSS's `$XDG_DATA_HOME/hookshot/ngx` (`gpu/vk/vk_dlss.cpp`), which is NVIDIA only.

## Save layout (names and sizes)

- **The whole layout.** One file, `save/<user id>/save.dat`. No folders inside the save, and no other file was written
  in any run.
- **Sizes.**
  - The first save is 4,667 B. The one written from the beach tutorial on is 4,907 B.
  - T13's later saves were 5,066-5,073 B (`M4-first-frame.md`). Your current save is 5,554 B, made past the prologue.
- **The extra probe.** Before each write the game asks for `saveMount:/extflag_clear_ph4_boss.dat`. It was "not found"
  every time and never written: a flag file for something later in the game (inferred from the name).
- **The sequence** (verified, `HOS_FS_TRACE=1`, `work/runs/save1/hookshot_log.txt`; times from the 5 s `vi:` lines):

  | Line | When | What |
  |---|---|---|
  | 1611-1612 | boot | `MountSaveData` as `saveMount:`; `SaveDataThread` opens `save.dat`: not found |
  | 11141-11143 | ~33 s, "Start!" after the difficulty | `GetEntryType` of both files (not found), then `save.dat` opened and written |
  | 23956-23958 | ~240 s | after customization's "Love it!": written again |
  | 33323-33325 | ~245 s | written again |
  | 34661-34664 | ~354 s (file time 20:13:14, run start 20:07:20) | on arrival at the beach tutorial: written again, 4,907 B |

- **`save2` (the continue run).** It opened `save.dat` at boot (line 1613) and wrote it again ~15 s after its first
  `vi:` line (line 22534), still 4,907 B, with a new md5 (`1180f22a…` before, `b7ed3efe…` after).
- **"Commit".** The log has no `Commit` line: `host/nn_fs.c` logs only opens, entry types and mounts, and its `Commit`
  does nothing (below).

## The round trip

| Run | Command | Result |
|---|---|---|
| `save1` | `scripts/deck/run.sh save1 600 --args "--user /home/deck/raiders/work/runs/save1/user" -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/save_and_quit.txt)" HOS_HANDHELD=1 RX_VK_SKIP_PROG=cffdbb02c4dfbd39 RX_VK_SHOT_EVERY=300 HOS_FS_TRACE=1` | `hid: input script of 420 presses (last at 589 s …)`. Stopped at the time limit: no crash, no device loss, 69 screenshots |
| `save2` | `scripts/deck/run.sh save2 200 --args "--user /home/deck/raiders/work/runs/save1/user" -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/continue.txt)"` and the same switches | `hid: input script of 8 presses (last at 58 s …)`. Stopped at the time limit, 24 screenshots |

- **What `save1` did** (screenshots):
  - "Select a difficulty", then the autosave notice, then the in-engine opening (~180 s at ~31 fps).
  - The hub and character customization (from ~207 s). The final prompt's "Love it!" was reached with RIGHT, then A.
  - The hub dialogue, the island cutscene, then the beach tutorial's first prompt: aim at the shard by moving the
    controller (T15's ground). It waited there from present ~14,000 until the limit.
- **What `save2` shows.** `ls work/runs/save2/shots | tail -1` gives `vk_007200.png`:
  - **the hub with the crew, at a later scene than `save1`'s first hub visit** (the crew counts the days since the crash
    landing), on a dialogue line waiting for A;
  - the run went clouds → hub. There was no "Select a difficulty", opening or customization, so the game continued from
    the save (verified, screenshots).
- **The two scripts** (`games/raiders/scripts/`, new):
  - `save_and_quit.txt`:
    - `20:A,24:RIGHT,26:A` (difficulty "Raider", then "Start!");
    - A every 6 s from 40 s to 196 s (the opening seems to need no input: inferred, it played the same with A every 2 s);
    - then `RIGHT` at t and `A` at t+1 every 2 s from 200 s to 589 s (420 presses, 3,307 characters).
  - **The RIGHT is needed.** Customization's last prompt ("Looking good? Happy with this?") starts on "Hold Up…", which
    goes back a step. A pressed alone, or `A+RIGHT` as one press, loops the steps (verified: the blocker's runs 2 and 3).
  - `continue.txt`: A every 4 s from 30 s to 58 s.
  - Both start from the game's first pad read. They work in the handheld profile (`HOS_HANDHELD=1`).
- **"Quit" is the time limit's kill** (`timeout`, SIGTERM then SIGKILL). On a console the game is closed from the HOME
  menu, which also gives no warning. The last write in `save1` was 246 s before the kill.

## Functions implemented

- **None in `nn::fs` or `nn::account`** (verified).
  - **The three "uncovered" `nn::fs` imports** in `work/imports_raiders.txt` are not stubs: `EnableGlobalFileDataCache`
    and `Get`/`SetCurrentThreadFsContext`.
    - None is in `work/standalone_stubbed.txt`, so they run as the lifted SDK's own code.
    - No log of these runs (or of T13's `save2`, `live1`, `play3`, `prologue2`) has an `ipc:` line, so that code reaches
      no system service (inferred).
  - **`M3-trace.md` has no `nn::fs` or `nn::account` row**: the trace marked no call of either wrong.
  - **The save path above works on the existing implementation:** `MountSaveData`, `GetEntryType`, `CreateFile`,
    `OpenFile`, `WriteFile`, `SetFileSize`, `FlushFile`, `CloseFile` and `Commit`, all in `host/nn_fs.c`.
- **New:** `hos_game_data_dir_name()` (`host/hos_main.c`, `host/hos_game.h`).

## Commit atomicity: not atomic (an upstream issue)

- `nn::fs::Commit` is `RET(0)` (`host/nn_fs.c:311`); `upstream/main` is the same.
- `WriteFile` writes into the host file at the guest's offset (`nn_fs.c:437`).
- `FlushFile` is `fdatasync` (`host/posix/win32_posix.c:930`).
- So on a console a save is all old or all new once committed, but here it is not.
  - If the game dies, or the Deck loses power, while `save.dat` is being written, the file can be left part old and part
    new (inferred from the code; not provoked).
  - The game's write is one file of ~5 KB, so the window is small.
- **The fix belongs upstream:**
  - the save mount writes to a copy, and `Commit` renames it into place (write, `fsync`, rename, `fsync` the folder);
  - or each file is written to a temporary name and renamed on close.
  - Either changes how `nn_fs.c` maps the save mount, so it was not redesigned here (the task's step 5). **A candidate
    upstream issue** (CLAUDE.md, T25).

## How to back up a save

1. **Close the game first.** It writes `save.dat` on its own: when the game starts, at story points, and on arrival in
   an area.
2. **Copy the folder:**
   ```bash
   cp -a ~/.local/share/raiders-recomp/save ~/raiders-save-backup-$(date +%F)
   ```
3. **To restore,** close the game and copy `save.dat` back into
   `~/.local/share/raiders-recomp/save/5a3c9e1f0b7d24680000000000000001/`.
4. **For test runs, keep your save out of reach:** give the run its own `--user <dir>`, as `save1`/`save2` did.
   - `scripts/deck/run.sh` without `--user` uses your real folder.
   - `--args "--user …"` is placed after the script's own `--user`, and the last one wins (`hos_main.c` argument loop).

## Deviations

1. **`HOS_ENV_FILE` lines are no longer cut at 511 characters** (your choice: option 1 of
   `BLOCKER-T16-2026-11-12.md`).
   - **The bug:** `load_hookshot_env` read lines into `char line[512]`. A longer `HOS_INPUT_SCRIPT` was cut there
     without a word, and its tail read as a line of its own.
   - **Effect on T13:** its "A to 598 s" scripts ran as 87 presses ending at 206 s.
   - **The fix:**
     - the buffer is now 16 KiB;
     - a line longer even than that is left out whole, with an `env: … a line longer than 16382 characters left out`
       message on stderr;
     - marked `(raiders, T16)` in `host/hos_main.c`.
   - **Test:** `tests/test_env_file.py` gained a 6,003-character value (read whole) and a 20,000-character line (left
     out, the next line still read).
   - **A generic fix:** a candidate upstream PR.
2. **`save1` ran 600 s, not 400 s** (your choice, the same option).
   - From an empty folder the game's progress save comes at ~354 s, after the opening, customization and the hub dialogue.
   - The 400 s budget left no margin.
3. **`--user` is written out as `/home/deck/raiders/work/runs/save1/user`.** The task's `$HOME/raiders/…` expands on
   the Mac, and `run.sh` takes plain words only.
4. **`save_and_quit.txt` is new, not an extension of `new_game.txt`.** That script is on the unmerged T15 branch and
   starts from a save past the prologue. This one starts from an empty folder, so the test covers creating the save.
5. **The runs add switches the task's command does not list:**
   - `HOS_HANDHELD=1` (the Deck's profile);
   - `RX_VK_SKIP_PROG=cffdbb02c4dfbd39` (T13's problem 7 hang, still open);
   - `RX_VK_SHOT_EVERY=300`;
   - `HOS_FS_TRACE=1` (the save's file names).

## Tests (Mac)

- `.venv/bin/python -I -B tests/run_all.py paths fs save`: **13 passed, 0 failed, 0 skipped.** This includes the new
  `tests/test_save_paths.py`, 24 checks:
  - it builds `saves_dir()` and its helpers from `hos_main.c` over its own Win32-on-POSIX layer;
  - it checks the XDG, HOME, no-HOME and empty `DATA_DIR` cases, and Ocarina's move and keep-old-place rule;
  - it checks that Raiders leaves `user/` alone.
- `tests/test_env_file.py` and `tests/test_game_gates.py`: pass.
- The full suite, with the baseline's `HOOKSHOT_VULKAN_HEADERS` and `HOOKSHOT_SPIRV_HEADERS`: **327 passed, 9 failed,
  9 skipped** in 737 s.
  - The 9 failures are `mac-test-baseline.md`'s 9.
  - The one more pass than T13's 326 is `test_save_paths.py`.

## Files

- `host/hos_main.c`: `hos_game_data_dir_name()`; `saves_dir()` takes the game's folder; the move is Ocarina's only;
  the env-file line cap.
- `host/hos_game.h`: the helper's declaration.
- `tests/test_save_paths.py` (new) and `tests/test_env_file.py` (long lines).
- `games/raiders/scripts/save_and_quit.txt` and `continue.txt` (new).
- `docs/plans/reports/T16-saves.md` (this report) and `BLOCKER-T16-2026-11-12.md` (marked resolved).
- **On the Deck:**
  - `~/raiders/work/t16_save1/save.dat` is `save1`'s save before `save2` rewrote it (md5 `1180f22a…`).
  - `~/raiders/work/runs/save1/` and `save2/` hold the runs.
  - All three are test data and safe to delete.
