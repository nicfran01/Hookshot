#!/usr/bin/env bash
# (raiders) A run's folder from the Deck ($DECK_ROOT/work/runs/<name>/: log, env.txt, screenshots) to the Mac's
# work/runs/<name>/. work/ is ignored: the log and the screenshots are the game's output and are never committed.
#
#     scripts/deck/fetch.sh <name> [--no-shots]
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || { echo "usage: scripts/deck/fetch.sh <name> [--no-shots]" >&2; exit 2; }
name=$1
[[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "fetch: a run name is letters, digits, . _ -" >&2; exit 2; }
skip=()
[ "${2:-}" = --no-shots ] && skip=(--exclude shots/)
need_deck
R=$(deck_root)
deck "[ -d $(quote "$R/work/runs/$name") ]" || { echo "fetch: no run $name on the Deck" >&2; exit 1; }
mkdir -p "$REPO/work/runs/$name"
rsync -a ${skip[@]+"${skip[@]}"} -e "ssh $(quote "${SSH_OPTS[@]}")" "$DECK_HOST:$R/work/runs/$name/" "$REPO/work/runs/$name/"
echo "fetch: $REPO/work/runs/$name ($(find "$REPO/work/runs/$name" -type f | wc -l | tr -d ' ') files)"
