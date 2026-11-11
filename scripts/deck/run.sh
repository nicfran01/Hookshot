#!/usr/bin/env bash
# (raiders) A named, time-limited run of the game on the Deck (the host, not the container: the game carries its own
# SDL2 and needs glibc 2.35 or newer). Headless and muted unless asked; no network update check.
#
#     scripts/deck/run.sh <name> [seconds=120] [--sound] [--window] [-- NAME=VALUE ...]
#
# Writes $DECK_ROOT/work/runs/<name>/: env.txt (the switches, read through HOS_ENV_FILE), hookshot_log.txt (what the
# game printed), shots/ (RX_VK_SHOTS), and game_log.txt when the game wrote its own log beside itself. Runs the
# standalone build ($DECK_ROOT/work/sa/build/hookshot) when there is one, else the game folder ~/Games/raiders.
# scripts/deck/fetch.sh <name> brings the folder back to the Mac's work/runs/<name>/ (game output: never committed).
set -euo pipefail
. "$(dirname "$0")/lib.sh"

usage() { echo "usage: scripts/deck/run.sh <name> [seconds] [--sound] [--window] [-- NAME=VALUE ...]" >&2; exit 2; }
[ $# -ge 1 ] || usage
name=$1; shift
[[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "run: a run name is letters, digits, . _ -" >&2; exit 2; }
secs=120 sound=0 window=0 env=()
if [ $# -ge 1 ] && [[ $1 =~ ^[0-9]+$ ]]; then secs=$1; shift; fi
while [ $# -gt 0 ]; do
    case $1 in
        --sound) sound=1 ;;
        --window) window=1 ;;
        --) shift; env=("$@"); break ;;
        *) usage ;;
    esac
    shift
done
for kv in ${env[@]+"${env[@]}"}; do
    [[ $kv =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]] || { echo "run: not NAME=VALUE: $kv" >&2; exit 2; }
done

need_deck
R=$(deck_root)
deck "bash -s -- $(quote "$R" "$name" "$secs" "$sound" "$window" ${env[@]+"${env[@]}"})" <<'EOS'
set -euo pipefail
R=$1 name=$2 secs=$3 sound=$4 window=$5; shift 5
if [ -x "$R/work/sa/build/hookshot" ]; then
    exe=$R/work/sa/build/hookshot
    args=("$R/work/sa/image/image.bin" --romfs "$R/dump/romfs")   # (the standalone lift's image: make_game.py ships the same)
elif [ -x "$HOME/Games/raiders/bin/hookshot" ]; then
    exe=$HOME/Games/raiders/bin/hookshot
    args=()
else
    echo "run: no game built yet on the Deck (neither $R/work/sa/build/hookshot nor ~/Games/raiders/bin/hookshot):" \
         "run scripts/deck/build.sh first" >&2
    exit 1
fi
run=$R/work/runs/$name
rm -rf "$run" && mkdir -p "$run/shots" "$HOME/.local/share/raiders-recomp"
{
    echo "# scripts/deck/run.sh $name, $(date -Is), ${secs}s"
    echo "HOOKSHOT_NO_UPDATE_CHECK=1"
    echo "RX_VK_SHOTS=$run/shots"
    [ "$window" = 1 ] || echo "HOS_HEADLESS=1"
    [ "$sound" = 1 ] || echo "HOS_AUDIO=0"
    for kv in "$@"; do echo "$kv"; done
} > "$run/env.txt"
if [ "$window" = 1 ]; then
    export DISPLAY=${DISPLAY:-:0} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
fi
marker=$run/.started && touch "$marker"
echo "run $name: $exe for ${secs}s"
set +e
(cd "$(dirname "$exe")" && HOS_ENV_FILE=$run/env.txt timeout --kill-after=15 "$secs" "$exe" ${args[@]+"${args[@]}"} \
    --user "$HOME/.local/share/raiders-recomp") > "$run/hookshot_log.txt" 2>&1 < /dev/null
code=$?
set -e
own=$(dirname "$exe")/hookshot_log.txt
[ -f "$own" ] && [ "$own" -nt "$marker" ] && cp "$own" "$run/game_log.txt"
rm -f "$marker"
case $code in
    124|137) echo "run $name: stopped at the time limit" ;;
    *) echo "run $name: exited with $code" ;;
esac
echo "run $name: $(ls "$run/shots" | wc -l) screenshots, log $run/hookshot_log.txt"
EOS
