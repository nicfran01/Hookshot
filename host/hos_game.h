/* (raiders) The game this build is: its id, title and data folder from games/<id>/game.py, written into gen/hos_image.c by
   the lift (nx2/standalone.py write_image_c). Code that only fits one game (Ocarina's fixed guest addresses, its menus'
   layouts) returns at its entry point unless hos_game_is("oot"), as hos_game_is_mkw() keeps Mario Kart World's hooks.
   Defined in host/hos_main.c. */
#pragma once

extern const char hos_game_id[];        /* "oot", "raiders" */
extern const char hos_game_title[];     /* the window's title */
extern const char hos_game_data_dir[];  /* the saves' folder name (~/.local/share/<it>) */

int hos_game_is(const char *id);        /* 1 when this build's game is id */
const char *hos_game_window_title(void);   /* hos_game_title, "Hookshot" when it is empty */
