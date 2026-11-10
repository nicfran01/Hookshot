# T08 · First Raiders build on the Deck; boot to `nnMain`

**Milestone:** M2 (exit) · **Depends on:** T03, T05, T06, T07 · **Machine:** Mac driving the Deck

## Context
Nothing of Raiders has been compiled or run yet. Hookshot's own stage S2 is the model: the standalone lift
and a full build link, and "the boot runs `_init_libc*`, `nnosInitialize`, `nninitStartup`, the modules'
DT_INIT, `nnMain` and reaches `nvnBootstrapLoader`" (`docs/design.md` §6). Raiders is SDK 21.4.4; the runtime
was last tuned for SDK 22.2.8 on top of a base written for SDK 21.4.0.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §2-§5; `docs/plans/reports/T06-lift.md`,
  `deck-environment.md`
- `docs/design.md` §3, §6, §9 (the S2 and S3 notes list what a first boot needed for Hookshot's game)
- `docs/development.md` "Use" and "Switches for testing and debugging"
- `host/hos_main.c` lines 1-260 (boot), `host/hos_svc.c`, `host/hos_thread.c` (TLS set-up)

## Scope
1. `scripts/deck/build.sh` default mode: lift + build on the Deck from `~/raiders/dump`.
2. Fix compile and link errors caused by Raiders (new stub names, generated-file differences).
3. Run headless with tracing; fix what stops the boot before `nnMain`/`nvnBootstrapLoader` when the fix is
   small and clearly in scope (a missing SVC answer, a TLS field, an SDK 21 overload). Anything larger is
   recorded for T09-T11.

## Non-goals
- No picture. No NVN proc implementations beyond what the boot needs before the bootstrap loader.
- No performance work, no hot list (none exists; the build must work without `work/hot_funcs.txt`).

## Steps
1. `scripts/deck/sync.sh`, then `scripts/deck/build.sh`: in the container, with
   `OOT_WORK=~/raiders/work OOT_DUMP=~/raiders/dump HOOKSHOT_JOBS=4 HOOKSHOT_KEEP_BUILD_FILES=1`:
   `python -I nx2/make_game.py --check --exefs …`, `python -I nx2/lift.py --standalone --write`,
   `python -I nx2/build.py --standalone --jobs 4`. Log to `~/raiders/work/build.log`. Record wall time and
   peak memory (`/usr/bin/time -v`).
   - Pitfall: 16 GB. Leave the memory gate on. If the kernel kills a compiler (`make_game.py:100`
     `killed_reason` describes the symptom), lower to `HOOKSHOT_JOBS=3`.
   - Pitfall: `build.py` looks for FFmpeg and SDL2 through `EMSDK`, `RX_CPM`, `HOOKSHOT_FFMPEG`,
     `HOOKSHOT_SDL2` (`builder/linux/AppRun` shows the full set the AppImage exports). Mirror those in
     `build.sh`, pointing into `~/raiders/deps`.
2. The lifter's differential tests are T08a's, not this task's: as written their harnesses are Windows only
   (T02). If T08a is done, read its report before step 4: a failing form or function it lists may explain a
   boot stop. (Revised 2026-11-10.)
3. First run: `scripts/deck/run.sh boot1 60 -- HOS_TRACE=1 HOS_NO_MOVIES=1` (headless, muted). Fetch the log.
4. Walk the log from the top. For each stop:
   - an unimplemented SVC or `svcGetInfo` id → `host/hos_svc.c`;
   - a null read near thread start → compare the TLS layout notes in `docs/design.md` §9 ("TLS: the owner
     handle at TLR+0x110 too (SDK 22)") with what SDK 21.4.4's `sdk` reads: disassemble the faulting lifted
     function's guest address with Capstone on the Mac (`work/image/image.bin`, base `0x80000000`);
   - "first call" lines from generated stubs → note the name; implement only if the boot cannot continue;
   - the NVN API version check: Hookshot reports 231.40 (`host/nvn_native.c`, comment above `devinfo[]`).
     If Raiders refuses it, read the minor it wants from the lifted check and make the reported minor a game
     config value.
   Repeat run → fix → run, naming runs `boot2`, `boot3`, ….
5. Stop when the log shows `nvnBootstrapLoader` reached (or the first `nvnDeviceInitialize`), or after the
   session's budget, whichever comes first.

## Pitfalls
- A run can hang rather than crash. `run.sh` always has a time limit; a hang's last log lines plus
  `HOS_THREAD_TIMES=5` say which thread spins.
- The log may contain file names from the romfs and SDK symbol names. It stays in `work/runs/`; the report
  quotes only SDK and runtime names.
- Do not "fix" a failing stub by returning success blindly for a whole namespace: T09 needs the first-call
  log to stay truthful.

## Acceptance criteria
```bash
scripts/deck/build.sh 2>&1 | tail -5                          # ends with the path of work/sa/build/hookshot
ssh $DECK_HOST 'ls -la ~/raiders/work/sa/build/hookshot ~/raiders/work/sa/build/hookshot_vk.so'
scripts/deck/run.sh bootN 60 -- HOS_TRACE=1 HOS_NO_MOVIES=1 && scripts/deck/fetch.sh bootN
grep -n "nnMain\|nvnBootstrapLoader\|native NVN device" work/runs/bootN/hookshot_log.txt | head
.venv/bin/python -I -B tests/run_all.py                       # no worse than the baseline
```
The milestone exit is met when the grep shows the boot reached NVN initialisation. If it does not, the task
still completes with a report that names the exact stopping point.

## Report
`docs/plans/reports/M2-boot.md`: build time and peak memory on the Deck, size of the executable, each boot
stop in order with its cause and fix (file:line), the SDK 21 versus 22 findings, the stopping point, and the
list of stub names seen so far (input to T09).
