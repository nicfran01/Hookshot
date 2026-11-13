#!/usr/bin/env bash
# (raiders) A named, time-limited run of the game on the Deck (the host, not the container: the game carries its own
# SDL2 and needs glibc 2.35 or newer). Headless and muted unless asked; no network update check.
#
#     scripts/deck/run.sh <name> [seconds=120] [--sound] [--window] [--net-check] [--rss] [--user-from <dir>]
#                         [--args "WORD ..."] [-- NAME=VALUE ...]
#
# --args: more arguments for the executable, after its own (e.g. --args --prepare-shaders): plain words split at spaces.
# Writes $DECK_ROOT/work/runs/<name>/: env.txt (the switches, read through HOS_ENV_FILE), hookshot_log.txt (what the
# game printed), shots/ (RX_VK_SHOTS), peak_rss_kb.txt (the largest resident set of the run's processes, as
# /usr/bin/time -v reports it: SteamOS has no time(1); only for a run that ends by itself: one stopped at the time
# limit is not reaped through timeout, and its figure leaves the game out), and game_log.txt when the game wrote its
# own log beside itself. Runs the
# standalone build ($DECK_ROOT/work/sa/build/hookshot) when there is one, else the game folder ~/Games/raiders.
# scripts/deck/fetch.sh <name> brings the folder back to the Mac's work/runs/<name>/ (game output: never committed).
# --net-check (T10): every 5 s while the game runs, its sockets (ss, the game process and its children) go to net.txt:
# a TCP or UDP socket with a peer that is not loopback is a FAIL line; Unix-domain sockets (Wayland, PipeWire, D-Bus,
# SDL) are listed as "unix" and are expected. The last line counts the samples and failures.
# --rss (T17): every 5 s while the game runs, the game process's VmRSS and VmHWM (/proc/<pid>/status) and the GPU's
# VRAM and GTT in use (amdgpu's mem_info_*_used: the whole GPU's, not the game's alone) go to rss.txt; the last line has
# the peaks. A time-limited run has no peak_rss_kb.txt (above), so this is the figure for one.
# --user-from <dir> (T17): the run's --user folder is a fresh copy of <dir> (an absolute path on the Deck) in
# work/runs/<name>/user, so the game's writes during the run never reach the real save folder.
# (T17) A relative file name given to RX_VK_FRAME_LOG, RX_VK_FRAMELOG or HOS_PRESENT_TRACE is made one in the run's
# folder (the game starts in the executable's folder, where fetch.sh never looks). RX_VK_FRAMELOG records only while
# <file>.go exists: run.sh makes that file, so the capture covers the whole run.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

usage() { echo "usage: scripts/deck/run.sh <name> [seconds] [--sound] [--window] [--net-check] [--rss] [--user-from <dir>] [--args \"WORD ...\"] [-- NAME=VALUE ...]" >&2; exit 2; }
[ $# -ge 1 ] || usage
name=$1; shift
[[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "run: a run name is letters, digits, . _ -" >&2; exit 2; }
secs=120 sound=0 window=0 netcheck=0 rss=0 userfrom='' extra='' env=()
if [ $# -ge 1 ] && [[ $1 =~ ^[0-9]+$ ]]; then secs=$1; shift; fi
while [ $# -gt 0 ]; do
    case $1 in
        --sound) sound=1 ;;
        --window) window=1 ;;
        --net-check) netcheck=1 ;;
        --rss) rss=1 ;;   # (raiders, T17)
        --user-from) [ $# -ge 2 ] || usage; userfrom=$2; shift ;;   # (raiders, T17)
        --args) [ $# -ge 2 ] || usage; extra=$2; shift ;;   # (raiders, T12: --prepare-shaders)
        --) shift; env=("$@"); break ;;
        *) usage ;;
    esac
    shift
done
for w in $extra; do   # (plain words only: they are split again on the Deck)
    [[ $w =~ ^[A-Za-z0-9_./=:,+-]+$ ]] || { echo "run: --args takes plain words (letters, digits, _ . / = : , + -): $w" >&2; exit 2; }
done
if [ -n "$userfrom" ] && ! [[ $userfrom =~ ^/[A-Za-z0-9_./-]+$ ]]; then
    echo "run: --user-from takes an absolute path on the Deck (letters, digits, _ . / -): $userfrom" >&2; exit 2
fi
for kv in ${env[@]+"${env[@]}"}; do
    [[ $kv =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]] || { echo "run: not NAME=VALUE: $kv" >&2; exit 2; }
done

need_deck
R=$(deck_root)
deck "bash -s -- $(quote "$R" "$name" "$secs" "$sound" "$window" "$netcheck" "$extra" "$rss" "$userfrom" ${env[@]+"${env[@]}"})" <<'EOS'
set -euo pipefail
R=$1 name=$2 secs=$3 sound=$4 window=$5 netcheck=$6 extra=$7 rss=$8 userfrom=$9; shift 9
read -r -a more <<< "$extra"
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
case "$userfrom/" in "$run/"*) echo "run: --user-from cannot be inside the run's own folder (it is emptied first)" >&2; exit 1 ;; esac
rm -rf "$run" && mkdir -p "$run/shots" "$HOME/.local/share/raiders-recomp"
user=$HOME/.local/share/raiders-recomp
if [ -n "$userfrom" ]; then   # (T17: the run's own copy of a user folder)
    [ -d "$userfrom" ] || { echo "run: --user-from: no folder $userfrom on the Deck" >&2; exit 1; }
    user=$run/user && mkdir -p "$user" && cp -a "$userfrom/." "$user/"
fi
{
    echo "# scripts/deck/run.sh $name, $(date -Is), ${secs}s"
    echo "HOOKSHOT_NO_UPDATE_CHECK=1"
    echo "RX_VK_SHOTS=$run/shots"
    [ "$window" = 1 ] || echo "HOS_HEADLESS=1"
    [ "$sound" = 1 ] || echo "HOS_AUDIO=0"
    for kv in "$@"; do
        case $kv in   # (T17: a relative output file goes in the run's folder; the frame log's .go file is made)
            RX_VK_FRAME_LOG=?*|RX_VK_FRAMELOG=?*|HOS_PRESENT_TRACE=?*)
                k=${kv%%=*} v=${kv#*=}
                [[ $v == /* ]] || v=$run/$v
                kv=$k=$v
                [ "$k" = RX_VK_FRAMELOG ] && touch "$v.go" ;;
        esac
        echo "$kv"
    done
} > "$run/env.txt"
if [ "$window" = 1 ]; then
    export DISPLAY=${DISPLAY:-:0} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
    # (raiders, T13) Desktop Mode is Plasma on Wayland: over SSH, SDL finds neither display without WAYLAND_DISPLAY
    # (Xwayland wants Plasma's auth cookie), and the game said "SDL_Init: wayland,x11 not available: no window"
    if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -S "$XDG_RUNTIME_DIR/wayland-0" ]; then export WAYLAND_DISPLAY=wayland-0; fi
fi
marker=$run/.started && touch "$marker"
echo "run $name: $exe ${more[*]+${more[*]}} for ${secs}s"
# (the peak resident set of the run: what timeout waited for, through Python's getrusage, as time -v does it)
peak=()
command -v python3 > /dev/null && peak=(python3 -I -c 'import resource, subprocess, sys
c = subprocess.call(sys.argv[2:])
open(sys.argv[1], "w").write("%d\n" % resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
sys.exit(c if c >= 0 else 128 - c)' "$run/peak_rss_kb.txt")
set +e
(cd "$(dirname "$exe")" && HOS_ENV_FILE=$run/env.txt ${peak[@]+"${peak[@]}"} timeout --kill-after=15 "$secs" "$exe" \
    ${args[@]+"${args[@]}"} --user "$user" ${more[@]+"${more[@]}"}) > "$run/hookshot_log.txt" 2>&1 < /dev/null &
game=$!
tree() { echo "$1"; local k; for k in $(pgrep -P "$1"); do tree "$k"; done; }
sampler=
if [ "$rss" = 1 ]; then   # (T17) the game's resident set and the GPU's memory every 5 s
    (
        out=$run/rss.txt start=$(date +%s) n=0 peak=0 hwm=0 pvram=0 pgtt=0
        dev=$(ls -d /sys/class/drm/card*/device 2>/dev/null | while read -r d; do [ -r "$d/mem_info_vram_used" ] && echo "$d" && break; done)
        echo "# t_s rss_kb hwm_kb vram_mb gtt_mb (GPU: ${dev:-none}, the whole GPU's)" > "$out"
        while kill -0 "$game" 2>/dev/null; do
            pid=
            for p in $(tree "$game"); do [ "$(cat /proc/$p/comm 2>/dev/null)" = hookshot ] && pid=$p && break; done
            if [ -n "$pid" ]; then
                r=$(awk '/^VmRSS:/{print $2}' /proc/$pid/status 2>/dev/null || true)
                h=$(awk '/^VmHWM:/{print $2}' /proc/$pid/status 2>/dev/null || true)
                v=0 g=0
                [ -n "$dev" ] && v=$(( $(cat "$dev/mem_info_vram_used") >> 20 )) g=$(( $(cat "$dev/mem_info_gtt_used") >> 20 ))
                if [ -n "$r" ]; then
                    echo "$(( $(date +%s) - start )) $r $h $v $g" >> "$out"
                    n=$((n + 1)); [ "$r" -gt "$peak" ] && peak=$r; [ "${h:-0}" -gt "$hwm" ] && hwm=$h
                    [ "$v" -gt "$pvram" ] && pvram=$v; [ "$g" -gt "$pgtt" ] && pgtt=$g
                fi
            fi
            sleep 5
        done
        echo "# rss: $n samples every 5 s; peak VmRSS $peak kB, VmHWM $hwm kB; GPU peak VRAM $pvram MB, GTT $pgtt MB" >> "$out"
    ) &
    sampler=$!
fi
if [ "$netcheck" = 1 ]; then   # (T10) the game's sockets every 5 s, classified by NET_AWK
    # net-check classifier BEGIN (tests/test_deck_scripts.py runs it on sample lines of `ss -tuxanpH`)
    NET_AWK='
    {
        netid = $1
        if (netid ~ /^(u_|unix)/) { print "t=" t "s unix " netid " " $2 " " $5; next }
        peer = $6; host = peer
        sub(/:[^:]*$/, "", host); gsub(/[][]/, "", host); sub(/%.*$/, "", host)
        if (host == "*" || host == "0.0.0.0" || host == "::" || host == "::1" || host ~ /^127\./ || host ~ /^::ffff:127\./)
            v = "ok"
        else
            v = "FAIL"
        print "t=" t "s " v " " netid " " $2 " " $5 " " peer
    }'
    # net-check classifier END
    net=$run/net.txt samples=0 start=$(date +%s)
    : > "$net"
    while kill -0 "$game" 2>/dev/null; do
        pids=$(tree "$game" | paste -sd'|' -)
        ss -tuxanpH 2>/dev/null | grep -E "pid=($pids)," | awk -v t=$(( $(date +%s) - start )) "$NET_AWK" >> "$net"
        samples=$((samples + 1))
        sleep 5
    done
    echo "# net-check: $samples samples every 5 s, $(grep -c ' FAIL ' "$net") failures" >> "$net"
fi
wait "$game"
code=$?
if [ -n "$sampler" ]; then wait "$sampler"; fi
set -e
own=$(dirname "$exe")/hookshot_log.txt
[ -f "$own" ] && [ "$own" -nt "$marker" ] && cp "$own" "$run/game_log.txt"
rm -f "$marker"
case $code in
    124|137) echo "run $name: stopped at the time limit" ;;
    *) echo "run $name: exited with $code" ;;
esac
echo "run $name: $(ls "$run/shots" | wc -l) screenshots, log $run/hookshot_log.txt"
if [ "$netcheck" = 1 ]; then tail -1 "$run/net.txt"; fi
if [ "$rss" = 1 ]; then tail -1 "$run/rss.txt"; fi
if [ -s "$run/peak_rss_kb.txt" ]; then
    case $code in
        124|137) echo "run $name: no peak resident set (stopped at the time limit: the game was not reaped)"; rm -f "$run/peak_rss_kb.txt" ;;
        *) echo "run $name: peak resident set $(cat "$run/peak_rss_kb.txt") kB" ;;
    esac
fi
EOS
