# Steam Deck build environment (T03, 2026-11-10)

**`VK_EXT_mesh_shader` is present** on this Deck's driver, so `04-steam-deck.md` §1 stands as planned.

Everything below is **verified** on the user's Deck from the Mac over SSH (`DECK_HOST=deck@steamdeck.local`), by the
command named or by `scripts/deck/setup.sh`'s output, unless it says otherwise.

## The Deck

| | |
|---|---|
| Model | `Jupiter` (`/sys/devices/virtual/dmi/id/product_name`): the LCD Steam Deck (**inferred** from that code name; the OLED is `Galileo`) |
| SteamOS | 3.9.5, build 20261023.100 (`/etc/os-release`) |
| Kernel | 7.2.7-valve2-2-neptune-72-g31504582a073 |
| CPU | AMD Custom APU 0405: 4 cores, 8 threads (`lscpu`, `nproc`) |
| Memory | 14 GiB total as `free -g` reports it (16 GB fitted, the rest held by the firmware and GPU: **inferred**) |
| Swap | zram 7.2 GiB (priority 100) and `/home/swapfile` 1 GiB |
| Disk | internal `/dev/nvme0n1p8` on `/home`: 465 GiB, **318 GiB free**; SD card `/run/media/deck/SD512`: 469 GiB, 404 GiB free |
| `~/raiders` | on internal storage (`/home/deck/raiders`), as the user asked. `~/Games/raiders` will be on the same filesystem, so hard links work |
| Network name | `deck@steamdeck` does not resolve from the Mac; `steamdeck.local` (mDNS) does. The scripts keep the `deck@steamdeck` default from the plan; set `DECK_HOST=deck@steamdeck.local` |
| Tools on SteamOS | `distrobox` 1.8.2.5, `podman` 6.0.2, `rsync`, `vulkaninfo`: all already in `/usr/bin`, so nothing was installed into `~/.local` |

## Vulkan (the host driver)

From `vulkaninfo` on SteamOS (not in the container: Ubuntu 22.04's own Mesa is older).

| | |
|---|---|
| Device | AMD Custom GPU 0405 (RADV VANGOGH), `PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU` |
| Driver | `radv`, driverInfo `Mesa 26.2.0-devel (git-5c65d4fc31)`, driverVersion 26.1.99 |
| Packages | `vulkan-radeon 26.2.0_devel.222147.steamos_26.05.19-1`, `mesa 26.1.2.221562.radeonsi_26.1.2-2.1` (`pacman -Q`) |
| Vulkan | apiVersion 1.4.350 |
| `VK_EXT_mesh_shader` | **present** (`vulkaninfo \| grep -c VK_EXT_mesh_shader` = 1) |
| `VK_KHR_cooperative_matrix` | **absent** |
| `VK_EXT_image_2d_view_of_3d` | present |
| `VK_EXT_external_memory_host` | present |
| Memory heaps | heap 0: 3.00 GiB, no flags; heap 1: 6.00 GiB, `MEMORY_HEAP_DEVICE_LOCAL_BIT` |

Not checked yet: headless rendering on RADV without a compositor (`04-steam-deck.md` §7 expects T03 to confirm it).
That needs a built game, so it is **unknown** until T08's first `HOS_HEADLESS` run.

## Build container

| | |
|---|---|
| Container | Distrobox `raiders-build` from `docker.io/library/ubuntu:22.04`, image `a7b0f6af325461862a99c677cf3229ca5241d9f4`; Ubuntu 22.04.5 LTS, glibc 2.35 (`ldd --version` inside), the same as upstream's CI |
| Home | the Deck's `/home/deck`, shared, so `~/raiders` is the same folder inside and out |
| apt | upstream's "System packages" step, read at run time from `.github/workflows/linux-appimage.yml` (21 lines: the toolchain PPA, `g++-13`, and the build and X11/Wayland/audio `-dev` packages). Run as root once; a stamp keyed by the step's text skips it on later runs |
| `deps.sh` | `DEPS=~/raiders/deps`, run unchanged; `deps/` holds appimagetool, cpm, emsdk, ffmpeg, python, runtime-x86_64, sdl2 and tk; 2.8 GiB |

## Times

| Step | First run | Re-run |
|---|---|---|
| `scripts/deck/setup.sh` (whole, after the container existed) | 667 s | 2-3 s |
| of which `deps.sh` (4 jobs) | 555 s | 0 s |
| Container creation (image pull and Distrobox set-up) | about 100 s (an earlier attempt that stopped later) | kept |
| `scripts/deck/build.sh --vk-only` | 135 s wall; "compiled in 134s, 0 failed"; `hookshot_vk.so` 10,902,624 bytes | 0 s (nothing to rebuild) |

Re-running `setup.sh` changed nothing: a hash of the path, size and mtime of every file under `~/raiders/deps` and
`~/raiders/src`, together with the container's id and start time, was the same before and after
(`b715746c8d75a2a3` / `e2c30b7585be`). Only `work/deps.log` is rewritten.

## Acceptance

| Command | Result |
|---|---|
| `scripts/deck/setup.sh` | ends `deck environment ready`; re-run 3.4 s, nothing changed (above) |
| `scripts/deck/sync.sh && ssh $DECK_HOST 'ls ~/raiders/src/nx2/make_game.py'` | `sync: 1772 files, 0 no longer tracked`; the file is listed |
| `scripts/deck/build.sh --vk-only` | ends `/home/deck/raiders/vk-work/sa/build/hookshot_vk.so` |
| `ssh $DECK_HOST 'ls -la ~/raiders/vk-work/sa/build/hookshot_vk.so'` | `-rwxr-xr-x 1 deck deck 10902624 Nov 10 17:11 ...` |
| `ssh $DECK_HOST 'vulkaninfo 2>/dev/null \| grep -c VK_EXT_mesh_shader'` | `1` |
| `ssh $DECK_HOST 'ls ~/raiders/dump/exefs/main ~/raiders/dump/romfs/Pack'` | both present (the dump the user copied) |
| `bash -n scripts/deck/*.sh` | no error |
| `scripts/deck/run.sh probe 10 -- HOS_TRACE=1` (step 6) | `run: no game built yet on the Deck (...): run scripts/deck/build.sh first`, exit 1 |

## Deviations

- **No change to upstream's `scripts/linux/*.sh`.** No `(raiders)` fix was needed there.
- **`JOBS=4` for `deps.sh` is passed as `OMP_NUM_THREADS=4`.** `deps.sh` line 21 sets `JOBS=$(nproc)` itself, so an
  exported `JOBS` is overwritten. GNU `nproc` honours `OMP_NUM_THREADS`: inside the container `nproc` printed 4.
  An upstream PR could let `JOBS` be passed in (`JOBS=${JOBS:-$(nproc)}`); a candidate for T25.
- **A sixth file, `scripts/deck/lib.sh`**, holds what the five scripts share: the three variables, SSH with one reused
  connection, and quoting. The `ControlPath` socket is in `/tmp`: macOS's per-user `$TMPDIR` made the path longer than
  a Unix socket's 104-byte limit (the first `setup.sh` run failed on it).
- **`setup.sh` and `build.sh` run the inside part from the synced source** (`<script> --inside`, through
  `distrobox enter --no-tty`), so a script must be tracked (or staged) before `sync.sh` sends it.
- **`build.sh` syncs first** unless `--no-sync`. For T08 its default and `--full` modes also set `HOOKSHOT_FFMPEG`
  and `HOOKSHOT_SDL2` to `deps/ffmpeg` and `deps/sdl2/libSDL2-2.0.so.0`, the paths `scripts/linux/appimage.sh`
  copies (lines 80, 82). They are untested until T08.
- **`run.sh`** passes its switches through `HOS_ENV_FILE=<run>/env.txt` and always sets `HOOKSHOT_NO_UPDATE_CHECK=1`,
  so a test run makes no network request. It runs on SteamOS itself, not in the container.
- **`deps.sh` log:** one `fatal: not a git repository: '.../src-dav1d/.git'` line: dav1d's build asks git for its
  version inside a tag archive. It is harmless; `deps.sh` went on and finished.
