# T19 · Movies: the `nn::movie` path to VP9 decoding

Branch `task/T19-movies` (from `main` at `63ac708`). Mac for the analysis and tests, the Deck for builds and runs.
All runs used `--user-from /home/deck/raiders/work/t17_user_seed`, so the real save was not touched. Logs and
screenshots stay in `work/runs/` (not committed).

## Short answer

- **The movie path already worked without IPC.** It decodes VP9 on the host's FFmpeg decoder.
- **Case 1 of the task applied** ("the chain reaches `nn::codec` and frames decode").
- **Removing the three `nn::movie` stubs exposed a real bug.** The `sdk`'s own `nn::movie::Initialize` takes an SDK
  TLS slot. The host freed that slot into a different table, so after 11 movie sessions (2 per preview open) the
  game aborted.
- **Two fixes:**
  - the three functions now run as the `sdk`'s lifted code;
  - the host now implements `nn::os::SdkAllocateTlsSlot` on its own TLS table.
- **Result:** a preview opened and closed ten times in one run. Decoders and image pools initialised and finalised
  in equal numbers (20/20 and 40/40). No `nn::movie` stub was called, and nothing aborted.
- **Speed and loop:** the preview plays at normal speed (the picture clock stays within 0.03 s of the wall clock)
  and loops.
- **Not smooth yet:** the game takes a new picture only about every 85 ms (about 12 a second) at the menu's
  25-26 fps. Decoding costs 3.2-3.9 ms a picture, so the decoder is not what limits it.

## Where the clips play (step 1)

**Path: + (Gear) → Right (Gadgets) → A → ZL → ZL (page 3).** The preview shows on page 3 of the Gadgets page.
Found with you and a steered run (`find1`) **(verified: screenshots `find1` and `movie1/shots/vk_002400.png`)**.

- **Other places checked:**
  - Opening the gear menu reads the 15 `Gadget_*.webm` files and `Default.webm` into memory, but starts no decoder.
  - The Tank pages (1 and 2) and Bot Buddy page show no movie **(verified)**.
- **First-tank screen:** in your `prologue3` play-through the same preview played on the starting-tank choice screen
  (line 53796 onwards). That screen is behind your current save.
- **Input script:** `games/raiders/scripts/gadget_movie.txt`.
  - It goes title → hub (ZL+ZR at 30, 35, 40 s), then + at 80 s and Right at 84 s.
  - Then ten cycles from 87 s, one every 12 s: A, ZL, ZL, 7 s on page 3, then B.
  - It closes the menu at 208 s.

## The observed call chain **(verified)**

| Step | Module | Evidence |
|---|---|---|
| The game calls `nn::movie::Initialize` / `Finalize` on each preview | `main` → `sdk` | backtrace in `movie1-abort` (below): `0x83235fd0` → `0x853e89f4` |
| Demuxing: `nn::movie::MediaExtractor` | `sdk`, lifted | `main` imports 43 `nn::movie` symbols and `subsdk0` 54, all defined by `sdk`. Threads `MediaExtractorWorker`, `NuCachedSource2` (`movietrace1`) |
| Decoding: `movie::VideoDecoder` / `VideoFrame` | `subsdk0`, lifted | `main` imports 41 `movie::` symbols from `subsdk0`. Threads `MovieOperateThread`, `VideoDecoderThread` |
| `nn::codec` VP9 decoder and image pools | host (`host/nn_video.c`, FFmpeg) | `subsdk0` imports 67 `nn::codec` symbols. `video: VP9 decoder ready` |
| Picture read back as NV12 | `subsdk0` → host | `ReadDecoderOutputImageNv12(pool … ok, 1280x720 …) lr 0x84e5f910` (a `subsdk0` address). `ReadDecoderOutputImageRgba`: 0 calls |

So the chain is not `main → nn::movie → subsdk0` as the task expected. `main` drives `subsdk0`'s `movie::` decoders
directly, and both use the `sdk`'s `nn::movie` for demuxing.

**No IPC (verified).** The runtime logs every `ConnectToNamedPort` and `SendSyncRequest` as an `ipc:` line, whether or
not tracing is on (`host/hos_svc.c:482-509`). `find1`, `movie1` and `movietrace1` have 0 `ipc:` lines. In
`movietrace1` (`HOS_TRACE=1`), from the first movie thread to the end of the run, the only SVCs are:

| SVC | Count |
|---|---:|
| `QueryMemoryInfo` | 1182 |
| `CreateThread` | 24 |
| `StartThread` | 25 |
| `WaitThread` | 25 |
| `DestroyThread` | 25 |

**The clips (verified: `ffprobe`, in place, on the Mac's dump):**
- all 16 are VP9, 1280x720, yuv420p, limited range, 30 fps, 1.0-8.6 s long;
- none has an audio track.

## The three `nn::movie` stubs: what they were, what replaced them

- **What the `sdk` really does there** (disassembly of `sdk+0x4b89a0..0x4b8b64`, **verified**):
  - `Initialize`: a reference count under a recursive mutex; on the first call it calls
    `nn::os::SdkAllocateTlsSlot` and aborts if that fails.
  - `IsInitialized`: returns Result `0x3eb00` while not initialised.
  - `Finalize`: frees the slot (`nn::os::FreeTlsSlot`) when the count reaches 0.
  - None of them calls a service.
- **Why they were stubbed:** `nx2/standalone.py`'s `os_facing` rule stubs every free function in an OS namespace that
  the game imports (`movie` is in `OS_NAMESPACES`).
- **What the stubs got wrong:** they answered 0. For `IsInitialized` that happens to mean "initialised", but no TLS
  slot was ever taken.
- **The change (decision: run the `sdk`'s own code, the smallest change):**
  - `games/raiders/game.py` gets `SDK_LIFTED`, listing the three names.
  - `nx2/standalone.py` gets `sdk_lifted()`: it leaves those imports to the `sdk`'s definition, and stops the lift
    if a name is not an `sdk` function or is replaced in `host/`.
  - `nx2/lift.py` passes the game to `hle_set`.
  - Result: stubs 259 → 256 (**verified**: build log `standalone: … 256 OS-facing imports stubbed`). Ocarina has no
    `SDK_LIFTED`, so upstream's stubs are unchanged.

## The bug un-stubbing exposed: TLS slots **(verified)**

- **What happened** (`movie1-abort`, the first acceptance run):
  - After 11 decoder sessions had started and stopped (11 `Stop` lines, the 6th preview open), the next
    `Initialize` aborted: `FATAL: the game aborted (nn::diag::detail::AbortImpl)`. One `Initialize` per session is
    **inferred** (the stubs' first calls in `prologue3` came at a session's start and end).
  - Guest backtrace: `0x8509b6e8` (`SdkAllocateTlsSlot`) ← `0x853e89f4` (`nn::movie::Initialize`) ← `0x83235fd0`.
- **Why:**
  - `nn::os::AllocateTlsSlot` and `SdkAllocateTlsSlot` both call `os::detail::TlsManager::AllocateTlsSlot`
    (`sdk+0x16cc30`), with an SDK flag.
  - The host replaced `AllocateTlsSlot`, `FreeTlsSlot`, `GetTlsValue` and `SetTlsValue`, but not
    `SdkAllocateTlsSlot`.
  - So an SDK slot came from the `sdk`'s table and was "freed" into the host's, and one slot leaked per preview.
- **Fix** (`host/hos_thread.c`):
  - The host implements `SdkAllocateTlsSlot` on the same table as the others, taking from the top (slot 31 down),
    while `AllocateTlsSlot` takes from the bottom.
  - Both now clear the slot's value in every thread. The console does the same (**verified**: `TlsManager`'s
    allocator calls `ThreadManager::SetZeroToAllThreadsTlsSafe`).
  - This is generic, not Raiders-specific: a candidate upstream PR (T25).
- **Before the change:** with the stubs, the slot index read was whatever the zeroed global held, slot 0, which the
  game's first `AllocateTlsSlot` also owns. That is a collision on any thread that used both **(inferred)**.

## Teardown and looping (step 4) **(verified, `movie1`)**

- **Lifecycle counts:**

  | Object | Initialised | Finalised |
  |---|---:|---:|
  | Decoders | 20 | 20 |
  | Image pools | 40 | 40 |

  Each open gives 2 decoder sessions (each with 2 pools of one image): one while the Gadgets list's first page is up
  (93 submissions, 19-21 pictures, then `Stop`), and one for page 3 (186 submissions over two loops, 89-92 pictures,
  then `Stop` at B).
- **Looping:** a loop is 93 submissions with a final picture at pts 3.033 s. At the end the library calls `Flush`
  and submits the clip again: 30 `Flush` lines in the run, 20 `Stop` lines.
- **New `HOS_VIDEO_LOG` lines:** one line per decoder or pool initialised or finalised, with the running counts
  (`host/nn_video.c`, `lifecycle_log`).

## Frame timing **(verified, `movie1`, 10 measurement lines, one per 60 pictures)**

| | Value |
|---|---|
| Decode time (libavcodec, 2 threads, on the movie thread) | 3.2-3.9 ms a submission |
| A picture handed to the game | every 84.6-87.0 ms (11.5-11.8 a second) |
| Menu frame rate while the preview played | 25.1-26.3 fps (38-40 ms a frame) |
| Picture clock against the wall clock | behind by 0.00-0.03 s |
| Pictures skipped to keep time | 1,245 in the run |

- **Speed and loop:** normal speed, and it loops **(verified)**.
- **Smoothness: about 12 distinct pictures a second for a 30 fps clip** (verified).
  - The game takes a picture about every 2.2 of its frames. That it takes one every second frame by design is
    **inferred**: at 60 fps that would be 30 a second.
  - The limit is the menu's frame rate (T22), not the decoder.
  - The new line `video: since the last line: N submissions decoded, X ms each; a picture handed out every Y ms`
    shows this.
- **The start-of-clip "shown black" note** (`prologue3`): the library takes both buffers before its first submission
  (`acquire 1/2: nothing decoded (idle: its sync not reached)`). Those buffers carry a sync handle that is not reached
  until a submission. That the game does not draw them is **inferred** from `nn_video.c`'s sync-handle comment; no
  screenshot caught a black frame.

## Presentation and colour **(verified, inferred where marked)**

- **Read path:** the game reads each picture back as NV12 through `ReadDecoderOutputImageNv12` into its own memory;
  `ReadDecoderOutputImageRgba` has 0 calls. The native handle from `AcquireVp9DecoderOutputBuffer` is only used as a
  sync point.
- **Brightness check:** `HOS_VIDEO_LOG`'s sampled picture means are plausible for a daylight scene, not black or
  garbage: Y 142-145, RGB about 125-138 / 152-163 / 137-141.
- **Screenshot `movie1/shots/vk_002400.png`:** the Gadgets page 3, with the preview showing a later moment of the
  clip than `find1`'s frame. Natural colours, no green or magenta cast **(verified by viewing)**.
- **Colour matrix:** the game converts NV12 to RGB itself; that it uses the right matrix for these limited-range clips
  is **inferred** from the natural-looking frames.

## `HOS_NO_MOVIES=1` (scope 3) **(verified, `nomovie1`)**

- The clip files are refused (`fs: OpenFile(…/UI/Movie/Gadget_*.webm): movies are left out (HOS_NO_MOVIES)`).
- No `video:` line appears, and the game does not crash.
- Page 3 shows an empty panel with a spinner where the clip would play.

## `Event/Movie/` at run time

- `main` contains the string `Event/Movie/` **(verified: `grep -c` on `work/modules/main.bin`)**.
- **Not opened in `find1`.** That run had `HOS_FS_TRACE=1`, which logs every open, existence check and directory
  listing, and covered boot, title, hub and the gear menu. It logged 8,139 `OpenFile` calls and 0 that mention
  `Event/Movie` **(verified)**.
- Whether a later story event looks there is **unknown** (not reached in these runs).

## Acceptance criteria (real output)

```
$ .venv/bin/python -I -B tests/run_all.py video movie
pass         0.5s  tests/test_movie_frame_count.py
pass         0.3s  tests/test_movie_tls_slots.py
pass         0.3s  tests/test_movie_upscale_policy.py
pass         0.0s  tests/test_movie_sdk_lifted.py
4 passed, 0 failed, 0 skipped in 0 s (linux, 8 at once)

$ scripts/deck/run.sh movie1 240 --user-from /home/deck/raiders/work/t17_user_seed -- HOS_VIDEO_LOG=1 HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/gadget_movie.txt)" && scripts/deck/fetch.sh movie1
run movie1: stopped at the time limit
run movie1: 20 screenshots, log /home/deck/raiders/work/runs/movie1/hookshot_log.txt
fetch: …/work/runs/movie1 (23 files)

$ grep -c "VP9" work/runs/movie1/hookshot_log.txt
4
$ grep -n "nn5movie.*first call" work/runs/movie1/hookshot_log.txt | wc -l
       0
$ grep -c "unimplemented import _ZN2nn5movie" work/runs/movie1/hookshot_log.txt
0
$ ls work/runs/movie1/shots | tail -2
vk_005700.png
vk_006000.png
```

- **The `VP9` count is 4.** `video: VP9 decoder ready` is logged for the first 4 decoders only (upstream's limit). The
  run's 20 decoders show in the lifecycle lines.
- **The `first call` grep can never match.** A generated stub logs `[a64] unimplemented import <symbol>`, never "first
  call". The stricter grep on that line is the real check, and it is 0. Before T19, every movie open logged all three
  `nn::movie` stubs (`prologue3`, lines 53796, 53797, 53866).
- **The last two screenshots** are after the menu closed (the hub). The preview is in `vk_002400.png`, described
  above.
- **Full Mac suite:** 301 passed, 9 failed, 42 skipped. The 9 failures are exactly
  `docs/plans/reports/mac-test-baseline.md`'s classes (a) and (b); no regression.
- **Your check** (preview plays smoothly at normal speed and loops) is **not yet done**.
  - Normal speed and looping: verified.
  - Smoothness: limited to about 12 pictures a second by the menu's 25 fps (above).

## Runs

| Run | What | Result |
|---|---|---|
| `find1` | build 1, steered, `HOS_FS_TRACE=1 HOS_VIDEO_LOG=1`, stopped by hand | path found; no `nn::movie` stub; 25 loops; 0 `Event/Movie` |
| `movie1-abort` | build 2, the acceptance command | aborted in `nn::movie::Initialize` (TLS slot) after 11 decoder sessions, at the 6th preview open |
| `movie1` | build 3, the acceptance command | to the time limit; decoders 20/20, pools 40/40 |
| `movietrace1` | build 3, `HOS_TRACE=1`, 105 s, first preview only | 0 `ipc:` lines; SVCs listed above |
| `nomovie1` | build 3, `HOS_NO_MOVIES=1`, 140 s | clips refused, no decoder, menu works |

Builds: lift 242 s (build 1), then 57 s compile (build 3); 0 failed.

## Changes

| File | Change |
|---|---|
| `games/raiders/game.py` | `SDK_LIFTED`: the three `nn::movie` functions |
| `nx2/standalone.py` | `hle_set(modules, game=None)`, `sdk_lifted()` (marked `(raiders)`) |
| `nx2/lift.py` | passes the game to `hle_set` |
| `host/hos_thread.c` | `take_tls_slot()`; `SdkAllocateTlsSlot` implemented; both allocators clear the slot in every thread |
| `host/nn_video.c` | `HOS_VIDEO_LOG` only: decoder and pool lifecycle counts; decode time and picture interval |
| `games/raiders/scripts/gadget_movie.txt` | the preview path and ten open/close cycles |
| `tests/test_movie_sdk_lifted.py` | `SDK_LIFTED` on made-up modules; Raiders' list; refusals |
| `tests/test_movie_tls_slots.py` | the TLS block cut from `hos_thread.c` and compiled: top/bottom, 100 cycles, values cleared, 32 then `0x2C01`. It fails on the code before the fix |

## Deviations

- **Every Deck run added `--user-from …/t17_user_seed`** to the acceptance command, so the game's save writes went to
  a copy. It does not change what is measured.
- **The `first call` grep** was run as written and supplemented with the stub's real log line (above).
- **`host/hos_thread.c` is outside a strict reading of "the movie path".** The task names "anything else the trace
  flags in this path", and this was the abort the un-stubbed path hit.

## Open

- **Smoothness** follows the menu's frame rate: T22. Recheck the picture interval once the menu runs near 60 fps.
- **`Event/Movie/`** may be used by story events past this save: **unknown**.
- **The TLS fix is a candidate upstream PR** (T25): `SdkAllocateTlsSlot` and the cleared values.
