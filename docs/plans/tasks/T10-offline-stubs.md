# T10 · Offline answers for network, local wireless, amiibo, friends, keyboard

**Milestone:** M3 · **Depends on:** T09 · **Machine:** Mac driving the Deck

## Context
Raiders links NPLN, Pia (online, local, LAN), `nn::ldn`, `nn::nfp`, `nn::friends`, `nn::swkbd`. The project
is offline by constraint. The runtime must make the game see a console with no network, no local wireless
partners, no amiibo reader activity and no friends, and must never open a real socket to a Nintendo service.
Hookshot already gives offline answers for its own game's NPLN path (`docs/design.md` §9: empty answers on
`sm:` sessions, `nsd::GetEnvironmentIdentifier` "lp1", `socket::detail::Poll` nothing ready,
`EnsureNetworkServiceAccountIdTokenCacheAsync` fails). Generated stubs return 0, which for many of these
functions means "success" and is the wrong answer.

## Read first
- `CLAUDE.md` (constraint 3); `docs/plans/reports/M3-trace.md` (classes "wrong answer" and "blocking");
  `docs/plans/02-gap-analysis.md` §3
- The existing offline HLEs: `grep -n "nifm\|nsd\|socket\|EnsureNetworkServiceAccount\|ConnectToNamedPort"
  host/*.c`
- `work/standalone_stubbed.txt` (regenerate with `spikes/standalone_summary.py`) for the exact mangled names
- For result-code conventions only: how existing HLEs return a failure `nn::Result` (`RET(...)` in `host/hos.h`)

## Scope
`host/nn_offline.c` (new), holding `HLE()` implementations for the functions the trace marked wrong or
blocking in these namespaces: `nn::ldn` (26), `nn::nfp` (23), `nn::friends` (6 + the lifted callers' needs),
`nn::swkbd` (7), `nn::nifm` (9), remaining `nn::socket`/`nnsocket*`/`nn::ssl`, `nn::account` network-token
calls, `nn::prepo`, `nn::err` viewer calls.

Behaviour to implement:

| Area | Answer |
|---|---|
| `nn::nifm` | Initialise succeeds; network not available; requests complete immediately with "not connected" |
| `nn::socket`, `nn::ssl` | No function ever reaches the host's network stack. Creation fails or `Poll`/`Select` report nothing ready, matching what exists upstream |
| `nn::ldn` | `Initialize`/`Finalize` succeed; state stays `None`/`Initialized`; `Scan*` returns 0 networks; `CreateNetwork`, `Connect*` return a failure result; `GetNetworkInfo`/`GetIpv4Address` fail; the state-change event is created and never signalled |
| `nn::nfp` | `Initialize` succeeds; `ListDevices` returns 0 devices; device-state queries say "unexpected/none"; events created, never signalled |
| `nn::friends` | Empty friend list; presence calls succeed and do nothing |
| `nn::swkbd` | `ShowKeyboard` returns the "cancelled" result; size queries return plausible fixed sizes |
| `nn::account` network token / NSA id | Fail as upstream does for `EnsureNetworkServiceAccountIdTokenCacheAsync` |
| `nn::prepo` (play reports), `nn::err` (error viewer) | Succeed and do nothing; log the error code once for `nn::err` |

## Non-goals
- No LAN or relay implementation of local play (out of scope by the user's decision; Recompia's
  `runtime/src/services/ldn_*.cpp` is the pointer if that changes).
- No host keyboard prompt. No amiibo emulation.
- Do not implement functions the trace never saw unless they are in the same small family as one it did
  (for example every `nn::ldn` state getter): keep the file reviewable.

## Steps
1. For each function, take the exact mangled name from `work/standalone_stubbed.txt` and write the `HLE()`
   with a one-line comment giving the demangled signature and the answer.
   - Pitfall: an `HLE()` for a name is picked up at lift time (`nx2/standalone.py`), so adding one changes
     the lift key and triggers a relift on the Deck (`make_game.py:1037`). Batch the additions; expect one
     full lift + partial compile per iteration.
   - Pitfall: result codes. Do not invent module/description numbers. Where the SDK's own lifted code
     defines the result a caller compares against, read that comparison in the lifted C on the Deck
     (`~/raiders/work/sa/gen`) or disassemble the caller on the Mac, and return what makes the caller take
     its "not available" branch. Record each such finding in the report by function name.
   - Pitfall: out-parameters (counts, handles, info structs) must be written (zeroed) even on failure.
2. Add `nn_offline.c` to the host sources list in `nx2/build.py` (next to the other `host/*.c`; see how
   `nn_gs.c` or `mods.c` is listed) for both Linux and Windows builds.
3. Test without the game: `tests/test_nn_offline.py` in upstream's style (cut each `HLE` out of the source by
   text, compile with stub `Ctx` helpers, call it, assert the result and out-parameters), covering at least
   `nn::ldn::Scan*`, `nn::nfp::ListDevices`, `nn::swkbd::ShowKeyboard`.
4. Build and run on the Deck: `scripts/deck/build.sh && scripts/deck/run.sh offline1 180 -- HOS_NO_MOVIES=1`.
   Re-run `scripts/trace_report.py`: no entry of these namespaces may remain "wrong answer" or "blocking".
5. Network guard: add one check that fails loudly if anything in the process calls the host's `connect()`
   to a non-loopback address (a wrapper in `host/posix/` or an `LD_PRELOAD`-free compile-time wrap; choose
   the simplest that `build.py` supports) and run with it enabled for the acceptance run.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py test_nn_offline
scripts/deck/build.sh && scripts/deck/run.sh offline1 180 -- HOS_NO_MOVIES=1 && scripts/deck/fetch.sh offline1
.venv/bin/python -I scripts/trace_report.py work/runs/offline1/hookshot_log.txt | grep -E "ldn|nfp|friends|swkbd|nifm|socket|ssl"
#   every listed call is now "implemented"; none is "blocking"
grep -ci "connect(" work/runs/offline1/hookshot_log.txt     # 0 outbound connection attempts logged by the guard
.venv/bin/python -I -B tests/run_all.py                     # no worse than the baseline
```

## Report
`docs/plans/reports/T10-offline.md`: table of functions implemented with their answers, the result-code
findings, what the game does next in the boot after these answers (from the log), and which parts are generic
enough for an upstream PR.
