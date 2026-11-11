// (raiders) Whether the game is Ocarina of Time, as the host said before the renderer started (option_set HOS_OPT_GAME_OOT,
// host/rx_backend.c; vk_menu.cpp menu_option_set keeps it here). Ocarina's own parts of the renderer ask it: the Debug tab's
// tools (vk_menu.cpp cheats_on, row_shown), the visual workaround (vk_shader.cpp oot_visual) and the default program skip
// (vk_draw.cpp). 1 until told: upstream's game, as before the host could say.
#pragma once

#include <atomic>

inline std::atomic<bool> vk_game_oot{true};
