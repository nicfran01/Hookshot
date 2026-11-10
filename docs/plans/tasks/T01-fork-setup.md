# T01 · Turn the working directory into the fork

**Milestone:** M0 · **Depends on:** the user has created a GitHub fork of `NotRexed/Hookshot` (user action)
· **Machine:** Mac

## Context
The working directory is not a git repository yet. It holds planning output (`CLAUDE.md`, `docs/plans/`,
`spikes/`, `.gitignore`), study clones in `refs/`, a venv and `work/`. The project must become a fork of
Hookshot with upstream's history and paths (`docs/plans/03-architecture.md` §1, §6).

## Read first
- `CLAUDE.md`
- `docs/plans/03-architecture.md` §1, §2, §6, §7
- `refs/Hookshot/AGENTS.md`, `refs/Hookshot/CONTRIBUTING.md` ("The rule with no exceptions", "Licensing")

## Scope
1. Make this directory a git clone of the user's fork with `upstream` pointing at NotRexed/Hookshot, without
   losing the planning files.
2. Merge the two `.gitignore` files.
3. Disable upstream's release workflows in the fork.
4. Add a short project section to `readme.md` and record the upstream base.

## Non-goals
- No code changes to `nx2/`, `host/`, `gpu/`.
- No push. No GitHub settings changes. Do not create the fork (the user does).
- Do not delete `refs/Recompia`.

## Files to touch
- `.gitignore` (merge), `readme.md` (prepend a section), `.github/workflows/release.yml`,
  `vulkan-dlss.yml` (rename to `*.yml.disabled`), `windows-builder.yml` (guard its `release` job to upstream's
  repository), `linux-appimage.yml` (remove or comment out only the `release` job),
  `docs/plans/reports/upstream-sync.md` (new), `spikes/*.py` (path fix).

## Steps
1. Ask the user for the fork's URL. If there is no fork yet, give them the steps (GitHub → NotRexed/Hookshot →
   Fork) and stop.
2. Safety check before any git command: `ls work refs .venv` exist and will be ignored. Move the planning
   `.gitignore` aside: `mv .gitignore .gitignore.raiders`.
3. `git init -b main`, `git remote add origin <fork url>`, `git remote add upstream
   https://github.com/NotRexed/Hookshot`, `git remote set-url --push upstream DISABLED`,
   `git fetch upstream`, then `git reset --mixed upstream/main && git checkout -- .`
   - Pitfall: `git checkout -- .` restores upstream's tracked files into the directory. It must not
     overwrite `CLAUDE.md`, `docs/plans/`, `spikes/` (upstream has none of them; verify with
     `git ls-tree -r upstream/main --name-only | grep -E '^(CLAUDE.md|docs/plans/|spikes/)'` printing
     nothing first). Upstream does have `docs/`: only `docs/plans/` is ours.
   - If the planning base matters for reproducing numbers: the plan was written against `88b554e`. Start from
     `upstream/main` as fetched (newer is fine) and record both commits.
4. Merge ignores: append every line of `.gitignore.raiders` that upstream's `.gitignore` lacks, under a
   `# ---- raiders-recomp ----` heading; delete `.gitignore.raiders`. `refs/`, `.venv/`, `work/`,
   `build-linux/` must be ignored.
5. `refs/Hookshot` is now redundant with the repo root: delete that clone (it is ignored and contains a built
   `liba64emit.so` and nothing of the game; check with `git -C refs/Hookshot status --porcelain --ignored`
   that nothing else was left in it, then `rm -rf refs/Hookshot`). Update the `refs/Hookshot/nx2` path in each
   `spikes/*.py` to the root `nx2`, and the note at the top of `spikes/README.md`.
6. Workflows: rename `release.yml` and `vulkan-dlss.yml` to `.disabled`; in `linux-appimage.yml` remove the
   `release` job only; in `windows-builder.yml` keep the file and its `release` job (a test reads both:
   `tests/test_recomplauncher_json.py`) and add `github.repository == 'NotRexed/Hookshot' &&` to the job's `if:`.
   Keep `source-regressions.yml`. (Revised 2026-11-10 after `reports/BLOCKER-T01-2026-11-10.md`.)
7. `readme.md`: add at the very top a section "raiders-recomp (fork)" of at most 15 lines: what this fork is
   for, that it is unofficial and contains no game data, a link to `docs/plans/00-overview.md`, and
   "Everything below is upstream Hookshot's README". Change nothing below it (credits and licence stay).
8. Write `docs/plans/reports/upstream-sync.md` with a table: date, upstream commit, conflicts. First row:
   today, the fetched `upstream/main` commit, "initial".
9. Commit in two commits: `chore: add raiders-recomp planning documents and spikes` (CLAUDE.md, docs/plans,
   spikes, .gitignore) and `ci: disable upstream release workflows in the fork` (+ readme section).

## Pitfalls
- Never `git add -A`. Add by path. `git status --porcelain` before each commit must list no file under
  `work/`, `refs/`, `.venv/`.
- `*.bin` is ignored on purpose (game images). Do not add exceptions.

## Acceptance criteria
```bash
git remote -v                                   # origin = the fork, upstream fetch = NotRexed/Hookshot, push DISABLED
git merge-base --is-ancestor upstream/main HEAD && echo "history ok"
git check-ignore -q work refs .venv build-linux && echo "ignores ok"
git ls-files | grep -Ec '^(work|refs|\.venv)/'  # 0
git ls-files docs/plans CLAUDE.md spikes | wc -l # > 30
ls .github/workflows                            # source-regressions.yml, linux-appimage.yml, windows-builder.yml, two *.disabled
head -20 readme.md                              # the fork section, then upstream's README
```

## Report
`docs/plans/reports/upstream-sync.md` (created here). No other report.
