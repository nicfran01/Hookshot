# T03 · Steam Deck build environment and remote scripts

**Milestone:** M0 · **Depends on:** T01; the user has enabled SSH on the Deck and copied the dump to
`~/raiders/dump` (user actions, steps below) · **Machine:** Mac driving the Deck

## Context
The Deck compiles and runs the game (`docs/plans/04-steam-deck.md` §7). SteamOS has a read-only root and no
compiler, so the build runs in a container. This task proves the toolchain on the Deck with a game-free
target: upstream's Vulkan back end built alone (`RX_VK_ONLY=1`), which is what `scripts/linux/appimage.sh`
does first.

## Read first
- `CLAUDE.md`
- `docs/plans/04-steam-deck.md` §1, §7; `docs/plans/03-architecture.md` §4, §5
- `scripts/linux/deps.sh` (header comment and version pins), `scripts/linux/appimage.sh` (first 30 lines)
- `docs/development.md` "Building"

## Scope
1. `scripts/deck/setup.sh`, `sync.sh`, `build.sh`, `run.sh`, `fetch.sh` as specified in
   `03-architecture.md` §5.
2. A build container on the Deck with upstream's dependencies.
3. A game-free build of `hookshot_vk.so` on the Deck.
4. A record of the Deck's facts.

## Non-goals
- No lift or game build (T08). No changes to upstream's `scripts/linux/*.sh` unless a `(raiders)`-marked fix
  is required for it to run in the container (then note it as an upstream PR candidate).
- The session does not change Deck system settings; it gives the user the commands.

## User actions (give these to the user and wait)
On the Deck in Desktop Mode, in Konsole:
```bash
passwd                                  # set a password for the deck user
sudo systemctl enable --now sshd        # allow SSH
mkdir -p ~/raiders/dump                 # then copy the dump's exefs/ and romfs/ folders into it
```
On the Mac: `ssh-copy-id deck@steamdeck` (or the Deck's IP). Ask which storage has ≥ 40 GB free; if only the
SD card does, `~/raiders` and `~/Games/raiders` both go there (hard links need one filesystem).

## Interfaces
- All scripts: `DECK_HOST` (default `deck@steamdeck`), `DECK_ROOT` (default `~/raiders`),
  `DECK_BOX` (container name, default `raiders-build`). `set -euo pipefail`. No script ever copies anything
  from `work/` on the Mac to the Deck or game files in either direction.
- `build.sh` modes: `--vk-only` (this task), default = lift + build (T08), `--full` = `make_game.py`.
- `run.sh <name> [seconds=120] [--sound] [--window] [-- NAME=VALUE …]`: writes
  `$DECK_ROOT/work/runs/<name>/{env.txt,hookshot_log.txt,shots/}`; default headless and muted.

## Steps
1. Probe: `ssh $DECK_HOST 'cat /etc/os-release; uname -r; nproc; free -g; df -h ~ /run/media/* 2>/dev/null;
   command -v distrobox podman; vulkaninfo --summary 2>/dev/null | head -40'`.
   - If `vulkaninfo` is missing on the host, run it later from the container with the host's GPU passed in.
   - If Distrobox is missing: install it to the home folder with its official installer using
     `--prefix ~/.local` (no root). If Podman is missing too, stop and write a blocker report.
2. `setup.sh`: create the container (Ubuntu 22.04: matches upstream CI's glibc 2.35), install the apt
   packages upstream's workflow installs (`.github/workflows/linux-appimage.yml`, "System packages" step),
   clone nothing from the network except what `deps.sh` fetches, run `DEPS=$DECK_ROOT/deps
   scripts/linux/deps.sh`.
   - Pitfall: `deps.sh` pins SHA-256s and versions; do not edit them. It builds FFmpeg and Tk: expect a long
     first run on 4 cores. The AppImage packer is fetched too and is harmless.
   - Pitfall: `deps.sh` uses `nproc` jobs; export `JOBS=4`.
3. `sync.sh`: `git ls-files -z | rsync -a --from0 --files-from=- ./ $DECK_HOST:$DECK_ROOT/src/`, plus
   deletion of files no longer tracked.
4. `build.sh --vk-only`: in the container,
   `EMSDK=$DECK_ROOT/deps/emsdk RX_CPM=$DECK_ROOT/deps/cpm OOT_WORK=$DECK_ROOT/vk-work RX_MARCH=x86-64-v3
   RX_VK_ONLY=1 python -I nx2/build.py --standalone --jobs 4` with `deps/python/bin/python3`.
5. Record Vulkan facts: driver name and version, Mesa version, `VK_EXT_mesh_shader`,
   `VK_KHR_cooperative_matrix`, `VK_EXT_image_2d_view_of_3d`, `VK_EXT_external_memory_host`, device type,
   heap sizes.
6. `run.sh` and `fetch.sh`: implement now; test `run.sh` only as far as "no game built yet" produces a clear
   message.

## Acceptance criteria
```bash
scripts/deck/setup.sh                              # ends "deck environment ready"; re-running is quick and changes nothing
scripts/deck/sync.sh && ssh $DECK_HOST 'ls ~/raiders/src/nx2/make_game.py'
scripts/deck/build.sh --vk-only                    # ends with the path of hookshot_vk.so
ssh $DECK_HOST 'ls -la ~/raiders/vk-work/sa/build/hookshot_vk.so'
ssh $DECK_HOST 'vulkaninfo 2>/dev/null | grep -c VK_EXT_mesh_shader'   # >= 1
ssh $DECK_HOST 'ls ~/raiders/dump/exefs/main ~/raiders/dump/romfs/Pack'
bash -n scripts/deck/*.sh                          # syntax
```

## Report
`docs/plans/reports/deck-environment.md`: model, SteamOS and kernel versions, Mesa/RADV version, the
extension list above (present or absent), CPU, memory, swap, free disk per volume, where `~/raiders` lives,
container image, time `deps.sh` took, time the `--vk-only` build took, and any deviation from upstream's
scripts. If `VK_EXT_mesh_shader` is absent, say so at the top: it changes `04-steam-deck.md` §1.
