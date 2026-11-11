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
