# T09 · Trace harness and the M3 call report

**Milestone:** M3 · **Depends on:** T08 · **Machine:** Mac driving the Deck

## Context
Static analysis lists 279 stubbed OS imports and 325 NVN names without an implementation, but not which the
game calls (`docs/plans/02-gap-analysis.md` §3, §5). The runtime already logs the first call of every
generated stub and of every NVN proc it lacks (`nx2/standalone.py` docstring; `host/PROVENANCE.md`).
This task turns those log lines into a report that drives T10 and T11, and looks for two specific things:
the queues and event waits the game uses, and where it reads GPU results on the CPU.

## Read first
- `CLAUDE.md`; `docs/plans/reports/M2-boot.md`; `docs/plans/02-gap-analysis.md` §3, §5
- `docs/design.md` §4 (rules 1-4 and their "check early" notes)
- `nx2/standalone.py` `gen_stubs` (the stub's log text), `host/nvn_native.c` `nvn_native_proc` and the
  fallback for unknown names, `hos_log` in `host/`

## Scope
1. `scripts/trace_report.py`: reads one or more `hookshot_log.txt` files and prints/writes a Markdown table.
2. Runs on the Deck up to the first crash, hang or present, with and without `HOS_NVN_STRICT=1`.
3. `docs/plans/reports/M3-trace.md`.

## Non-goals
- No fixes (T10, T11). No changes to what the runtime logs, unless a category is not logged at all; then add
  a first-call log in the same style and mark it `(raiders)`.

## Interfaces
```
python -I scripts/trace_report.py <log> [<log> …] [--stubs work/standalone_stubbed.txt] [--md out.md]
```
Output sections: (1) OS stubs called: mangled name, demangled name if `c++filt` is available, first-call
order, namespace; (2) NVN procs called without an implementation; (3) NVN procs called with one (counts, if
logged); (4) services opened by name (`ConnectToNamedPort`, `sm:` lookups); (5) queues created and
`nvnCommandBufferWaitEvent` uses; (6) the last 20 runtime lines before the end.
It parses by the fixed prefixes the runtime prints; unit-test it with a synthetic log
(`tests/test_trace_report.py`), not a real one.

## Steps
1. Read the exact log formats (do not guess them) and write the parser and its test.
2. Run `scripts/deck/run.sh trace1 120 -- HOS_NO_MOVIES=1` and `trace2` with `HOS_NVN_STRICT=1`; fetch both.
3. For each stub called before the end: classify **safe** (returning 0 is a correct offline answer),
   **wrong answer** (0 means success where failure is needed, or an out-parameter is left unset),
   **blocking** (the game stops or loops because of it). Use the mangled signature to judge out-parameters.
4. NVN: for each unimplemented proc called, note what state it sets and whether the op stream needs it.
5. Queues and events: log which queues exist and how many event waits per frame occur
   (`docs/design.md` §4 rule 1 asks for this on a new game).
6. Read-backs: search the trace for texture or buffer read-back procs (`nvnTextureReadTexels`-style names in
   `work/nvn_main.txt`, buffer maps of GPU-written pools). List candidates for the ink read-back path
   (`00-overview.md` risk 2) with evidence, or state that none appears before gameplay.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py test_trace_report
.venv/bin/python -I scripts/trace_report.py work/runs/trace1/hookshot_log.txt --md docs/plans/reports/M3-trace.md
grep -c "^|" docs/plans/reports/M3-trace.md         # tables present
git diff --stat                                     # only scripts/, tests/, docs/plans/reports/
```

## Report
`docs/plans/reports/M3-trace.md` (generated, then annotated by hand): every called stub and missing NVN proc
with a class (safe / wrong answer / blocking) and the owning task (T10 for OS, T11 for NVN); the queue and
event summary; read-back candidates. Names and counts only.
