# T07 · Ocarina-specific runtime and renderer code gated on the game id (2026-11-10)

The host knows its game from `gen/hos_image.c` (`hos_game_id`, written by T06's lift) through a new
`host/hos_game.h`. Every Ocarina entry point in `host/` returns at its first statement unless the game is
Ocarina: 9 `hos_oot_*` functions and the Discord status. The host tells the renderer the game before the renderer
starts, through the existing `option_set` channel, with no API version bump. With that, the renderer hides Ocarina's
debug tools and turns off the visual workaround and the default program skip for any other game.

Every claim is **verified** (the file, line or command named) unless marked otherwise.

## Branch base

T07 depends on T06 (`hos_game_id`), which was not on `main`. By the user's choice, `task/T05-ingest-fixes` and
`task/T06-lift-gating` were merged into `main` locally (`d56d1dd`, `6728d2f`, both `--no-ff`, not pushed), and this
branch starts from `6728d2f`. After the merges: 21 checks covering both tasks passed.

## How the code was reached before, and now

The guest-address code in `host/hos_main.c` and `host/oot_menu.c` is called only from C that Ocarina's lift patches
insert: `nx2/oot_patches.py` inserts the calls to `hos_oot_is_player`, `hos_oot_lift_player`, `hos_oot_flight_*`,
`hos_oot_free_view` and `hos_oot_menu_*`. The Debug tab's actions and the live input's `!cheat` only set values that
`hos_oot_lift_player` reads (`rx_option(HOS_OPT_CHEAT_ACTION)`, `hos_oot_live_action`). Since T06, Raiders' lift
inserts none of these calls (`tests/test_lift_game_patches.py`), so on Raiders this code was already unreachable
(**verified** by the call sites: every caller of these functions is either in `nx2/oot_*.py`'s inserted text or in
these functions themselves, by `grep`). The guards are a second wall: they stay correct even if a later lift patch or
an upstream merge calls one of them from somewhere else.

## Inventory

Token search as the task gives it (`grep -rnE "oot_|OOT_|hos_oot|HOS_OOT|Ocarina" host gpu/vk nx2/rt`, `.c/.h/.cpp`):
**388 lines** after this change. **47 of them are false positives**: `root_stmt`/`root_block` (all 39 in
`frontend/maxwell/structured_control_flow.cpp`, 2 in `ssa_rewrite_pass.cpp`), `boot_ns`/`hos_boot_main_thread` (5), and
1 more in `hos_main.c`. Lines with only the contributor name "EvilOOT" (about 30 in `vk_draw.cpp` and `vk_shader.cpp`)
are comments, class (d). `nx2/rt` has none.

Classes: (a) a fixed guest address or game data structure, (b) UI for (a), (c) a tuning default, (d) a comment or name only.

| File | Site | Class | How it is gated |
|---|---|---|---|
| `host/hos_main.c` | `hos_oot_hearts_enabled` (called from `oot_patches` heart protection) | a | **guard** → 0 |
| `host/hos_main.c` | `hos_oot_is_player` (actor vtable `0x84b6c460`, resource name) | a | **guard** → 0 |
| `host/hos_main.c` | `hos_oot_flight_shortcut_ready` (called every frame by `nn_hid.c` `flight_jump_shortcut`, for any game) | a | **guard** → 0 |
| `host/hos_main.c` | `hos_oot_flight_rotation`, `hos_oot_flight_pose` (matrices written through guest pointers) | a | **guard** each |
| `host/hos_main.c` | `hos_oot_lift_player` (vtable `0x84b45e18`; the only caller of `oot_update_player_cheats`, so of the inventory, pouch, time, teleport, age and flight code: `oot_pouch_*`, `oot_inventory_*`, `oot_set_time`, `oot_teleport*`, `oot_toggle_age`, `oot_gamedata_*`, `oot_event_arg`, `oot_singleton` with `OOT_GAMEDATA_SLOT 0x84c9e180`, `OOT_EVENTMGR_SLOT 0x84c9e090`, `oot_destinations[]`) | a | **guard**: one at the entry, none in the helpers |
| `host/hos_main.c` | `hos_oot_free_view` (vtable `0x84c18a88`) and `oot_build_free_view` | a | **guard** at `hos_oot_free_view` |
| `host/hos_main.c` | `hos_oot_protect_hearts`, `HOS_OOT_PROTECT_HEARTS` read at start; `hos_oot_live_action` | c | inert: read only by guarded functions |
| `host/hos_main.c` | `occlusion_switch` (`HOOKSHOT_OCCLUSION_OFF` → `hos_occlusion_off`); `HOS_SCENE_NATIVE`, `HOS_FIX_RES` → `hos_native_scene`, `hos_fix_res` | c | inert: the variables are read only by `oot_occlusion`/`oot_native_resolution`-patched C |
| `host/oot_menu.c` | `hos_oot_menu_focus`, `hos_oot_menu_tick` (the game's menu screens' layout) | a | **guard** each (the Windows definitions; the other builds' one-line stubs do nothing) |
| `host/discord_rpc.c` | `hos_discord_start`: the status says "Ocarina of Time" with Hookshot's application id | b | **guard**: no Discord status for another game |
| `host/nn_hid.c` | `!cheat <n>` in the live input file (stores `hos_oot_live_action`); the flight shortcut's caller | b | inert: the value is read only by `hos_oot_lift_player`; `hos_oot_flight_shortcut_ready` is guarded |
| `host/nn_vi.c` | `hos_fixed_resolution`, `hos_text_scale`, `hos_res_module`, the frame-seconds bits | c | inert: read only by `oot_patches`-patched C |
| `host/nn_applet.c` | `hos_output_size`, `hos_rt_pool_size` (asked by `oot_patches` output-size edits) | c | inert: called only from patched C |
| `host/mouse_native.c` | `hos_mouse_camera` (called by `oot_patches` `patch_mouse_camera`) | a | inert: called only from patched C. Not guarded (it is not `hos_oot_*`; see Follow-ups) |
| `host/rx_backend.c` | `hos_dlss_jitter_clip` (called by `oot_jitter`-patched C); `HOS_WIDE_KEEP` (`oot_wide`) | c | inert: called only from patched C |
| `host/display.c`, `host/nn_audio.c`, `host/hos.h` | comments | d | — |
| `gpu/vk/oot_cheat_items.h` (97) | the inventory's items, sections and teleport names | b | not offered: its rows and pages show only when `cheats_on()` |
| `gpu/vk/vk_menu.cpp` (30) | Debug tab: "Debug tools" switch and its 11 tool rows (heart protection, flight, mark, return, time, inventory item, quantity, free camera, teleport, age, inventory), the Teleport and Inventory pages, `HOS_OOT_CHEATS`, `HOS_OOT_PROTECT_HEARTS` | b | `cheats_on()` is false for another game (`HOS_OOT_CHEATS=1` included), so the tool rows, pages and actions are gone; `row_shown()` hides the "Debug tools" switch too. The Developer rows of the same tab (descriptor reuse, sampler cache) stay |
| `gpu/vk/vk_menu.h` | `debug_tools`, comments | d | — |
| `gpu/vk/vk_shader.cpp` `oot_visual` | `ApplyOotVisualWorkaround`, fog 0.08 and exposure 1.0 (off unless `RX_VK_OOT_VISUAL=1`) | c | off for another game even with `RX_VK_OOT_VISUAL=1` (`vk_game_oot`) |
| `gpu/vk/vk_draw.cpp` | the default skip of program `53509044401d78d2` while its targets have no view | c | default only for Ocarina; an explicit `RX_VK_SKIP_PROG` works for any game, as before |
| `gpu/vk/vk_temporal.cpp`, `vk_fsr3_inputs.cpp/.h`, `vk_fsr4.h`, `dlss_math.h`, `vk_replay.cpp` | the temporal upscalers read the scene camera from Ocarina's uniform buffer layout (UBO 3: size at `0x120`, view-projection at `0x30`, projection at `0x70`) and its jitter | a (renderer) | **not gated here.** Reached only when the player chooses DLSS, FSR 3.1 or FSR 4 in the Upscaler row. On Raiders the layout is **unknown** → T13 (see Follow-ups) |
| `gpu/vk/vk_draw.cpp` | program keys `0x1a7482c0ec9991ea` (world drawn) and `0x02ff9920c2571cc2` (wheel drawn) for `vk_framegen.cpp`'s wide sides | c | inert: keys are hashes of a program's code, and Raiders' programs have other keys (**inferred**) |
| `gpu/vk/vk_api.h` | `keep_mask` (ultrawide menus: `oot_wide` `KEEP_VTABLES`) | c | inert: read by `oot_wide`-patched C only |
| `gpu/vk/vk_main.cpp:1055` | the "no mesh shaders" message names Ocarina of Time | d | left as is (text only; the Deck has mesh shaders, T03) |
| `gpu/vk/vk_texture.cpp`, `vk_framegen.cpp`, Eden's `spirv_emit_context.cpp`, `emit_spirv.h`, `constant_propagation_pass.cpp`, `global_memory_to_storage_buffer_pass.cpp` | comments naming the Ocarina bug a generic fix came from | d | — (generic fixes, kept) |
| Eden `ir_opt/oot_visual_workaround.h` | the workaround pass itself | c | reached only through `oot_visual`, now gated |
| Eden `frontend/maxwell/structured_control_flow.cpp` | 39 hits, all `root_stmt` | — (false positive) | **not touched**: no Ocarina tokens in it |

## Interface decision (renderer)

- **The channel:** `MkwVkRenderer.option_set(id, value)` already exists. The host calls it, and the renderer's
  `menu_option_set` already takes ids that are not saved to the options file (Link's age 4090, inventory counts 4096+).
  New id **`HOS_OPT_GAME_OOT = 4089`** (`gpu/vk/vk_api.h`). It is an enum value, not a struct field, so
  **`MKWVK_API_VERSION` stays 13**.
- **When:** `host/rx_backend.c` `load_vulkan` calls it right after the version check and before `r->start()`, so it
  comes before the renderer's start translates any program (the seed precompile), and the same holds for
  `--prepare-shaders` (`rx_prepare_shaders` goes through `load_vulkan`).
- **The renderer's copy:** `gpu/vk/vk_game.h`, `inline std::atomic<bool> vk_game_oot{true}`. It is true until the host
  says otherwise, so an unmodified host (upstream's) keeps upstream's behaviour. Each use loads it at the time of use
  rather than caching it in a `static`, so there is no race with an early translation.
- **Keyed on the id, not on the game config's fields:** `VISUAL_WORKAROUNDS` and `SKIP_PROGRAMS` (`games/<id>/game.py`)
  are set only for Ocarina and are not written into `hos_image.c`. The C side therefore asks "is the game Ocarina", which
  matches the config today. Writing the fields themselves into the generated C is a change to T06's emitter, left out of
  this task.
- **Program cache:** the workaround changes the SPIR-V. The cache key includes every `RX_VK_OOT*` variable
  (`vk_shader.cpp`, the prefix list), but not the game. It does not need to: the cache lives in the game's own folder,
  beside its executable (`gpu/vk/vk_paths.h`, lines 2-4), so two games never share one, and for any game but Ocarina the
  workaround is now never on.

## Window title

`host/hos.h`: `HOS_GAME_TITLE` is now `hos_game_window_title()` under `#ifndef HOS_GAME_TITLE`. Its two uses
(`host/display.c:459`, `host/posix/display_sdl.c:257`; the task's `:311` and `:236` have moved) are unchanged as text, so
`tests/display_startup_failure_test.cpp`, which extracts that code and defines `HOS_GAME_TITLE "authored window"`, builds
as before. Raiders' window is titled "Raiders Recomp"; Ocarina's stays "Hookshot" (`games/oot/game.py` TITLE).

## Ocarina switches that stay visible but do nothing on another game

| Switch | Where | Why it is inert |
|---|---|---|
| `HOS_OOT_PROTECT_HEARTS`, `HOS_OOT_TELEPORT_EVENT`, `HOS_OOT_TELEPORT_STARTER` | `hos_main.c` | read by guarded code only |
| `HOS_OOT_CHEATS` | `vk_menu.cpp` | `cheats_on()` is false for another game |
| `RX_VK_OOT_VISUAL`, `RX_VK_OOT_FOG`, `RX_VK_OOT_EXPOSURE` | `vk_shader.cpp` | `oot_visual` returns for another game (they still go into the program cache key) |
| `HOOKSHOT_OCCLUSION_OFF`, `HOS_SCENE_NATIVE`, `HOS_FIX_RES`, `HOS_WIDE_KEEP`, `HOS_TEXT_SPEED` | `hos_main.c`, `rx_backend.c`, `nn_vi.c` | set variables read only by Ocarina-patched lifted C |
| `!cheat <n>` (live input file) | `nn_hid.c` | stored; read only by the guarded `hos_oot_lift_player` |
| Insert menu rows wired to Ocarina's patches: Text speed, dynamic resolution and its scale, Output resolution, Ultrawide menus, Native mouse look | `vk_menu.cpp` | the values reach only Ocarina-patched C: **inert, still shown** (hiding them is not in this task) |

## Tests

- `tests/test_game_gates.py` (new, 9 checks, about 0.01 s). It finds every `hos_oot_*` definition in `host/**.c`
  (9 now) and requires the guard as its first statement; one-line bodies that are only `(void)` casts are exempt. It
  also checks the Discord guard, the helpers, the `HOS_GAME_TITLE` fallback, the host's call before the start,
  `menu_option_set`, `cheats_on`, `row_shown`, `oot_visual`, the default skip, that the explicit `RX_VK_SKIP_PROG` is
  still read, and that `MKWVK_API_VERSION` is 13.
- `tests/test_oot_menu_mouse.py`: the stand-in `hos.h` declares `hos_game_is` and the fixture defines it as Ocarina, since
  `oot_menu.c` now calls it. That test runs on Windows only (`sys.platform != "win32"` skips it), so the change is
  **not run** on the Mac.

## Acceptance criteria

| Command | Result |
|---|---|
| `run_all.py test_game_gates vk_menu display debug_tools` | 5 passed, 0 failed, 0 skipped (`test_game_gates`, `test_debug_tools_linux`, `test_display_startup_failure`, `test_display_pointer`, `test_windows_display_startup`). **Met.** `vk_menu` matches no test file name: the 25 tests that read `vk_menu.cpp` ran in the full suite and passed |
| `run_all.py` (full, with Homebrew tools as in the baseline's reference row) | 318 passed, 9 failed, 9 skipped, 823 s (336 checks; the baseline's reference row is 312 / 9 / 9 of 330). The 6 new checks are T04's to T07's tests, all passing. The 9 failures are exactly the baseline's 9 (the two ASan hangs, `test_mem_gate`, `test_mem_gate_children`, `test_low_memory_notice`, `test_prof_symbols` and the three temp-symlink ones). `test_oot_menu_mouse` reports pass because its unittest skips off Windows. **Met: no worse than the baseline** |
| `grep -n "hos_game_is" host/*.c gpu/vk/*.cpp \| wc -l` | **15**: 10 guards (`hos_main.c` 7, `oot_menu.c` 2, `discord_rpc.c` 1), the definition (`hos_main.c:75`), the call to the renderer (`rx_backend.c:264`), and 3 lines of upstream's `hos_game_is_mkw` (`hos_main.c:73`, `hos_thread.c:386`, `nvn_native.c:2450`), which the pattern also matches |
| `grep -n "MKWVK_API_VERSION" gpu/vk/vk_api.h` | `18:#define MKWVK_API_VERSION 13`: not bumped, because no field was added |
| `scripts/deck/sync.sh && scripts/deck/build.sh --vk-only` (optional) | `DECK_HOST=deck@steamdeck.local` (the default name does not resolve, as T03 found). The first run failed because `sync.sh` sends only `git ls-files`, and `vk_game.h` was not yet staged (`fatal error: 'vk_game.h' file not found` in `vk_draw.cpp`, `vk_menu.cpp` and `vk_shader.cpp`). With the new files staged: `linked /home/deck/raiders/vk-work/sa/build/hookshot_vk.so: 10 MB`, 30.5 s, exit 0. **The renderer builds.** `--vk-only` does not compile `host/`, so in the `raiders-build` container `clang -fsyntax-only -D_GNU_SOURCE -Ihost/posix -Ihost -Ithird_party/a64-kit/rt -Inx2/rt -Wno-everything` was run on `hos_main.c`, `rx_backend.c`, `oot_menu.c` and `discord_rpc.c`: 0 errors each. The full host compile and link is T08 |

## Follow-ups (not done here)

- **The temporal upscalers' camera** (`vk_temporal.cpp`, `vk_fsr3_inputs.cpp`) assumes Ocarina's uniform buffer 3 layout.
  On Raiders, DLSS, FSR 3.1 or FSR 4 would read whatever that buffer holds (**unknown**). T13, which decides the upscaler
  for the Deck, should either find Raiders' camera or keep these choices off for another game.
- `hos_mouse_camera` (`mouse_native.c`) writes through a guest camera pointer but is not named `hos_oot_*`, so the
  test's discovery does not cover it. Today only Ocarina-patched C calls it.
