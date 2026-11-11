# 02 · Gap analysis: Hookshot subsystem by subsystem

Verdicts: **UNCHANGED** (expected to work as is), **GENERALISE** (hardcoded for Ocarina of Time; needs a
per-game switch), **NEW** (Raiders uses something Hookshot's game does not). Evidence is from the dump unless a
Hookshot path is given. Tags as in `01-research-findings.md`. Hookshot paths are relative to the repo root
after T01 (today: `refs/Hookshot/`).

Summary:

| # | Subsystem | Verdict | Size of work | Tasks |
|---|---|---|---|---|
| 1 | Ingestion and version checks | GENERALISE | small | T04, T05 |
| 2 | Lifter | UNCHANGED core, GENERALISE driver | small | T06 |
| 3 | Host OS services | GENERALISE + NEW stubs | medium | T07, T09, T09a, T10 |
| 4 | Threading and sync | UNCHANGED, tune for 4 cores | small | T08, T22 |
| 5 | NVN2 record/replay | UNCHANGED core, NEW procs as traced | medium, unknown tail | T09, T11, T13 |
| 6 | Shader lowering and translation | UNCHANGED core, NEW geometry stage (conditional) | unknown until T12 | T12, T14 |
| 7 | Texture formats | UNCHANGED | none expected | T20 |
| 8 | Audio | UNCHANGED core, NEW effect calls as traced | small-medium | T18 |
| 9 | Input / HID | UNCHANGED core, NEW handheld and gyro checks | small-medium | T15 |
| 10 | Saves | GENERALISE (data folder) | small | T16 |
| 11 | Movies | UNCHANGED codec, NEW `nn::movie` front end check | small-medium | T19 |
| 12 | Mods / romfs | UNCHANGED | none | (T05 for the size table name) |
| 13 | Builder (`make_game.py`, `build.py`) | GENERALISE | small | T04, T08 |
| 14 | Launcher and UI builders | GENERALISE, mostly unused | small | T24 |
| 15 | Packaging | GENERALISE | small-medium | T24 |

---

## 1. Ingestion and version checks: GENERALISE

- **Input format: works.** The dump is `romfs/` + `exefs/` folders; `make_game.py --romfs <dir> --exefs <dir>`
  takes that form (`readme.md`, "Build from source") **[verified]**. No `.nup`, no ZBIC: `nx2/nup.py` and
  `nx2/unpack.py` are not on Raiders' path **[verified: a64-kit's loader read all four NSOs directly]**.
- **`nx2/dump.py`: works unchanged** **[verified: run on the dump]**.
- **Version pin: hardcoded.** `nx2/make_game.py:44` `BUILD_ID = "e0f3ccfa"`; `check_supported_build` (`:311`)
  and `check` (`:378-393`) compare `main`'s build id against it. Raiders' is `abb30e2f…` so `--check` answers
  "bad" today **[verified by reading]**. → T04 moves the pin into `games/<id>/game.py`.
- **Languages: differ.** `make_game.py:55` lists 16 languages including `pt-BR`, `pl`, `ru`; Raiders'
  `System/RegionLangMask.txt` has 13 region-language pairs and none of those three **[verified]**. → T04 takes
  the list from the game config; T05 validates `--language` against it.
- **romfs sanity:** Hookshot checks for damaged files (`stand_in_damaged_files`, `make_game.py:317`) tied to
  its `.nup` flow. For a folder copied to a Deck, add a file-count and byte-count floor in the game config
  (idea from Recompia's `game::Info::romfs_min_files`) and ignore `*.part` **[new, small]** → T05.

## 2. Lifter: UNCHANGED core, GENERALISE driver

- **Instruction coverage: complete.** 258,115 functions, 18,409,608 instructions, 100.0000% translated, 0
  untranslated words, 0 `BR` without a jump table **[verified: `work/lift_coverage.log`]**. No new
  instruction forms are needed in `nx2/insn.py`.
- **Image layout: works.** `rtld@0x80000000`, `main@0x80020000+0x4e30000`, `subsdk0@0x84e50000`,
  `sdk@0x84f30000`; 0 unresolved non-weak imports **[verified: same log]**.
- **Driver: Ocarina patches are installed unconditionally.** `nx2/lift.py:162-167` imports and installs
  `oot_wide`, `oot_jitter`, `oot_occlusion` for every `--standalone` lift; they patch at addresses found in
  Ocarina's `main`. `lift.py:186-188` passes `main_build == oot_patches.LIFE_BUILD_ID` to `chunks.edit_c`
  (already gated). Whether each `install()` gates itself on the build id is **[unknown]**; on another game
  they must do nothing. → T06 routes them through `games/<id>/patches.py`.
- **Semantic correctness on Raiders' code: untested.** Hookshot's differential tests need Unicorn:
  `nx2/test_insn.py` (every instruction form the game uses) and `nx2/test_leaf.py` (random whole functions)
  **[verified: `docs/design.md` §7]**. → T08a, on the Deck. (Revised 2026-11-10: T02 found both harnesses
  Windows only (`windows.h`, `VirtualAlloc`, SEH) and the Mac arm64, so neither runs on the Mac or, as written,
  on Linux; `docs/plans/reports/mac-test-baseline.md`.)
- **Emit size [inferred]:** Hookshot's game emitted 1.4 GB of C in 57 chunks for 294,450 functions; Raiders
  has 12% fewer functions, so about 1.2 GB.
- **Hot list and PGO:** none exist for Raiders. Without them "the game builds but runs slower" (`readme.md`).
  → T22 generates them from Deck play (`scripts/hotlist.py`, `RX_PGO=gen`, `nx2/pgo_pieces.py`).

## 3. Host OS services: GENERALISE + NEW stubs

Hookshot replaces SDK functions by mangled name; whatever is not replaced runs as lifted SDK code, and
OS-facing imports without an implementation get a stub that logs its first call and returns 0
(`nx2/standalone.py` docstring) **[verified]**.

For Raiders: **528 functions hooked, 279 stubbed** **[verified: `spikes/standalone_summary.py`]**. Stubs by
namespace and the plan for each:

| Namespace | Stubbed | Raiders evidence | Plan |
|---|---|---|---|
| `nn::audio` | 121 | Effects: `AddDelay/Reverb/Compressor/Capture`, `Remove*`, setters (`work/standalone_stubbed.txt`) | Returning 0 from an "add effect" call is usually tolerated (Hookshot's game ran with "audio effects" on the generic stub, `docs/design.md` §9). Implement only what the trace shows breaks sound → T18 |
| `nn::socket`, `nnsocket*`, `nn::ssl`, `nn::nifm` | 32 + 2 + 9 | NPLN, gRPC, libcurl, Pia linked into `main` | Offline answers: no network available, `Poll` nothing ready. Hookshot already does this for its game's NPLN (`docs/design.md` §9 "Offline answers") **[verified]**; confirm the same HLEs cover Raiders' imports → T10 |
| `nn::ldn` | 26 | `Initialize`, `OpenStation`, `ScanPrivate`, `CreateNetwork`, … | **NEW**: `Initialize` succeeds, state stays `None`, scans return 0 networks, create/connect return a failure result. Out of scope beyond failing cleanly → T10 |
| `nn::nfp` | 23 | `Initialize`, `ListDevices`, `StartDetection`, … | **NEW**: no device: `ListDevices` returns 0 → T10 |
| `nn::codec` | 21 | `AacDecoder*`, `*H264Decoder*` (imported by `subsdk0`) | Leave stubbed. The shipped movies are VP9 with no audio track **[verified for one file; inferred for the rest]**; revisit only if T19's log shows these called |
| `nn::hid` | 13 | `InitializeJcms/GetJcmsStates` (Joy-Con 2 mouse), `GetMouseStates`, `InitializeNmouse` | Stub "no mouse" → T15 |
| `nn::swkbd` | 7 | `ShowKeyboard`, `SetTextCheckCallback` | **NEW**: return "cancelled". A text prompt is a later nicety → T10 |
| `nn::friends` | 6 | friend list and presence | **NEW**: empty list, offline → T10 |
| `nn::pl` | 3 | `GetBuiltInFontData` (Nx and Ounce overloads), `RequestLoadNxFont`. The Ounce overload is the first blocking call of every run: the game dereferences the font pointer it expects back (`reports/M2-boot.md`, `reports/M3-trace.md`) **[verified]** | **NEW**: serve a stand-in font from the bundled OFL fonts → T09a |
| `nn::time`, `nn::prepo`, `nn::movie`, `nn::account`, `nn::vi`, `nn::oe`, `nn::err`, `nn::ro` | 18 | assorted | Decide per call from the trace; owners by namespace in `tasks/T10-offline-stubs.md` ("Ownership of traced calls") |

Other points:

- **SDK generation.** Raiders is SDK 21.4.4. Hookshot's runtime came from mkw-recomp (SDK 21.4.0) and was
  then extended for SDK 22.2.8 (`docs/design.md` §5, §9: "TLS: the owner handle at TLR+0x110 too (SDK 22)",
  "SDK 22 overloads left to the guest SDK", NVN API version 231.40). Whether every SDK 22 change is still
  right for an SDK 21 game is **[unknown]**; the common base makes breakage unlikely **[inferred]** → T08.
- **Ocarina-only runtime code.** `host/hos_main.c:414-800` (inventory, time-of-day, teleport: fixed guest
  addresses such as `0x84c9e0d0`, called through `a64_lookup`), reached from the debug menu and
  `HOS_OOT_CHEATS`. On Raiders these addresses hold other code: the entry points must be unreachable unless
  the build id is Ocarina's → T07.
- **Program id** comes from `main.npdm` through `gen/hos_image.c` (`host/hos_svc.c:37`) **[verified]**: no
  change needed.
- **Microphone** (`host/nn_audio_in.c`): Hookshot's game uses it; Raiders' need is **[unknown]** (`aud:u`,
  `audsmx:u` are in every application's service list). Keep the default "hears silence" behaviour.

## 4. Threading and sync: UNCHANGED, tune for the Deck

- `nn::os` coverage is 118 of 123 imports **[verified: `work/imports_raiders.txt`]**. The five uncovered are
  to be listed in T08 (`grep '^    .*2nn2os' work/imports_raiders.txt`).
- `nn::async` (42 imports) is the NPLN fiber pattern Hookshot already runs on host fibers
  (`docs/design.md` §9: "nn::os fibers … nn::async's FiberTaskCoordinator on the nn.npln threads")
  **[verified in the docs; behaviour on Raiders unknown]**.
- Fixed-address pacer hooks are gated on Mario Kart's build id (`hos_game_is_mkw`, `host/hos_main.c:73`) and
  are inert here **[verified]**.
- **Deck tuning.** The game sees 6 virtual cores by default and one host core is reserved for the replay when
  there are 8 or more logical processors (`HOS_CORES`, `HOS_VCORES`, `HOS_RESERVE_CORE`,
  `docs/development.md`). The Deck has 4 cores / 8 threads, so the reserve rule applies as written
  **[inferred]**; the right values are measured, not guessed (`docs/design.md` §4 rule 7) → T22.

## 5. NVN2 record and replay: UNCHANGED core, NEW procs as traced

- **Same API generation as the pipeline's first game.** NVN 21.4.4; `host/nvn_native.c`'s device limits
  (`devinfo[]`) were read from Mario Kart World's SDK 21.4.0 driver, and the reported API version is 231.40
  (`nvn_native.c` comment above `devinfo[]`) **[verified]**. Whether an SDK 21.4.4 game accepts minor 40 is
  **[inferred yes]**: the comment says MKW "said 39, which MKW accepts too", and games check a minimum.
- **Names.** `main` carries 734 `nvn*` names; 427 have implementations; 325 do not
  **[verified: `work/nvn_missing.txt`]**. This is the name table the game loads through
  `nvnDeviceGetProcAddress`, not its call set. Hookshot's own game had 14 unimplemented names that mattered
  at first boot (`docs/design.md` §5). Unimplemented procs log their first call and return 0;
  `HOS_NVN_STRICT=1` stops instead (`host/PROVENANCE.md`) **[verified]**.
- **Missing families worth watching** (from `work/nvn_missing.txt`): `nvnDlssParameters*`/`nvnDlssNetwork*`
  (57: Hookshot handles DLSS evaluation its own way; these setters may need to be accepted),
  `nvnCommandBuffer*` (73), `nvnProgramBuilder*` (19), `nvnMultisampleState*` (18), `nvnDirtyTile*` (13),
  `nvnQueueBuilder*` (12), `nvnWindowBuilder*` (10).
- **Queues and events.** Hookshot's rules for cross-queue event waits, submit-time captures and ordered
  texture registration (`docs/design.md` §4 rules 1-3) are engine-level and the engine is shared
  **[inferred]**. First-boot check from the same section: log Raiders' queues and event waits.
- **Dynamic resolution.** Driven by fake GPU timestamps (`RX_VK_TS_SCALE`, rule 4). Raiders' controller and
  handheld resolution are **[unknown]** → observed in T13/T17.
- **GPU-written data read by the CPU.** Write-backs exist (`RX_VK_NO_WRITEBACK`, `RX_VK_WB_DIFF`,
  `docs/development.md`). Raiders-specific concern: ink coverage tests **[inferred]** → T17.

## 6. Shader lowering and translation: UNCHANGED core, NEW geometry stage (conditional)

- **Packages: same.** `Nin_Ounce_NVN2` BNSH, agl BAHS archives, NDSR networks, particle sets: the census
  reads all of them **[verified: `spikes/shader_census_nodict.py`]**. Fix needed: `nx2/shader_census.py:38`
  opens `Pack/ZsDic.pack.zs` unconditionally → T05 (upstream candidate). The same assumption is in
  `nx2/prompt_assets.py` and `gpu/vk/vk_game_font.h` (the in-game menu font and button prompts): they must
  fall back, not fail → T05.
- **Stage mix [verified: `spikes/shader_stage_kinds.py`]:**

  | Archive | vertex+fragment | compute | +geometry | fragment+mesh |
  |---|---|---|---|---|
  | `Shader/Hoian_UBER…bfsha.zs` | 6,756 | 0 | 0 | 0 |
  | `Shader/Sample…release.sarc.zs` | 4,205 | 21 | 440 | 1 |
  | `Lib/agl/agl_resource…` (release) | 6,567 | 356 | 0 | 0 |
  | `Lib/gsys/gsys_resource…` (release) | 81 | 3 | 0 | 0 |
  | `Effect/*` (363 sets) | 26,247 | 301 | 0 | 0 |

  (Counts before de-duplication; unique totals are in `01-research-findings.md`.)
- **Task/mesh:** no task stage, one mesh program. Hookshot's mesh path and the Deck's culling-shader hang
  concern task+mesh programs (`readme.md`); Raiders barely touches this path **[verified statically]**.
  The engine could still build programs at run time from data the census does not walk
  (`Layout/`, `UI/LayoutArchive`, `Pack/`) **[unknown]** → T12 compares the census with a run's program log.
- **Geometry stages: not supported.** `gpu/vk/vk_shader.cpp:2087-2090` drops stages 2-4 and logs
  "dropped stages" **[verified]**. 160 unique Raiders programs have a geometry stage, all in the `Sample`
  archive. Whether normal play draws them is **[unknown]**. Plan: do nothing until a run logs "dropped
  stages" for a visible effect; then T14 (Eden's recompiler has a Maxwell geometry path; the Ampere lowering
  and pipeline creation need extending). Why not reuse something existing: no reference project translates
  Ampere geometry stages for this pipeline **[inferred from Hookshot's comment; check Lichii and Eden first in T14]**.
- **Opcode coverage: unknown.** Hookshot's game still has a handful of programs that do not lower
  (`docs/design.md` §9). Raiders' rate is **[unknown]** → T12 translates all 26,960 stages on the Deck and
  feeds failures to `nx2/lower_test.py`.
- **Ocarina-only shader code:** `oot_visual_workaround.h` (fog 0.25, exposure 0.65) applied at
  `vk_shader.cpp:879-890`; the default `RX_VK_SKIP_PROG=53509044401d78d2`; Ocarina tokens in
  `frontend/maxwell/structured_control_flow.cpp`. All must be off for Raiders → T07.
- **Neural networks (NDSR, DLSS).** SMAA for NDSR 2.3.0 is linked and 57 `nvnDlss*` names exist. Hookshot runs
  its game's networks through `VK_KHR_cooperative_matrix` on NVIDIA and falls back to linear upscaling
  elsewhere (`readme.md` "RX_VK_MOVIE_UPSCALE"; `gpu/vk/vk_coopmat.cpp`). Whether Raiders evaluates a DLSS
  network in handheld mode, and what the fallback looks like on the Deck, is **[unknown]** → T13.

## 7. Texture formats, including ASTC: UNCHANGED

- 35,255 BNTX files: 96.5% BC1/BC4/BC5/BC6H/BC7, which the Deck's GPU samples natively; 1,213 ASTC 4x4 files
  (3.4%) **[verified: `spikes/bntx_formats.py`]**. Hookshot decodes ASTC and re-encodes to BC3, or keeps
  RGBA8 with `RX_VK_ASTC_RGBA8=1` (`readme.md` "AMD texture workaround", `gpu/vk/astc_bc_policy.h`)
  **[verified]**. RGBA8 for 1,213 textures is affordable if the BC3 path shows artifacts on RADV
  **[inferred]** → decided in T20.
- The Switch 2 GOB swizzle and tile layouts are engine-independent (`gpu/PROVENANCE.md`).
- BNTX is the same container as Hookshot's game (35,255 `.bntx` here; `dump.py` counts them the same way).

## 8. Audio: UNCHANGED core, NEW effect calls as traced

- `nn::audio`: 114 of 238 imports implemented; the 121 stubs are mostly effects (section 3).
- Formats: BARS/BWAV and Opus (`UseOpus`, `OpusDecoder` strings; `nn::codec` Opus functions are among the 45
  implemented; libopus is vendored at `third_party/opus`) **[verified]**. `hwopus` IPC is not used by Hookshot's
  model: the `nn::codec` layer is replaced above it **[inferred]**.
- Output: SDL on Linux (`host/posix/display_sdl.c`, `build.py:744`), stereo on the Deck's speakers
  (`HOS_AUDIO_CHANNELS=2`).
- Test runs are muted by default (`HOS_AUDIO=0`); audio is validated late (M6) because it does not block boot.

## 9. Input / HID: UNCHANGED core, NEW checks

- `nn::hid`: 22 of 60 imports implemented, including the six-axis functions (`host/nn_hid.c:830-857`). Most of
  the uncovered 38 are SDK-side classes that run as lifted code (`VibrationNode`, `VibrationMixer`,
  `VibrationPlayer`) plus the 13 OS-facing stubs **[verified: `work/imports_raiders.txt`]**.
- **Handheld mode.** The plan runs the game as undocked (`HOS_HANDHELD=1`, `handheld_profile` in the options
  file, read in `host/nn_applet.c`). Which Npad style the game then expects (Handheld versus FullKey) and what
  Hookshot reports is **[unknown]** → T15.
- **Gyro.** A Splatoon-series game aims with motion. Hookshot feeds SDL gyro data to the six-axis state
  (`readme.md` "Motion controls", `host/hos_motion.h`). On the Deck in Gaming Mode the pad reaches SDL
  through Steam Input, and whether gyro data comes with it is **[unknown]** → T15, with a fallback that needs
  no code (Steam Input "gyro to right stick").
- Scripted input for tests: `HOS_INPUT_SCRIPT`, `HOS_INPUT_LIVE` (`docs/development.md`) **[verified]**.
- Amiibo, Joy-Con 2 mouse, IR (`irs`), GameChat (`chat:u`): stubbed, out of scope.

## 10. Saves: GENERALISE

- `nn::fs`: 25 of 28 imports implemented; `nn::account`: 10 of 19 **[verified]**.
- Save layout for Raiders is **[unknown]** until the game writes one. Hookshot stores per-user saves under
  `~/.local/share/hookshot/save/<user id>/` on Linux (`docs/saves.md`) **[verified]**.
- Change: the data folder name comes from the game config (`raiders-recomp`), so a Hookshot install on the
  same Deck cannot collide → T16. `scripts/oot_saves.py` is Ocarina-only and stays untouched.

## 11. Movies: UNCHANGED codec, NEW front-end check

- Files: 16 VP9 WebM clips in `UI/Movie/` (gadget previews), 40 MB **[verified]**.
- Codec layer: `host/nn_video.c` implements `nn::codec`'s VP9 decoder on FFmpeg (`:734-749`) **[verified]**.
  FFmpeg with VP9 is in `scripts/linux/deps.sh`; dav1d (AV1) is not needed for Raiders.
- Front end differs from Hookshot's games: there the movie library was `movie::` inside `subsdk0`. Here `main`
  imports 43 `nn::movie` functions that **`sdk` defines** (604 symbols), and `subsdk0` (NintendoSDK_movie
  21.4.4) imports 67 `nn::codec` symbols **[verified: `spikes/standalone_summary.py`]**. The expected path is
  `main` → `nn::movie` (lifted `sdk`) → `subsdk0` (lifted) → `nn::codec` (host). Whether that chain runs
  without IPC to a media service is **[unknown]** → T19. Three `nn::movie` functions are stubbed today.
- `HOS_NO_MOVIES=1` skips movies while booting (`docs/design.md` §5).

## 12. Mods and romfs: UNCHANGED

- `host/mods.c` layers `mods/<name>/romfs/` over the game's files (`readme.md` "Mods") **[verified]**. Not
  needed for the goal; costs nothing to keep.
- The romfs is hard-linked into the game folder where the disk allows (`make_game.py:1001`), so the dump and
  the output folder should be on the same filesystem on the Deck (`04-steam-deck.md`).

## 13. Builder: GENERALISE

- `nx2/make_game.py`: build id pin (`:44`), output names (`BESIDE`, `:53`), languages (`:55`), the performance
  data it copies from `work/` (`:1305`: `hot_funcs.txt`, `hot_order.txt`, `hookshot_pieces.prof`,
  `hookshot.res`), `seed_pipelines` (`:861`) and `ship_state_list` (`:883`). All tolerate missing files
  ("Good for any build: optional") **[verified by reading]**.
- `nx2/build.py`: `HOS_GAME_VERSION` and the main build id are written into generated C (`:521`); Linux build
  uses SDL2, `host/posix`, FFmpeg from the CPM cache or `HOOKSHOT_FFMPEG` (`:441-470`, `:744`); CPU level from
  `RX_MARCH` or the host (`:494-505`). The Deck's Zen 2 supports `x86-64-v3` **[inferred]**.
- Memory gate: each compiler starts only when free memory holds it (`HOOKSHOT_MEM_GATE`, `docs/development.md`)
  which suits a 16 GB Deck **[verified]**.
- Binary names stay `hookshot` / `hookshot_vk.so` inside the build until M8: 303 tests read sources by text
  (`AGENTS.md`), and renaming buys nothing before packaging → decision recorded in `03-architecture.md`.

## 14. Launcher and builder UIs: GENERALISE, mostly unused

- `builder/HookshotBuilder` (.NET WPF) and `builder/msi`, `builder/setup`: Windows only. Not built, not
  deleted (deleting them causes merge conflicts for no gain).
- `builder/linux/hookshot_builder.py` (Tk window), `hookshot-launch`, `hookshot-folder`, `linux_update.py`:
  the launcher's update path points at upstream's GitHub releases and must be disabled for the fork
  (`HOOKSHOT_NO_UPDATE_CHECK=1` exists) → T24.
- In-game menu (`gpu/vk/vk_menu.cpp`): generic rows stay; Ocarina cheat pages are hidden by T07.

## 15. Packaging: GENERALISE

- `scripts/linux/deps.sh` + `scripts/linux/appimage.sh` build a game-free AppImage that carries the
  toolchain, the sources and a prebuilt `hookshot_vk.so`, and builds the game on the user's machine with
  `--cli` (`builder/linux/AppRun`) **[verified]**. This is the right final form for the Deck (no distrobox
  needed after M8) → T24.
- `.github/workflows/linux-appimage.yml` builds it on Ubuntu 22.04 for glibc 2.35; SteamOS is newer
  **[inferred]**. The fork's CI must not publish releases to upstream's channels: disable `release.yml`,
  `windows-builder.yml`, `vulkan-dlss.yml` in the fork → T01.
