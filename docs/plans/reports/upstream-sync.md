# Upstream sync log

One line per merge of `upstream/main` (`https://github.com/NotRexed/Hookshot`) into the fork
(`03-architecture.md` §6). After each merge: `python -I -B tests/run_all.py` on the Mac, and a Deck build before
the next runtime task.

| Date | Upstream commit | Conflicts |
|---|---|---|
| 2026-11-10 | `78e1112d70d8124a8009d67a97a126ef31390b8b` (`upstream/main` as fetched; merge of upstream PR #1910) | initial |

## Bases (T01)

- **verified:** the plan was written against `88b554e572636601538e341a1df2748699c8e5db` (the removed study clone
  `refs/Hookshot`, `git -C refs/Hookshot log -1`). It is an ancestor of `78e1112`, 345 commits back
  (`git rev-list --count 88b554e..upstream/main`). Numbers in `01-research-findings.md` and `spikes/README.md` are
  from `88b554e`.
- **verified:** the fork's `origin/main` was `6c596af2667c8e095e6620ce896430f6465803` when fetched, an ancestor of
  `78e1112` (36 commits behind), so pushing a `main` built on `78e1112` fast-forwards.
- **verified:** remotes: `origin` = the fork `nicfran01/Hookshot`, `upstream` = `NotRexed/Hookshot` with push URL
  `DISABLED` (`git remote -v`).

## T01 decisions

- `.gitignore`: upstream's file plus the planning file's missing lines (`refs/`, `.venv/`, `.DS_Store`) under
  `# ---- raiders-recomp ----`. Every other planning line was already in upstream's file.
- `refs/Hookshot` removed. **verified:** it held only ignored build products besides upstream's tree
  (`__pycache__/` folders, `third_party/a64-kit/lift/liba64emit.so` and its `.sha1`). The root checkout has no
  `liba64emit.so` yet: the next Mac lift (T02) builds its own.
- Spikes: the five `refs/Hookshot/nx2` imports now point at the root `nx2/`; they run from the repository root.
- Workflows: `release.yml` and `vulkan-dlss.yml` renamed to `*.yml.disabled`; `linux-appimage.yml` lost its
  `release` job only; `windows-builder.yml` keeps its name and its `release` job, guarded to
  `github.repository == 'NotRexed/Hookshot'`. `source-regressions.yml` unchanged.
- `readme.md`: a 14-line "raiders-recomp (fork)" section on top; nothing below it changed (`git diff --numstat`:
  14 added, 0 deleted).

## Acceptance (T01, 2026-11-10, branch `task/T01-fork-setup`)

All **verified** by running the commands on the Mac:

| Check | Result |
|---|---|
| `git remote -v` | `origin` = `nicfran01/Hookshot` (fetch and push), `upstream` fetch = `NotRexed/Hookshot`, push `DISABLED` |
| `git merge-base --is-ancestor upstream/main HEAD` | `history ok` |
| `git check-ignore -v work refs .venv build-linux/` | all four ignored (`.gitignore` lines 3, 43, 44, 35) |
| `git ls-files \| grep -Ec '^(work\|refs\|\.venv)/'` | `0` |
| `git ls-files docs/plans CLAUDE.md spikes \| wc -l` | `43` |
| `ls .github/workflows` | `linux-appimage.yml`, `release.yml.disabled`, `source-regressions.yml`, `vulkan-dlss.yml.disabled`, `windows-builder.yml` |
| `head -20 readme.md` | the fork section, then upstream's README from its first line |
| `tests/run_all.py recomplauncher_json appimage_package_retry appimage_player_build stick_dead_zone` | 4 passed, 0 failed, 0 skipped (the four checks that read the changed workflows and `readme.md`) |
| byte-compile of `spikes/*.py` | 6 files, no error |

The full game-free suite was not run here: T02 takes the Mac baseline.

## Deviations

- **The task's ignore check could not run as written.** `git check-ignore -q work refs .venv build-linux`
  fails with `fatal: --quiet is only valid with a single pathname` (**verified**). Checked one path at a time
  instead; `build-linux` needs the trailing slash while the folder does not exist, since `build-linux/` matches
  folders only (**verified**: ignored once created). The acceptance line in `T01-fork-setup.md` is corrected.

- **`windows-builder.yml` is guarded, not renamed** (blocker `BLOCKER-T01-2026-11-10.md`, decided by the user).
  **verified:** `tests/test_recomplauncher_json.py:31` (`test_windows_zip_carries_it`) reads
  `.github/workflows/windows-builder.yml` by path and asserts two strings in it, so a rename fails it. The blocker's
  option 1 (remove its `release` job) was wrong too: **verified** by `grep -n 'Windows-x64.zip'`, the asserted
  `dist/Hookshot-*-Windows-x64.zip` is only in that job. The user chose the one-line guard instead: the job cannot
  run in the fork even if `vars.CI_RELEASE_WINDOWS` is set. The acceptance line `ls .github/workflows` therefore
  shows two `*.disabled` files, not three. `T01-fork-setup.md` and `03-architecture.md` §7 are updated to match.
