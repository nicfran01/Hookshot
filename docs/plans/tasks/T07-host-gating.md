# T07 · Gate Ocarina-specific runtime and renderer code on the game id

**Milestone:** M2 · **Depends on:** T04, T06 (for the generated `hos_game_id`) · **Machine:** Mac

## Context
Upstream's runtime and renderer contain code that is only correct for Ocarina of Time: functions that read
and call fixed guest addresses, a shader workaround, a default program skip. On Raiders the same addresses
hold unrelated code, so reaching any of it corrupts state. Mario Kart's hooks are already gated by
`hos_game_is_mkw()` (`host/hos_main.c:73`); this task does the same for Ocarina's, through a general helper.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §3, §6; `docs/plans/03-architecture.md` §3 "Runtime side"
- `host/hos.h` lines 15-60; `host/hos_main.c` lines 60-80 and 410-800 (skim: entry points only);
  `gpu/vk/oot_cheat_items.h`; the `oot` uses in `gpu/vk/vk_menu.cpp`, `host/nn_hid.c`, `host/nn_applet.c`,
  `host/nn_vi.c`, `host/mouse_native.c`, `gpu/vk/vk_shader.cpp:870-895`, `gpu/vk/vk_draw.cpp`
  (`RX_VK_SKIP_PROG` default), `gpu/vk/vk_fsr3_inputs.cpp`
- `gpu/vk/vk_api.h` (how the host tells the renderer things); `AGENTS.md` (API version rule)

## Scope
1. `host/hos_game.h` (new): `extern const char hos_game_id[]; int hos_game_is(const char *id);` and the
   window title from `hos_game_title`.
2. Every entry point into Ocarina-only code returns early unless `hos_game_is("oot")`.
3. Renderer: the fog/exposure workaround, the default `RX_VK_SKIP_PROG`, and the cheat/teleport/inventory
   menu pages are off for other games.
4. A written inventory of every Ocarina-specific site and how it is gated.

## Non-goals
- Do not delete or move Ocarina code. Do not add Raiders features. Do not rename `HOS_OOT_*` switches.
- Do not touch `frontend/maxwell/structured_control_flow.cpp` unless its Ocarina tokens turn out to be
  behaviour keyed to that game (read it; if they are comments or generic fixes credited to an Ocarina bug,
  leave them and say so in the report).

## Interfaces
```c
/* host/hos_game.h */
int hos_game_is(const char *id);        /* strcmp with hos_game_id from gen/hos_image.c */
const char *hos_game_window_title(void);
```
Renderer side: prefer passing the game id (or three booleans: cheats available, visual workaround factors,
default skip list) through the existing host-to-renderer interface in `gpu/vk/vk_api.h`. Adding a field
bumps `MKWVK_API_VERSION`. If the renderer already receives an options block from the host
(`rx_option_set`), use that instead and avoid the version bump.

## Steps
1. Inventory: `grep -rnE "oot_|OOT_|hos_oot|HOS_OOT|Ocarina" host gpu/vk nx2/rt --include='*.c' --include='*.h'
   --include='*.cpp'` (planning counted 125 tokens in `hos_main.c`, 96 in `oot_cheat_items.h`, 25 in
   `vk_menu.cpp`). Classify each site: (a) fixed guest address or game data structure, (b) UI for (a),
   (c) tuning default, (d) comment or name only.
2. Gate (a) at the smallest set of entry points (the functions the menu actions, `HOS_OOT_CHEATS`, the live
   input `!cheat` command and per-frame callers reach). One guard per entry point; do not sprinkle guards
   through helpers.
3. Gate (b): the debug-tools rows and pages that drive (a) are not offered when the game is not Ocarina.
   - Pitfall: `vk_menu.cpp` is read by 17 tests. Add a condition where rows are listed; keep functions'
     names and signatures. Run `python -I -B tests/run_all.py vk_menu` after each edit.
4. Gate (c): `ApplyOotVisualWorkaround` (`vk_shader.cpp:879-890`) only when the game config supplies
   factors; the `RX_VK_SKIP_PROG` default only for Ocarina (`SKIP_PROGRAMS` in the game config). An explicit
   `RX_VK_SKIP_PROG` in the environment still wins for any game.
   - Pitfall: cached programs. Upstream notes that switches "did nothing for programs already cached"
     (`vk_shader.cpp:1034`). The program cache key must differ when the workaround is off, or the cache must
     be per game folder (it is beside the executable, so per game folder already: confirm).
5. `HOS_GAME_TITLE` (`host/hos.h:53`) becomes `hos_game_window_title()` at its two uses
   (`host/display.c:311`, `host/posix/display_sdl.c:236`). `tests/display_startup_failure_test.cpp` defines
   `HOS_GAME_TITLE` itself: keep the macro defined as a fallback so the test builds.
6. Tests: `tests/test_game_gates.py` reads the sources and asserts each entry point found in step 2 contains
   the guard (the same source-reading style upstream uses), so an upstream merge that adds a new Ocarina
   entry point without a guard is caught.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py test_game_gates vk_menu display debug_tools
.venv/bin/python -I -B tests/run_all.py                      # no worse than the baseline
grep -n "hos_game_is" host/*.c gpu/vk/*.cpp | wc -l          # matches the count in the report
grep -n "MKWVK_API_VERSION" gpu/vk/vk_api.h                  # bumped if and only if the interface changed
```
A compile check happens in T08 on the Deck; if T03's container is available, also run
`scripts/deck/sync.sh && scripts/deck/build.sh --vk-only` now and show that the renderer still builds.

## Report
`docs/plans/reports/T07-game-gates.md`: the inventory table (file, function, class a-d, how gated), the
interface decision for the renderer, and the list of Ocarina switches that remain visible but inert.
