# 03 · Target architecture

## 1. Repository model

`raiders-recomp` is a **git fork of NotRexed/Hookshot** with upstream's paths kept. Decisions:

| Decision | Options | Chosen | Why |
|---|---|---|---|
| Relationship to Hookshot | fork with history / subtree in a new repo / submodule + patches | **fork with history** | `git merge upstream/main` works file by file; Hookshot uses the same model against mkw-recomp (`docs/design.md` §2). The user chose this. |
| Where Raiders code lives | edit shared files / new files + a per-game layer | **new files + `games/<id>/`** | Shared files stay mergeable. Hookshot's own rule: "OoT-specific code goes into new files where it can". |
| What happens to Ocarina code | delete / leave and gate | **leave and gate on the game id** | Deleting guarantees merge conflicts on every upstream change to those lines. Gating is also what an upstream PR would need. |
| Internal names (`hookshot`, `hookshot_vk.so`, `HOS_`, `RX_`, `OOT_WORK`) | rename / keep | **keep until M8, then rename only user-visible ones through the game config** | 303 tests read sources by text; renames conflict with daily upstream commits. |
| Performance data (hot list, link order, profile, pipeline state list) | commit / keep local | **keep local in `work/` on the Deck** (open question for the user, `05-roadmap.md`) | They hold addresses and counts, no code, and upstream ships equivalents with its tools; but the hard constraint says no generated output in the repo, so the default is local. |
| Default branch | `main` tracking the fork | `main`; upstream is the `upstream` remote; never push to it | |

## 2. Layout

Paths marked (new) are added by this project. Everything else is upstream's and keeps its place.

```
raiders-recomp/
├── CLAUDE.md                     (new) the guide every Opus session loads
├── AGENTS.md, CONTRIBUTING.md    upstream's; still apply (tests read the source, python -I, no game files)
├── LICENSE                       GPL-3.0-or-later, unchanged
├── readme.md                     upstream's + a short "raiders-recomp" section on top (T01); credits kept
├── docs/
│   ├── design.md, development.md, …      upstream's
│   └── plans/                    (new) these planning documents, tasks/, reports/
├── games/                        (new) the per-game layer
│   ├── __init__.py
│   ├── oot/game.py               upstream's constants moved here, values unchanged
│   └── raiders/
│       ├── game.py               identity and pins (section 3)
│       ├── patches.py            lift-time patches: install(L, img); empty until one is needed
│       ├── deck_env.txt          the Deck's default switches, copied to the game folder as hookshot_env.txt
│       └── steam_input/          (M8) a Steam Input layout template and notes; no binaries
├── nx2/                          lift pipeline
│   ├── game.py                   (new) loads games/<id>/game.py: by HOOKSHOT_GAME, else by the dump's program id
│   ├── make_game.py, lift.py, build.py, shader_census.py, …   upstream's, with small lookups into nx2/game.py
│   └── oot_*.py                  upstream's, reached only through games/oot
├── host/
│   ├── *.c                       upstream's Horizon runtime
│   ├── hos_game.h                (new) the generated game id and helpers: hos_game_is("raiders")
│   ├── nn_offline.c              (new) ldn, nfp, friends, swkbd, nifm answers for an offline console
│   └── raiders_game.c            (new) build-id-gated hooks for Raiders, when any are found
├── gpu/vk/                       upstream's Vulkan back end; Ocarina workarounds gated (T07)
├── scripts/
│   ├── linux/                    upstream's deps.sh, appimage.sh
│   ├── deck/                     (new) setup.sh, sync.sh, build.sh, run.sh, fetch.sh (section 5)
│   └── trace_report.py           (new) summarises first-call stub and NVN logs (T09)
├── spikes/                       (new) planning-time throwaway scripts (see spikes/README.md)
├── tests/                        upstream's game-free suite + tests for the new files
├── third_party/                  upstream's
├── refs/                         (ignored) study clones: Recompia; Hookshot's clone is removed by T01
├── work/                         (ignored) everything made from the dump
└── .venv/                        (ignored)
```

## 3. The per-game layer

### `games/<id>/game.py`

Plain data, importable with `python -I` and no third-party packages. Modelled on Recompia's
`recomp/games/pkp/config.py` and `runtime/include/nxrt/game.h`.

```python
# games/raiders/game.py
ID = "raiders"
TITLE = "Raiders Recomp"                 # window title, launcher name (no Nintendo marks)
PROGRAM_ID = 0x0400380020056000
# main's build id (the NSO's 20 bytes, lower-case hex) -> display version. The first entry is the pinned one.
BUILDS = {"abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5": "1.0.0 (base)"}
MODULES = ("rtld", "main", "subsdk0", "sdk")
SDK = "21.4.4"
LANGUAGES = [("ja", "Japanese"), ("en-US", "English (US)"), ("es-419", "Spanish (Latin America)"),
             ("fr-CA", "French (Canada)"), ("en-GB", "English (UK)"), ("es", "Spanish (Spain)"),
             ("fr", "French (France)"), ("de", "German"), ("it", "Italian"), ("nl", "Dutch"),
             ("ko", "Korean"), ("zh-Hans", "Chinese (Simplified)"), ("zh-Hant", "Chinese (Traditional)")]
ROMFS_MIN_FILES = 46_000                 # the base game has 46,340 (one stray *.part ignored)
ROMFS_MIN_BYTES = 13_600_000_000         # 12.69 GiB
ZS_DICTIONARY = None                     # no Pack/ZsDic.pack.zs
DATA_DIR = "raiders-recomp"              # ~/.local/share/<DATA_DIR>
EXE = "hookshot"                         # internal name until M8
LIFT_PATCHES = "games.raiders.patches"   # module with install(L, img); may be None
SKIP_PROGRAMS = ()                       # default RX_VK_SKIP_PROG for this game: none
VISUAL_WORKAROUNDS = None                # (fog, exposure) factors; None: off
PERF_FILES = ("hot_funcs.txt", "hot_order.txt", "raiders_pieces.prof")   # looked for in work/, all optional
```

The language codes above are a mapping of `System/RegionLangMask.txt` onto the codes `make_game.py` uses;
T04 verifies each against `host/`'s language table before relying on it.

`games/oot/game.py` holds the same fields with upstream's values (`BUILDS = {"e0f3ccfa…": …}`,
`ZS_DICTIONARY = "Pack/ZsDic.pack.zs"`, `LIFT_PATCHES = "games.oot.patches"` wrapping `oot_wide`,
`oot_jitter`, `oot_occlusion`, `oot_patches`; `SKIP_PROGRAMS = ("53509044401d78d2",)`;
`VISUAL_WORKAROUNDS = (0.25, 0.65)`), so upstream's behaviour is unchanged when its game is selected.

### `nx2/game.py`

```python
def select(exefs=None):
    """The game config: HOOKSHOT_GAME=<id> if set, else the config whose PROGRAM_ID matches exefs/main.npdm,
    else SystemExit naming the program id found and the ids supported."""
def check_build(cfg, main_build_id) -> (ok: bool, text: str)
```

Callers: `make_game.py` (`check`, `check_supported_build`, `LANGUAGES`, perf files, data folder),
`lift.py` (patch installation, `chunks.edit_c` gate), `shader_census.py` (dictionary), `build.py` (writes
`HOS_GAME_ID`, title and data folder into the generated `gen/hos_image.c` beside the build id it already
writes at `build.py:521`).

### Runtime side

- `gen/hos_image.c` (generated by `nx2/standalone.py`/`build.py`) gains `const char hos_game_id[]`,
  `hos_game_title[]`, `hos_game_data_dir[]`.
- `host/hos_game.h`: `int hos_game_is(const char *id);` and `HOS_GAME_TITLE` reading the generated string.
- Game-specific runtime code is compiled in always and guarded at its entry points
  (`if (!hos_game_is("oot")) return;`), the way `hos_game_is_mkw()` guards Mario Kart's hooks today
  (`host/hos_main.c:73`). No `#ifdef` per game: one binary shape keeps the tests simple.
- The renderer learns the game through the existing host interface (`gpu/vk/vk_api.h`); if a new field is
  needed, bump `MKWVK_API_VERSION` (`AGENTS.md`).

## 4. Build flow

```
Mac (development)                               Deck (build and run)
─────────────────                               ────────────────────
edit, game-free tests (tests/run_all.py)        ~/raiders/dump/{exefs,romfs}     the user's copy of the dump
lift.py for analysis (work/ on the Mac)         ~/raiders/src                    the fork, synced from the Mac
git commit, git push                            ~/raiders/work                   OOT_WORK: image, lifted C, objects
scripts/deck/sync.sh  ── rsync over SSH ──▶     ~/raiders/deps                   scripts/linux/deps.sh output
scripts/deck/build.sh ── ssh ─────────────▶     ~/Games/raiders                  the game folder make_game.py writes
scripts/deck/run.sh   ── ssh ─────────────▶     ~/.local/share/raiders-recomp    saves
scripts/deck/fetch.sh ◀── logs, PNGs ──────     ~/Games/raiders/hookshot_log.txt, work/runs/<name>/
```

Steps on the Deck (inside the build container until M8; see `04-steam-deck.md` §7):

1. `python -I nx2/make_game.py --check --exefs ~/raiders/dump/exefs` → "This is the version … supports".
2. `python -I nx2/lift.py --standalone --write` → `work/sa/gen` (about 1.2 GB of C).
3. `python -I nx2/build.py --standalone --jobs 4` → `work/sa/build/hookshot` + `hookshot_vk.so`.
   For a full packaged folder: `python -I nx2/make_game.py --romfs … --exefs … --out ~/Games/raiders
   --language en-US` with `HOOKSHOT_KEEP_BUILD_FILES=1` during development.
4. Run: `~/Games/raiders/bin/hookshot --romfs … --user …`, switches from `hookshot_env.txt`.

Incremental rule (from upstream): a change in `host/` alone recompiles only the runtime; a change to the HLE
set, a lift patch or the hot list relifts (`make_game.py:1037` `lift_key`).

## 5. Deck scripts (`scripts/deck/`, new)

All take the Deck's SSH name from `DECK_HOST` (default `deck@steamdeck`) and never copy game files from the
Mac to anywhere but the Deck, and never from the Deck back except logs and screenshots.

| Script | Does |
|---|---|
| `setup.sh` | Creates `~/raiders/{src,work,deps}`, the build container, runs `scripts/linux/deps.sh` in it, prints `vulkaninfo` facts (driver, Mesa version, `VK_EXT_mesh_shader`). Idempotent. |
| `sync.sh` | `rsync -a --delete` of the tracked source tree (from `git ls-files`) to `~/raiders/src`. |
| `build.sh [--full]` | Runs lift + build (or `make_game.py`) in the container with `OOT_WORK=~/raiders/work`, `OOT_DUMP=~/raiders/dump`, `HOOKSHOT_JOBS=4`, `HOOKSHOT_KEEP_BUILD_FILES=1`; tees `~/raiders/work/build.log`. |
| `run.sh <name> [seconds] [-- ENV=VAL …]` | Starts the game with a named env file, a time limit, `RX_VK_SHOTS=work/runs/<name>/shots`, `HOS_AUDIO=0` unless `--sound`; stops it; leaves `work/runs/<name>/hookshot_log.txt`. |
| `fetch.sh <name>` | Copies `work/runs/<name>/` (log, PNG screenshots, reports) to the Mac's `work/runs/<name>/`. Screenshots are the game's output: they stay in `work/`, never in git. |

## 6. Upstream sync

- Remotes: `origin` = the user's fork, `upstream` = `https://github.com/NotRexed/Hookshot` (fetch only;
  `git remote set-url --push upstream DISABLED`).
- Cadence: merge `upstream/main` at the start of each milestone and whenever a task needs an upstream fix.
  `git merge upstream/main`, never rebase `main` (the fork's history is shared with the Deck checkout).
- After each merge: `python -I -B tests/run_all.py` on the Mac; a Deck build before the next runtime task.
- Conflict policy: upstream wins in shared files; re-apply our lookup (usually one line). If a shared-file
  edit of ours conflicts twice, move it behind a function in a new file.
- The planning base is `88b554e`. T01 records the merge base in `docs/plans/reports/upstream-sync.md`, one
  line per sync (date, upstream commit, conflicts).
- **Sending fixes upstream (T25 and ad hoc):** generic fixes go on a branch cut from `upstream/main`
  (not from our `main`), one fix per PR, following upstream's `CONTRIBUTING.md` (Conventional Commit subject,
  why first, tests in the same PR). Candidates known today: optional `Pack/ZsDic.pack.zs`
  (`nx2/shader_census.py`, `nx2/prompt_assets.py`, `gpu/vk/vk_game_font.h`); a per-game config module if the
  maintainer wants it (ask in an issue before writing it for upstream). Opening a PR is outward-facing: an
  Opus session prepares the branch and the description and the user opens it.

## 7. CI in the fork

- Keep `.github/workflows/source-regressions.yml` (game-free tests on push).
- Disable `release.yml` and `vulkan-dlss.yml` (renamed to `*.yml.disabled` in T01), remove the release job of
  `linux-appimage.yml`, and guard the release job of `windows-builder.yml` to `github.repository ==
  'NotRexed/Hookshot'` (a test reads that file and that job, so it is not renamed). A fork must not publish
  under upstream's release scheme. T24 re-enables an artifact-only AppImage build.
- CI never has a dump (`AGENTS.md`: "No game in CI").
