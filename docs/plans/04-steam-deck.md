# 04 · Steam Deck plan

Target: Steam Deck (LCD or OLED), x86-64 Zen 2 4 cores / 8 threads, 16 GB shared between CPU and GPU, RDNA2
integrated GPU ("Van Gogh"), SteamOS, Vulkan through Mesa RADV, 1280×800 panel. Tags as elsewhere. Nothing in
this document has been measured on the user's Deck yet: T03 records the real values in
`docs/plans/reports/deck-environment.md`.

## 1. Mesh shaders and the known GPU hang

- Hookshot requires Vulkan 1.3 and `VK_EXT_mesh_shader`, and lists SteamOS as tested
  (`readme.md` status table) **[verified]**. RADV exposes the extension on RDNA2 **[inferred from that
  status; verified on the user's Deck by T03: `vulkaninfo | grep -i mesh`]**.
- The known Deck hang is a task shader (code key `2c56dc1006942f74`) in Hookshot's own game that walks a depth
  grid per meshlet for seconds until the kernel resets the GPU (`gfx_0.0.0 timeout` in `journalctl -k`);
  workarounds `RX_VK_MESH_NOCULL=<key>` (culling off, everything drawn) and `RX_VK_SKIP_CODE=<key>`
  (draws left out) (`readme.md`, `docs/development.md`, issue #817) **[verified]**.
- **Raiders:** no task stage in any shader archive and a single fragment+mesh program, in the `Sample` archive
  **[verified: `spikes/shader_stage_kinds.py`]**. That shader key cannot occur in Raiders. The general
  failure mode (a long-running shader hitting the kernel's GPU timeout) can.
- Plan:
  1. T12 logs every program that has a task or mesh stage at run time; expected: none or one.
  2. T23 soak test watches `journalctl -k -f | grep -E "amdgpu|gfx_"` during play. On a timeout, the log's
     last "its code:" key identifies the program; try `RX_VK_MESH_NOCULL` (if it is a task shader), then
     `RX_VK_SKIP_CODE`, then report upstream.
  3. If the mesh program is drawn and misbehaves, `RX_VK_SKIP_CODE=<its key>` is acceptable for a `Sample`
     effect; the compute fallback is not needed on a GPU that has the extension.

## 2. Memory budget (16 GB shared)

What is known:

| Consumer | Hookshot's game on desktop | Raiders on the Deck (estimate) | Tag |
|---|---|---|---|
| Guest memory limit | 9,809 MB reported to the game, committed on demand (`host/hos_mem.c:50`) | same limit; real commit unknown | verified / unknown |
| Process RAM | "A run uses about 10 GB" (`readme.md`) | 6-9 GB: romfs is 12.7 GiB against 24.4 GiB, handheld profile | inferred |
| Lifted code + runtime | 426 MB executable (`docs/design.md` §9) | about 400 MB | inferred |
| Texture cache | 70% of the driver's allowance, at most 6 GB; **integrated GPUs: at most 2,560 MB** (`gpu/vk/vk_texture.cpp:3338-3344`) | 2,560 MB cap, lower if needed (`RX_VK_VRAM_MB`) | verified |
| VRAM mirrors of guest pools | on for discrete cards only (`RX_VK_MIRROR`) | off; pools are imported host memory, not copied | verified in docs; inferred for the Deck |
| SteamOS, gamescope, Steam client | n/a | 1.5-2 GB | inferred |

Budget target for T20: **process RSS + GPU memory ≤ 12.5 GB** with Steam running, leaving 1.5 GB of headroom
before swap. Levers, in the order to try them:

1. Handheld profile (`HOS_HANDHELD=1`): smaller render targets.
2. `RX_VK_VRAM_MB=2048` (or lower) for the texture cache; `RX_VK_TEX_MAX_DIM=1024` drops top mips of large
   textures (the comment at `vk_texture.cpp:1702` names the Deck).
3. ASTC policy: BC3 re-encode (default) keeps ASTC 4x4 textures at 1 byte per texel; `RX_VK_ASTC_RGBA8=1`
   costs 4× on 1,213 textures and is only for artifacts.
4. Quality preset "Minimum (4GB)" or "Low (6GB)" in the options file as a starting point
   (`quality_preset=1|2`, `docs/development.md`).
5. `HOS_MEMORY_MB`: only if the game sizes heaps from the reported total (the comment at `hos_mem.c:39` says
   TotK does). Lowering it risks out-of-memory inside the game; last resort, measured.
6. Swap: SteamOS ships a small swap file plus zram **[inferred]**. A larger swap file hides spikes during
   shader preparation and compiles. This is a system setting: the user changes it, not an Opus session.

Measurement (T20): `HOS_PROFILE`/the `vk: status:` line every 600 frames gives video memory in use against
the driver's allowance (`readme.md` "Where is the log?"); `grep VmRSS /proc/<pid>/status` and
`cat /sys/class/drm/card*/device/mem_info_vram_used` for the rest.

## 3. Shader compilation, pipeline caches, Steam's pre-caching

How Hookshot avoids stutter **[verified: `docs/design.md` §10, `docs/development.md`, `make_game.py:861-960`]**:

- `nx2/shader_census.py` writes `hookshot_shaders.bin` (every stage in the romfs) into the game folder at
  build time.
- A release build (`RX_RELEASE=1`) prepares shaders before the title on first start, or ahead of time with
  `hookshot --prepare-shaders`; results go to `hookshot_programs.bin` (+ `.idx`) and
  `hookshot_pipelines.bin` beside the executable. Later starts read them.
- Pipelines depend on draw state, so they are only known after play: `hookshot_pipeline_states.bin` is written
  as the game is played, and `nx2/pipeline_states.py` merges lists into a shipped list that the next
  preparation builds before the title.

Plan for Raiders:

1. **T12 (early):** run `--prepare-shaders` on the Deck over all 26,960 stages. This is both the translation
   census (risk 5) and the first measurement of preparation time on 4 cores. Hookshot's notes do not give a
   Deck figure; expect tens of minutes **[inferred]**. It must be resumable or at least not repeat on every
   start: confirm how the cache keys on driver version (`docs/pipeline-cache-save-check.md`).
2. **T21:** play through the first areas with pipeline-state recording on, merge the lists
   (`nx2/pipeline_states.py --out work/pipeline_states.bin …`), rebuild so the list ships in the game folder,
   and re-run preparation. Exit: a second visit to an area compiles nothing new (count of
   pipeline-compile log lines).
3. **Mesa's own cache** (`~/.cache/mesa_shader_cache`) works under any launcher and persists across runs
   **[inferred]**. A Mesa or SteamOS update invalidates driver caches: the launcher script should then re-run
   `--prepare-shaders` (T24) rather than stutter in game.
4. **Steam's shader pre-caching.** For Steam titles it downloads Fossilize caches; a non-Steam shortcut has
   nothing to download, and whether Steam's Fossilize layer records and replays locally for a non-Steam game
   is **[unknown]**. Hookshot's own caches do the same job. T21 tests both settings of
   *Settings → Downloads → Shader Pre-caching* and of the per-shortcut background processing, and records
   whether either changes first-run stutter or start-up time. Default recommendation until measured: leave
   Steam's setting alone and rely on `--prepare-shaders`.
5. `RX_VK_PIPE_SKIP` (default on): a draw whose pipeline is not ready is left out for a frame instead of
   stalling (`docs/development.md`). Good for smoothness, bad for accuracy screenshots: test runs that
   compare pictures set `RX_VK_PIPE_SKIP=0`.

## 4. Resolution, scaling, frame pacing, power

- **Panel and aspect.** 1280×800 is 16:10; the game renders 16:9. Accuracy first: present 1280×720 centred
  with 40-pixel bars (gamescope does this for a 1280×720 fullscreen window) **[inferred]**. Hookshot's
  ultrawide path widens cameras only for shapes wider than 16:9 and "narrower down to 5:4" exists in the menu
  (`readme.md`, Ultrawide row); a 16:10 fill is an optional enhancement after M7.
- **Handheld profile.** "Runs the game as if the console were undocked" (`readme.md`); set
  `handheld_profile=1` / `HOS_HANDHELD=1`. Hookshot's game renders 1536×864 output in handheld; Raiders'
  handheld size is **[unknown]** until T13 reads it from the log. If it is above 1280×720, the window scaling
  filter downsamples; if below, see FSR.
- **Window.** `HOS_WINDOW_SIZE=1280x720`, `HOS_FULLSCREEN=1` under gamescope (`docs/development.md`).
- **Upscaling.** Order of preference: the game's own resolution at 100% if the GPU holds it; else the game's
  dynamic resolution (`resolution=0` Auto) with the Catmull-Rom window filter; else FSR 3.1 upscaling
  (`RX_VK_FSR=1`, built in, needs only Vulkan 1.3 features; `readme.md` "AMD FSR 3.1"). gamescope's own FSR
  is an alternative that needs no code (render the window below 720p and let gamescope scale). Frame
  generation is out for accuracy-first and because the bottleneck is expected to be the CPU.
- **DLSS-class networks.** The game links `nvnDlss*` and SMAA for NDSR. On non-NVIDIA GPUs Hookshot uses a
  linear stand-in (`readme.md` "RX_VK_MOVIE_UPSCALE"; `gpu/vk/vk_coopmat.cpp`). What Raiders' anti-aliasing
  or upscale looks like with the stand-in on the Deck is **[unknown]** → T13 screenshot review.
- **Frame pacing.** The game's own target is presumably 60 fps **[inferred from the series]**; the Deck is
  expected to be CPU-bound below that (risk 1). Plan: measure uncapped (T17), then choose a cap that holds:
  gamescope's limiter at 30 (or 40 on a 40/80/90 Hz refresh setting) with Hookshot's `Game speed = Real time`
  so the game keeps normal speed below 60 fps ("down to 15 fps", `readme.md`). `RX_VK_FRAME_LOG=<csv>` gives
  per-present frame times because MangoHud's log stays empty under gamescope (`vk_replay.cpp:3600`).
- **Power.** Default 15 W TDP. The lifted code is single-thread heavy, so lowering TDP costs frame rate
  directly **[inferred]**. T22 records fps at 15 W and at 10 W for a battery profile; SMT stays on (the
  runtime reserves a logical core for the replay only with 8 logical processors).
- **CPU threads.** Start from upstream defaults (`HOS_CORES=6` virtual cores, one reserved for the replay);
  T22 measures `HOS_CORES=4`, `HOS_VCORES=0`, `HOS_RESERVE_CORE=0`, `RX_VK_ASYNC=1` one at a time
  (`docs/design.md` §4 rule 7: "thread counts are measured, never raised by default").

## 5. Controls: pad + gyro through SDL and Steam Input

- Hookshot reads controllers through SDL (SDL2 on Linux by default, SDL3 where present; `readme.md`
  "Rumble", `make_game.py:53`) and has Steam Deck button prompts (`host/prompts.c:85`) **[verified]**.
- Layout: Nintendo layout preset is the default (A on the right face button). The Deck's ABXY are in Xbox
  positions; keep `layout_preset=0` so the physical position matches the Switch (accuracy), and let the
  user switch to "Xbox / PC" in the menu.
- **Gyro, plan A (native):** SDL reports the Deck's gyro as a gamepad sensor; Hookshot's motion code
  (`host/hos_motion.h`, `host/nn_hid.c:857`) turns it into six-axis state. Whether SDL sees the sensor when
  the game is started from Gaming Mode (Steam Input presents a virtual pad) is **[unknown]**. Test in T15 with
  `HOS_MOTION_DEBUG=1` under three conditions: Desktop Mode without Steam; Gaming Mode with Steam Input
  enabled; Gaming Mode with Steam Input disabled for the shortcut.
- **Gyro, plan B (no code):** a Steam Input layout that maps gyro to "as joystick" on the right stick,
  active while a trigger or the right-pad touch is held. Ships as notes and a template in
  `games/raiders/steam_input/` (T24). Less faithful than six-axis aiming but always available.
- Recommendation: implement plan A's checks first; ship plan B as the documented fallback either way.
- Trackpads and back grips: not planned (the user chose pad + gyro). Steam Input can still bind them.
- Menu shortcut: "Home or Select+Start" opens Hookshot's menu on a pad (`readme.md`). On the Deck the Steam
  button is taken by Steam; Select+Start works. T15 confirms it does not clash with the game's own use.
- Rumble: plain two-motor rumble on the Deck (`HOS_HD_RUMBLE` only matters for Switch controllers).

## 6. Packaging and launching

- **Final form (T24):** an AppImage built by the fork's CI from `scripts/linux/deps.sh` +
  `scripts/linux/appimage.sh`: toolchain, Python, FFmpeg, SDL2, prebuilt `hookshot_vk.so`, the sources. No game
  data. On the Deck: `./RaidersRecomp-x86_64.AppImage --cli --romfs ~/raiders/dump/romfs --exefs
  ~/raiders/dump/exefs --out ~/Games/raiders --language en-US`, then `--play ~/Games/raiders`
  (`builder/linux/AppRun`) **[verified flow for upstream's game]**.
- **Gaming Mode:** in Desktop Mode, *Add a Non-Steam Game* → the AppImage, launch options
  `--play /home/deck/Games/raiders` (Recompia documents the same route for its launcher). Before M8, add
  `~/Games/raiders/hookshot` directly. Compatibility tool: none (native Linux binary; do not force Proton).
- **Environment:** `~/Games/raiders/hookshot_env.txt` is read by the game itself (`docs/development.md`), so
  switches work identically from a terminal, Desktop Mode and Gaming Mode. `games/raiders/deck_env.txt` is the
  template the build copies there (only if the file does not exist: never overwrite the user's edits).
- **Saves:** `~/.local/share/raiders-recomp/save/<user id>/` after T16 (upstream default:
  `~/.local/share/hookshot`). Options: `~/Games/raiders/hookshot_options.ini`. Log:
  `~/Games/raiders/hookshot_log.txt` and four older ones.
- **Disk layout on the Deck:** the romfs is hard-linked into the game folder when the dump and the output are
  on the same filesystem (`make_game.py:1001`); otherwise it is copied (another 12.7 GiB). Put
  `~/raiders/dump` and `~/Games/raiders` on the same volume (both on internal storage, or both on the same
  SD card).
- **Updates:** the launcher's update check points at upstream's releases; set
  `HOOKSHOT_NO_UPDATE_CHECK=1` in `deck_env.txt` and remove the Update action from the fork's launcher (T24).

## 7. Building on the Deck versus elsewhere

The user's decision: develop on the Mac, compile and run on the Deck, with the dump copied to the Deck.

| | Build on the Deck (chosen) | Build on another x86-64 Linux PC | Linux VM on the Mac |
|---|---|---|---|
| Hardware needed | none extra | a PC | none extra |
| Works with upstream's scripts | yes, in a glibc ≥ 2.35 container | yes | no: arm64 host, needs a cross-compile path upstream does not have |
| Full build time | Hookshot reports 10-45 min on PCs and 25-43 min with 4 jobs (`readme.md`, `docs/design.md` §9-§11); expect 45-90 min on the Deck **[inferred]** | 10-45 min | n/a |
| Disk | upstream asks for about 60 GB free while building; Raiders needs less (no `.nup` extraction, romfs hard-linked): about 25-30 GB for deps, lifted C, objects and the game folder **[inferred]** | same | n/a |
| Test loop | build and run on the same machine | copy the game folder each time | n/a |

How the Deck builds:

- **During development (M1-M7): a container.** SteamOS's root filesystem is read-only and has no compiler.
  Use a Distrobox container (Ubuntu 22.04 or 24.04) in the `deck` user's home; SteamOS ships Distrobox and
  Podman **[inferred; T03 verifies, with the fallback of installing them into the home folder]**. Inside it,
  `scripts/linux/deps.sh` fetches LLVM 23.1.5, a standalone Python with the needed packages, FFmpeg, SDL2 and
  the Vulkan/SPIR-V headers and VMA into `build-linux/deps` (sizes and versions in the script's header)
  **[verified by reading]**. The game binary built in the container runs on the host: it needs glibc 2.35+
  and carries its own SDL2 (`BESIDE` in `make_game.py:53`).
- **Settings for a 16 GB machine:** `HOOKSHOT_JOBS=4`; leave the memory gate on (`HOOKSHOT_MEM_GATE`);
  close Steam's client UI heavy pages or build from Desktop Mode over SSH; hot pieces need 0.8-1.7 GB each
  (`build.py:270`, `:374`), which only matters once a hot list exists (T22).
- **Remote control from the Mac:** enable SSH on the Deck (`passwd`, `sudo systemctl enable --now sshd` in
  Desktop Mode). This is a system change the user makes; T03 gives the exact steps. With it, an Opus session
  on the Mac runs `scripts/deck/build.sh` and `scripts/deck/run.sh` and reads back logs and screenshots, so
  acceptance commands in the task files can be executed without the user at the Deck.
- **Running under SSH:** a run started over SSH has no display. Use `HOS_HEADLESS` (offscreen rendering for
  screenshots and frame dumps, `docs/development.md`) for automated checks, and start from Desktop or Gaming
  Mode for anything interactive. T03 confirms headless rendering works on RADV without a compositor.
- **After M8:** the AppImage replaces the container for the user's own rebuilds.

## 8. Deck-specific defaults (`games/raiders/deck_env.txt`, first draft for T20)

```ini
# Raiders on a Steam Deck. One NAME=VALUE a line; the game reads this file as hookshot_env.txt.
HOS_HANDHELD=1
HOS_WINDOW_SIZE=1280x720
HOS_FULLSCREEN=1
HOS_AUDIO_CHANNELS=2
HOOKSHOT_NO_UPDATE_CHECK=1
RX_VK_FRAMEGEN=0
# to be set from measurements (T20, T22): RX_VK_VRAM_MB, RX_VK_TEX_MAX_DIM, HOS_CORES
```

Every line added later cites the report that justified it.
