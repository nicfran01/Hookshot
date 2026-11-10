# 01 · Research findings

Tags: **[verified]**, **[inferred]**, **[unknown]**. Paths under `refs/` are the study clones made on
2026-11-10 (after T01 the same Hookshot paths exist at the repo root). Files under `work/` are local outputs
and are gitignored; each is reproducible with the command given.

## 1. The dump

Location: `/Users/nick/Downloads/Splatoon Raiders Switch 2 NSP BASE GAME` (read in place, never modified).

| Fact | Value | Tag and source |
|---|---|---|
| Format | Already extracted: `exefs/` and `romfs/` folders. No `.nup`, NCA or NSP container. | verified: `ls` |
| Program ID | `0400380020056000` | verified: `nx2/dump.py`, `exefs/main.npdm` |
| Version | Base game. npdm version field 0; `romfs/System/RomConfig` reads `Normal` / `100` / the main build id. No update is present. | verified: `dump.py`, the RomConfig file |
| Platform | Switch 2 by all seven of Hookshot's signals (program id prefix, ACID layout, no `nvdrv`, DT_RELR, ARMv8.1+ forms, NVN2 names, `Nin_Ounce_NVN2` files) | verified: `dump.py` output |
| Process | 64-bit, 39-bit address space, main thread priority 44 on core 0, 1 MB stack, system resource 32 MB | verified: `dump.py` |
| Services | 46 declared: `acc:u0 aoc:u apm appletOE aud:u auddmg:u audsmx:u banana bcat:u bsd:u caps:su caps:u chat:u csrng ectx:aw friend:u fsp-srv hid htc htc:tenv htcs hwopus imf irs ldn:u ldr:ro lm mii:u mnpp:app nfc:mf:u nfc:user nfp:user ngc:u nifm:u nim:eca notif:a nsd:u ntc pctl pl:u prepo:u set sfdnsres ssl stpl:u time:u` | verified: `dump.py` |
| SVCs | 49 allowed (0x01-0x29, 0x2c, 0x2d, 0x32-0x36, 0x80) | verified: `dump.py` |
| Same service set as Hookshot's game | Both have 46 services and 49 SVCs (`refs/Hookshot/docs/design.md` §5). Identical names are likely, since this is the standard Switch 2 application set. | inferred (counts verified, names not compared: no reference dump) |

### Modules

| Module | Build ID | .text | .rodata | .data | .bss | Functions (unwind starts) |
|---|---|---|---|---|---|---|
| rtld | `d7a368b573ce3def3c8ef1adebe16d91dc45608f` | 10,048 | 2,512 | 49,160 | 65,528 | 42 |
| main | `abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5` | 66,394,912 | 10,045,148 | 4,459,232 | 1,082,656 | 210,187 |
| subsdk0 | `07e685d1c23a77a389fd205288ae904c34e059a0` | 541,808 | 230,440 | 73,744 | 65,520 | 1,028 |
| sdk | `41d4de4a3b78214ad20c896960df0e5ea0ed595f` | 8,897,712 | 6,019,708 | 383,904 | 1,864,800 | 35,919 |

[verified: `nx2/dump.py`]. `main` is 5% larger than Hookshot's game's `main` (63.2 MB, `docs/design.md` §9).
`main`'s NSO flags byte is `0x7f` (the others `0x3f`); a64-kit's loader read it without `nx2/unpack.py`, and the
segment hashes and the lift agree, so it is LZ4, not ZBIC. What flag bit 6 means is **[unknown]** and has had no
effect so far.

### Middleware and engine [verified: `spikes/strings_probe.py`]

- `sdk`: NintendoSdk nnSdk 21.4.4, NVN 21.4.4, libz 21.4.4.
- `subsdk0`: NintendoSDK_movie 21.4.4.
- `main`: Sead 1.0.0.0; NintendoWare G3d2, Vfx2, Ui2d, Font (all 21.4.4); SMAA for NDSR 2.3.0; Havok Physics,
  AI, Cloth, Animation 2025.1; Pia 7.2.0 (Clone, Common, Local, Lan, Session, Sync, Transport, Nplnd,
  ZStandard); NPLN 1.47.0 with gRPC, Google APIs and OpenSSL; libcurl 21.4.4.
- Namespaces in strings: `sead::`, `agl::`, `gsys::`, `phive::`, `engine::`, `spl::`. Shader names
  `Hoian_UBER`, `Hoian_ProcFluidFog`, `Hoian_ProcOcean`, `BlitzMain_S`.
- **Conclusion [inferred]:** the same Nintendo in-house engine family as Hookshot's game and Tears of the
  Kingdom (romfs layout `Pack/`, `RSDB/`, `Gyml/`, `Phive/`, `Banc/`, `Bake/`, `Mals/`; `docs/design.md` §5
  describes the same layout for its game), at the SDK generation of Mario Kart World (21.4.0), the game the
  pipeline was first written for.

### romfs [verified: `dump.py`, `ls`, spikes]

- 46,340 files, 12.69 GiB: `Tex` 9.24, `Model` 1.24, `Sound` 1.00, `UI` 0.55, `Effect` 0.31, `Layout` 0.18 GiB.
- 43,844 `.zs` files, plain zstd. **No `Pack/ZsDic.pack.zs`** (Hookshot's game and TotK have one).
- Shaders: 1,850 `Nin_Ounce_NVN2` files. `Shader/Hoian_UBER.Product.100.product.Nin_Ounce_NVN2.bfsha.zs`,
  `Shader/Sample.Nin_Ounce_NVN2.release.sarc.zs`, agl and gsys archives under `Lib/`, 363 particle sets under
  `Effect/`. Census: 22,042 unique programs from 26,960 stages (21,583 vertex+fragment, 298 compute, 160
  vertex+fragment+geometry, 1 fragment+mesh).
- Textures: 35,255 BNTX. BC4 16,793; BC1 9,493; BC5 7,494; ASTC 4x4 1,213; BC6H 166; BC7 66; BC3 16; others 14.
- Movies: 16 files in `UI/Movie/*.webm` (40 MB total), VP9 video (`V_VP9` track id found), no audio track id
  found in the one file probed. Strings name `Event/Movie/` too, but that folder is not in the base game.
- Audio: `Sound/Resource/*.bars.zs` (423), `Sound/Resource/Stream/*.bwav` (204), `alto` config; strings
  `UseOpus`, `OpusDecoder`; `hwopus` in the services.
- Languages: `System/RegionLangMask.txt` lists `JPja USen USes USfr EUen EUes EUfr EUde EUit EUnl KRko CNzh TWzh`.
- One stray file: `Effect/CoopEnemySakelienTower.Nin_Ounce_NVN2.esetb.byml.zs.part` (2,048 bytes, dated
  2025-10-25 unlike the dump's other files). The complete file sits beside it. It looks like a leftover of the
  extraction and is harmless, but the ingest check should ignore `*.part`.

### What Hookshot's tools do with the binary

| Check | Result | Tag |
|---|---|---|
| Lift discovery and coverage (`nx2/lift.py`, no `--write`) | 258,115 functions; 18,409,608 instructions; 100.0000% translated; 987 jump tables (926 bounded, 22 bounded by function, 1 ADR table); 0 `BR` without a table; 9,969 PLT stubs; 14,889 reached UDF sites (trap, as on hardware). 37 s on an Apple M2. | verified: `work/lift_coverage.log` |
| SDK imports (`nx2/imports.py`) | 1,336 sdk symbols imported by `main` and `subsdk0`; 385 have an `HLE()` in `host/`. Largest namespaces: `nn::audio` 238 (114 covered), `nn::os` 123 (118), `nn::codec` 68 (45), `nn::hid` 60 (22), `nn::movie` 51 (0), `nn::async` 42 (0), `nn::prepo` 34 (2), `nn::socket` 33 (0), `nn::fs` 28 (25), `nn::ldn` 26 (0), `nn::nfp` 23 (0), `nn::oe` 20 (19), `nn::account` 19 (10), `nn::vi` 13 (11). | verified: `work/imports_raiders.txt` |
| Standalone hook set (`nx2/standalone.py`) | 528 HLE functions, 279 OS-facing imports would get generated stubs: `nn::audio` 121, `nn::socket` 32, `nn::ldn` 26, `nn::nfp` 23, `nn::codec` 21, `nn::hid` 13, `nn::nifm` 9, `nn::swkbd` 7, `nn::friends` 6, others 21. | verified: `spikes/standalone_summary.py`, `work/standalone_stubbed.txt` |
| NVN names | 734 in `main` (66 DLSS or mesh/task); 427 implemented by name in `host/nvn_native.c`; 325 not (73 `nvnCommandBuffer*`, 57 `nvnDlss*`, 19 `nvnProgramBuilder*`, 18 `nvnMultisampleState*`, 13 `nvnDirtyTile*`, …). | verified: `work/nvn_missing.txt` |
| Which NVN procs the game actually calls | Needs a run. | unknown: task T09 |
| Standalone lift with `--write`, compile, link, boot | Not attempted in planning. | unknown: tasks T06, T08 |

## 2. Hookshot

Repository: https://github.com/NotRexed/Hookshot, commit `88b554e572636601538e341a1df2748699c8e5db`
(2026-11-10). 1,601 tracked files. Licence GPL-3.0-or-later (`LICENSE`, `readme.md` "License").

### Lineage [verified: `docs/design.md` §1-§2, `host/PROVENANCE.md`, `gpu/PROVENANCE.md`]

TOTKPort (Switch 1, NVN1) → mkw-recomp (Mario Kart World, Switch 2, SDK 21.4.0) → Hookshot (SDK 22.2.8).
Hookshot keeps mkw-recomp's paths so upstream patches apply with `git apply -3`; game-specific code goes in
new files where possible. This is exactly the relationship planned between Hookshot and this project.

### Pipeline [verified: `docs/design.md` §3, `docs/development.md`]

1. `nx2/nup.py`, `nx2/unpack.py`: `.nup` extraction and ZBIC NSO rewriting (not needed for this dump).
2. `nx2/dump.py`: characterises a dump; `--set` records its folder in `work/dump.txt`.
3. `nx2/image.py`: builds the relocated image in Eden's layout from `0x80000000` (rtld, main, subsdk*, sdk).
4. `nx2/lift.py` over `third_party/a64-kit` (`lift/a64_lift.py`, suyu's translator `a64emit`), with
   `nx2/insn.py` (ARMv8.1-8.5 forms), `nx2/lift_fixes.py` (jump tables), `nx2/poll.py` (loop-header polls),
   `nx2/chunks.py` (stable chunking), `nx2/standalone.py` (HLE set, stubs, `hos_image.c`, NVN exports).
5. `nx2/build.py --standalone`: clang `-O1`, hot functions `-O2` with a profile, lld; links `hookshot` and
   `hookshot_vk.so`. `nx2/split_hot.py`, `nx2/pgo_pieces.py`, `host/pgo_rt.c` support the hot path and PGO.
6. `nx2/make_game.py`: end-to-end (check version, lift, build, romfs hard-links, shader census, shader
   preparation, launcher). The builder UIs (`builder/`) and the AppImage (`scripts/linux/appimage.sh`,
   `builder/linux/AppRun`) run this script.
7. Runtime: `host/` (Horizon at the `nn::` boundary: `HLE(<mangled name>)` functions; everything else in the
   SDK runs as lifted code; unimplemented OS-facing imports become stubs that log their first call).
8. GPU: `host/nvn_native.c` implements NVN2 procs over guest memory and records an op stream
   (`gpu/render/rx_nvn.h`); `gpu/vk/` replays it on Vulkan 1.3. Shaders: Ampere to Maxwell
   (`gpu/vk/eden/shader_recompiler/frontend/ampere/lower_to_maxwell.h`) then Eden's recompiler to SPIR-V.

### Game-agnostic versus Ocarina-specific [verified by grep unless tagged]

| Area | Game-agnostic | Ocarina-specific (must be gated or replaced) |
|---|---|---|
| Version pin | `nx2/make_game.py` `check_modules`, `build_id` | `BUILD_ID = "e0f3ccfa"` (`make_game.py:44`), messages at `:311-314`, `:390-393`; builder strings in `builder/py/hookshot_builder/strings.py`, `builder/HookshotBuilder/Strings.cs` |
| Lift | `lift.py`, `insn.py`, `lift_fixes.py`, `poll.py`, `chunks.py`, `image.py`, `nso2.py`, a64-kit | `lift.py:162-167` installs `oot_wide`, `oot_jitter`, `oot_occlusion` on every standalone lift; `lift.py:186-188` and `chunks.py:302` use `oot_patches.LIFE_BUILD_ID`; files `nx2/oot_patches.py`, `oot_native_resolution.py`, `oot_wide.py`, `oot_jitter.py`, `oot_occlusion.py` |
| Shader census | `nx2/shader_census.py` walk of BNSH, BAHS, NDSR, particle sets | hard requirement of `Pack/ZsDic.pack.zs` (`shader_census.py:38-46`); the same file is read by `nx2/prompt_assets.py` and `gpu/vk/vk_game_font.h` |
| Runtime | `host/hos_*.c`, `nn_*.c`, `nvn_native.c`, `nvdrv.c`, `host/posix/` | `host/hos_main.c:414-800`: cheats, inventory, time, teleport at fixed guest addresses (125 `oot` tokens); `hos_game_is_mkw()` gates at `hos_thread.c:347`, `nvn_native.c:2450` (inert for other builds) |
| Renderer | `gpu/vk/*` | `gpu/vk/oot_cheat_items.h`; cheat/teleport pages in `vk_menu.cpp` (25 tokens); `gpu/vk/eden/shader_recompiler/ir_opt/oot_visual_workaround.h` applied at `vk_shader.cpp:879-890` (fog 0.25, exposure 0.65, from Orchid); `RX_VK_SKIP_PROG` default `53509044401d78d2` (`docs/development.md`); Ocarina tokens in `frontend/maxwell/structured_control_flow.cpp` |
| Performance data | `scripts/hotlist.py`, `scripts/crit.py`, `scripts/prof.py`, `nx2/pipeline_states.py` | `work/hot_funcs.txt`, `work/hot_order.txt`, `work/hookshot_pieces.prof`, `hookshot_pipelines_seed.bin`, `work/pipeline_states.bin`: made from play of its game, shipped with the builder tools, not in the repo (`readme.md` "Build from source"; `make_game.py:1305`) |
| Saves and paths | `host/nn_fs.c`, `host/hos_paths.h`, `--user` | data folder `~/.local/share/hookshot`; `scripts/oot_saves.py` (title id at `:31`) |
| Names | none | binaries `hookshot`, `hookshot_vk.so`; `HOS_GAME_TITLE "Hookshot"` (`host/hos.h:53`); env prefix `OOT_` for the work and dump folders (`nx2/kit.py`) |

### Facts that matter for the Deck [verified: file and line given]

- Mesh/task programs need `VK_EXT_mesh_shader`; a compute fallback exists for GPUs with buffer device
  addresses and leaves out mesh draws with indirect counts (`readme.md` status table).
- Deck GPU hang: `gfx_0.0.0 timeout` in a task shader shared by programs with code key `2c56dc1006942f74`;
  switches `RX_VK_MESH_NOCULL` and `RX_VK_SKIP_CODE` (`readme.md`, `docs/development.md`,
  `gpu/vk/vk_draw.cpp:5441`).
- Integrated GPUs: texture cache capped at 2,560 MB (`gpu/vk/vk_texture.cpp:3338-3344`);
  `RX_VK_TEX_MAX_DIM=1024` suggested for the Deck (`vk_texture.cpp:1702`); VRAM mirrors of guest pools are on
  for discrete cards only (`docs/development.md`, `RX_VK_MIRROR`).
- RADV: batched submits on by default (`gpu/vk/vk_replay.cpp:145-156`); host-pointer imports need
  `/dev/udmabuf` handling (`host/hos_main.c:153`); transparent huge pages changed (`hos_main.c:197`).
- gamescope is detected for SDL window ordering (`host/posix/display_sdl.c:196`); frame pacing note for the
  Deck at `vk_replay.cpp:3600`; Steam Deck button prompts (`host/prompts.c:85`).
- Guest memory default is a Switch 2 application's 9,809 MB, committed on demand (`host/hos_mem.c:50-51`,
  `HOS_MEMORY_MB`).
- Geometry and tessellation stages are not translated: the program runs without them and logs
  "dropped stages" (`gpu/vk/vk_shader.cpp:2087-2090`).
- Movies: `host/nn_video.c` implements `nn::codec` VP8/VP9 (and AV1 through dav1d for its game) on FFmpeg.
- Motion: `nn::hid` six-axis functions are implemented (`host/nn_hid.c:830-857`, `host/hos_motion.h`).

### Process rules worth adopting [verified: `AGENTS.md`, `CONTRIBUTING.md`, `docs/versioning.md`]

- `python -I` for every tool; the game-free suite is `python -I -B tests/run_all.py` (303 files in `tests/`).
- Many tests cut functions out of source files by their text: reshaping a shared function can break a test
  far away. Changing `MkwVkHost`/`MkwVkRenderer` in `gpu/vk/vk_api.h` bumps `MKWVK_API_VERSION`.
- Conventional Commits decide upstream's releases. No game in CI.

## 3. Recompia

Repository: https://github.com/Dittobyte/Recompia, commit `07f9c6e` (2026-11-10). Licence GPL-3.0-or-later
(root, `recomp/`, `runtime/`, `launcher/` each carry the GPL text).

- **Target [verified: `README.md`, `PROJECT.md` §3]:** Pokémon Pokopia (Switch 2, program
  `0400A3A01EE4C000`, v2.0.1). Native Windows x64; on Linux and the Steam Deck the game runs through Proton
  (the launcher is a native AppImage). Reported 26-53 fps on a Steam Deck.
- **Architecture [verified: `PROJECT.md` §3-§4, `recomp/README.md`]:**
  - `recomp/nxrecomp/`: Python AArch64-to-C++ lifter (`driver.py`, `lift/`), sharded translation units, CMake
    integration. Derived from smo-recomp, SuperMarioWonderRecomp, ssbu-recomp (`recomp/THIRD_PARTY.md`).
  - `runtime/` (nxrt): C++20 runtime with kernel SVCs, IPC-level services, NVN on Vulkan
    (`runtime/src/gfx/nvn/`, 97 files), play mode, overlay.
  - `tools/shaders/`: offline shader translation harness (Ryujinx's translator in .NET, plus an Ampere front
    end in `tools/shaders/ampere/`); a shader pack is built ahead of time (1-2 hours on first setup).
  - `launcher/`: Tauri 2 (Rust + JS).
- **Differences from Hookshot:**

  | | Hookshot | Recompia |
  |---|---|---|
  | Lifter output | C, one function per guest function, suyu-derived translator | C++, Capstone-driven emitters, landing-pad resume entries |
  | OS boundary | `nn::` SDK functions replaced (`HLE(mangled)`) | kernel SVC and service IPC level (`runtime/src/kernel`, `services`) |
  | Game boundary | by convention (new files, build-id gates) | enforced: `recomp/games/<id>/config.py`, `runtime/games/<id>/`, `nxrt/game.h` `game::Info` |
  | Linux | native ELF + AppImage | Windows exe under Proton |
  | Shaders | translated at run time and cached; precompile at first start | translated ahead of time into a pack |
  | Local multiplayer | none | `nn::ldn` over LAN and a relay (`runtime/src/services/ldn_*.cpp`) |

- **What to take from it (ideas, not code, unless a task says otherwise):**
  1. The per-game descriptor: `recomp/games/pkp/config.py` (`BUILDS` map of build id to version, module
     list) and `runtime/include/nxrt/game.h` (`Info`: id, title, program id, version, file names, save folder,
     romfs minimum file count and bytes). `03-architecture.md` models `games/raiders/game.py` on these.
  2. A romfs completeness check before start (`romfs_min_files`, `romfs_min_bytes`): cheap and it prevents
     unexplained crashes from a partial copy to the Deck.
  3. The Steam route on the Deck: add the launcher as a non-Steam game with `--play`
     (`README.md` "Linux, SteamOS and the Steam Deck").
  4. If local multiplayer is ever wanted: its `nn::ldn` LAN backend is the reference (GPL-3.0-or-later, so
     compatible). Out of scope here.
- Its `AGENTS.md` and `PROJECT.md` carry rules addressed to AI agents working **in that repository**. They do
  not apply to this project and were read as documentation only.

## 4. Other prior art

| Project | Relevance | Licence | Tag |
|---|---|---|---|
| Eden (https://git.eden-emu.dev/eden-emu/eden) and Eglantine | Shader recompiler vendored at `gpu/vk/eden/`; Switch 2 service behaviour reference; Hookshot's image layout is Eden's | GPL-3.0-or-later | verified: `readme.md` Credits, `docs/design.md` §2 |
| suyu | AArch64-to-C translator (`third_party/a64-kit/lift/suyu/arm64_to_c.h`), texture decoders | GPL-2.0-or-later / GPL-3.0-or-later per file | verified: `gpu/PROVENANCE.md` |
| Lichii (zortos293) | Ampere lowering reference, structured control-flow fix | see its repo | verified: `readme.md` Credits; licence unknown: check before copying anything |
| seedds/nxnative | Task/mesh shader behaviour reference | see its repo | verified credit; licence unknown |
| Mesa NAK | Ampere instruction encoding reference | MIT | inferred (Mesa's licence); verified credit |
| Orchid (MythosOfs) | Fog and exposure workaround for Hookshot's game | GPL-3.0 | verified: header of `oot_visual_workaround.h` |
| TotK Recomp (valentderah), MacNativeGames | BNSH layout and census walk | MIT | verified: `nx2/shader_census.py` docstring |
| pokopia-native (xFractals) | Recompia's parent; co-op protocol | MIT, `ampere-lower/` GPL-3.0-or-later | verified: Recompia `CREDITS.md` |

## 5. Licence findings

- **This project is GPL-3.0-or-later.** A fork of Hookshot inherits it; the lifted C and every build are GPL
  too because suyu's translator output and Eden's code are part of them (`docs/design.md` §8). That only
  matters for distribution, and builds are never distributed (they contain the game).
- Keep, unmodified: `LICENSE`, `host/PROVENANCE.md`, `gpu/PROVENANCE.md`, `third_party/*/` notices,
  `third_party/a64-kit/NOTICE.TOTKPort.md`, the Credits section of `readme.md`. Add this project's own
  credits beneath them; never remove an upstream credit.
- Third-party parts under GPL-compatible licences keep their notices in their folders: Sirit, VMA, SDL, Opus,
  Dear ImGui, zstd, Libertinus fonts, zbic, FidelityFX SDK (MIT), a64-kit.
- NVIDIA's DLSS SDK is optional upstream and irrelevant on the Deck: never fetch it.
- Trademarks: the repo and binaries are named `raiders-recomp`; documentation states it is unofficial and not
  affiliated with Nintendo.

## 6. Open research items (each is owned by a task)

| Unknown | Task |
|---|---|
| Does `tests/run_all.py` run on macOS (it targets Windows and Linux)? | T02 |
| Deck: Mesa version, `VK_EXT_mesh_shader`, free disk, distrobox availability | T03 |
| Does the standalone lift emit and compile cleanly for Raiders? | T06, T08 |
| SDK 21.4.4 behaviour where Hookshot was tuned for 22.2.8 (TLS layout at `TLR+0x110`, NVN API minor version check, `devinfo[]`) | T08, T11 |
| Which stubs and NVN procs the game calls before and after the first frame | T09 |
| How many of the 26,960 stages lower and translate; which opcodes fail | T12 |
| Whether programs with geometry stages are drawn in normal play | T13, T14 |
| Where the game reads GPU results back on the CPU (ink) and whether write-back timing is good enough | T09, T17 |
| How `nn::movie` (in `sdk`, lifted) reaches the HLE'd `nn::codec` decoders | T19 |
| Gyro through SDL under Steam Input in Gaming Mode | T15 |
| Raiders' handheld render resolution and frame-rate target | T13, T17 |
| Real memory use on the Deck | T20 |
