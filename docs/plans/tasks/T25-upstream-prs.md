# T25 · Prepare generic fixes for upstream Hookshot

**Milestone:** M8 (and ad hoc earlier) · **Depends on:** the task that produced each fix · **Machine:** Mac

## Context
The user chose to send generic fixes upstream. Upstream's rules: no game files or anything made from them;
Conventional Commit subjects; "open the description with why the PR is needed"; screenshots when the change
shows on screen; tests in the same PR; game-free checks must pass (`AGENTS.md`, `CONTRIBUTING.md`,
`docs/versioning.md`). Upstream's maintainer cannot test Raiders, so each PR must be justified and tested
without it. This task can be run more than once: after M1 for the dictionary fix, at M8 for the rest.

## Read first
- `CLAUDE.md` (constraint 7: the user opens PRs); `docs/plans/03-architecture.md` §6
- `CONTRIBUTING.md` in full, especially "Before you open an issue or a PR", "Commits and pull requests",
  "Licensing"; `docs/versioning.md` "Commits decide the version"
- The reports that flagged upstream candidates: `T05-ingest.md`, `T04-game-config.md`, `T07-game-gates.md`,
  `T10-offline.md`, `T11-nvn2.md`, `T14-geometry.md`, `T21-shader-caches.md`

## Candidates (as known at planning time; the reports are authoritative)

| # | Fix | Files | Generic because |
|---|---|---|---|
| 1 | `Pack/ZsDic.pack.zs` optional | `nx2/shader_census.py`, `nx2/prompt_assets.py`, `gpu/vk/vk_game_font.h` | Any game without zstd dictionaries; a romfs mod that removes it |
| 2 | `*.part` and dotfiles ignored by romfs checks | `nx2/make_game.py` or the new check | Robustness |
| 3 | Per-game config module replacing hardcoded build id, languages, names | `nx2/game.py`, `games/`, `nx2/make_game.py`, `nx2/lift.py` | The maintainer has three ports from one pipeline; ask in an issue first whether they want it |
| 4 | Guards on game-specific entry points | `host/hos_main.c`, `gpu/vk/vk_menu.cpp`, `gpu/vk/vk_shader.cpp` | Only with #3 |
| 5 | Offline answers for `nn::ldn`, `nn::nfp`, `nn::friends`, `nn::swkbd` | `host/nn_offline.c` | Any game linking them |
| 6 | NVN2 procs added | `host/nvn_native.c` | Any NVN 21.4.x/22.x game |
| 7 | Geometry-stage support | `gpu/vk/vk_shader.cpp`, Eden front end | Any game with geometry shaders |
| 8 | Draw-time pipeline compile counter in the status line | `gpu/vk/vk_draw.cpp` | Diagnostics |
| 9 | Linux path for the lifter's differential tests (T08a) | `nx2/test_leaf.py`, `nx2/test_insn.py` | Their harnesses use `windows.h`, `VirtualAlloc` and SEH, so the lifter cannot be checked on Linux. The vendored `third_party/a64-kit/tests/insn_test.py` is not edited; say in the PR that a fix there belongs to a64-kit |

## Scope
For each candidate that still applies:
1. A branch `upstream/<short-name>` cut from `upstream/main` (not from `main`), containing only that fix,
   with the `(raiders)` markers removed and no reference to Raiders' data.
2. Tests that run without any dump.
3. A PR description file `docs/plans/reports/upstream/<short-name>.md` in upstream's format.

## Non-goals
- Opening PRs, pushing branches, or commenting on upstream issues: the user does these.
- Upstreaming anything Raiders-specific (`games/raiders/`, Deck scripts, the plan).
- Splitting hairs: if a fix cannot be justified without Raiders, list it as "kept in the fork" with the
  reason.

## Steps
1. `git fetch upstream`. For each candidate: `git switch -c upstream/<name> upstream/main`, re-apply the fix
   by hand or `git cherry-pick -n` and trim. Check upstream has not already fixed it
   (`git log upstream/main --oneline -- <files> | head`).
2. Run `python -I -B tests/run_all.py` on the branch.
3. Description: first sentence = why (for #1: "A game folder without `Pack/ZsDic.pack.zs` stops the shader
   census with FileNotFoundError; games of this engine exist without zstd dictionaries"). Then what changed,
   how it was tested (game-free test names; "run on a second Switch 2 title" stated without naming files or
   contents beyond what is needed), and risks. No screenshots from the game unless the change is visual and
   the user supplies and approves them.
4. Commit subject per `docs/versioning.md` (`fix: …`, `feat: …`); upstream's release tooling reads it.
   Trailer per upstream's convention (`docs/design.md` §8).
5. For #3, write an issue text first (`docs/plans/reports/upstream/game-config-issue.md`) describing the
   proposal in ten lines and asking whether a PR is welcome. Do not prepare the big PR until the user
   reports the answer.
6. Give the user, per branch, the two commands to publish it (`git push origin upstream/<name>`, then the
   GitHub compare URL against `NotRexed/Hookshot:main`).

## Acceptance criteria
```bash
git branch --list 'upstream/*'
for b in $(git branch --list 'upstream/*' --format='%(refname:short)'); do
  git diff --stat upstream/main...$b | tail -1
  git diff upstream/main...$b | grep -ciE "raiders|0400380020056000|abb30e2f"      # 0 for every branch
done
ls docs/plans/reports/upstream/
```
Each branch passes `python -I -B tests/run_all.py` (show the summary line per branch).

## Report
`docs/plans/reports/upstream/README.md`: a table of candidates (branch, state: ready / kept in fork /
already upstream / waiting for the maintainer's answer), and the commands for the user.
