# M4 · First frame and title screen (T13, session 1, 2026-11-11)

**Short answer: Gate 1 is not passed in this session.**

- **What works.** The game reaches its first-start screens on the Deck, headless and windowed. Starting a game plays
  its 3D opening, and you can play on into character customization.
  - **Errors:** no device loss, no GPU timeout, no "dropped stages", no failed translation in play.
  - **Menus:** 60 fps, with 1.2-1.9 ms of GPU time a frame.
  - **3D opening:** 30-41 fps.
  - **Memory:** about 3.7 GB resident at the first menu and about 4.5 GB in the opening. The windowed run's peak was
    5.8 GB.
- **What stops the gate:**
  1. **There is no title screen to reach yet.** On a fresh save the game shows no title: it goes from a cloud
     background straight to "Select a difficulty". The save it writes after "Start!" still brings the next boot back to
     that screen. So the title screen proper needs either a save with progress (T16) or playing on past the opening (T15).
  2. **The game crashes after character customization.** It sets up its profanity filter (`nn::ngc`), whose system
     service the runtime does not have, and the SDK aborts. Under the task's ownership rule this is a blocker
     (`BLOCKER-T13-2026-11-11.md`).
  3. **Your check at the Deck found three visual differences.** The rest of what you saw matched.
     - The confirmation buttons have no label or icon.
     - Yellow boxes flash between options in character customization.
     - The 3D background there has artifacts.

Claims are **verified** (command, file:line or log line named) unless marked **inferred** or **unknown**. Logs and
screenshots stay in `work/runs/<name>/` on the Mac and `~/raiders/work/runs/` on the Deck; none are committed. The
screens are described in words; game text is not quoted beyond screen titles.

## Branch base and build

- **Branch base.** T13 depends on T08a, T10, T11 and T12, none of which was on `main`. By your choice they were merged
  into `main` locally, `--no-ff`, not pushed: `74907df` (T08a), `5a14da8` (T10), `9cc35bb` (T11), `7e0321e` (T12).
  The only conflict was `scripts/deck/run.sh` and its test (T10 `--net-check`, T12 `--args` and peak RSS). Both features
  were kept, the Deck side taking `netcheck` and `extra` as positions 6 and 7, and the two text checks were updated to
  match. `task/T13-first-frame` starts from `7e0321e`.
- **Build.** `scripts/deck/sync.sh && scripts/deck/build.sh`: 185 s, `273 import stubs` (T10's count), `compiled in 4s,
  0 failed`, `hookshot` 451 MB, `hookshot_vk.so` 10 MB.
- **Shader caches.** The Deck's build folder still has T12's filtered census and prepared program cache (2.76 GB). A dev
  build does not prepare, but it reads that cache, so programs came from it rather than being translated in play.

## Runs

All are on the Deck with `HOS_NO_MOVIES=1`; headless unless marked.

| Run | Switches | What it showed |
|---|---|---|
| `title1` | handheld, shots every 120 presents | about 12 s of a soft cloud background (presents 120-720), then "Select a difficulty" from present 840 to the end, as a looping 14 s animation (the frames repeat every 840 presents) |
| `title2` | handheld, `HOS_INPUT_SCRIPT=20:A`, pass trace and timing | A on the default (Raider) brings up "Start on this difficulty?": the difficulty card, an orange ink shape with no label where the cursor sits, and a "Start!" button |
| `title3` | handheld, `20:A,24:RIGHT,26:A` | "Start!" goes straight into the in-engine opening: a newspaper close-up with subtitles, then a snowy crash site with characters and dialogue. Frame rate falls from 60 to about 31 fps. `save.dat` (4,667 bytes) is written 33 s into the run |
| **`title`** (acceptance) | handheld, as the task writes it | **"Select a difficulty"** again: the same frame hashes as `title1`'s loop, although `save.dat` existed and was opened (below) |
| `save1`, `save2` | `HOS_TRACE=1` (with and without the presses) | the save thread's opens of `saveMount:/save.dat` (below) |
| `open_hh`, `open_dk` | handheld and docked, presses to the opening, pass trace every 1,500 presents, pass timing | render sizes, passes, GPU and replay times (below) |
| `mem_hh` | handheld, presses to the opening, `VmRSS` polled every 10 s | memory (below) |
| `titlew` | **windowed** on the Deck (Desktop Mode, `--window --sound`, `HOS_WINDOW_SIZE=1280x720`, handheld), played by you with the Deck's controls | swapchain 1280x718, 4 images, mailbox. About 200 s from boot to character customization, then the `nn::ngc` crash. Exit code 3; peak RSS 5,807,984 kB |

## Problems found and their state

| # | Problem | Evidence | State |
|---|---|---|---|
| 1 | **No title screen on a fresh save**, and the second boot asks for a difficulty again | `title1`, `title` (the same frame hashes). In `save1`/`save2`, `SaveDataThread` opens `saveMount:/save.dat` at boot and again when saving (lines 3606 and 25436). `host/nn_fs.c` implements open, read, write, set size, flush and commit (`:311`-`:456`) | **Not fixed.** Inferred: the save written at "Start!" carries no progress yet, and the game keeps the difficulty only from a later checkpoint. Whether a title screen exists once a save has progress is **unknown**. Owner: T16 (saves) or T15 (playing on), by the ownership table (`nn::fs` → T16) |
| 2 | **Crash after confirming character customization** (`titlew`, ~200 s) | `[hos SceneLowPriority] ipc: ConnectToNamedPort("sm:") -> session 0x7e000001 (requests answered empty)`, two requests answered empty, then `FATAL: svcBreak(reason 0, …) (lr 0x84fecd5c)`. Backtrace by nearest export (`work/sa/image/image.json`): `nn::sm::Initialize+0x50` ← `nn::ngc::detail::CreateServiceByHipc+0xb0` ← **`nn::ngc::ProfanityFilter::Initialize(void*, unsigned long, bool)+0xf4`** ← the game (`main` `0x82b7fb68`, `0x82ba5bac`, `0x814b6cbc`, …), aborted through `nn::diag::detail::Abort(const Result*)` | **Blocker** (`BLOCKER-T13-2026-11-11.md`): `nn::ngc` is in no owner's list, and the game imports 7 `ngc` functions, none of them stubbed or HLE'd (`work/imports_raiders.txt`, `work/hle_names.txt`). The task allows a fix here only for one caller-checked function |
| 3 | **Confirmation buttons without label or icon** ("Start on this difficulty?") | Your windowed check; also in the headless shots (`title2` present 1500: the orange shape has no label; "Start!" is drawn). The built-in font stand-in is not involved: only type 0 was requested in every run (`pl: GetBuiltInFontData(Ounce, type 0, 0)`) | **Open.** Cause **unknown**. Next: `RX_VK_DUMP=<present>` on that screen to see whether the label's draw happens, and whether its program is one of the 11 the census misses (`M3-shaders.md` §5, mostly `Layout` archives) |
| 4 | **Yellow boxes flash** for a split second when moving between options in character customization | Your windowed check | **Open.** Not reproduced headless (it needs scripted input through the opening). Next: a scripted run to that screen with `RX_VK_FLASH=1` (it writes the frames around a flash) and `RX_VK_PIPE_SKIP=0`, to rule out draws left out while pipelines compile |
| 5 | **3D background artifacts** in character customization | Your windowed check | **Open**, as 4: `RX_VK_PASS_TRACE` and `RX_VK_PROBE=2` at that screen |
| 6 | `run.sh --window` opened no window over SSH | `display: SDL_Init: wayland,x11 not available: no window`: Desktop Mode is Plasma on Wayland, and `run.sh` set only `DISPLAY=:0` | **Fixed:** `scripts/deck/run.sh` exports `WAYLAND_DISPLAY=wayland-0` for `--window` when the session has that socket and the caller set none. `tests/test_deck_scripts.py` checks it |

Nothing in `gpu/vk/` or `host/` was changed this session: no rendering fault could be tied to a pass yet.

## Render facts

### Output and render sizes

| | Handheld (`HOS_HANDHELD=1`) | Docked |
|---|---|---|
| Window textures | 3 × 3840x2160, format 0x25 (`nvn: window of 3 textures (3 active), 3840x2160`) | the same |
| Window crop (what is shown) | **1536x864** (`nvn: window crop 0,0 1536x864`) | **2560x1440** |
| 3D scene (opening) | **1536x864**, the full output | **1707x960**, 2/3 of the output, upscaled by the game's own passes into 2560x1440 |
| Shadow maps | 2048x2048 | 2048x2048 |
| Half and smaller | 768x432 … 24x13 (a mip chain of passes), 64x64 effect passes | 853x480 … 26x15, 64x64 |
| Menus | one 1536x864 pass of about 60 draws, then one draw into the 3840x2160 window texture | 2560x1440, then the same |

- **Why the handheld switch works.** `nn::oe::GetOperationMode` is an HLE (`host/nn_applet.c:193`) and Raiders imports
  it.
- **The game asks no graphics scale:** `oe: GetCurrentGraphicsScale -> 1.00`.
- **A misleading log line.** `oe: output resolution 2048x1152 (the game's)` is Ocarina's output-size logic
  (`nn_applet.c:154-163`) and has no effect on Raiders, which never asks `hos_output_size` (**inferred**: no such call in
  the passes). It is a T07 leftover worth gating.
- **Dynamic resolution:** the pass sizes were the same in frames 2999 and 4499, 25 s apart, in both modes. In the
  opening the docked 3D held 1707x960 and the handheld 1536x864. Whether the game's controller moves them in gameplay is
  **unknown**: the opening may run at a fixed scale. `RX_VK_TS_SCALE` was left at its default.

### Frame time and fps

| Where | Headless (`vi:` lines, 5 s windows) | Windowed (`RX_VK_FRAME_LOG`, `titlew`) |
|---|---|---|
| Boot clouds and menus | 59.7-60.0 fps; the slowest frame in each 600 is 36 ms | 60.0 fps (15-25 s: mean 16.67 ms, p95 18.9, p99 20.0, max 39 ms) |
| 3D opening, handheld | 29.5-34.1 fps | 38-41 fps (presents 1500-5800) |
| 3D opening, docked | 27.9-32.4 fps | not run |
| After 120 s (character customization) | not reached | 59.5 fps (mean 16.81 ms, p95 20.2, p99 27.4, max 121 ms) |
| Whole windowed run | | 10,364 frames, mean 19.12 ms (52.3 fps), max 1,785 ms |

- **GPU time a frame** (`RX_VK_PASS_TIMING=1`), menus: 1.2-1.9 ms.
- **GPU time a frame, 3D opening:** 9-15 ms handheld, 12-20 ms docked. The longest submission was 8-12 ms.
- **The 30-40 fps in the 3D opening is not GPU-bound:** frames take 25-33 ms and the "GPU-bound wait" is 0.2 ms.
  - The replay's own time a frame is 5.5 ms handheld (submit 5.47 ms, draw 3.16 ms) and 6.5 ms docked.
  - Whether the rest is the game's threads or a 30 fps cap on cutscenes is **unknown**. That is for T17/T22.
  - The windowed run was faster than the headless one in the same scene (38-41 against 30-34 fps; **inferred**: offscreen
    presents pace differently).
- **The headless frame time cannot be logged per frame:** `RX_VK_FRAME_LOG` is written only on the swapchain path
  (`gpu/vk/vk_replay.cpp:3716-3728`).

### Queues and event waits

- **5 submits a frame** in menus and in 3D (the `presents, … fps; a frame:` lines).
- The game initialises its queues at boot (`nvnQueueInitialize`; 5 queues per `M3-trace.md`).
- `vk: queues ordered by their events` (600 presents, `open_hh`): 12,000 submissions stopped at a wait, 11,979 went on
  once it was reached, **18 waits gone past**, waits met 17,166, **not met 0**; 6 stops reached 50 ms (at most 50.6 ms).
  `open_dk` gave the same pattern: 17,026 met, 0 not met.
- Design rule 1 (cross-queue waits honoured) holds, with no flashes seen headless.

### Upscaler and AA path on the Deck

- **There are no cooperative matrices on RADV** ("matrix multiplies in software").
- **Handheld:** no network was met in the runs.
- **Docked:** one network program was met in play and replaced as designed:
  `program 20ce8fa19e5349c2 does not translate: its dispatch replaced by a linear upscale of … 1366x768 … into …
  2048x1152`. It is one of the 20 networks in `M3-shaders.md` class 2. What that network upscales (a 1366x768 →
  2048x1152 image) is **unknown**; it is not the 3D scene, which is 1707x960.
- **The 3D scene's own 1707x960 → 2560x1440 upscale** in docked mode is ordinary passes (`f37`/`f64` targets, programs
  `f0f4432499ecf2b6`, `a33275399f6e2b4c`, `b256429218889313`). No network is involved.
- No DLSS call was seen (no `dlss` line in any log).

### Memory at the first menu and in the opening

| | |
|---|---|
| RSS (`mem_hh`, `VmRSS` every 10 s) | 2.05 GB at 9 s; **3.65-3.70 GB at the difficulty menu** (18-37 s); **4.48-4.55 GB in the 3D opening** (46-103 s) |
| System at the same time | 7.1-8.8 GB available, swap untouched (6.68 GB free) |
| Windowed run peak (`peak_rss_kb.txt`, the game exited by itself) | **5,807,984 kB** (5.5 GiB), through character customization |
| `vk: status:` (headless, handheld) | menus: `VRAM 0.8 of 5.7 GB`; opening: `VRAM 1.5 of 5.3 GB` (docked: `1.8 of 5.5 GB`) |
| `vk: status:` (windowed) | `VRAM 1.6-1.9 of 5.3-5.4 GB`; the slowest frame in 600 was 54-79 ms |

### Dropped stages (for T14)

**None.** `grep -c "dropped stages"` gives 0 in every run here: `title`, `title1`-`title3`, `open_hh`, `open_dk`,
`titlew` (through character customization). No program with a geometry stage was drawn up to that point.

### In-play translations

- **Programs translated in play:** 1 in `title3`, 5 in `titlew`, with no failures. The rest came from T12's prepared
  cache.
- **No lowering failure** in any run.

## Open visual differences

1. The confirmation screen's buttons: no label or icon (problem 3).
2. Yellow boxes flashing between options in character customization (problem 4).
3. 3D background artifacts in character customization (problem 5).
4. **Not checked against the console:** the boot's soft cloud background, which is plausibly the game's own transition,
   and the newspaper headline's lettering, which reads like mirrored Latin. The series' in-world script looks like that
   (**inferred**). You saw the opening and found it fine.

## What remains for Gate 1, and an estimate

1. **Unblock the crash:** `nn::ngc` offline answers (the blocker report's options). Small: one HLE family, a relift
   (~3 min with the object cache), a run.
2. **Get a title screen** if the game has one:
   - **either** scripted input through the opening and customization to the first progress save (needs 1; T15's
     territory),
   - **or** settle in T16 why the second boot asks for a difficulty again.

   The cost is **unknown** until it is known when the game saves progress.
3. **Find problems 3-5** with dumps and flash captures at those screens: one or two sessions (**inferred**: the method is
   in the task; the screens need scripted input to reach).
4. **Your windowed check again** on the title screen.

Estimate: 2-3 more sessions after the blocker is resolved (**inferred**).

## Task text out of date (for the planner)

- **"Stops before the first present"** no longer applies: the boot has presented since T09a.
- **The acceptance `title` run** cannot show a title screen on a fresh or a first-start save (problem 1). It shows
  "Select a difficulty".
- **`journalctl -k -b | grep -cE "gfx_|amdgpu.*timeout"` cannot be 0 until the Deck reboots.** This boot has 4 matching
  ring set-up lines from before T12 (`M3-shaders.md` §7).
- **The pitfalls' RADV line numbers have moved:** `vk_replay.cpp:164` (was 145), `vk_memory.cpp:134` (127), and
  `vk_draw.cpp:5511`/`5875` (5131).

## Acceptance criteria (real output)

| Command | Result |
|---|---|
| `scripts/deck/run.sh title 180 -- HOS_NO_MOVIES=1 HOS_HANDHELD=1 && scripts/deck/fetch.sh title` | `run title: stopped at the time limit`, `37 screenshots`; `fetch: …/work/runs/title (39 files)` |
| `ls work/runs/title/shots/*.png \| tail -3` | `vk_010500.png`, `vk_010800.png`, `vk_011100.png`. **The last one shows "Select a difficulty"** (Tourist / Raider / Survivalist, Raider selected, its description and a note below), **not a title screen**. **Not met** (problem 1) |
| `grep -ci "device lost" work/runs/title/hookshot_log.txt` | `0`. **Met** |
| `ssh $DECK_HOST 'journalctl -k -b \| grep -cE "gfx_\|amdgpu.*timeout"'` | `4`: the same 4 ring set-up lines as before T12 (boot 2026-11-10 15:39 and the S3 resume 2026-11-11 07:09). **No new line from T13's runs.** Not literally 0 (above) |
| `grep -n "dropped stages" work/runs/title/hookshot_log.txt \| head` | empty: recorded for T14 as none |
| `.venv/bin/python -I -B tests/run_all.py` (with `HOOKSHOT_VULKAN_HEADERS` / `HOOKSHOT_SPIRV_HEADERS=/opt/homebrew/include`) | **326 passed, 9 failed, 9 skipped** of 344 in 742 s, with this change. `test_deck_scripts` passes, now with 8 checks. The 9 failures are exactly `mac-test-baseline.md`'s 9 (8 FAIL and the `test_program_cache_reader` TIMEOUT). **Met** |

**Final check by you at the Deck:** done for the screens reached, with the differences above. **Gate 1 is not passed**:
there was no title screen, and problems 3-5 are open.

---

# Session 2 (2026-11-11, after the `nn::ngc` fix)

**Short answer: Gate 1 is still not passed, for two reasons.**

- **The crash is gone, and the save now works.** Play runs go past character customization. A boot from the save the
  game writes after its first scene resumes that scene (problem 1, now answered).
- **There is still no title screen.** That boot shows the same ~12 s of cloud images, then the scene, without any
  input. Whether the console shows something over those clouds, a logo for example, is **unknown**: that is the
  question for you.
- **A new stop: a GPU hang** in one draw program, `cffdbb02c4dfbd39`, right after the loading screen that follows that
  scene. It reproduced 3 times out of 3. Leaving that program out (diagnosis only) avoids it, and the game then reaches
  its first playable area. Its cause is **unknown**; its fragment stage is traced as far as one bounded loop (below).

## Branches

- **Merged into `main` by your choice:**
  - `91a5336`: `task/T10-ngc-offline`, the `nn::ngc` answer (`T10-offline.md`, "Part B, second iteration");
  - `1a8f381`: `task/T13-first-frame`, session 1.
- `task/T13-first-frame` was then fast-forwarded to `main`.
- `BLOCKER-T13-2026-11-11.md` is marked resolved.

## Runs (Deck, headless, handheld)

The input scripts press A every 2 s (they go through dialogue and confirmations) and start at the menu:
`20:A,24:RIGHT,26:A` on a first-start save.

| Run | Save at boot | Switches | What happened |
|---|---|---|---|
| `ngc1` (T10) | first-start | A to 418 s, 460 s limit | Customization passed, then the hub scene and its dialogue, then a loading screen. **A ring timeout at 12:27:11**, at the time limit, so the log has no device-lost line |
| `play1` | first-start | A to 598 s, `HOS_INPUT_LIVE` | The same path. The save was written at 12:40:14 (after "Start!") and **again at 12:42:09**, after that loading screen. **Device lost** 13 s later (12:42:22), at present ~3,830. Exit 3, peak RSS 6,078,092 kB |
| `play2` | `play1`'s | as `play1`, plus `RX_VK_CHECKPOINTS=1` | The same stop at the same frame (3,747). The buffer markers name the program (below). Save written at 12:45:27. Peak RSS 6,107,568 kB |
| `title4` | `play2`'s | no input, 180 s, as the acceptance run | **No title.** Presents 120-840 are the cloud images (5 draws, 5 dispatches, 3 passes a frame, 60 fps), then the hub scene and its first dialogue line, waiting for A |
| `play3` | `play2`'s | A to 398 s, `RX_VK_SKIP_PROG=cffdbb02c4dfbd39` | **No hang** in 420 s. Through the loading screen into the **first playable area**, which waits at a tutorial prompt to aim by moving the controller (T15's ground). Save written at 12:52:56 |
| `play4` | `play2`'s (restored) | `RX_VK_NO_PROGRAM_CACHE=1`, `RX_VK_IR=cffdbb02c4dfbd39`, the same skip | No hang in 330 s. The program's IR was written (below) |

- Saves were copied before each change (`~/raiders/work/t13s2_save_before/`, `t13s2_save_now/`, `t13s2_save_after_play2/`).
- `play3`'s later save (12:52:56) was overwritten by the restore before `play4`, with no copy kept.
- In every run of this session:
  - **no "dropped stages"** (still nothing for T14);
  - no program left untranslated and no lowering failure;
  - no device loss except the hang.

## Problem 1, updated: the save and the title

- **The save is honoured** once the game has saved after its first scene (`play1`'s second write).
  - Verified: `title4` boots into that scene, not "Select a difficulty".
  - So session 1's "the next boot asks for a difficulty again" was the game's own behaviour: its first save, at "Start!",
    keeps no progress.
  - **No T16 work is needed for this.**
- **No title screen in any boot so far:** first-start, after "Start!", or after the first scene.
  - The only screen before play is the cloud background: 3 passes and 5 draws a frame, so it is not a full menu layout.
    It is shown for ~12 s and needs no button.
  - Two possibilities, **unknown** which:
    - the game has no title screen at that point, so Gate 1's "title screen" is the cloud screen;
    - the clouds should carry a logo or text that is not drawn (compare problem 3, the missing button labels).
  - The console settles it.

## Problem 7 (new): GPU hang in program `cffdbb02c4dfbd39`

**Evidence (verified):**
- **Kernel:** `ring gfx_0.0.0 timeout` with `Process hookshot … thread ModuleSystemWor` at 12:27:11 (`ngc1`), 12:42:22
  (`play1`) and 12:45:39 (`play2`). Then `Ring gfx_0.0.0 reset succeeded`. There is no GPU page fault in this boot's
  kernel log.
- **`play2`'s buffer markers** (`RX_VK_CHECKPOINTS=1`, `VK_AMD_buffer_marker`):
  - `2535556 markers set, 63965 reached; the last whose earlier work all finished: 2534082`;
  - `reached, earlier work unfinished: marker 2533980 (draw of program cffdbb02c4dfbd39, frame 3747)`.

  That draw started and never finished, while 102 later markers did.
- **The program:** `its code: 0:02ff83a48c3b8aee 1:6d6b06b5cd3001e9`, a vertex and a fragment stage. It is not a task or
  mesh program, so not upstream's culling-loop hang (`RX_VK_MESH_NOCULL`). Neither stage is among T12's left-out programs.
- **With it left out** (`play3`, `play4`): no hang.

**The fragment stage** (`RX_VK_IR`, 10,410 lines of Eden IR, kept in `work/t13_ir/`; game-derived, not committed):
- **One loop:** header `Block $98`, back edge from `Block $196`. The vertex stage has none.
- **The counter** starts at 0 and steps by 1. The loop runs again while `i + 1 < n` (signed).
- **The bound:** `n = SMin32(LoadStorage32 #0[…], GetCbufU32 #4, #2832)`. That is a count read from storage buffer 0,
  capped by a word of constant buffer 4.
  - Storage buffer 0's address comes from constant buffer 0 word 1296, and storage buffer 1's from word 1312.
  - The index is built from the fragment's position, as in a tiled light or decal list (**inferred**).
- **The body** reads storage buffer 1 and samples textures. There is no nested loop.
- So, as written, the loop is bounded by the game's own cap. A hang needs one of these (**inferred**, not yet told apart):
  1. both the count and the cap read wrong values: a wrong constant buffer 4, or a wrong storage binding or address;
  2. an out-of-range read that does not fault on RADV but returns huge values;
  3. a translation fault in the loop's structure, its exit branch for example. The IR above is Eden's view, before
     SPIR-V and RADV's compiler.

**Next steps:**
- Read the loop's inputs on the GPU at that draw: constant buffer 4 word 2832, and the storage word at the first pixel.
  Then check the binding sizes for storage buffers 0 and 1 against the game's addresses.
- If the inputs are sane, dump the SPIR-V (`RX_VK_DUMP_SPV`) and check the loop's exit in it.
- A program-key skip is not a fix: what the program draws is **unknown**. So this stays a diagnosis switch, not a game
  default.

## Render facts added

| Where | fps (headless) | A frame | Replay time a frame |
|---|---|---|---|
| Hub scene (after customization) | 21-23 | ~1,000 draws, 80 passes, 8 dispatches | submit 35 ms, of which **descriptors 26 ms** (`play1`) |
| First playable area (`play3`, program left out) | 33-35 | ~1,478 draws, 102 passes, 17 dispatches | submit 25.7 ms, descriptors 17.4 ms |

- **Not GPU-bound:** the GPU-bound wait is 0.2-0.3 ms.
- **The replay's descriptor work** is the largest single cost in 3D scenes (**verified** from the `replay time` lines).
  That is for T22.
- **Memory:** peak RSS of 6.08-6.11 GB over a run to the hub scene. The game was reaped after the device loss, so the
  figure is real.

## Open visual differences, added

- The first playable area has red and yellow ink shapes over the screen edges. With the health bar at half, they are
  probably the game's own damage effect (**inferred**; not checked against the console).

## What remains for Gate 1

1. **Your answer:** what the console shows between power-on and the first scene, a title or logo over the clouds or
   not.
2. **Problem 7**, the hang: one more session (**inferred**).
3. **Problems 3-5**, the visual differences: unchanged since session 1.
4. **Your windowed check again.**

## Acceptance criteria (session 2)

| Command | Result |
|---|---|
| `run.sh title4 180 -- HOS_NO_MOVIES=1 HOS_HANDHELD=1 RX_VK_SHOT_EVERY=300` (the acceptance run with a progress save) | Stopped at the time limit with 15 screenshots. **The last one shows the hub scene's first dialogue line, not a title. Not met** (problem 1) |
| `grep -ci "device lost" work/runs/title4/hookshot_log.txt` | `0`. **Met.** (`play1`/`play2`: 1 and 2, problem 7) |
| `journalctl -k -b \| grep -cE "gfx_\|amdgpu.*timeout"` | **Not 0:** 4 ring timeouts in this session (problem 7), on top of session 1's 4 set-up lines |
| `grep -n "dropped stages"` | empty in every run |
| `.venv/bin/python -I -B tests/run_all.py` | **Not re-run on the merge.** Each side gave 326 passed, 9 failed, 9 skipped (the baseline's 9; with the header paths): `task/T10-ngc-offline` (`T10-offline.md`) and session 1's branch. The merge had no conflicts, and this session changed no code or tests |

---

# Session 3 (2026-11-11): where the title screen is

**Your information (from the console):** with a save from someone who has played, the boot plays the intro cutscene
again and then shows the real title screen. It has:
- the logo at the top left;
- "press ZL+ZR" at the right;
- the version number at the top right;
- "Nintendo" at the bottom left.

**Short answer:** the title is not reachable from the saves made so far.
- Every save made in these runs is a **prologue** save.
- A boot from any of them goes clouds → the scene after customization. Played on from there, the game leads back into
  the tutorial and writes its prologue save again.
- So reaching the title needs a save from after the prologue (**inferred** from your report and these runs). That means
  playing the prologue to its end, which needs:
  - the hang avoided (problem 7);
  - input for the tutorial's aiming and swimming (T15's ground, done by hand here).

## Runs

| Run | Save at boot | Switches | What happened |
|---|---|---|---|
| `title5` | `play4`'s (prologue, 4,907 B) | **movies on**, `HOS_VIDEO_LOG=1`, no input, 240 s | The same as `title4`: clouds for presents 120-840, then the scene's first dialogue line. **No movie call at all** (no `movie`/`video` log line): the clouds and the intro are not movie files, and `HOS_NO_MOVIES` changes nothing here |
| `live1` | the same | `RX_VK_SKIP_PROG=cffdbb02c4dfbd39`, `HOS_INPUT_LIVE`, steered by hand (screenshots every 60 presents, presses written to the live file) | Through the scene, the island cutscene and the first tutorial steps. The steps: line up the reticle on a shard (the right stick turns the camera, so it works without motion), collect shards, turn into a squid with ZL, swim through ink. **Save written at 13:42:11, 5,073 B.** No hang, no device loss; stopped by hand at present ~17,000 (about 9.5 min) |
| `title6` | `live1`'s (5,073 B) | movies on, no input, 240 s | **Clouds, then the same scene**, waiting on its first line. No title |
| `title7` | the same | A every 2 s from 25 s, the skip | Through the scene, then **back into the tutorial's start** (the beach, the first dialogue). The save was **rewritten to 4,907 B at 13:53:14**, the prologue save again |

- `live1`'s save is kept in `~/raiders/work/t13s3_save_tutorial/` and was put back after `title7`.
- No run of this session had a device loss or "dropped stages".

## New facts

- **The input path works for the first tutorial steps** with the right stick, the left stick, ZL and A (`live1`). Those
  are the scripted pad and live input, not the Deck's own controls. Holding ZL while moving did not always keep squid
  form; the cause is **unknown**, so it is noted for T15.
- **The red and yellow shapes at the screen edges** are the game's low-health effect (**verified** in `live1`): they
  go when health refills to 100 in the squid form, and come back as it falls.
- **The flat-box UI glitch is common in play** (problem 4, the "yellow boxes" you saw), and seen headless:
  - `vk_007980`: a **solid yellow square** in place of the shard counter's icon;
  - `vk_008940`: a flat teal box beside the counter;
  - `vk_011040`: flat grey and white bars over the health bar, and a translucent box behind a tutorial prompt line;
  - `vk_011340`: dark bars over the health bar.

  They appear when HUD elements change (a counter updating, a prompt appearing). This is the same class as the missing
  button labels (problem 3): UI layout drawing (**inferred**). The frame numbers above are `live1`'s screenshots, in
  `work/runs/live1/shots/`.

## What remains for Gate 1, updated

1. **A save from after the prologue.** One of:
   - **You play the prologue to its end in a windowed run** on the Deck, with the hang's program left out:

     ```
     scripts/deck/run.sh <name> 3600 --window --sound -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39
     ```

     Then boot again and check the title against the console. This is the shortest path. Its cost: whatever the
     program draws is missing while you play (**unknown** what that is).
   - **Fix problem 7 first, then play.** The same, without the switch.
2. **Problem 7**, the hang: one session (**inferred**).
3. **Problems 3-5**, the UI box and label class and the 3D artifacts: the UI class now has headless frames to start
   from.

---

# Session 3, continued: your windowed play-through (`prologue`)

**Short answer:** the prologue cannot be finished yet. The game behaves as if the player stands in **enemy ink
everywhere**. Its GPU results are a likely cause: the game reads back two GPU buffers every frame, and those buffers
are **never written back** by the replay (problem 8, below). Gate 1 now waits on problem 8 as well as the hang.

## What you saw (windowed, Deck controls, from the tutorial save)

`scripts/deck/run.sh prologue 3600 --window --sound -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39`.
The swapchain was 1280x718, mailbox. Exit 0 after you closed it; peak RSS 6,263,920 kB; save written at 14:02:27
(5,073 B, kept in `~/raiders/work/t13s3_save_prologue/`). No device loss.

- **A jump to the next platform falls short.**
- **Walking is very slow,** with a "stuck in something sticky" animation.
- **ZL turns you into a squid, but you cannot stay in your own ink.**
- **The UI flickers a lot** (problem 4's class), **and foliage renders smeared.**

These are consistent with one thing: the game believes the ground is enemy ink. In this game, enemy ink slows walking
with that animation, stops normal jumps, keeps you out of squid form, and drains health. That fits the health loss and
the gold ring under the character in `live1` (**inferred**; how the game decides what ink you stand on is **unknown**).

## Problem 8 (new): two GPU readback buffers are never written back

Run `ink1` (headless, the tutorial save, A presses into the tutorial area, `RX_VK_LOG_INVALIDATE=1`,
`RX_VK_LOG_READBACK=5000`). Run `ink2`: the same path with `RX_VK_WATCH_RANGE=7fcda11000:7fcda18300`.

- **The game reads back two buffers every frame** (verified): `nvnMemoryPoolInvalidateMappedRange` on `0x7fcda11000`
  and `0x7fcda14980`.
  - Each is 0x3980 bytes, and they alternate (double-buffered).
  - They make up 332 of the first 400 invalidates in `ink1`, and the addresses are the same in `ink2`.
  - `invalidate` reports "no texture the GPU wrote" for them.
- **What the CPU reads is the same every time** in the 300 logged reads from present 5000: `3e4ccccd 44fa0000 3fe38e39
  3f7ff972 0 0 44f9f99a 38d1bc75`. As floats that is 0.2, 2000, 1.778, 0.99999, 0, 0, 1999.8, 0.0001, which looks like
  a camera header the CPU wrote (**inferred**). Only the first 32 bytes are logged, so the results behind them were not
  seen.
- **No write-back ever covered these ranges** (**inferred** from the counters).
  - `vk_replay.cpp` `invalidate` counts a readback only when `memory_writeback_value(…, &ever)` says a write-back has
    covered the range, and prints `readbacks of GPU results: … of 3000` every 3,000 such reads.
  - That line never appears in `ink1`, although there are about 2 such reads a frame for thousands of frames.
  - So the replay never wrote GPU output back to these ranges, and the CPU reads whatever was there.
- **No GPU copy, clear or texture touches them** (verified, `ink2`: no `watch range` line of any kind). So if the GPU
  writes them, it does so from a shader:
  - a storage-buffer or global-memory write that the replay does not count as a written binding;
  - or a write Eden could not track. `global_memory_to_storage_buffer_pass.cpp` uses run-time "fallbacks" for global
    addresses it cannot trace back to a constant buffer.
- **The program left out for the hang (`cffdbb02c4dfbd39`) is not the writer** (verified): its fragment IR has no
  storage or global write (0 matches). Whether a program that was never drawn is the writer is **unknown**.

**Next steps (one session, inferred):**
1. A diagnostic, behind a switch (`(raiders)`, in `gpu/vk/`): log every written storage binding, and every
   global-memory fallback write, that overlaps `RX_VK_WATCH_RANGE`, with its program key. That names the writer, or
   shows there is none.
2. If a writer exists: why its write is not written back (binding not marked written, fallback path, or an untracked
   address). Fix it in the replay and check with a play run (the slow walk and ZL).
3. If no GPU writer exists, the game fills them on the CPU, and the ink check is elsewhere. Then look at what the CPU
   writes into these buffers after the readback (`RX_VK_WATCH_CPU`).

## Gate 1, updated

The title screen needs a save from after the prologue. Finishing the prologue needs problem 8 fixed (the ink state),
and, for play without the switch, problem 7 (the hang). Problems 3-5 (UI boxes and labels, smeared foliage, 3D
artifacts) remain open.

---

# Session 4 (2026-11-11): problem 8, the ink readback

**Short answer: session 3's lead was wrong.** The replay does return the GPU's results to the game: what the CPU reads
matches what the GPU wrote, byte for byte, one frame later. So the "never written back" reading of the counters was
mistaken. The cause of the enemy-ink behaviour is still **unknown**.

## Diagnostics added (switches only; no change in behaviour)

- `gpu/vk/vk_draw.cpp` `build_descriptors`: with `RX_VK_WATCH_RANGE=<lo>:<hi>`, each storage binding overlapping the
  range is logged (400 lines). The line gives the program, stage, entry, constant-buffer source, address and length,
  whether it is written, and whether it is written back whole or only 64 bytes (bare).
- `gpu/vk/vk_dump.cpp`: each `RX_VK_DUMP_SSBO` buffer line now ends with the FNV-1a hash of the whole buffer,
  `(hash …)` after the existing colon. `tests/dump_readback_test.cpp` still matches.
- `gpu/vk/vk_replay.cpp` `invalidate`: each `RX_VK_LOG_READBACK` line now also gives:
  - the same hash over the whole range the CPU is about to read;
  - whether a write-back was ever recorded for the range, and its value.

All three are marked `(raiders)`.

**Tests.** The first full run gave 325 passed, **10** failed: `tests/test_parallel_rb_refresh.py` compiles a text cut of
`build_descriptors` (up to the "(EvilOOT) the wanted programs' storage descriptors" block), and the watch block was
inside the cut. It was moved to just after that block, outside the cut, with no change to upstream's text. Then:
- `test_parallel_rb_refresh`, `test_dump_readback`, `test_recorded_wait_flush` and `test_desc_clock` all pass;
- the full suite (header paths set) gives **326 passed, 9 failed, 9 skipped** in 728 s, the baseline's 9.

The Deck build of the final code: `compiled in 13s, 0 failed`.

## Runs (headless, tutorial save, A presses into the tutorial area, the hang's program left out)

| Run | Switches | Found |
|---|---|---|
| `ink3` | `RX_VK_WATCH_RANGE=7fcda11000:7fcda18300` | **3 compute programs bind the two readback buffers as written storage every frame:** `8e895bab2bdea870`, `1b75d9ca469133ac` and `fd958faab99f20a2`. Each binds stage 5, entry 0, from `c0+0x20`, 0x3980 bytes, "written back whole", ~66 times each in the run. `99b055ff7493a6ae` binds them twice |
| `ink4` | `RX_VK_DUMP=5000`, `RX_VK_DUMP_SSBO=` the three | Their other buffers: `8e895bab` rewrites a 64 KB list (`sb1`) and sets a counter (`sb4`); `1b75d9ca`'s `sb1` is 23,360 bytes, mostly `0x00ffffff` words |
| `ink5` | the same, with the hash | **`1b75d9ca` and `fd958faa` change the readback buffer on every frame; `8e895bab` does not** (before and after hashes, 3 frames) |
| `ink6` | the hash on both sides, presents 4998-5003 | **The CPU reads exactly the GPU's output a frame later.** Present 5001 reads `0x7fcda11000` with hash `d615145559254c6d`, which is `fd958faa`'s output in the frame dumped just before. Presents 5002 (`8b39e385…`) and 5003 (`5108f1a5…`) match the same way. The write-back flag says "never", but the bytes arrive: the GPU writes this pool in place, which that flag does not record |

## What this rules out, and what is left

- **Ruled out (verified):**
  - lost write-backs of these two buffers;
  - a read of stale memory by the CPU;
  - the hang's program as their writer.
- **The buffers' content:** the first 26 words of each look like camera data. A header of 0.2, 2000, 16/9 and
  0.99999 (near, far, aspect), then values like a view matrix. The GPU writes elsewhere in the 3,680 words.
  - So these readbacks may be a camera or visibility query, not the ink query (**unknown**). Session 3's "likely the
    ink query" was an inference.
- **Still open:** how the game decides the ink under the player. Candidates (**inferred**):
  1. **Another GPU readback.** Only these two were among the first 400 invalidates of the session, but other buffers
     read less often (`0x7f…1000 +0x80` pairs, read once or twice) were not examined.
  2. **The paint itself:** a compute pass reads a paint texture that is wrong in the replay (format, or not drawn). The
     query would then compute "enemy" or "none" correctly from a wrong texture.
  3. **A CPU-side check** that never touches the GPU.

## Next steps (inferred, about one session)

1. Examine the small, rare readbacks (`+0x80`): their writers and contents, with the same switches.
2. Dump the textures `1b75d9ca` and `fd958faa` sample (`RX_VK_DUMP` with PNGs, `RX_VK_DUMP_PROGS`), to see whether a
   paint map is among them and what it holds.
3. Failing those, look at the game side: which CPU code reads these results, and what it decides from them.

---

# Session 5 (2026-11-11): problem 8 found and fixed (occlusion counts)

**Short answer:** the enemy-ink behaviour came from the replay's answer to the game's **samples-passed counter** (an
occlusion query). The replay wrote a fixed 4096 for every such report (`gpu/vk/vk_replay.cpp:811`, upstream's fix for
Ocarina's sun). Raiders uses these counts to work out the ink under the player. Real counts from Vulkan occlusion
queries fix it in a headless run (**verified**, below): normal walking, no health drain, squid form in the player's own
ink. Your windowed check is still to do.

## How it was found

1. **The rare readbacks (session 4's next step 1).** In `ink1`, besides the two camera buffers, a thread named
   `ColPaintThread` invalidated 61 ranges once each at load (present ~840; log lines 15405-15471). Their sizes fit
   16-bit index buffers, e.g. `+0x2a0` = 112 triangles. So they look like map geometry the collision-paint builder
   reads, not GPU results (**inferred**).
2. **The game side** (strings and their references in `work/image/image.bin`, scratch scripts, not committed):
   - the collision-paint code is `spl::paint::ColPaint*` (`ColPaintBuilder`, `ColPaintPixelAreaBuilder`,
     `ColPaintMaskDrawer`, `ColPaintBakePaintableUnitDrawQueryPool`), at about `0x82ab0000`-`0x82ae0000`;
   - the game's only samples-passed (type 1) report comes from `lr 0x82ac7998` (**verified**, `nvn: the game reports
     counter type 1` in every run). It is in the function that also references `ColPaintMaskDrawer::depth` and
     `countup` (`0x82ac5d20`). There the sequence is: take a query slot, `ResetCounter(SAMPLES_PASSED)`, one
     `DrawElements`, `ReportCounter(SAMPLES_PASSED, slot)`. So the game counts pixels per paint unit;
   - the query pool has 65,536 slots of 0x60 bytes (`0x82ab56a0`). Its result reader (`0x811eb380`) waits for the
     report's timestamp word to be non-zero, takes the low 32 bits as the count, then zeroes the slot.
3. **The test** (`occ0`): the same save and the same steering, with `RX_VK_OCC_FIXED=0` (every count 0). At the
   beach's first tutorial step:

   | Run | Counts | Health at the reticle step | Stance |
   |---|---|---|---|
   | `live1` (session 3) | 4096 (default then) | **61/100** at present 7080, 50/100 at 8280, damage edges | the "sticky" pose, gold ring |
   | `occ0` | 0 | **100/100** at present 9120 and still at 14700 | normal |

   So the counter results decide the ink state under the player (**verified**). Zero is not right either: `occ0` drew
   ~1,220 draws and 84-92 passes a frame against the baseline's ~1,600 and 103. The game left work out when nothing
   counted.

## The fix

New `gpu/vk/vk_occlusion.h` and `gpu/vk/vk_occlusion.cpp`, with small hooks marked `(raiders)`:

- `vk_replay.cpp:829` (reset): a reset of SAMPLES_PASSED opens a **bracket**.
- `vk_replay.cpp:1198`, `1211`, `1225`, `1243` (the four draw ops): each draw in a bracket takes the next query number.
- `vk_draw.cpp:6234`: `OccQuery` begins that Vulkan occlusion query (precise) around the draw command, just after
  `StatsQuery`, in the open pass.
- `vk_replay.cpp:785` (report): the bracket's numbers so far are queued.
- A collector thread (`vk_occlusion.cpp` `collector`) writes `{sum, timestamp}` to the report's address once the GPU
  has every query, and marks the words CPU-owned so write-backs leave them alone.
- The numbers are given out in stream order by the dry pass and the serial replay, under `replay_mu`. Parallel workers
  get the same numbers from their state snapshots, and `vk_replay.cpp:1408` (`occ_sync`) keeps them following across
  command buffers and queues.
- A draw left out (not recorded) counts 0. A bracket stops counting after 4,096 draws, and its later reports get the
  fixed value.
- The bookkeeping is kept in `NvnState::samples_passed`, so `vk_state.h` is unchanged: that file is part of the
  shader-cache stamp (`nx2/build.py`), and changing it would make every shader recompile.

**Switches:**
- `RX_VK_OCC_REAL=1/0`. The default is **on for every game except Ocarina** (`vk_game_oot`), so upstream's game keeps
  its fixed 4096. Setting `RX_VK_OCC_FIXED` also selects the old path, as before.
- `RX_VK_OCC_LOG=<n>` logs the first n collected reports.

This is generic (any NVN game that reads occlusion counts), so it is an **upstream PR candidate**.

## Runs

| Run | Switches | Result |
|---|---|---|
| `occ0` | `RX_VK_OCC_FIXED=0`, live input, the hang's program left out | The table above. No device loss |
| `occ1` | the new build (real counts by default), `RX_VK_OCC_LOG=60`, live input, the hang's program left out | The details are below this table. No device loss, no "given up" reports |

**`occ1` in detail:**
- **Startup:** `vk: occlusion: samples-passed reports from occlusion queries (262144, precise)`.
- **The first 60 reports** carry real per-unit counts from 0 to 1,176, mostly in equal pairs (968, 968, 952, 952…).
  Before this fix every one was 4096.
- **The reticle step:** health **100/100** and the normal stance at presents 6600-8280.
- **Walking:** after the step was accepted, 4 s of walking climbed the dune and picked up the first shard. 8 s more reached the
  water's edge.
- **Squid form:** ZL into the teal ink put the player fully under the ink as a squid (the character is hidden), and the
  squid then moved on out onto sand.

**Frame rate:** at the same place, `occ1` runs at 32.5-33.4 fps with 1,607-1,682 draws and 103-104 passes. The baseline
`live1` ran at 32.3-33.0 fps with 1,478-1,687 draws and 102-104 passes. So the queries cost nothing measurable
(**verified** from the `presents` lines).

**Saves:**
- `occ0` rewrote the save as the 4,907-byte prologue save (as `title7` did); `occ1` wrote 5,073 B.
- Both are kept, in `~/raiders/work/t13s5_save_after_occ0/` and `t13s5_save_after_occ1/`.
- Your prologue save (`f5f463d9…`, from `t13s3_save_prologue`) was put back after each run.

**Smoke runs after the last change** (`occ2`, `occ3`: headless, no input, 150 s):
- 5 and 200 reports collected, 132 of the 200 non-zero; no device loss.
- The change was writing the report words through `guest_cpu_write` (below).

## Tests

- **The first full run** (`HOOKSHOT_VULKAN_HEADERS`/`HOOKSHOT_SPIRV_HEADERS` set to `/opt/homebrew/include`, `--jobs 4`):
  325 passed, **10** failed, 9 skipped in 826 s.
  - The new failure was `tests/test_wb_diff_cpu_writes.py`: the collector wrote guest memory with `host->gpu_write`, which
    the write-back diff's shadows never hear of.
  - It now writes through `guest_cpu_write`, and that test passes on its own (5 tests OK).
  - The other 9 failures are session 4's set (compared by name with `work/t13_ink_run_all2.log`). One of them is
    `test_program_cache_reader`, which timed out at 600 s here.
- **Not re-run in full** after that one-line change.
- **Deck build of the final code:** `compiled in 4s, 0 failed`.

## Open points

- **The first ~22 reports differ between runs (unknown).** In `occ1` they were 0, 0, 800, 0, 186, 135…; in `occ2` and
  `occ3`, all 0. From the 23rd on, the runs agree value for value (40, 0, 968, 968, 952, 952…). Whether this is the
  game's own timing (units baked before their mask is drawn) or an ordering problem in the replay is **unknown**.
  `occ1` played correctly with its values. If the ink state is wrong in some places, compare `RX_VK_OCC_LOG=200` across
  runs there.

- **Render conditions on these counts: unknown.** Reports are now written when the GPU has them, not in stream order.
  The game's NVN proc list names `SetRenderEnableConditional`, but whether it uses it on samples-passed reports is
  unknown. If objects go missing or flicker, look there first (`RX_VK_OCC_REAL=0` is the A/B).
- **The UI flat boxes (problem 4) are still there**, now over the health bar and the prompts, in `occ1` too.
- **No game-free test** for the new module yet: it needs a Vulkan device for the queries. The bracket numbering could be
  tested on its own if it is split out.

## Gate 1, updated

1. **Your windowed play-through** with the new build. Problem 8 is fixed headless. The prologue may now be playable to
   its end (jumps, swimming, the rest of the tutorial), which gives the save the title screen needs. The hang (problem 7)
   still needs `RX_VK_SKIP_PROG=cffdbb02c4dfbd39`:

   ```
   scripts/deck/run.sh prologue2 3600 --window --sound -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39
   ```

2. **Problem 7**, the hang: unchanged.
3. **Problems 3-5**, the UI boxes and labels, smeared foliage and 3D artifacts: unchanged.

---

# Session 5, continued: your windowed play-through (`prologue2`)

`scripts/deck/run.sh prologue2 3600 --window --sound -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720 RX_VK_SKIP_PROG=cffdbb02c4dfbd39`,
on the occlusion-fix build: swapchain 1280x718, mailbox.

## What you saw

- **Fixed:** you went past session 3's point and took out a bigger enemy. Jumps and swimming in your own ink work.
  Walking may feel a little slow; the frame rate is the likely reason (**inferred**). In 3D scenes (frames over
  300 draws) it was 10.6-60.2 fps, median 50.0.
- **The freeze:** you went into a room, a short cutscene played, then the black loading screen stayed up for good.
- **Flicker:** the UI still flickers (problem 4), and 3D things flicker a little while a blur effect is on (new detail
  for problems 4/5).
- **Sound:** music and the characters' talking noises play. Nothing plays for shooting, hitting the ground, boxes or
  balloons, hitting or defeating enemies, or collecting things.

## Problem 9 (new): the freeze at the loading screen is an audio effect that never becomes removable

- **The process was alive but idle (verified):**
  - presents stopped at 19,800 on the loading screen (5 draws a frame);
  - other threads kept logging, and every thread was asleep (`top -H`, no thread using CPU);
  - no device loss, no GPU timeout this boot after 12:45 (`journalctl -k`), and no occlusion report given up.
- **The last new calls before it (verified):** after the last present, the game made its first calls to three
  `nn::audio` functions the host does not implement (`[a64] unimplemented import`):
  - `nn::audio::IsBiquadFilterEnabled` (`lr 0x8357f790`)
  - `nn::audio::RemoveBiquadFilter` (`lr 0x83582e8c`)
  - `nn::audio::IsDelayRemovable` (`lr 0x8357f7b8`)
- **The caller (verified, `0x8357f720`, an effect wrapper):** it asks whether the effect is enabled, disables it, then
  asks whether it is removable. Only on yes does it remove it; on no it branches to `0x8357f8ac` to try again later.
- **Why it hangs (inferred):** the host's unimplemented imports answer 0, so a delay effect is never removable, and the
  scene change that waits for the old scene's audio to be torn down never ends. The host already answers 1 for the
  sibling calls (`IsReverbRemovable`, `IsAuxRemovable`, `IsBiquadFilterRemovable`… `host/nn_audio.c:1582-1591`). The
  `Delay`, plain `Reverb`, `Compressor` and `Capture` families are missing. In this run, 29 distinct `nn::audio`
  imports were unimplemented (each is logged on its first call), most of them `Delay` and `BiquadFilter` setters.
- **Owner:** `nn::audio` is **T18** by T10's ownership table (`docs/plans/tasks/T10-offline-stubs.md:98`). T13 does not
  fix it.
- **What T18 has to do here:** its scope item 2 covers exactly this: effect calls must leave the effect in a state the
  game's later calls accept. At minimum, the delay effect needs an "add, enable/disable, removable, remove" bypass. That
  likely also covers the missing sound effects (**inferred**: music and voices play, so the device and the main mix
  work; what is missing goes through other paths, effects among them).

## Saves

- Your play wrote a new save at 22:08:18, 5,066 B, md5 `55ce2485…`. It is **left in place** as your latest progress, and
  a copy is in `~/raiders/work/t13s5_save_prologue2/`.
- The game was stopped after the log was fetched (it was frozen).

## Gate 1, updated

1. **Problem 9 (T18):** the loading-screen freeze, then playing on to the end of the prologue for the title save.
2. **Problem 7**, the hang: unchanged (the switch is still needed).
3. **Problems 3-5:** UI boxes and flicker, 3D flicker under blur, smeared foliage.

## Problem 9: the freeze fix, done here at your request

You asked for the freeze alone to be fixed in T13, ahead of T18. The rest of the audio work (sound effects, effect
processing) stays with T18.

- **The change:** `host/nn_audio.c`, after `IsLightLimiterRemovable`, marked `(raiders)`: `IsDelayRemovable`,
  `IsCompressorRemovable` and `IsCaptureRemovable` now answer 1, as the host already does for the other effect types.
  - Only `IsDelayRemovable` was met in a run (**verified**).
  - The other two are imported, have no implementation, and would stop the same generic wrapper the same way
    (**inferred**).
- **Why nothing else is needed (verified):** the game's call to `RemoveDelay` (`0x83582788`, through the stub at
  `0x83f71050`) ignores its result (the function then returns 1). So the unimplemented `RemoveDelay`, which does
  nothing and answers 0, is enough.
- **Build:** the Deck build gives `compiled in 4s, 0 failed`, `build (lift): 190 s`.
- **Tests:** the six tests that read `nn_audio.c` (`tests/test_audio_*.py`) pass. The full suite was not re-run.
- **Boot check (`boot9`):** headless from your new save, A presses, 200 s.
  - The save boots into a story scene on a pier, then free movement there: no title screen, so the game treats the save
    as mid-story.
  - No device loss.
  - That run did not reach a delay effect, so the fix itself is **not yet verified**: it needs the room transition
    played again.
  - The game wrote its own save during the run; yours (`55ce2485…`) was put back.

---

# Session 5, continued: your second play-through (`prologue3`)

Same command as `prologue2`, on the build with the freeze fix (`18218a6`), from your save `55ce2485…`.

## Problem 9: fixed (verified)

- **The delay effect now comes and goes:**
  - the game added it (log line 28944, `AddDelay`, still unimplemented and harmless);
  - it then **removed** it (line 39166, `RemoveDelay`, called from `0x8358278c`). In `prologue2` the game never got
    past `IsDelayRemovable`.
- **The game kept going:** 99 frame-count lines (about 11,900 presents) came after the removal, with no device loss.
- **You beat a level.** The game saved at 22:55:31: 5,554 B, md5 `83abe43e…`. It is left in place, with a copy in
  `~/raiders/work/t13s5_save_prologue3/`.
- The game was stopped at 22:57, after the save and after the log was fetched.

## What you saw (open, recorded for later tasks)

| # | What | Notes |
|---|---|---|
| 10 | **Animations play slowly**; the game sometimes slows down, then plays faster after an area reloads | The frame rate in 3D frames (over 300 draws) swung between 10.6 and 60.3 fps over the run (e.g. 20.3-27.2 in long stretches). At the slow points the replay's submit time was 38-43 ms a frame, **29-31 ms of it descriptors**, the cost already noted for T22 (**verified** from the `replay time` lines). That the game's animation follows the frame rate (slow motion below 60 fps) is **inferred**. That the descriptor cost grows within an area and drops at a reload is **inferred**, not measured |
| 11 | **Gear menu: flickering icons cover the whole screen** | The UI flat-box/flicker class (problem 4), at its worst so far |
| 12 | **After leaving the gear menu, the scene is brighter**; **once, after a level and the gear menu, the floor went invisible under you** | State left behind by the menu's rendering: render targets, exposure or textures the 3D pass reuses (**unknown**). The next step is a frame dump (`RX_VK_DUMP`) before and after the menu at one spot |
| 13 | **Nets flicker in and out** | Thin alpha-tested geometry; whether it is a draw left out (`RX_VK_PIPE_SKIP=0` would show) or a depth/alpha problem is **unknown** |
| 14 | **Short loading screens flicker between black and 3D** | Presentation of the loading screen against the scene still being drawn; **unknown** |
| — | Sound effects missing (T18), UI flicker (problem 4), 3D flicker under blur | As in `prologue2` |

## Gate 1, updated

- **The title screen:** booting from this save to check for the title screen is the next step. Your save is past a
  level, but whether the prologue is over is **unknown**.
- **Problem 7**, the hang: unchanged (`RX_VK_SKIP_PROG=cffdbb02c4dfbd39` still used).
- **Problems 3-5 and 10-14:** for the follow-up tasks:
  - 10 is mostly T22 (descriptor cost);
  - 11-14 are rendering problems for T13's remaining work or T17.

---

# Session 5, continued: the title screen

**Short answer: the title screen is on screen headless.** It shows from a boot of your `prologue3` save (after the
level you beat) and matches your description of the console:
- the logo at the top left;
- the version (1.8.0) at the top right;
- "press ZL+ZR" at the right;
- the copyright line at the bottom left.

## Runs

| Run | Switches | Result |
|---|---|---|
| `title8` | your save `83abe43e…`, no input, `RX_VK_SKIP_PROG=cffdbb02c4dfbd39`, 240 s | The title from about present 1200 (shot `vk_001200`) to the end (`vk_014100`), with the platform scene behind it. 60 fps with ~1,063 draws a frame from present 3000 on. No device loss |
| `titlegate` | **T13's acceptance command** (`HOS_NO_MOVIES=1 HOS_HANDHELD=1`, no program left out), 180 s | The last screenshot (`vk_006600`) shows the title. The last frame line: 33.4 fps, 1,231 draws, 74 passes, replay submit 22.8 ms (descriptors 11.5 ms). Highest `vk: status` VRAM: 1.5 of 5.1 GB |

- Both runs rewrote the save (`8deb25a1…`, `3687a2b6…`); yours was put back each time and is in place (`83abe43e…`).
- The two frame rates differ: `title8` at 60 fps with ~1,063 draws, `titlegate` at 33 fps with ~1,231. Why is
  **unknown** (the title scene's animation phase, or work left out with the skip switch); recorded for T22.

## Acceptance criteria (session 5)

| Command | Result |
|---|---|
| `run.sh titlegate 180 -- HOS_NO_MOVIES=1 HOS_HANDHELD=1 && fetch.sh titlegate` | The last screenshot shows the title screen (above). **Met** (named `titlegate`, so session 1's `title` run is kept) |
| `grep -ci "device lost" work/runs/titlegate/hookshot_log.txt` | `0`. **Met** |
| `journalctl -k -b \| grep -cE "gfx_\|amdgpu.*timeout"` | 22 before the run and 22 after: **no new lines** from this run. The 22 are earlier sessions' (sessions 1-2 and the set-up lines of this boot). Literally the count is not 0 |
| `grep -n "dropped stages"` | Empty. **Met** |
| `tests/run_all.py` | The last full run (on `03ae582`) gave 325 passed, 10 failed, 9 skipped. The extra failure was fixed and its test passes on its own; the audio tests pass after `18218a6`. **Not re-run in full** since |

## Gate 1

**Headless: reached.** What remains is **your check at the Deck**: the title screen windowed against the console
(layout, colours, motion). Gate 1 passes when you confirm.

```
scripts/deck/run.sh titlew2 300 --window --sound -- HOS_HANDHELD=1 HOS_WINDOW_SIZE=1280x720
```

Known differences to expect, which are not Gate 1's:
- sound effects (T18);
- the UI flicker class (problems 3-4, 11);
- problems 10-14 from the play-through;
- the gameplay hang (problem 7), which still needs its switch in play.
