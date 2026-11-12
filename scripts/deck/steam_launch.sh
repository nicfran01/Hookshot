#!/usr/bin/env bash
# (raiders, T15) Runs ON the Deck, not on the Mac: the target of a Steam "non-Steam game" shortcut for a named test run
# started from Gaming Mode (or Desktop Mode), where scripts/deck/run.sh cannot start the game for you.
#
#     <shortcut target>  /home/deck/raiders/src/scripts/deck/steam_launch.sh
#     <launch options>   <name> [--raw-deck-pad] [NAME=VALUE ...]
#
# --raw-deck-pad: take the Deck's own controller (28de:1205) off SDL_GAMECONTROLLER_IGNORE_DEVICES, the list Steam sets
# for a game it starts. Steam lists it whether Steam Input is on or off for the shortcut (T15, runs gyro_b and gyro_c),
# so SDL only sees Steam's virtual pad, which has no gyroscope. With it off the list, SDL also opens the controller
# itself and its gyroscope, as in Desktop Mode; the virtual pad stays too (inferred: both then press the game's buttons).
#
# Like run.sh, it writes $DECK_ROOT/work/runs/<name>/: env.txt (the switches, read through HOS_ENV_FILE: motion logging
# and the handheld profile, then the NAME=VALUE words), hookshot_log.txt (what the game printed) and steam_env.txt (the
# variables Steam sets that decide which controllers SDL sees: whether Steam Input hides the Deck's own controller behind
# its virtual one). Windowed, with sound; no time limit (quit the game from Steam). scripts/deck/fetch.sh <name> on the
# Mac brings the folder back (game output: never committed).
set -euo pipefail
R=${DECK_ROOT:-$HOME/raiders}
name=${1:-}
[[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "steam_launch: a run name is letters, digits, . _ -" >&2; exit 2; }
shift
raw=0
if [ "${1:-}" = --raw-deck-pad ]; then raw=1; shift; fi
for kv in "$@"; do
    [[ $kv =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]] || { echo "steam_launch: not NAME=VALUE: $kv" >&2; exit 2; }
done
exe=$R/work/sa/build/hookshot
[ -x "$exe" ] || { echo "steam_launch: no standalone build at $exe (scripts/deck/build.sh)" >&2; exit 1; }
run=$R/work/runs/$name
rm -rf "$run" && mkdir -p "$run" "$HOME/.local/share/raiders-recomp"
{
    echo "# scripts/deck/steam_launch.sh $name, $(date -Is)"
    echo "HOOKSHOT_NO_UPDATE_CHECK=1"
    echo "HOS_HANDHELD=1"
    echo "HOS_MOTION_DEBUG=1"
    for kv in "$@"; do echo "$kv"; done
} > "$run/env.txt"
# (the controller-related part of Steam's environment: names only where a value could be personal; none of these are)
env | grep -E '^(SteamAppId|SteamGameId|SteamDeck|SteamOS|SDL_GAMECONTROLLER[A-Z_]*|SDL_JOYSTICK[A-Z_]*|SteamVirtualGamepadInfo|ENABLE_VK_LAYER_VALVE[A-Z_]*|XDG_CURRENT_DESKTOP|XDG_SESSION_DESKTOP)=' \
    | sort > "$run/steam_env.txt" || true
if [ "$raw" = 1 ] && [ -n "${SDL_GAMECONTROLLER_IGNORE_DEVICES:-}" ]; then
    kept=$(printf '%s' "$SDL_GAMECONTROLLER_IGNORE_DEVICES" | tr ',' '\n' | grep -vix '0x28de/0x1205' | paste -sd, - || true)
    export SDL_GAMECONTROLLER_IGNORE_DEVICES=$kept
    echo "# --raw-deck-pad: 28de:1205 taken off SDL_GAMECONTROLLER_IGNORE_DEVICES" >> "$run/env.txt"
fi
cd "$(dirname "$exe")"
HOS_ENV_FILE=$run/env.txt exec "$exe" "$R/work/sa/image/image.bin" --romfs "$R/dump/romfs" \
    --user "$HOME/.local/share/raiders-recomp" > "$run/hookshot_log.txt" 2>&1 < /dev/null
