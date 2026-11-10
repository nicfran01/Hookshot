# (raiders) Shared by scripts/deck/*.sh, which run on the Mac and drive the Steam Deck over SSH. Sourced, not run.
#
#   DECK_HOST  the Deck's SSH name            (default deck@steamdeck; deck@steamdeck.local or deck@<ip> also work)
#   DECK_ROOT  the project folder on the Deck (default ~/raiders: src/, work/, deps/, dump/, vk-work/)
#   DECK_BOX   the Distrobox build container  (default raiders-build)
#
# Nothing here copies game files: sync.sh sends only `git ls-files`, fetch.sh brings back only work/runs/<name>/.

DECK_HOST=${DECK_HOST:-deck@steamdeck}
DECK_ROOT=${DECK_ROOT:-'~/raiders'}        # (quoted: the ~ is the Deck's, expanded there)
DECK_BOX=${DECK_BOX:-raiders-build}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

case "$DECK_ROOT$DECK_BOX" in
    *[[:space:]\'\"\$\`\;\&\|\<\>\(\)\\]*) echo "deck: DECK_ROOT and DECK_BOX must be plain paths and names" >&2; exit 2 ;;
esac

# (one SSH connection reused by every call of a script: the Deck is asked for a password or key once. The socket is
# in /tmp, not $TMPDIR: macOS's per-user $TMPDIR makes the path longer than a Unix socket's 104 bytes)
SSH_OPTS=(-o ConnectTimeout=10 -o ServerAliveInterval=30 -o ControlMaster=auto
          -o "ControlPath=/tmp/raiders-deck-%C" -o ControlPersist=120)

deck() {   # run one command line on the Deck (its shell parses it), with ~/.local/bin (a home-folder distrobox) on PATH
    ssh "${SSH_OPTS[@]}" "$DECK_HOST" "PATH=\"\$HOME/.local/bin:\$PATH\"; $1"
}

quote() {   # the arguments as one line the Deck's shell reads back as the same words
    local out="" a
    for a in "$@"; do out+=$(printf '%q ' "$a"); done
    printf '%s' "$out"
}

deck_root() {   # DECK_ROOT as an absolute path on the Deck
    deck "cd && echo $DECK_ROOT"
}

in_box() {   # run one of these scripts inside the build container, from the synced source: in_box <script> <args...>
    local root=$1; shift
    deck "distrobox enter --no-tty $DECK_BOX -- bash $(quote "$root/src/scripts/deck/$1" "${@:2}")"
}

need_deck() {
    deck true 2>/dev/null || {
        echo "deck: cannot reach $DECK_HOST over SSH. On the Deck (Desktop Mode, Konsole): passwd;" \
             "sudo systemctl enable --now sshd. On the Mac: ssh-copy-id $DECK_HOST. Or set DECK_HOST." >&2
        exit 1
    }
}
