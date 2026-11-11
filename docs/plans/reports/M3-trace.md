# M3 · Trace report: what the game calls that the runtime lacks (T09, 2026-11-10)

**Short answer.** Both runs stopped where M2 stopped: on `sead::MainThread`, at the null read after the generated stub for
`nn::pl::GetBuiltInFontData` (the Ounce overload). That is log line 819 of 1828 in both runs, with no submit and no present
before it. Before the stop the game called **3 generated OS stubs** (2 safe, 1 blocking, all → T10) and **0 NVN procs
without an implementation**. It called 141 implemented NVN procs, created 5 queues, 102 events and 8 syncs, and made
**0** `nvnCommandBufferWaitEvent` calls. No read-back happens before the stop. So the queue/event check and the ink
read-back question wait for the first run past the font (T10, then T13 and T17).

Claims are **verified** (log line, command or file named) unless marked **inferred** or **unknown**. The logs are in
`work/runs/trace1/` and `work/runs/trace2/` on the Mac, and are not committed. The generated part below comes from
`scripts/trace_report.py work/runs/trace1/hookshot_log.txt --md docs/plans/reports/M3-trace.md`. Running it again keeps
the text outside the markers and the Class / Owner / Note cells.

## Runs

`DECK_HOST=deck@steamdeck.local`, the T08 build (`~/raiders/work/sa/build/hookshot`, 473,160,408 bytes, unchanged:
T09 touches no runtime code). Headless and muted (`run.sh` defaults).

| Run | Command | Wall (Mac, with fetch) | Log | End |
|---|---|---|---|---|
| `trace1` | `scripts/deck/run.sh trace1 120 -- HOS_NO_MOVIES=1 HOS_TRACE=1 HOS_HOSTCALL_STATS=1 HOS_STATS_AFTER=100 HOS_LOG_SYNC=1` | 136 s | 1828 lines | CRASH line 819; `run.sh`: "Killed … stopped at the time limit" |
| `trace2` | the same and `HOS_NVN_STRICT=1` | 137 s | 1828 lines | the same |

**`trace2` = `trace1`** (verified): with hex values taken out and the lines sorted, the logs are identical (`diff` 0 lines).
The only difference is the order in which threads start. The two call-count tables are identical too. Strict mode never
fired, because no unimplemented NVN proc was called (`grep -c "is not implemented"`: 0 and 0).

<!-- trace_report.py: generated, BEGIN (edit outside, or the Class / Owner / Note cells) -->

Logs: `trace1` (1828 lines).
- `trace1`: end: line 819, CRASH; first present: none; NVN counts: exact (HOS_HOSTCALL_STATS).

### 1. Generated OS stubs called

3 of the 279 stubbed imports in the stub list were called; 0 called stub(s) not in it.

| # | Mangled | Demangled | Namespace | lr | Runs (order) | Class | Owner | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | `_ZN2nn2ro12ProtectRelroEPKvS2_S2_S2_S2_` | `nn::ro::ProtectRelro(void const*, void const*, void const*, void const*, void const*)` | nn::ro | `0x80020168` | trace1 #1 | safe | T10 | Five input pointers, no out-parameter; 0 is success, and the image is already relocated and writable. The boot went on (inferred) |
| 2 | `_ZN2nn3hid14InitializeJcmsEPvm` | `nn::hid::InitializeJcms(void*, unsigned long)` | nn::hid | `0x83dc2dcc` | trace1 #2 | safe | T10 (T15) | Work buffer and size in, no out-parameter; 0 leaves the Joy-Con 2 mouse uninitialised, which is T15's no-mouse plan. `GetJcmsStates` is not called before the stop (inferred) |
| 3 | `_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb` | `nn::pl::GetBuiltInFontData(nn::pl::BuiltInFontDataOunce*, nn::pl::BuiltInFontTypeOunce, bool)` | nn::pl | `0x836e6f18` | trace1 #3 | blocking | T10 | Out-parameter `BuiltInFontDataOunce*` left unset (wrong answer). The caller dereferences its pointer field: the crash at line 819 (M2-boot.md, verified there by disassembly) |

### 2. NVN procs called without an implementation

| # | Proc | Answer | lr | Runs (order) | Class | Owner | Note |
|---|---|---|---|---|---|---|---|
| | none | | | | | | |

### 3. NVN procs called with an implementation

141 procs.

| Proc | calls (trace1) |
|---|---|
| `nvnBlendStateSetBlendEquation` | 9 |
| `nvnBlendStateSetBlendFunc` | 9 |
| `nvnBlendStateSetBlendTarget` | 9 |
| `nvnBlendStateSetDefaults` | 9 |
| `nvnBufferBuilderSetDefaults` | 128 |
| `nvnBufferBuilderSetDevice` | 128 |
| `nvnBufferBuilderSetStorage` | 128 |
| `nvnBufferGetAddress` | 7006 |
| `nvnBufferInitialize` | 128 |
| `nvnBufferMap` | 10 |
| `nvnBufferSetDebugLabel` | 14 |
| `nvnChannelMaskStateSetChannelMask` | 9 |
| `nvnChannelMaskStateSetDefaults` | 9 |
| `nvnColorStateSetBlendEnable` | 9 |
| `nvnColorStateSetDefaults` | 9 |
| `nvnCommandBufferAddCommandMemory` | 1 |
| `nvnCommandBufferAddControlMemory` | 1 |
| `nvnCommandBufferBeginRecording` | 1 |
| `nvnCommandBufferDrawElements` | 1 |
| `nvnCommandBufferEndRecording` | 1 |
| `nvnCommandBufferFinalize` | 1 |
| `nvnCommandBufferGetCommandMemoryUsed` | 1 |
| `nvnCommandBufferGetControlMemoryUsed` | 1 |
| `nvnCommandBufferInitialize` | 2 |
| `nvnCommandBufferSetMemoryCallback` | 2 |
| `nvnCommandBufferSetMemoryCallbackData` | 2 |
| `nvnDepthStencilStateSetDefaults` | 3 |
| `nvnDepthStencilStateSetDepthFunc` | 3 |
| `nvnDepthStencilStateSetDepthTestEnable` | 3 |
| `nvnDepthStencilStateSetDepthWriteEnable` | 3 |
| `nvnDepthStencilStateSetStencilFunc` | 6 |
| `nvnDepthStencilStateSetStencilOp` | 6 |
| `nvnDepthStencilStateSetStencilTestEnable` | 3 |
| `nvnDeviceBuilderSetDefaults` | 1 |
| `nvnDeviceBuilderSetFlags` | 1 |
| `nvnDeviceGetInteger` | 99 |
| `nvnDeviceGetProcAddress` | 1462 |
| `nvnDeviceGetTextureHandle` | 2 |
| `nvnDeviceInitialize` | 1 |
| `nvnDeviceRegisterFastClearColor` | 1 |
| `nvnDeviceSetDepthMode` | 1 |
| `nvnDeviceSetWindowOriginMode` | 1 |
| `nvnEventBuilderSetDefaults` | 102 |
| `nvnEventBuilderSetStorage` | 102 |
| `nvnEventInitialize` | 102 |
| `nvnMemoryPoolBuilderSetDefaults` | 57 |
| `nvnMemoryPoolBuilderSetDevice` | 57 |
| `nvnMemoryPoolBuilderSetFlags` | 57 |
| `nvnMemoryPoolBuilderSetStorage` | 57 |
| `nvnMemoryPoolFlushMappedRange` | 222 |
| `nvnMemoryPoolGetBufferAddress` | 88 |
| `nvnMemoryPoolGetFlags` | 118 |
| `nvnMemoryPoolGetSize` | 1 |
| `nvnMemoryPoolInitialize` | 57 |
| `nvnMemoryPoolMap` | 15 |
| `nvnMemoryPoolMapVirtual` | 1 |
| `nvnMemoryPoolSetDebugLabel` | 15 |
| `nvnProgramBuilderSetDefaults` | 35 |
| `nvnProgramBuilderSetDevice` | 35 |
| `nvnProgramBuilderSetShaders` | 35 |
| `nvnProgramInitialize` | 48 |
| `nvnProgramInitializeFromBuilder` | 35 |
| `nvnProgramSetShadersExt` | 48 |
| `nvnQueueBuilderGetQueueMemorySize` | 5 |
| `nvnQueueBuilderSetCommandMemorySize` | 5 |
| `nvnQueueBuilderSetComputeMemorySize` | 5 |
| `nvnQueueBuilderSetControlMemorySize` | 5 |
| `nvnQueueBuilderSetDefaults` | 5 |
| `nvnQueueBuilderSetDevice` | 5 |
| `nvnQueueBuilderSetFlags` | 5 |
| `nvnQueueBuilderSetPrimaryQueue` | 2 |
| `nvnQueueBuilderSetQueueMemory` | 5 |
| `nvnQueueInitialize` | 5 |
| `nvnSamplerBuilderSetBorderColor` | 330 |
| `nvnSamplerBuilderSetCompare` | 332 |
| `nvnSamplerBuilderSetDefaults` | 333 |
| `nvnSamplerBuilderSetDevice` | 333 |
| `nvnSamplerBuilderSetLodBias` | 330 |
| `nvnSamplerBuilderSetLodClamp` | 330 |
| `nvnSamplerBuilderSetMaxAnisotropy` | 166 |
| `nvnSamplerBuilderSetMinMagFilter` | 333 |
| `nvnSamplerBuilderSetReductionFilter` | 330 |
| `nvnSamplerBuilderSetWrapMode` | 332 |
| `nvnSamplerGetBorderColor` | 2 |
| `nvnSamplerGetCompare` | 2 |
| `nvnSamplerGetLodBias` | 2 |
| `nvnSamplerGetLodClamp` | 2 |
| `nvnSamplerGetMaxAnisotropy` | 2 |
| `nvnSamplerGetMinMagFilter` | 2 |
| `nvnSamplerGetReductionFilter` | 2 |
| `nvnSamplerGetWrapMode` | 2 |
| `nvnSamplerInitialize` | 333 |
| `nvnSamplerPoolInitialize` | 1 |
| `nvnSamplerPoolRegisterSampler` | 165 |
| `nvnSamplerSetDebugLabel` | 128 |
| `nvnSyncInitialize` | 8 |
| `nvnTextureBuilderGetStorageAlignment` | 42 |
| `nvnTextureBuilderGetStorageClass` | 804 |
| `nvnTextureBuilderGetStorageSize` | 75 |
| `nvnTextureBuilderSetDefaults` | 880 |
| `nvnTextureBuilderSetDepth` | 873 |
| `nvnTextureBuilderSetDepthStencilMode` | 871 |
| `nvnTextureBuilderSetDevice` | 880 |
| `nvnTextureBuilderSetFlags` | 880 |
| `nvnTextureBuilderSetFormat` | 880 |
| `nvnTextureBuilderSetHeight` | 873 |
| `nvnTextureBuilderSetLevels` | 875 |
| `nvnTextureBuilderSetSamples` | 871 |
| `nvnTextureBuilderSetSize2D` | 7 |
| `nvnTextureBuilderSetStorage` | 39 |
| `nvnTextureBuilderSetStride` | 52 |
| `nvnTextureBuilderSetSwizzle` | 873 |
| `nvnTextureBuilderSetTarget` | 880 |
| `nvnTextureBuilderSetWidth` | 873 |
| `nvnTextureFlushTexels` | 34 |
| `nvnTextureGetFlags` | 36 |
| `nvnTextureInitialize` | 39 |
| `nvnTexturePoolInitialize` | 1 |
| `nvnTexturePoolRegisterTexture` | 36 |
| `nvnTextureSetDebugLabel` | 1 |
| `nvnTextureViewSetDefaults` | 34 |
| `nvnTextureViewSetDepthStencilMode` | 1 |
| `nvnTextureViewSetFormat` | 1 |
| `nvnTextureViewSetLevels` | 34 |
| `nvnTextureViewSetSwizzle` | 1 |
| `nvnTextureViewSetTarget` | 1 |
| `nvnTextureWriteTexels` | 34 |
| `nvnVertexAttribStateSetDefaults` | 333 |
| `nvnVertexAttribStateSetFormat` | 104 |
| `nvnVertexAttribStateSetStreamIndex` | 104 |
| `nvnVertexStreamStateSetDefaults` | 320 |
| `nvnVertexStreamStateSetDivisor` | 48 |
| `nvnVertexStreamStateSetStride` | 65 |
| `nvnWindowAcquireTexture` | 1 |
| `nvnWindowBuilderSetDefaults` | 1 |
| `nvnWindowBuilderSetDevice` | 1 |
| `nvnWindowBuilderSetNativeWindow` | 1 |
| `nvnWindowBuilderSetNumActiveTextures` | 1 |
| `nvnWindowBuilderSetPresentInterval` | 1 |
| `nvnWindowBuilderSetTextures` | 1 |
| `nvnWindowInitialize` | 1 |

### 4. Services opened by name

| Run | How | Name | Times |
|---|---|---|---|
| | none | | |

`sm:` service lookups by name are not logged by the runtime: host/hos_svc.c logs `ConnectToNamedPort` only, and the SDK's service clients are mostly replaced by HLE functions.

### 5. Queues and event waits

| Run | Queues initialised | Submits | Events initialised | WaitEvent calls (highest #) | Distinct events (logged) | Distinct callers (logged) | WaitSync calls | Presents | WaitEvent per present |
|---|---|---|---|---|---|---|---|---|---|
| trace1 | 5 | 0 | 102 | 0 | 0 | 0 | 0 | 0 |  |

WaitEvent calls are logged one by one up to 40, then every 5000th (host/nvn_native.c): the distinct events and callers are among the logged ones.

### 6. The last 20 runtime lines

Without the call-count tables, register and guest-memory rows; file paths and strings left out.

`trace1`:

```text
   803  [hos sead::MainThread] hostcall nvnDepthStencilStateSetDepthTestEnable(0x1056196cc8, 0, 0x1100770, 0x1)
   804  [hos sead::MainThread] hostcall nvnDepthStencilStateSetDepthWriteEnable(0x1056196cc8, 0, 0x1100770, 0x1)
   805  [hos sead::MainThread] hostcall nvnDepthStencilStateSetStencilTestEnable(0x1056196cc8, 0x1, 0x1100770, 0x1)
   806  [hos sead::MainThread] hostcall nvnDepthStencilStateSetDepthFunc(0x1056196cc8, 0x2, 0x1100770, 0x1)
   807  [hos EventMgr::EventSettingLoad] thread start: entry 0x8320c750 arg 0x1055e0a8c8
   808  [hos EventMgr::EventSettingLoad] thread EventMgr::EventSettingLoad: TLS hook gave TP 0x10000cba20, DTV 0x10000cb600; ideal core -2 mask 0 priority 27
   809  [hos Resource Memory] FreeMemoryPages(0x7ff2be9000, 0x7000, 0x8, 0x100c520a28) lr 0x831ea684
   810  [hos Resource Memory] QueryMemoryInfo(0x100c0b4d78, 0x7000, 0x8, 0x100c520a28) lr 0x831eae4c
   811  [hos Resource Memory] fs: OpenFile (path left out)
   812  [hos Resource Memory] fs: OpenFile (path left out)
   813  [hos Resource Memory] fs: OpenFile (path left out)
   814  [hos Resource Memory] AllocateAddressRegion(0x100c0b4c10, 0x10000, 0x8, 0x8) lr 0x831e9e58
   815  [hos Resource Memory] AllocateMemoryPages(0x7ff29f0000, 0x9000, 0x8, 0x8) lr 0x831e9f74
   816  [hos Resource Memory] QueryMemoryInfo(0x100c0b4d78, 0x8, 0x8351d040, 0x100def5a28) lr 0x831eae4c
   817  [hos ARes Loading 0] fs: OpenFile (path left out)
   818  [a64] unimplemented import _ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb (lr 0x836e6f18)
   819  [hos sead::MainThread] CRASH: exception 0xc0000005 (read 0, guest 0xfffff00000000000) at <path>
   820  [hos sead::MainThread] CRASH: host backtrace: hookshot+0x19c67219 hookshot+0x19cad9b1 libc.so.6+0x3e270 hookshot+0xb990a3f hookshot+0xb98cfc0 hookshot+0xb1ec926 hookshot+0x91a0028 hookshot+0x919c35c hookshot+0x19c54b38 hookshot+0x8f5493e hookshot+0x8f535dc hookshot+0x19c54b38 hookshot+0xbdc6cbb hookshot+0xbdd860d hookshot+0x19c54b38 hookshot+0xbdc0002 hookshot+0x19c54b38 hookshot+0xbdd1aed hookshot+0x184e8de5 hookshot+0x19c5bb50 hookshot+0x19c594c3 hookshot+0x19ca8ccf libc.so.6+0x97739 libc.so.6+0x11bedc
   821  [hos sead::MainThread] CRASH: thread sead::MainThread, sp 0x10e7540
   830  [hos sead::MainThread] CRASH: guest backtrace: lr 0x808309d0 0x8082fb24 0x836e655c 0x83ebf39c 0x83ebcc34 0x83e253fc 0x83e22f8c 0x831ddbbc 0x831da244 0x831d7500 0x831d93ec 0x80ff9100 0
```

### 7. Read-back candidates called

| Run | Proc | Implemented | Calls |
|---|---|---|---|
| trace1 | `nvnBufferMap` | yes | 10 |
| trace1 | `nvnMemoryPoolMap` | yes | 15 |
| trace1 | `nvnMemoryPoolMapVirtual` | yes | 1 |

<!-- trace_report.py: generated, END -->

## Stubs called (step 3)

The Class column above uses the task's three classes. The judgement comes from the mangled signature: which parameters are
out-parameters the stub leaves unset.

| Class | Count | Stubs | Owner |
|---|---|---|---|
| safe | 2 | `nn::ro::ProtectRelro`, `nn::hid::InitializeJcms` | T10 (T15 for the mouse) |
| wrong answer | 0 on its own | `nn::pl::GetBuiltInFontData` also fits here (its out-struct is left unset), but it is counted as blocking | |
| blocking | 1 | `nn::pl::GetBuiltInFontData(BuiltInFontDataOunce*, BuiltInFontTypeOunce, bool)` | **T10** |

- Ordering is exact: `HOS_LOG_SYNC=1` writes each `hos_log` line on the thread that logs it, in step with the stub's own
  `fprintf(stderr)` (`host/hos_thread.c` `log_queue`; `third_party/a64-kit/rt/a64_rt.c:226`).
- The other 276 stubbed imports in `work/standalone_stubbed.txt` are not called before the stop. That is no evidence that
  they are never called (**inferred**): the run ends at the first font request.
- T10's input from this trace is only `GetBuiltInFontData` (Ounce). M2-boot.md has its caller and the two fixes it
  considered: serve a stand-in font in the structure's layout, or return a failure the game handles.

## NVN (step 4)

- **No unimplemented proc called** (section 2 is empty in both runs). Nothing is owed to T11 from this trace.
- The game asked for procs 1462 times through `nvnDeviceGetProcAddress` (count table), and called 141 distinct
  implemented procs. Almost all of it is setup: builders, pools, textures, samplers, 48 + 35 programs, one window of 3
  textures. There are 2 command buffers, which recorded 1 `nvnCommandBufferDrawElements` but were never submitted
  (`nvnQueueSubmitCommands` 0).
- What T11 can look at next comes from the next trace. The static list (`work/nvn_missing.txt`, 325 names) is unchanged.

## Queues and events (step 5, `docs/design.md` §4 rule 1)

| What | Count (count table) | Detail |
|---|---|---|
| Queues (`nvnQueueInitialize`) | 5 | The first logged `nvnQueueBuilderSetFlags` passes flags `0x9` (log line 72). The next two queues call `nvnQueueBuilderSetPrimaryQueue` (2 calls) with flags `0x4` (lines 538-549). `nvnQueueBuilderSetFlags` ran 5 times, but the trace logs only the first 3, so the last two queues' flags are **unknown**. What these flag bits mean in NVN2 is **unknown** |
| Events (`nvnEventInitialize`) | 102 | |
| Syncs (`nvnSyncInitialize`) | 8 | |
| `nvnCommandBufferWaitEvent` / `WaitSync` | 0 / 0 | |
| Submits / presents | 0 / 0 | |

Rule 1's check ("which queues, how many waits per frame") **cannot be answered before the first submit**. We know 5
queues exist, 2 of them made against a primary queue (**inferred** from the builder calls). The waits per frame are for
the first run that presents (T10's run after the font fix, or T13). `scripts/trace_report.py` §5 computes them from the
same switches.

## Read-backs (step 6, `00-overview.md` risk 2)

- **Called before the stop:** `nvnBufferMap` 10, `nvnMemoryPoolMap` 15, `nvnMemoryPoolMapVirtual` 1. These only give CPU
  pointers to pools and buffers. With 0 submits the GPU has written nothing, so none of them is a read-back yet
  (**inferred**).
- **Not called:** `nvnTextureReadTexels`, `nvnTextureReadTexelsStrided`, `nvnTextureInvalidateTexels`,
  `nvnBufferInvalidateMappedRange`, `nvnMemoryPoolInvalidateMappedRange`, `nvnCommandBufferCopyTextureToBuffer`,
  `nvnCommandBufferCopyBufferToBuffer`, `nvnCommandBufferReportCounter`, `nvnEventGetValue`, `nvnSyncWait`,
  `nvnQueueFinish` (count table: 0 or absent).
- **Static candidates** (`work/nvn_main.txt` names matching the script's read-back pattern): 15 names. 14 have an
  implementation; `nvnCommandBufferReportValue` does not (`work/nvn_missing.txt`). These are the procs to watch for the
  ink path.
- **Verdict:** no read-back appears before the stop. The stop is long before gameplay, so the ink read-back question
  stays **open → T17**. Section 7 of this script lists the candidates on any later log.

## After the crash the process stays (M2's unknown)

- `run.sh` printed "Killed" for both runs (verified): `timeout`'s SIGTERM at 120 s did not end the process, and the
  SIGKILL 15 s later did.
- The log has no `stats: after 100 s` line, although `HOS_STATS_AFTER=100` was set (`grep -c "stats: after"`: 0). After
  the crash report and its count table (lines 819-1828), nothing in the process logged again (verified). So the whole
  process, or at least logging, is stuck after `report_crash` returns, not just the crashing thread (**inferred**).
- The cause is **unknown**. The code path is `host/posix/win32_posix.c` `on_signal`: after the unhandled filter returns
  `EXCEPTION_CONTINUE_SEARCH`, the previous handler runs, or the default (`signal(sig, SIG_DFL)`). Ignoring SIGTERM points
  to a SIGTERM handler in the process (**inferred**; which one is **unknown**).
- **Research step** (not a fix, not T09's scope): on the next crash, attach `gdb -p` on the Deck and take
  `thread apply all bt`. This is a stability matter for the plan to place (T10's first run, or T23). Effect so far: each
  crashing run costs the full time limit + 15 s.

## Deviations

1. **Branch base.** T09 depends on T08, which was not on `main`, and `main`'s `run.sh` still used the wrong image path. By
   the user's choice, `task/T08-first-build-and-boot` was merged into `main` locally (`6b68684`, `--no-ff`, not pushed).
   This branch starts from that merge.
2. **Run switches.** The task's command is `run.sh trace1 120 -- HOS_NO_MOVIES=1`. Without the extra switches, the runtime
   does not log sections 3 and 5 (the NVN calls with an implementation, and the queue count). So both runs added:
   - `HOS_TRACE=1`: the hostcall lines
   - `HOS_HOSTCALL_STATS=1`: exact counts, printed by the crash report
   - `HOS_STATS_AFTER=100`: a count table for a hang
   - `HOS_LOG_SYNC=1`: exact order between stub lines and `hos_log` lines

   No runtime logging was added: every category is logged with these switches (the Non-goals allow a new log only for
   a category that is not logged at all).
3. **First attempt discarded.** The first `trace1`/`trace2` runs passed the switches as one word: zsh does not split an
   unquoted `$T`, so `env.txt` held one line. Both were run again. The logs in `work/runs/` are from the second runs.
4. **Section 7 added** (read-back candidates called) for step 6. The other six sections are as the interface says.
5. **`sm:` lookups.** There is no separate `sm:` log. An SDK service client reaches `sm:` through `ConnectToNamedPort`,
   which `host/hos_svc.c:488` logs; it was called 0 times before the stop.
6. **One log in the acceptance output.** The acceptance command generates the tables from `trace1` only. `trace2` was
   compared above (identical), and `trace_report.py` accepts both logs at once (`… trace1/… trace2/… --md …`).

## Files

| File | What |
|---|---|
| `scripts/trace_report.py` (new) | The parser and Markdown writer: the line formats it reads are listed in its docstring, each with its source |
| `tests/test_trace_report.py` (new) | 12 checks on a synthetic log in the runtime's formats. Covers stub order and dedup; lenient and strict NVN lines; the last count table winning; count tables, register and memory rows left out of section 6; services, waits, presents and the end; namespaces; redaction; render; merge keeping annotations (a second run changes nothing); `main` |
| `docs/plans/reports/M3-trace.md` (new) | This report |

## Acceptance criteria

| Command | Result |
|---|---|
| `.venv/bin/python -I -B tests/run_all.py test_trace_report` | `1 passed, 0 failed, 0 skipped`. **Met** |
| `.venv/bin/python -I scripts/trace_report.py work/runs/trace1/hookshot_log.txt --md docs/plans/reports/M3-trace.md` | `trace_report: docs/plans/reports/M3-trace.md (1 logs, 3 stubs, 0 NVN procs missing)`. Running it again on the annotated file left it byte-for-byte the same (`cmp`). **Met** |
| `grep -c "^\|" docs/plans/reports/M3-trace.md` | 183 table lines before this section was added. **Met** |
| `git diff --stat` | Only `scripts/trace_report.py`, `tests/test_trace_report.py` and `docs/plans/reports/M3-trace.md` (all new, so shown staged: `git diff --cached --stat`, 3 files, 973 insertions before this section). **Met** |
| `run_all.py` (full, not required) | 287 passed / 9 failed / 42 skipped without the header variables. The 33 checks skipped for `vulkan_headers` / `spirv_headers` were run again with `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`: 33 passed. Total 320 / 9 / 9 of 338 (T08: 319 / 9 / 9 of 337; the new check is `test_trace_report`). The 9 failures are exactly the baseline's 9. **No worse than the baseline** |
