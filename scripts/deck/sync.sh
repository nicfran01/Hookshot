#!/usr/bin/env bash
# (raiders) The tracked source tree (git ls-files: the working copy of each tracked file, edits included) to the Deck's
# $DECK_ROOT/src. A file an earlier sync sent that is no longer tracked is deleted there; anything else in src/ (what
# a build writes beside the source, like third_party/a64-kit/lift/liba64emit.so) is left alone. Only tracked files
# are sent, so nothing from work/ and no game file ever leaves the Mac.
#
#     scripts/deck/sync.sh
set -euo pipefail
. "$(dirname "$0")/lib.sh"
need_deck
R=$(deck_root)
cd "$REPO"

tmp=$(mktemp -d "${TMPDIR:-/tmp}/raiders-sync.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
git ls-files -z > "$tmp/now"
# (refuse a list that names anything outside the tree, or the ignored folders: neither can come from git ls-files,
# but this is the one place a mistake would copy game data)
python3 -I - "$tmp/now" <<'PY'
import sys
bad = [p for p in open(sys.argv[1], "rb").read().decode("utf-8").split("\0") if p and
       (p.startswith("/") or ".." in p.split("/") or p.split("/")[0] in ("work", "refs", ".venv", "build-linux"))]
if bad:
    sys.exit("sync: refusing to send %s" % bad[:5])
PY

deck "mkdir -p $(quote "$R/src")"
rsync -a --from0 --files-from="$tmp/now" -e "ssh $(quote "${SSH_OPTS[@]}")" ./ "$DECK_HOST:$R/src/"

# ---- deletions: in the last sync's list, not in this one ----
deck "cat $(quote "$R/src/.raiders-sync-files") 2>/dev/null || true" > "$tmp/before"
python3 -I - "$tmp/before" "$tmp/now" "$tmp/gone" <<'PY'
import sys
read = lambda p: {x for x in open(p, "rb").read().split(b"\0") if x}
gone = sorted(read(sys.argv[1]) - read(sys.argv[2]))
open(sys.argv[3], "wb").write(b"".join(g + b"\0" for g in gone))
print("sync: %d files, %d no longer tracked" % (len(read(sys.argv[2])), len(gone)))
PY
if [ -s "$tmp/gone" ]; then
    deck "cd $(quote "$R/src") && xargs -0 rm -f --" < "$tmp/gone"
fi
cmp -s "$tmp/before" "$tmp/now" || deck "cat > $(quote "$R/src/.raiders-sync-files")" < "$tmp/now"
echo "sync: $DECK_HOST:$R/src"
