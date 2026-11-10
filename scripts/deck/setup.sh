#!/usr/bin/env bash
# (raiders) The Steam Deck's build environment, driven from the Mac (docs/plans/03-architecture.md section 5):
#   ~/raiders/{src,work,deps,dump}, the Distrobox container (Ubuntu 22.04, upstream CI's glibc 2.35), the apt packages
#   upstream's AppImage workflow installs, scripts/linux/deps.sh into ~/raiders/deps, and the Deck's Vulkan facts.
# Safe to run again: the source is re-synced, an existing container is kept, apt runs only when upstream's package
# list changed, and deps.sh keeps every part whose version is unchanged.
#
#     scripts/deck/setup.sh            (on the Mac)
#     setup.sh --inside                (what it runs inside the container; not for direct use)
set -euo pipefail
. "$(dirname "$0")/lib.sh"

UBUNTU_IMAGE=docker.io/library/ubuntu:22.04
DISTROBOX_VER=1.8.2.0   # (only used when SteamOS has no distrobox: its installer, at this tag, into ~/.local.
                        # The tag is unchecked until a Deck without distrobox needs it: check it on GitHub first)
DEPS_JOBS=4             # (deps.sh sets JOBS=$(nproc); GNU nproc honours OMP_NUM_THREADS, so this needs no edit there)

if [ "${1:-}" = --inside ]; then
    # ---- inside the container: $HOME is the Deck's, so ~/raiders is the same folder ----
    ROOT=$(cd "$(dirname "$0")/../.." && pwd)        # (= $DECK_ROOT/src)
    R=$(dirname "$ROOT")
    flow=$ROOT/.github/workflows/linux-appimage.yml
    # (upstream's "System packages" step, read from the workflow as tests/test_appimage_package_retry.py reads it,
    # so the container follows upstream's list without a copy of it here)
    pkgs=$(awk '
        /^      - name: System packages$/ { s = 1; next }
        s == 1 && /^        run: \|$/    { s = 2; next }
        s == 2 && length($0) && !/^          / { exit }
        s == 2 { print substr($0, 11) }' "$flow")
    [ -n "$pkgs" ] || { echo "setup: no System packages step in $flow" >&2; exit 1; }
    key=$(printf '%s' "$pkgs" | sha256sum | cut -c1-16)
    stamp=/var/lib/raiders-recomp/apt-$key
    if [ ! -f "$stamp" ]; then
        echo "---- apt: upstream's System packages step ($key)"
        printf '%s\n' "$pkgs" > "$R/work/.apt-step.sh"
        sudo env DEBIAN_FRONTEND=noninteractive bash -e "$R/work/.apt-step.sh"
        sudo mkdir -p /var/lib/raiders-recomp && sudo touch "$stamp"
    else
        echo "---- apt: up to date ($key)"
    fi
    echo "---- deps.sh into $R/deps (OMP_NUM_THREADS=$DEPS_JOBS: nproc says $(OMP_NUM_THREADS=$DEPS_JOBS nproc))"
    start=$SECONDS
    (cd "$ROOT" && DEPS=$R/deps OMP_NUM_THREADS=$DEPS_JOBS scripts/linux/deps.sh) 2>&1 | tee "$R/work/deps.log"
    echo "deps.sh: $((SECONDS - start)) s" | tee -a "$R/work/deps.log"
    "$R/deps/python/bin/python3" -I -c 'import lz4, numpy, capstone, unicorn, zstandard; print("deps python: ok")'
    exit 0
fi

# ---- on the Mac ----
need_deck
R=$(deck_root)
echo "---- the Deck: $DECK_HOST, $R"
deck "mkdir -p $(quote "$R/src" "$R/work" "$R/deps" "$R/dump") && . /etc/os-release && echo \"\$PRETTY_NAME, kernel \$(uname -r), \$(nproc) threads\""
"$(dirname "$0")/sync.sh"

if ! deck 'command -v podman >/dev/null'; then
    echo "setup: SteamOS has no podman here; the build container needs it (blocker, see T03)" >&2
    exit 1
fi
if ! deck 'command -v distrobox >/dev/null || [ -x ~/.local/bin/distrobox ]'; then
    echo "---- distrobox $DISTROBOX_VER into ~/.local (no root)"
    deck "curl -fsSL https://raw.githubusercontent.com/89luca89/distrobox/$DISTROBOX_VER/install | sh -s -- --prefix ~/.local"
fi

if deck "podman container exists $DECK_BOX"; then
    echo "---- container $DECK_BOX: exists"
else
    echo "---- container $DECK_BOX: creating from $UBUNTU_IMAGE"
    deck "distrobox create --yes --no-entry --name $DECK_BOX --image $UBUNTU_IMAGE"
fi
in_box "$R" setup.sh --inside

echo "---- Vulkan on the Deck (host driver)"
deck 'if command -v vulkaninfo >/dev/null; then
    v=$(vulkaninfo 2>/dev/null)
    printf "%s\n" "$v" | grep -m1 -E "^\s*deviceName"
    printf "%s\n" "$v" | grep -m1 -E "^\s*deviceType"
    printf "%s\n" "$v" | grep -m1 -E "^\s*driverName"
    printf "%s\n" "$v" | grep -m1 -E "^\s*driverInfo"
    printf "%s\n" "$v" | grep -m1 -E "^\s*apiVersion"
    for e in VK_EXT_mesh_shader VK_KHR_cooperative_matrix VK_EXT_image_2d_view_of_3d VK_EXT_external_memory_host; do
        if printf "%s\n" "$v" | grep -q "\b$e\b"; then echo "  $e: present"; else echo "  $e: ABSENT"; fi
    done
    printf "%s\n" "$v" | grep -E "^\s*memoryHeaps\[|^\s*size\s*=|^\s*flags\s*=" | head -12
else
    echo "  vulkaninfo: not on the host"
fi'
echo "deck environment ready"
