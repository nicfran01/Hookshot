# 06 · Handoff guide: driving Opus sessions

Each task in `docs/plans/tasks/` is written for one Claude Code session with Claude Opus 5.5 in this
repository. `CLAUDE.md` at the repo root loads automatically and carries the rules; the task file carries the
work.

## 1. Before a session

1. Check the task's **Dependencies** are done (their reports exist in `docs/plans/reports/`).
2. If the task runs anything on the Deck: the Deck is on, on the same network, SSH works
   (`ssh deck@steamdeck true`), and the dump is at `~/raiders/dump`.
3. `git status` is clean and `main` is pushed. Each task works on its own branch `task/TNN-short-name`.
4. At the start of a milestone, do the upstream merge first (its own short session; prompt in §3).

## 2. The prompt template

Paste this, with the task number filled in:

```text
You are implementing one task of the raiders-recomp plan. Work only on this task.

Task file: docs/plans/tasks/T<NN>-<name>.md

Do this, in order:
1. Read CLAUDE.md, then the task file, then every document the task lists under "Read first".
2. Create the branch task/T<NN>-<name> from main.
3. Before changing anything, tell me in a few lines what you will do and anything in the task that looks
   wrong or out of date against the code as it is now. If something material is wrong, stop and write a
   blocker report (docs/plans/06-handoff-guide.md §5) instead of improvising.
4. Do the work. Stay inside the task's scope and "Files to touch". Follow upstream's conventions
   (CONTRIBUTING.md, AGENTS.md): python -I, tests in the same change, no reshaping of functions the tests
   read by text unless you update those tests.
5. Run every command under "Acceptance criteria" and show me the real output. For Deck commands use
   scripts/deck/*.sh. If a criterion cannot be met, say so plainly: do not weaken it.
6. Write the task's report to docs/plans/reports/ as the task specifies (names, counts, timings and
   decisions only: no game code, strings, assets or screenshots).
7. Commit (Conventional Commit subject), and stop. Do not push, open a PR or merge unless I say so.

Hard rules: never commit or copy out anything from the dump or made from it (work/, lifted C, image.bin,
shader blobs, screenshots, saves). Never contact Nintendo network services. Label claims in reports as
verified, inferred or unknown.
```

For the two conditional tasks (T14, and any "implement what the trace shows" step) add one line naming the
trigger, for example: `Trigger: M4 report lists program keys with dropped geometry stages: <keys>`.

## 3. Other reusable prompts

**Upstream merge**

```text
Merge upstream Hookshot into main following docs/plans/03-architecture.md §6. Fetch upstream, merge
upstream/main, resolve conflicts with "upstream wins, re-apply our game-config lookup", run
python -I -B tests/run_all.py, and append one line to docs/plans/reports/upstream-sync.md (date, upstream
commit, files that conflicted). Show me the conflict list before committing the merge. Do not push.
```

**Triage of a failed Deck run**

```text
The last Deck run is in work/runs/<name>/ (fetch it with scripts/deck/fetch.sh <name>). Read
hookshot_log.txt from the end, find the first error or the last line before the stall, and tell me which
subsystem it points at (docs/plans/02-gap-analysis.md section numbers) and which task owns it. Do not change
code in this session.
```

## 4. Conventions

- **Code style:** match the file being edited. Upstream's C is compact with trailing comments explaining why;
  Python is plain standard library plus `lz4`, `numpy`, `capstone`, `unicorn`, `zstandard`. New files start
  with a comment saying what the file is for, as upstream's do. Mark edits to upstream files with
  `(raiders)` in a comment, the way upstream marks its own with `(hookshot)`: it makes merges and upstream
  PRs easier.
- **Where code goes:** `03-architecture.md` §2. If a change needs a Raiders-specific `if` in a shared file,
  put the decision in `games/raiders/game.py` (or a function in a new file) and make the shared file ask.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `perf:`, `refactor:`, `test:`, `docs:`, `build:`,
  `chore:`), imperative subject, body says why. One task may have several commits; each builds. The commit
  trailer is `Co-Authored-By:` with the model that did the work (upstream's `docs/design.md` §8 does the
  same).
- **Tests:** every new Python module gets a `tests/test_<name>.py` that runs without a dump (use tiny
  synthetic inputs, as upstream's `tests/test_nup_*.py` do). `python -I -B tests/run_all.py` must be no worse
  than the baseline in `docs/plans/reports/mac-test-baseline.md`.
- **Never committed:** anything under `work/`, `refs/`, `build-linux/`; lifted C; `image.bin`;
  `*_shaders.bin`; shader or stage dumps (`RX_VK_DUMP_FAILED` output is game data); screenshots; saves;
  logs that contain game strings. `git add` by path, never `git add -A`.
- **Reports:** `docs/plans/reports/<milestone or task>-<topic>.md`. Allowed content: mangled SDK symbol
  names, NVN proc names, counts, addresses and hashes, timings, decisions. Not allowed: disassembly or lifted
  code of the game, game text, asset contents.
- **Evidence tags:** verified (with a path, command or log line), inferred, unknown.
- **Deck runs:** one game run at a time; muted unless the task is about audio; each run has a name and
  lives in `work/runs/<name>/` on both machines.
- **Asking the user:** system changes on the Deck (SSH, swap, SteamOS settings), creating the GitHub fork,
  opening PRs, and anything that publishes are the user's actions. A session prepares exact steps and waits.

## 5. Blocker and deviation reports

When a task cannot be completed as written, the session stops and writes
`docs/plans/reports/BLOCKER-T<NN>-<date>.md`:

```markdown
# Blocker: T<NN> <title>   (<date>)
## What the task asked
## What was found            (with evidence: file:line, command and output, log lines)
## What was tried
## Options                   (2-3, each with cost and risk)
## Recommendation
## State left behind         (branch name, what is committed, what is safe to discard)
```

A **deviation** (the task was completed, but differently from the plan) goes in the task's normal report
under a `## Deviations` heading with the reason.

To revise the plan, bring the blocker report back to the planning session (Fable) with:

```text
Read docs/plans/reports/BLOCKER-T<NN>-<date>.md and the task file it refers to. Revise the plan: edit the
affected task files and docs/plans/05-roadmap.md (add a change-log line), and tell me what changed and why.
Planning only: no production code.
```

## 6. What "done" means for a task

- Every acceptance command was run and its output shown, or the failure is reported as a blocker.
- The report exists.
- `git status` shows nothing from the dump staged or untracked outside ignored folders
  (`git status --porcelain --ignored | grep -v '^!!'` lists only intended files).
- The branch is committed and not pushed; you review, then merge to `main` and push.
