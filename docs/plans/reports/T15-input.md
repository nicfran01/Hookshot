# T15 · Input: handheld pad, scripted input, gyro on the Deck (2026-11-12)

**Short answer.**
- **Npad:** the game supports Handheld, but it plays fine with the runtime's one FullKey controller on No.1, which is a
  real console setup (undocked, with a Pro Controller). That reporting is kept, and no Handheld mapping was added.
- **Scripted input:** `games/raiders/scripts/new_game.txt` goes from the title into the hub, where you have control.
  It works from a save made after the prologue.
- **Stubs:** the three `nn::hid` stubs the game calls, and the rest of their family, now give explicit answers: no
  Joy-Con 2 mouse, and the zero-drift mode is remembered.
- **Gyro:** plan A works in Desktop Mode. SDL3 sees the Deck's gyroscope, the data follows the Deck's tilt, and you
  aimed with it.
  - **Gaming Mode:** plan A does not work. Steam keeps the Deck's own controller behind its virtual pad, which has no
    gyroscope, whether Steam Input is on or off. Taking the controller off Steam's list opens the gyroscope, but its
    readings freeze after about 2 s.
  - **Plan B works there,** by your check: Steam Input's gyro on the right stick, while the right trackpad is touched.
- **The docked profile draws the hub's 3D in magenta.** That is a rendering problem, recorded for T17. The
  acceptance run is docked, so that criterion is only partly met (below).

Claims are **verified** (command, file:line or log line named) unless marked **inferred** or **unknown**. Runs are in
`work/runs/<name>/` on the Mac and `~/raiders/work/runs/` on the Deck. Logs and screenshots are game output and are
not committed.

## Branch and build

- `task/T15-input-and-gyro` was made from `main` at `2df50e1`, which now includes all of T13.
- The Deck build gives `build (lift): 189 s`, exit 0.
- Your title save (`d9dfb4bb…`, 5,554 B) is kept in `~/raiders/work/t15_save_title/`. It was put back after every run.

## 1. Npad: what the game asks for (run `inp_a`, verified)

New `(raiders, T15)` log lines in `host/nn_hid.c` (`npad_seen`) print each set-up call and each value once.

| Call | Value(s) | lr |
|---|---|---|
| `SetSupportedNpadIdType` | 9 ids: 0-7 and `0x20` | `0x831cf594` |
| `SetSupportedNpadStyleSet` | `0x1f` (FullKey, Handheld, JoyDual, JoyLeft, JoyRight) | `0x831cf66c` |
| `SetSupportedNpadIdType` | 5 ids (all among the 9 above, so not printed again) | `0x83dc2ddc` |
| `SetSupportedNpadStyleSet` | `0x7` (FullKey, Handheld, JoyDual) | `0x83dc41d8` |
| `SetNpadJoyHoldType` | 1 | `0x83dc41fc` |
| `GetNpadStyleSet` | every id: 0-7 and `0x20` | `0x831cfa48` |
| `GetNpadStates` | **FullKey only, npad 0 only** | `0x831cfab4` |

**What the runtime reports:**
- FullKey on No.1 and nothing on any other id (`nn_hid.c`: `GetNpadStyleSet`), in both profiles. `HOS_HANDHELD`
  changes only the operation and performance mode (`nn_applet.c:193-194`).

**What that means:**
- The game polls every id, `0x20` included, and reads whichever one has a style.
- FullKey is in both sets it supports, so a Pro Controller-style pad on No.1 is accepted in handheld mode (verified: it
  plays). A real undocked Switch 2 with a Pro Controller looks the same.
- On a console with the Joy-Cons attached, the game would instead read `GetNpadStates(Handheld)` on `0x20`
  (**inferred**).

**Decision: keep FullKey on No.1; no Handheld mapping.** This departs from step 1's "add the handheld mapping". That step assumed the game might accept only Handheld when undocked, and this game does not.
- **Reasons:**
  - nothing is wrong to fix: menus, the title, walking and aiming all work;
  - a Handheld mapping would change upstream's npad-0 logic in `npad_states`, which `tests/test_input_background.py`
    cuts out by text, along with the six-axis and vibration handles and `ShowControllerSupport`.
- **What could differ (unknown):** whether the game shows anything differently for a Handheld-style controller,
  button icons for example.

## 2. Scripted input (`games/raiders/scripts/new_game.txt`)

`30:ZL+ZR/500,40:ZL+ZR/500,100:LUP/2000,104:RRIGHT/300,110:LDOWN/1500`. Times are on the frame clock
(`HOS_INPUT_FRAME_CLOCK=1`).

- **What it is for:** a repeatable run from the title into the first area where you have control. The title's
  ZL+ZR is pressed twice, for margin. Then a walk forward, a camera turn and a walk back show the input reaching play.
  It holds button timings only, no game data.
- **What it needs:** a save from after the prologue. Only such a save shows the title (`M4-first-frame.md`, session
  5). A fresh save goes to "Select a difficulty" instead, and this script does not cover that path.
- **Where it lands:** the hub, the platform from the title's backdrop. Control is free there, with the reticle, the
  health bar, the counter, and the "Reset Camera" and "Gear" prompts.

| Run | Profile | Result |
|---|---|---|
| `inp_a` | handheld, ZL+ZR only | Title at present 1500; hub with control at present 3000 |
| `input1` | **the acceptance command as written** (docked) | Hub HUD on screen from present 2100 to the end (5400), but **the 3D is drawn in magenta** (below) |
| `input1h` | the same script, `HOS_HANDHELD=1`, a shot every 150 presents | The hub at 5700. By 7350 the camera has moved behind the nets: **the walk and the turn reached the game** |

None of the three logged a device loss, a validation error or "dropped stages".

**The magenta scene (for T17, verified; cause unknown):**
- **When:** in `input1` (docked, game output 2048x1152), the 3D is magenta from present 2100, when the hub appears.
  Over 87-96 % of sampled pixels are magenta from then on. The HUD draws normally.
- **Handheld is fine:** `inp_a` and `input1h` (handheld) render it correctly.
- **The one log difference:** `vk: in play: compute 20ce8fa19e5349c2`, a compute program translated in play only in
  the docked run. It is a lead, not a cause.
- **Earlier docked runs:** T13's only docked run (`open_dk`) stopped at the opening, so the hub had not been seen
  docked before.

## 3. `nn::hid` stubs answered (`host/nn_hid.c`, `(raiders, T15)`)

**Which stubs the game calls (verified):** "unimplemented import" lines across all 41 earlier runs, and `M3-trace.md`.
- Only three of the 13 stubbed `nn::hid` imports were ever called: `InitializeJcms`, `GetGyroscopeZeroDriftMode` and
  `SetGyroscopeZeroDriftMode`.
- All three were classed "safe". There was no "wrong answer" `nn::hid` row to fix.
- So this is about explicit answers, not a fix.

| Function | Answer |
|---|---|
| `GetGyroscopeZeroDriftMode` / `SetGyroscopeZeroDriftMode` | Remembered per six-axis handle; Standard (1) until set (the enum order and the default are **inferred** from libnx and yuzu, not read in the SDK); a value past Tight (2) is ignored. The host learns drift itself (`hos_motion.h`), so the mode only reads back |
| `InitializeJcms`, `FinalizeJcms`, `StartJcms`, `StopJcms` | Nothing done (no Joy-Con 2 attached) |
| `GetJcmsHandle`, `GetJcmsStates` | 0: no handle state, no states |
| `GetNmouseHandles`, `GetNmouseTypeSet`, `FinalizeNmouse` | No mouse; type set 0. Imported but never called so far |

- **Where the meanings come from:** `refs/Recompia/runtime/docs/hid_mouse_sw2.md` (GPL-3.0). Its notes on the
  Jcms/Nmouse calls were read; no code was copied.
- **What is left alone:** `GetMouseStates` and `GetKeyboardState`, the plain USB mouse and keyboard. They are
  imported, never called, and their family is upstream's.
- **The test:** `tests/test_hid_npad_setup.py` compiles these functions, cut from `nn_hid.c`, with a fake context. It
  covers each set-up value being logged once, a full table staying quiet, FullKey on No.1 only, the zero-drift
  round trip, and the "none" answers.

## 4. Gyro: plan A, three launch conditions

`HOS_MOTION_DEBUG=1` logs the six-axis state the game gets twice a second (`host/pad_sdl.c:254`). `pad_sdl.c:319`
already logs whether a connected pad has a gyroscope, so no new connect line was needed.

| Condition | Run | SDL | Sensor seen | Data flows when tilted | Aims in game (your check) |
|---|---|---|---|---|---|
| (a) Desktop Mode, started outside Steam (over SSH, windowed) | `gyro_a` | SDL3 (`sdl: SDL3`) | **yes**: `"Steam Deck Controller" connected (SDL), with a gyroscope` | **yes**: 344 motion lines; acceleration followed the tilt, and the gyro peaked at 0.50, 0.67 and 0.13 turns/s on its three axes, 0 while held still | **yes** |
| (b) Gaming Mode, non-Steam shortcut, Steam Input on | `gyro_b` | SDL3 | **no**: `"Steam Deck Controller" connected (SDL)`, with no gyroscope | **no**: 0 motion lines | **no** |
| (c) Gaming Mode, Steam Input disabled for the shortcut | `gyro_c` | SDL3 | **no**: the same line as (b) | **no**: 0 motion lines | **no** |

**Which SDL (verified):**
- The game loads the system's SDL3 (`/usr/lib/libSDL3.so.0.4.12`) before the SDL2 beside the executable.
- So the task's "SDL2 by default on Linux" does not hold on the Deck. `scripts/deck/run.sh`'s comment ("carries its
  own SDL2") describes the fallback.

**The Gaming Mode launcher:** `scripts/deck/steam_launch.sh` is new. It runs on the Deck and is the target of a
non-Steam shortcut.
- It starts the same build and image as `run.sh`, with `HOS_MOTION_DEBUG=1` and `HOS_HANDHELD=1`.
- It writes `work/runs/<name>/`, which `fetch.sh` brings back. `steam_env.txt` records the controller variables Steam
  sets.
- It is tested in `tests/test_deck_scripts.py`.

**Why Gaming Mode gives no gyro (verified from `steam_env.txt` in `gyro_b` and `gyro_c`):**
- **Steam hides the Deck's own controller.** It starts the game with `SDL_GAMECONTROLLER_IGNORE_DEVICES` and
  `SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=1`. The ignore list holds the Deck's own controller,
  `0x28de/0x1205`.
- **SDL sees only Steam's virtual pad instead.** `SteamVirtualGamepadInfo` names that pad "Steam Deck Controller"
  (VID `0x28de`, PID `0x1205`, type `steam`). It carries buttons and sticks, not sensors.
- **"Disable Steam Input" does not change that.** In (c) the setting took effect: the ignore list is shorter (external
  pads are no longer hidden), and `SDL_GAMECONTROLLER_USE_BUTTON_LABELS` is gone. But `0x28de/0x1205` is still on the
  list. On the Deck, Gaming Mode keeps the built-in controls behind Steam Input whatever the shortcut says.

**Extra condition (d): `steam_launch.sh --raw-deck-pad`** (Gaming Mode, Steam Input on, run `gyro_d`). The launcher
takes `0x28de/0x1205` off Steam's list, leaving the rest.
- **The real controller opens** (verified): SDL opens two pads, the controller itself (`connected (SDL), with a
  gyroscope`) and Steam's virtual pad. Motion is taken from the real one.
- **No doubled buttons** (your check): a press did one thing, and Select+Start opened the menu.
- **But the readings freeze after about 2 s** (verified). 5 motion lines at the start follow the Deck's angle, then no
  new reading until the very end of the run, when a few more come. The runtime skips a repeated reading
  (`hos_motion_update`), so the log stays silent. You saw no aiming.
- **Inferred cause:** in Gaming Mode, Steam keeps the gyroscope powered only while its own layout for the game uses it.
  The readings at the end fit Steam's menu being opened to quit. Desktop Mode does not do this, which is why (a)
  works.
- **Not tried:** whether `--raw-deck-pad` plus a Steam layout that uses the gyro keeps the readings flowing. That is
  **unknown**, and left to T24 as a lead. The switch stays in the launcher, opt-in, for that test.

**Plan B check (run `gyro_e`):** Gaming Mode, Steam Input on, the layout below.
- The game sees only Steam's virtual pad and gets no six-axis motion (verified: 0 motion lines). Steam turns the tilt
  into right-stick movement.
- By your check, every step below worked and the camera follows the tilt while the right trackpad is touched.
- No device loss and no validation errors.

**Decision:** **plan A where the game sees the Deck's controller itself, plan B in Gaming Mode.**
- **Desktop Mode, or any launch outside Steam:** the game's own motion aiming (six-axis, Eden-style). It is the more
  faithful one, with sensitivity and inversion in the menu's Motion page.
- **Gaming Mode:** Steam Input's gyro on the right stick (§5). It works now and needs no code.
- **The Gaming Mode lead (d)** may later let plan A work there too. T24 tries it before shipping the layout file.

## 5. Plan B: gyro as a joystick through Steam Input (no code)

These are the exact Steam UI steps, for T24's layout file and for anyone whose launch gives no gyro. You confirmed every step works (`gyro_e`). The labels are as written here: you reported "all
of the steps worked" without other wording, so a menu name that differs in a later Steam client is **unknown**.

1. Gaming Mode: start the game from its non-Steam shortcut, with Steam Input on (the shortcut's default).
2. Press the Steam button, then **Controller Settings → Edit Layout → Gyro**.
3. Gyro behaviour: **as joystick** ("joystick camera"), output to the **right joystick**.
4. Gyro enable button: **right trackpad touch**.
   - Not ZL: in this game ZL is the squid form, so holding it to aim would turn you into a squid.
5. Back out, rest your thumb on the right trackpad and tilt: the camera follows.

**Notes for T24's layout file:**
- With plan B the game's own Motion controls row can stay on. The game then sees a pad lying still (no sensor), so the
  two do not add up.
- The trackpad-touch activation is the one this check used. "Always on" was not tried.

## 6. Deck defaults

- **Layout preset: Nintendo (0).** It is already the code default (`gpu/vk/vk_menu.h:51`, `pad_layout = 0`), so no
  file sets it.
  - The Deck's A is on the right face button, where the Switch's is.
  - "Xbox / PC" stays one menu change away.
- **Menu shortcut: Select+Start** (`nn_hid.c`: the Back+Start chord).
  - With both held, neither reaches the game. Held alone, each still reaches it as Minus or Plus.
  - Your check: it opens the menu and did not set anything off in the game (in `gyro_d`, with two pads open, too).
- **Stick dead zone: the default** (Insert menu "Stick dead zone" 0, XInput's 7849, about 24 %). Your check in Gaming Mode found no problem with movement and looking. Moving and turning worked in every run. No other zone was tried.
- **`games/raiders/deck_env.txt`: not created.**
  - The input needs no environment switch: layout, dead zone and motion are menu options with working defaults.
  - The file's first draft stays with T20 (`04-steam-deck.md` §8). `HOS_HANDHELD=1` belongs in it: the hub renders
    correctly only in that profile so far (§2).

## Acceptance criteria

| Command | Result |
|---|---|
| `scripts/deck/run.sh input1 240 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/new_game.txt)" HOS_INPUT_FRAME_CLOCK=1 && scripts/deck/fetch.sh input1` | `stopped at the time limit`, `18 screenshots`; fetched 20 files |
| `ls work/runs/input1/shots \| tail -2` | `vk_005100.png`, `vk_005400.png`: both show the hub with its HUD (counter, health bar, "Reset Camera" and "Gear" prompts, the "!" marker over the robot), but **the 3D is magenta** (§2). **Partly met:** the first playable area is reached, but it is not drawn correctly in the docked profile the command runs. The same script in the handheld profile (`input1h`) shows it correctly, with the walk and turn |
| `grep -n "motion" work/runs/gyro*/hookshot_log.txt \| head` | `gyro_a`: `motion controls from "Steam Deck Controller"`, then readings that follow the tilt (345 "motion" lines). **Met** for condition (a). Gaming Mode needs plan B, for the reasons in §4 |
| `.venv/bin/python -I -B tests/run_all.py hid input motion` | `4 passed, 0 failed, 0 skipped`: `test_input_background`, `test_motion`, `test_hid_npad_setup` (new), `test_shader_stamp_inputs` |
| User check: move, look and aim on the Deck's controls; gyro or the fallback works in Gaming Mode | **Met.** Plan A aims in Desktop Mode (`gyro_a`); plan B aims in Gaming Mode (`gyro_e`); buttons, sticks and Select+Start behave (`gyro_d`) |

**Also run:**
- `tests/test_deck_scripts.py`: 9 tests, OK. It includes the new `steam_launch.sh` test, with `--raw-deck-pad`.
- No run here had a device loss, a validation error or "dropped stages".

**Saves:**
- Your title save `d9dfb4bb…` was put back after every run.
- The game's own writes from the Gaming Mode runs are kept in `~/raiders/work/t15_save_after_gyro_{b,c,d}/`. `gyro_e`'s copy is made, and your save put back, once
  that game is closed.

## Upstream PR candidates

- **The zero-drift round trip and the Jcms/Nmouse "none" answers.** They are generic for Switch 2 SDK games. The
  `(raiders)` marks would come off for upstream.
- **The npad set-up log (`npad_seen`).** A small diagnostic that any game benefits from.
