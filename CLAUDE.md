# raiders-recomp

A static recompilation of the user's own dump of *Splatoon Raiders* (Nintendo Switch 2, program
`0400380020056000`, base game, main build `abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5`) to a native x86-64
Linux program for the Steam Deck. It is a **fork of Hookshot** (https://github.com/NotRexed/Hookshot,
GPL-3.0-or-later): the game's ARM64 code is lifted to C, Horizon OS is reimplemented in `host/`, and NVN2
graphics calls are recorded and replayed on Vulkan in `gpu/vk/`.

The plan is in `docs/plans/`. Work is done one task at a time from `docs/plans/tasks/`.

**Until task T01 is done** this directory is not yet the fork: Hookshot's tree is the study clone at
`refs/Hookshot/`, and every `nx2/`, `host/`, `gpu/`, `scripts/`, `tests/` path below means
`refs/Hookshot/<path>`. T01 makes them root paths.
Upstream's `AGENTS.md`, `CONTRIBUTING.md`, `docs/development.md` and `docs/design.md` still apply.

## Hard constraints (never break these)

1. **No copyrighted material in git.** Nothing from the dump and nothing made from it: no game code, lifted
   C, `image.bin`, assets, shader blobs, keys, firmware, saves, screenshots, or logs with game text. All of it
   stays under `work/` (ignored) or on the Deck. `git add` by path only, never `git add -A`.
2. **The dump is read-only.** Never modify, move or delete anything in the dump folder.
3. **Offline only.** No Nintendo network services, no online play, no local wireless. Stub them so the game
   sees an offline console.
4. **GPL-3.0-or-later.** Keep every upstream licence, notice, provenance file and credit.
5. **Verify, don't guess.** In reports, tag claims **verified** (path, command or log line), **inferred** or
   **unknown**. An unknown becomes a research step, not an assumption.
6. **Stay in the task's scope.** If the task is wrong or blocked, stop and write a blocker report
   (`docs/plans/06-handoff-guide.md` §5).
7. **The user does outward-facing and system actions:** creating the fork, pushing, opening PRs, changing
   Deck system settings. Prepare the exact steps and wait.

## Strategy in five lines

- Keep upstream's paths so `git merge upstream/main` works. Do not rename or delete upstream files.
- Raiders-specific code goes in **new files**: `games/raiders/`, `host/raiders_*.c`, `host/nn_offline.c`,
  `scripts/deck/`. Shared files only gain a lookup into the per-game config (`nx2/game.py`).
- Ocarina-specific upstream code is **gated on the game id**, not removed.
- Mark edits to upstream files with `(raiders)` in a comment.
- Generic fixes are candidates for upstream PRs (branch from `upstream/main`, one fix each).

## Layout

| Path | What |
|---|---|
| `docs/plans/` | Plan (`00`-`06`), `tasks/`, `reports/` |
| `games/<id>/game.py` | Per-game config: program id, build ids, languages, data folder, patches |
| `nx2/` | Lift pipeline and builder: `dump.py`, `lift.py`, `build.py`, `make_game.py`, `shader_census.py`, `game.py` |
| `host/` | Horizon OS runtime: `HLE(<mangled name>)` functions replace SDK functions; `nvn_native.c` is NVN2 |
| `gpu/vk/` | Vulkan replay; `gpu/vk/eden/` is Eden's shader recompiler with the Ampere lowering |
| `scripts/deck/` | Sync, build, run and fetch logs on the Steam Deck over SSH |
| `tests/` | Game-free checks. Many cut functions out of sources by text: reshaping a function can break one |
| `spikes/` | Planning-time throwaway scripts |
| `work/`, `refs/`, `.venv/`, `build-linux/` | Ignored. `work/` holds everything derived from the dump |

## Two machines

- **Mac (this machine, Apple Silicon):** editing, lifting for analysis, game-free tests. It cannot compile
  or run the game.
- **Steam Deck (`$DECK_HOST`, default `deck@steamdeck`):** compiles, links and runs. Its own copy of the dump
  is at `~/raiders/dump`. Source at `~/raiders/src`, work folder `~/raiders/work`, game folder
  `~/Games/raiders`, saves `~/.local/share/raiders-recomp`.

## Commands

Run every Python tool with `python -I` (on the Mac: `.venv/bin/python -I`).

```bash
# Mac: environment
python3 -m venv .venv && .venv/bin/pip install lz4 numpy capstone "unicorn>=2.1,<2.2" zstandard
export OOT_WORK="$PWD/work" OOT_DUMP="/Users/nick/Downloads/Splatoon Raiders Switch 2 NSP BASE GAME"

# Mac: what is this dump / is it the supported build
.venv/bin/python -I nx2/dump.py --dump "$OOT_DUMP"
.venv/bin/python -I nx2/make_game.py --check --exefs "$OOT_DUMP/exefs"

# Mac: lift for analysis (coverage only; add --standalone --write to emit C into work/sa/gen)
.venv/bin/python -I nx2/lift.py

# Mac: game-free tests (compare with docs/plans/reports/mac-test-baseline.md)
.venv/bin/python -I -B tests/run_all.py

# Deck, driven from the Mac
scripts/deck/sync.sh                      # source tree to the Deck
scripts/deck/build.sh                     # lift + compile + link on the Deck
scripts/deck/run.sh <name> <seconds>      # a named, time-limited, muted run with screenshots
scripts/deck/fetch.sh <name>              # log and screenshots back to work/runs/<name>/
```

(`OOT_WORK` and `OOT_DUMP` are upstream's variable names for the work and dump folders; they are kept.)

## Debug switches

Switches go in the environment or in `hookshot_env.txt` beside the game (`NAME=VALUE` per line). The full
list is in `docs/development.md`; `grep -rn 'getenv("' host gpu/vk` finds the rest.

| Switch | Use |
|---|---|
| `HOS_TRACE=1` (or `--trace`) | Log every Horizon OS call |
| `HOS_NVN_STRICT=1` | Stop at the first unimplemented NVN proc instead of answering 0 |
| `HOS_HEADLESS` | No window; render offscreen (runs over SSH) |
| `HOS_AUDIO=0` | No sound device (default for test runs) |
| `HOS_NO_MOVIES=1` | Skip movies while booting |
| `HOS_INPUT_SCRIPT=<presses>` | Scripted pad input, e.g. `2:A,5.5:LUP/1500` |
| `HOS_HANDHELD=1`, `HOS_WINDOW_SIZE=1280x720` | Handheld profile and window size for the Deck |
| `HOS_MOTION_DEBUG=1`, `HOS_VIDEO_LOG=1` | Log gyro state; log movie decoder calls |
| `HOS_PROFILE=<s>`, `HOS_THREAD_TIMES=<s>` | Busiest threads per interval |
| `RX_VK_SHOTS=<dir>`, `RX_VK_SHOT_EVERY=<n>` | PNG screenshots every n presents |
| `RX_VK_VALIDATION` | Vulkan validation layer |
| `RX_VK_DUMP_FAILED=<dir>` | Dump programs that fail to translate (game data: keep in `work/`) |
| `RX_VK_FRAME_LOG=<csv>` | Frame time per present |
| `RX_VK_SKIP_CODE=<key>`, `RX_VK_MESH_NOCULL=<key>` | Leave out or simplify programs by code key (GPU hangs) |
| `RX_VK_VRAM_MB=<MB>`, `RX_VK_TEX_MAX_DIM=<px>` | Texture memory limits |
| `RX_VK_PIPE_SKIP=0` | Wait for pipelines instead of skipping draws (accuracy screenshots) |

Logs: `hookshot_log.txt` in the game folder (the last run; `.1`-`.4` are older). On the Deck, GPU resets show
in `journalctl -k | grep -E "amdgpu|gfx_"`.

## Conventions

- Conventional Commits; one branch per task (`task/TNN-name`); commit, do not push.
- A new Python module gets a game-free test in `tests/`. A change to `MkwVkHost`/`MkwVkRenderer` in
  `gpu/vk/vk_api.h` bumps `MKWVK_API_VERSION`.
- Reports go to `docs/plans/reports/`: symbol names, counts, hashes, timings and decisions only.
