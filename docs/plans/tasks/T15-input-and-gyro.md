# T15 · Input: handheld pad, scripted input past the title, gyro on the Deck

**Milestone:** M5 · **Depends on:** T13 · **Machine:** Mac driving the Deck; the user at the Deck for the
gyro and feel checks

## Context
The game must be playable with the Deck's own controls, with gyro aiming (the user's choice: pad + gyro).
Hookshot reads pads through SDL, maps them to `nn::hid` Npad state and turns SDL gyro data into six-axis
state (`host/nn_hid.c:830-857`, `host/hos_motion.h`, `host/pad_sdl.c`). Unknowns: which Npad style Raiders
expects in handheld mode; whether SDL receives the Deck's gyro under Steam Input in Gaming Mode
(`docs/plans/04-steam-deck.md` §5); the 13 stubbed `nn::hid` imports (Joy-Con 2 mouse and others).

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §5; `docs/plans/02-gap-analysis.md` §9
- `readme.md` "Controls", "Motion controls", "Rumble"; `docs/development.md` "Input for scripted runs"
- `host/nn_hid.c` (Npad style set, handheld versus full key, six-axis), `host/pad_sdl.c`,
  `host/hos_motion.h`, `host/nn_applet.c` (operation mode, `handheld_profile`), `host/prompts.c`
- `docs/plans/reports/M3-trace.md` (the `nn::hid` rows)

## Scope
1. Scripted input that goes from the title into the first playable area (`HOS_INPUT_SCRIPT`), saved as
   `games/raiders/scripts/new_game.txt` (button timings only: not game data).
2. Correct Npad reporting in handheld mode.
3. `nn::hid` stubs the game calls answered properly ("no mouse", "no Joy-Con 2 mouse").
4. Gyro: plan A verified or ruled out under three launch conditions; plan B documented.
5. Deck defaults: layout preset, menu shortcut, dead zone.

## Non-goals
- Trackpads, back grips, touch screen. HD rumble. Keyboard and mouse tuning.
- A Steam Input layout file for release (T24 ships it; this task writes the notes it is made from).

## Steps
1. Find what the game asks for: from the trace, the calls `SetSupportedNpadStyleSet`,
   `SetSupportedNpadIdType`, `GetNpadStyleSet`, `SetNpadJoyHoldType`, and which `GetNpadStates` overloads it
   uses (mangled names in `work/imports_raiders.txt`: `grep 2nn3hid work/imports_raiders.txt`). Compare with
   what `nn_hid.c` reports when `HOS_HANDHELD=1`.
   - Expected for an undocked console: player 1 is the Handheld Npad (id 0x20) with the Handheld style; some
     games accept only that in handheld mode. If the runtime reports FullKey on player 1 regardless, add the
     handheld mapping behind the existing handheld switch.
2. Scripted run: build the press list by trial (`HOS_INPUT_SCRIPT="3:A,6:A,…"`, `HOS_INPUT_FRAME_CLOCK=1`
   for repeatability), checking screenshots, until the first playable area is on screen. Save it.
3. Stubs: implement the "wrong answer" `nn::hid` entries from the trace in `host/nn_offline.c` or
   `host/nn_hid.c` (generic fixes go in `nn_hid.c`, marked `(raiders)`).
4. Gyro plan A. With `HOS_MOTION_DEBUG=1` (logs the six-axis state twice a second), have the user start the
   game three ways and tilt the Deck:
   (a) Desktop Mode, from a terminal; (b) Gaming Mode, non-Steam shortcut, Steam Input on;
   (c) Gaming Mode, Steam Input disabled for the shortcut.
   Record for each whether SDL lists a sensor (`grep -n "SDL_.*Sensor\|gyro" host/pad_sdl.c` for where it is
   logged; add a one-line log of "pad <name>: gyro yes/no" at connect if there is none).
   - If no condition gives gyro: check which SDL the build uses (SDL2 by default on Linux,
     `make_game.py:53`) and whether SDL3 changes the answer (`readme.md` says SDL3 is used where present).
     Record the finding; do not vendor a new SDL in this task.
5. In game (user): gyro aims; sensitivity and inversion in the menu's Motion page behave; the game's own
   motion setting is respected.
6. Gyro plan B notes: Steam Input → gyro "as joystick" → right stick, enabled while right-pad touch or ZL is
   held; write the exact Steam UI steps in the report.
7. Defaults in `games/raiders/deck_env.txt` / options template: `layout_preset=0` (Nintendo positions),
   confirm Select+Start opens the menu and does not collide with the game.

## Acceptance criteria
```bash
scripts/deck/run.sh input1 240 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/new_game.txt)" HOS_INPUT_FRAME_CLOCK=1 \
  && scripts/deck/fetch.sh input1
ls work/runs/input1/shots | tail -2            # the last screenshots show the first playable area (describe them)
grep -n "motion" work/runs/gyro*/hookshot_log.txt | head   # six-axis values change while the Deck is tilted, in at least one launch condition,
                                                           # or the report states plan B is required and why
.venv/bin/python -I -B tests/run_all.py hid input motion
```
User check: move, look and aim on the Deck's controls; gyro (plan A) or the Steam Input fallback (plan B)
works in Gaming Mode.

## Report
`docs/plans/reports/T15-input.md`: Npad findings, the gyro matrix (three conditions × sensor seen / data
flows), the plan A or B decision, the stubs answered, defaults chosen, and the scripted-input file's purpose.
