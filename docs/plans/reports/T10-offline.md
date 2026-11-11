# T10 · Offline guard and offline answers (2026-11-11)

**Short answer.**
- **Part A is done.** A source check fails on any network call in the runtime outside a 5-entry allowlist (each entry
  with its reason). The Discord status was already off for this game; the test now guards that. `run.sh --net-check`
  samples the game's sockets.
- **The acceptance run `offline1`** opened **no TCP or UDP socket in 39 samples** (only Unix-domain sockets) and logged no
  Discord line.
- **Part B was triggered** by one wrong answer in T10's namespaces, `nn::prepo::GetOverSaveFrequencyLimitEvent` (T09a's
  `font1` trace). It is implemented with its family in `host/nn_offline.c`.
- **Where the boot is:** past the font call, at the same interactive menu, with no crash in 180 s.

Claims are **verified** (command, file:line, log line or Capstone disassembly of `work/sa/image/image.bin`) unless marked
**inferred** or **unknown**. Names, counts and decisions only.

## Branch base

T10 depends on T09a, which was not on `main`. By the user's choice, `task/T09a-builtin-font-stand-in` was merged into
`main` locally (`374154a`, `--no-ff`, not pushed). The old `task/T10-offline-stubs` (its one commit, the blocker report,
is the same content as `main`'s `df5950f`) was deleted and the branch made again from `main`.

## Part A

### A1 · Source check (`tests/test_no_network.py`)

- **What it scans:** every `.c/.cpp/.h/.hpp/.cc/.inl` under `host/` and `gpu/vk/` (`gpu/vk/eden` included,
  `third_party/` not), with C and C++ comments taken out and line numbers kept.
- **What it looks for:** the task's patterns (`socket(`, `connect(`, `getaddrinfo(`, `sendto(`, `WSAStartup`, `curl_`),
  plus `gethostbyname(`, WinHTTP (`WinHttp*(`), WinINet / `URLDownloadTo*`, and a `curl`/`wget` command line in a string.
  The extras are needed: without them, the scan misses the one real network user, the update offer.

| Allowed (file, pattern) | Reason |
|---|---|
| `host/discord_rpc.c`, `socket(` / `connect(` | The Discord status: an `AF_UNIX` socket to a Discord client on this machine (local IPC). It starts only for upstream's game (A2) |
| `host/hos_update.c`, `WinHttp` / curl command | Upstream's update offer: one HTTPS GET to `api.github.com`, not a Nintendo service. It runs only in a game folder with `hookshot_version.txt`, and `HOOKSHOT_NO_UPDATE_CHECK=1` turns it off (`hos_update.c:97`, `:261-262`) |
| `host/nn_audio_in.c`, `connect(` | A function of its own named `connect` (it opens the microphone), not the socket call |

Four checks: no match outside the allowlist; every allowlist entry still matches something (stale ones fail); the patterns
catch what they should and comments do not count; and the Discord gate (A2).

**Finding for the plan (not changed here):** `make_game.py:1742` writes `hookshot_version.txt` into every game folder
it builds, this fork's included. So a player who starts `bin/hookshot` directly gets upstream's update offer: a request to
`api.github.com` for **upstream Hookshot's** latest release, and an offer to "update" the folder with upstream's Builder
(verified by reading). It is not a Nintendo service, so constraint 3 holds. But it is network access the user did not ask
for, and for this fork it is the wrong offer. Gating it like the Discord status, or setting `HOOKSHOT_NO_UPDATE_CHECK=1`
in the shipped `hookshot_env.txt`, fits T24 (packaging). `run.sh` always sets `HOOKSHOT_NO_UPDATE_CHECK=1`, so no Deck
run so far has exercised it.

### A2 · Discord presence

**Already off for this game, and it cannot be turned on** (verified): `hos_discord_start` begins with
`if (!hos_game_is("oot")) return;` (`host/discord_rpc.c:314`, added by T07). That check comes before the `HOS_DISCORD`
switch and the Insert menu's row are read. `offline1`'s log has no line containing "discord" (`grep -ci discord`: 0).

**Deviation from the task:** the task asked for a `DISCORD_PRESENCE = False` field in `games/raiders/game.py`, with the
existing option still able to turn it on. Not done:
- The status text names Ocarina of Time under Hookshot's Discord application (the file's header and `discord_rpc.c:314`'s
  comment). Turning it on for Raiders would publish the wrong game, under an application this project does not own.
- A correct opt-in needs a Discord application of the fork's own, an outward-facing step for the user (constraint 7).

T07's gate already gives what the task's step is for: off for any game but upstream's. `test_no_network.py` now fails if
a merge drops the gate or moves it after the switch.

### A3 · Run-time check (`scripts/deck/run.sh --net-check`)

- **How it samples:** the Deck has `ss` (iproute2 7.1.0) and `lsof` (verified: `command -v`), so `ss` is used. The game
  starts in the background; every 5 s, `ss -tuxanpH` lines whose `users:` list names the game's process tree
  (`pgrep -P`, recursively) go through an awk classifier into `work/runs/<name>/net.txt`.
- **How it classifies:**
  - TCP or UDP with a peer that is not loopback (`127.0.0.0/8`, `::1`, `::ffff:127.*`): `FAIL`.
  - Loopback, or no peer (`*`, `0.0.0.0`, `::`: listening or unconnected): `ok`.
  - Unix-domain: `unix` (expected: Wayland, PipeWire, D-Bus, SDL).
  - The last line counts the samples and failures, written in lower case, so `grep -c FAIL` counts only failure lines.
- **Tests:** `tests/test_deck_scripts.py` gained 2 checks. One covers the option's wiring; it also checks that a run
  without the option still ends with status 0. The other cuts the awk program out of `run.sh` by its markers and runs it
  on 9 sample `ss` lines: IPv4 and IPv6 remote → FAIL; IPv4, IPv6 and v4-mapped loopback, listening and unconnected → ok;
  Unix → unix.

**`offline1`'s output** (verified, `work/runs/offline1/net.txt`): 39 samples, **0 FAIL lines, 0 TCP or UDP sockets at
any time**. There were 152 `unix u_str ESTAB` lines, about 4 Unix stream sockets per sample, with unnamed peers in `ss`.
Which libraries own them is **unknown** (likely SDL, D-Bus and PipeWire clients: **inferred**).

### A4 · What answers `nn::socket` (by reading)

- **No path to a host socket** (verified by A1 and by reading `third_party/a64-kit/rt/a64_rt.c` and `host/hos_svc.c`).
  Lifted guest code reaches the host only through `svc` (`host/hos_svc.c`) and through hooked functions (`host/*.c`
  HLEs and `gen/a64_stubs.c`). Neither opens a network socket (A1). So the game's socket code, lifted or not, cannot
  reach the host's network stack.
- **The C++ `nn::socket::` imports:** the game imports 32. All 32 are generated stubs (`work/standalone_stubbed.txt`):
  they return 0 and run no SDK code.
- **The `nnsocket*` C wrappers in `sdk`:** `sdk` exports 61, and `main`/`subsdk0` import 29 of them. Of those 29:
  - 11 tail-call a generated stub (for example `nnsocketSocket` → `nn::socket::Socket`);
  - 14 tail-call an `sdk` C++ function the game does not import, which therefore stays **lifted** (for example
    `nnsocketConnect` → `nn::socket::Connect`, and `nnsocketGetAddrInfoWithOptions` → `nn::socket::GetAddrInfo`);
  - 4 are their own code.

  (Verified by following each wrapper's first branch through its `sdk` PLT and GOT slot.)
- **What lifted socket and resolver code meets:** it ends in IPC to `bsd:u` and `sfdnsres`, which it can only reach
  through `svc`:
  - `ConnectToNamedPort` (0x1F) returns a session handle `0x7E00000N` and logs `ipc: ConnectToNamedPort(...)`
    (`host/hos_svc.c:482-493`).
  - `SendSyncRequest` (0x21) answers every request with an empty CMIF success ('SFCO', result 0, zeroed outputs) and
    logs the first 64 as `ipc: handle … command …: answered empty` (`host/hos_svc.c:494-512`).
- **What the runs show:** `font1` and `offline1` have **0 `ipc:` lines**. No SDK service client (`sm:`, `bsd:u`,
  `sfdnsres`) was opened before the time limit (verified: `grep -c "ipc: "`).
- **Caveat:** an empty success can be a wrong answer for a lifted socket function (for example a `Connect` that
  "succeeds"). That is a Part B matter for when a trace shows it (**inferred**). It cannot reach a network.

## Part B

**Triggered.** `M3-trace.md` (T09a, `font1`) classed exactly one call in T10's namespaces as a wrong answer:
`nn::prepo::GetOverSaveFrequencyLimitEvent` (lr `0x83cb17d8`). The other T10-namespace calls were classed safe:
`nn::nifm::Initialize`, `nn::prepo::AddInternetConnectionStatus`, `nn::prepo::RequestImmediateTransmission`.

### Implemented (`host/nn_offline.c`, new; generic, no game check)

The family is every `nn::prepo` name in `work/standalone_stubbed.txt` (3, all traced in `font1`).

| Function | Answer | Evidence |
|---|---|---|
| `nn::os::SystemEvent* nn::prepo::GetOverSaveFrequencyLimitEvent()` | A real event, made once on first call (under a lock): 0x40 zeroed bytes from `hos_sys_alloc`, registered with `hos_system_event_init(e, 0)` (manual clear), **never signalled**. The same pointer every call | The SDK's own (`sdk` `0x854d0170`) returns a function-local static `os::SystemEvent` at `0x85e885f8`, 0x30 bytes (the next static is at `0x85e88628`), made once through `os::CreateSystemEvent(obj, ManualClear (0), false)` (`0x854d0200` → `0x8578c690`) (verified). The caller (`main` `0x83cb17d8`) stores the pointer at `[obj+0x48]` (verified); the stub's null would reach whatever waits on it later (**inferred**). Never signalled: nothing is saved, so the save limit is never reached |
| `Result nn::prepo::AddInternetConnectionStatus(PlayReport*, char const*, char const*, char const*)` | 0, nothing added | Reports are dropped (`host/nn_applet.c`: `PlayReport::Save`/`Send` answer 0). The task's table: "succeed and do nothing" |
| `Result nn::prepo::RequestImmediateTransmission()` | 0 | Nothing is saved or sent; the same |

**Result-code findings:** none needed. No function returns a failure, and no module/description number is used.

`nx2/build.py` needed no change: the runtime's `host/*.c` files are found by `os.listdir` (`nx2/build.py` `host_srcs`), so
the task's step 2 is out of date. `tests/test_nn_offline.py` (new) compiles `nn_offline.c` with stand-in helpers
(`-Wall -Werror`) and covers:
- the event: not null, aligned, at least 0x30 bytes, manual-clear, made once, the same pointer every call;
- `AddInternetConnectionStatus`: success, and the report's bytes untouched;
- `RequestImmediateTransmission`: success;
- the source: each HLE has its comment above it, and `nx2/standalone.py implemented()` finds all three, so the lift hooks
  them.

### After (`offline1`)

- The Deck lift now says `273 import stubs` (T09a: 276) (verified: `work/t10_build.log`). The regenerated
  `work/standalone_stubbed.txt` has 273 names and no `nn::prepo` entry.
- `offline1` called **17 generated stubs**. None of the three prepo names is among them (`grep -c "unimplemented
  import.*prepo"`: 0).
- The acceptance grep for T10's namespaces matches **1** row, `nn::nifm::Initialize`, classed **safe**: 0 is success,
  and no network-state query follows before the time limit.
- `M3-trace.md` is regenerated from `font1` and `offline1` together (`font1` has the call counts). The three prepo rows
  now read "implemented, T10 Part B".

## Where the boot stops now

As after T09a: **no stop in 180 s**. `offline1`'s trace summary says `end: no crash or fatal error logged (time limit or
exit); first present: line 5041`, with 37 screenshots. The game waits at the same interactive menu (headless, no input).
That is past the built-in font call, which T09a answers at the same point as before.

## Upstream candidates

- `tests/test_no_network.py`: generic (any merge that adds networking to the runtime). The allowlist's reasons are
  upstream's own components. It is worth offering together with the update-offer finding, since upstream decides whether
  its update check belongs in a guard's allowlist.
- `host/nn_offline.c`'s `nn::prepo` answers: generic (any SDK 21/22 game that asks for the over-save-frequency event).
- `run.sh --net-check` is Deck tooling: kept in the fork.

They are added to T25's list as candidates 11 and 12.

## Deviations

1. **Discord:** no `DISCORD_PRESENCE` field (A2). T07's game-id gate stays, and a test now guards it.
2. **Update offer:** found and allowlisted with its reason, not gated. Gating it is packaging (T24) and outside T10's
   files. See the finding in A1.
3. **Patterns beyond the task's list** (WinHTTP, WinINet, `gethostbyname`, curl/wget command lines), so that the check
   sees the update offer.
4. **`scripts/trace_report.py` (T09's) fixed.** With two logs, rows that tie on first-call order came out in
   hash-randomized order, so the report changed from run to run. The tie-break is now by name, in both sorts.
   `tests/test_trace_report.py` gained a check for it (13 tests). This was needed to regenerate `M3-trace.md` from two
   logs reproducibly (three runs, same MD5).
5. **`nx2/build.py` untouched** (Part B step 2 is out of date: see above).
6. **`work/standalone_stubbed.txt` regenerated** (273 names), so the report's "of the N stubbed imports" stays true.

## Acceptance criteria

| Command | Result |
|---|---|
| `.venv/bin/python -I -B tests/run_all.py test_no_network test_deck_scripts` | `2 passed, 0 failed, 0 skipped`. **Met** |
| `scripts/deck/build.sh && scripts/deck/run.sh offline1 180 --net-check -- HOS_NO_MOVIES=1 && scripts/deck/fetch.sh offline1` | Build 249 s (lift 241 s, `273 import stubs`, `compiled in 4s, 0 failed`, `linked … 451 MB`). The run went to the time limit with 37 screenshots and printed `# net-check: 39 samples every 5 s, 0 failures`; 40 files fetched; the chain's status was 0. **Met** |
| `grep -c "FAIL" work/runs/offline1/net.txt` | `0`. **Met: no non-loopback socket** (no TCP or UDP socket at all) |
| `grep -ci "discord" work/runs/offline1/hookshot_log.txt` | `0`. The log shows nothing about Discord: `hos_discord_start` returns before logging for any game but upstream's (A2). **Met** |
| `.venv/bin/python -I scripts/trace_report.py work/runs/offline1/hookshot_log.txt \| head -12` | `offline1: end: no crash or fatal error logged (time limit or exit); first present: line 5041`. **Met: past the built-in font call** |
| `… \| grep -cE "ldn\|nfp\|friends\|swkbd\|nifm\|socket\|ssl\|prepo\|nn::err"` | `1`: `nn::nifm::Initialize`, classed **safe** in `M3-trace.md`. None is a wrong answer or blocking. **Met** |
| `.venv/bin/python -I -B tests/run_all.py test_nn_offline` | `1 passed, 0 failed, 0 skipped`. **Met** |
| `.venv/bin/python -I -B tests/run_all.py` | With `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`: **323 passed, 9 failed, 9 skipped** of 341 in 721 s (T09a: 321 / 9 / 9 of 339; the 2 new checks pass). The 9 failures are exactly the baseline's 9 (`mac-test-baseline.md`). This run started before Deviation 4's `trace_report.py` fix, so `test_trace_report` was then run again on its own: `1 passed`. **Met** |
| `git status --porcelain \| grep -c 'work/'` (`06-handoff-guide.md` §6) | `0` |
