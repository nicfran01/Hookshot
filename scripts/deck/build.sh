#!/usr/bin/env bash
# (raiders) Build on the Deck, in the container, from the synced source (it syncs first; --no-sync skips that).
#
#     scripts/deck/build.sh --vk-only   the Vulkan back end alone, no game (T03): $DECK_ROOT/vk-work/sa/build/hookshot_vk.so
#     scripts/deck/build.sh             lift + build from $DECK_ROOT/dump (T08): $DECK_ROOT/work/sa/build/hookshot
#     scripts/deck/build.sh --full      make_game.py: the game folder ~/Games/raiders
#
# The log is tee'd to build.log in the work folder. The last line printed is the path of what was built.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

JOBS=${HOOKSHOT_JOBS:-4}   # (16 GB shared with the GPU: 04-steam-deck.md section 7; the memory gate stays on)

if [ "${1:-}" = --inside ]; then
    mode=$2
    ROOT=$(cd "$(dirname "$0")/../.." && pwd)
    R=$(dirname "$ROOT")
    D=$R/deps
    PY=$D/python/bin/python3
    # (the toolchain and libraries deps.sh made, named as the AppImage's AppRun names them; no sysroot: the container
    # is Ubuntu 22.04 itself, the glibc the game is built for)
    export EMSDK=$D/emsdk RX_CPM=$D/cpm HOOKSHOT_FFMPEG=$D/ffmpeg HOOKSHOT_SDL2=$D/sdl2/libSDL2-2.0.so.0
    export RX_MARCH=x86-64-v3 HOOKSHOT_JOBS=$JOBS
    cd "$ROOT"
    start=$SECONDS
    case $mode in
        vk-only)
            export OOT_WORK=$R/vk-work
            mkdir -p "$OOT_WORK"
            RX_VK_ONLY=1 "$PY" -I nx2/build.py --standalone --jobs "$JOBS" 2>&1 | tee "$OOT_WORK/build.log"
            out=$OOT_WORK/sa/build/hookshot_vk.so ;;
        lift)
            export OOT_WORK=$R/work OOT_DUMP=$R/dump HOOKSHOT_KEEP_BUILD_FILES=1
            # (work/image too, as make_game.py makes it before its lift: the standalone lift saves its chunk boundaries there,
            # nx2/chunks.py save, and stopped with FileNotFoundError in a new work folder)
            mkdir -p "$OOT_WORK/image"
            # (each step under /usr/bin/time -v: its wall time and peak memory at the end of its output, for the M2 report;
            # set -o pipefail: a failed step stops the build, and the tee'd log keeps what it said)
            timed() { /usr/bin/time -v "$@"; }
            {
                timed "$PY" -I nx2/make_game.py --check --exefs "$OOT_DUMP/exefs" &&
                timed "$PY" -I -u nx2/lift.py --standalone --write &&
                timed "$PY" -I nx2/build.py --standalone --jobs "$JOBS"
            } 2>&1 | tee "$OOT_WORK/build.log"
            out=$OOT_WORK/sa/build/hookshot ;;
        full)
            export OOT_WORK=$R/work OOT_DUMP=$R/dump HOOKSHOT_KEEP_BUILD_FILES=1
            "$PY" -I nx2/make_game.py --romfs "$OOT_DUMP/romfs" --exefs "$OOT_DUMP/exefs" --out "$HOME/Games/raiders" \
                --language en-US 2>&1 | tee "$OOT_WORK/build.log"
            out=$HOME/Games/raiders/bin/hookshot ;;
        *) echo "build: unknown mode $mode" >&2; exit 2 ;;
    esac
    echo "build ($mode): $((SECONDS - start)) s" | tee -a "$OOT_WORK/build.log"
    [ -f "$out" ] || { echo "build: $out was not built" >&2; exit 1; }
    echo "$out"
    exit 0
fi

mode=lift sync=1
for a in "$@"; do
    case $a in
        --vk-only) mode=vk-only ;;
        --full) mode=full ;;
        --no-sync) sync=0 ;;
        *) echo "usage: scripts/deck/build.sh [--vk-only | --full] [--no-sync]" >&2; exit 2 ;;
    esac
done
need_deck
R=$(deck_root)
[ "$sync" = 1 ] && "$(dirname "$0")/sync.sh"
deck "[ -x $(quote "$R/deps/python/bin/python3") ]" || { echo "build: no deps on the Deck: run scripts/deck/setup.sh" >&2; exit 1; }
if [ "$mode" != vk-only ]; then
    deck "[ -d $(quote "$R/dump/exefs") ] && [ -d $(quote "$R/dump/romfs") ]" ||
        { echo "build: no dump at $R/dump/{exefs,romfs} on the Deck (the user copies it there)" >&2; exit 1; }
fi
in_box "$R" build.sh --inside "$mode"
