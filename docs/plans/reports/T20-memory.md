# T20 · Deck memory budget and default profile   (2026-11-17)

**Short answer.**
- **The game's defaults already fit** (verified, `mem-base`, `mem-base2`, `mem-final`):
  - In the hub with `HOS_HANDHELD=1`, the peak footprint is **7.37 GB** against the 12.5 GB target (11,921 MiB).
  - That leaves **4.55 GB of headroom**.
  - VmSwap stays 0, and the log has 0 over-allowance warnings.
  - `mem-final` (the acceptance run, 660 s): peak 7,383 MB, 4,538 MB of headroom, VmSwap 0, 0 warnings.
- **No memory switch is needed.**
  - The texture cache peaks at 1.07 GB of its 2.56 GB budget, so lowering its budget, the texture size, the
    ASTC policy or the quality preset changed nothing measurable: every one of them is within ±50 MB of the
    baseline.
  - The one lever that saved memory, `RX_VK_CAPTURE_POOL_MB=0` (−330 MB), turns off a correctness mechanism and
    is rejected.
  - `HOS_MEMORY_MB=6144` crashes the game at boot.
- **Profile** (`games/raiders/deck_env.txt`): `HOS_HANDHELD=1` only. There is no options-file template, since no preset
  is used.
- **Swap:** the Deck already has 7.2 GB zram plus an 8 GB swap file, and nothing here needs a change.
- **Not done:** the stress run (step 4: heaviest scene, ten minutes, Steam overlay) needs you at the Deck. See *What
  is left*.

## The accounting method

The footprint is **VmRSS + VmSwap + own resident VRAM + own resident GTT − own shared GTT**, sampled every 5 s by
`scripts/deck/mem_report.sh`.
- **VmRSS / VmSwap:** `/proc/<pid>/status` of the game, found by its `comm` (`hookshot`) and by
  `HOS_ENV_FILE=<run>/env.txt` in its environment.
- **Own VRAM / GTT:** the game's `/proc/<pid>/fdinfo` entries for amdgpu, summed once per `drm-client-id`. The
  `drm-resident-*` figures are used, not `drm-total-*`.
  - In the probe run (`mem-probe`), `drm-total-vram` was 1,426 MB but `drm-resident-vram` was 914 MB (verified).
  - The excess was asked for as VRAM but placed in GTT. Counting `total` would count it twice.
- **− own shared GTT** (`drm-shared-gtt`): the guest's memory is a memfd (`hookshot-guest`), and its pools are
  imported into the GPU as dma-bufs of the same pages (`gpu/vk/vk_memory.cpp`, the Linux udmabuf path).
  - Those pages are in VmRSS (as RssShmem) and in GTT, so they are taken out once.
  - In `mem-base` that is 1,184 MB (verified).
- **The VRAM carve-out (1 GiB)** is outside MemTotal (14,798 MB). It is counted in the footprint all the same, the
  stricter reading.
- **The target:** 12.5 GB = 12.5 × 10⁹ bytes = **11,921 MiB**, the smaller of the two readings. All MB below are
  MiB.
- **Cross-check:** the system cost of the run, (MemAvailable before − now) + (swap used now − before) + (VRAM used
  now − before), comes out at 7,398 MB in `mem-base`. The footprint there is 7,368 MB, a 0.4 % difference
  (verified).
- **The texture cache** is parsed from the game's `vk: VRAM: … textures N MB (budget M MB)` lines, printed every 600
  frames.
  - The task said `vk: status:`, but that line gives the device-local heap against the driver's budget, not the
    cache.
  - Its parts come from `vk: textures:`, and the driver heaps from `vk: memory heaps:`.
- **Run conditions:**
  - headless at 1280×720, sound off, a copy of the T17 seed save (`--user-from`);
  - the `area1_loop.txt` route with `HOS_INPUT_FRAME_CLOCK=1`, 420 s (`mem-final`: 660 s, as written in the
    acceptance criteria, without the frame clock);
  - no `hookshot_options.ini` (Deviations).

## The breakdown (`mem-base`, at its peak, 431 s)

| Part | MB | How it is known |
|---|---|---|
| Guest memory committed (heap, the game's own objects, its pools) | 4,505 | verified: RssShmem; smaps `hookshot-guest` 4,505 |
| … of which pools imported into the GPU (also in GTT) | 1,184 | verified: `drm-shared-gtt` |
| Lifted image (the executable's mapped code and data) | 245 | verified: smaps of the executable |
| Host heap and anonymous memory (replay, decoders, pipeline and program caches, threads) | 789 | verified total (smaps anon); the share per user is **unknown** (smaps cannot split one heap) |
| Vulkan loader, driver libraries, other files | 22 | verified: smaps |
| **VmRSS** | **5,561** | verified |
| GPU, own resident VRAM | 918 | verified: fdinfo |
| GPU, own resident GTT | 2,073 | verified: fdinfo |
| … texture cache (decoded ASTC 32, rendered 512, other 473) | 1,075 peak, budget 2,560 | verified: `vk: VRAM:` / `vk: textures:` lines |
| … render-target pool | ≤ 11 | verified: log |
| … driver heap 0 (system): blocks, captures among them | 1,431 used of 3,072 | verified: `vk: memory heaps:`; the captures' share **inferred** at ~180 MB from `mem-cap0` (192 → 16 MB of blocks) |
| … driver heap 1 (device) | 1,554 used of 5,502 | verified |
| − own shared GTT (counted in VmRSS already) | −1,184 | verified |
| **Footprint** | **7,368** | verified; the whole GPU (every process) holds 3,294 MB |

- **Over time** (verified, `mem-base`, `mem-base2`, one sample a minute):
  - the footprint reaches 7.17–7.30 GB within 62 s (title → hub);
  - it stays between 7.27 and 7.37 GB from 2 min to 7 min, growing about 20 MB over the last five minutes.
- **MemAvailable** falls from ~13.0 GB before the run to ~6.5 GB at its lowest (verified).

## The lever table

All runs used `HOS_HANDHELD=1`, 420 s, the same route and seed save.
- **Picture** is the mean absolute difference (MAD, 0–255, RGB) against `mem-base`'s screenshots at the same present
  numbers, plus an eye check.
- The MAD only means something between presents 3,000 and 5,400 (the hub arrival).
  - After that, even two runs with the same settings walk apart (`mem-base2`: MAD 4–7 until 5,400, then 24–77 as
    the player ends up somewhere else; verified by eye at 7,200).
  - So the comparison window is those nine shots, and `mem-base2` is the noise floor.

| Run | Setting | Peak footprint MB | Peak RSS MB | Own VRAM + GTT MB | Texture cache peak / budget MB | Picture (MAD 3,000–5,400: median, max) |
|---|---|---|---|---|---|---|
| `mem-base` | defaults (`RX_VK_TEX_MAX_DIM` 2048 is the default) | 7,368 | 5,589 | 970 + 2,073 | 1,075 / 2,560 | reference |
| `mem-base2` | defaults again (noise floor) | 7,365 | 5,580 | 950 + 2,039 | 1,062 / 2,560 | 5.6, 7.2 |
| `mem-vram2048` | `RX_VK_VRAM_MB=2048` | 7,405 | 5,604 | 949 + 2,007 | 1,057 / 2,048 | 8.1, 9.0: no visible change |
| `mem-vram1536` | `RX_VK_VRAM_MB=1536` | 7,355 | 5,583 | 954 + 1,975 | 1,059 / 1,536 | 7.9, 8.8: no visible change |
| `mem-tex1024` | `RX_VK_TEX_MAX_DIM=1024` | 7,399 | 5,598 | 954 + 2,073 | 1,073 / 2,560 | 4.1, 5.9: none by eye (side by side at 4,500) |
| `mem-q2` | options `quality_preset=2` (Low: resolution 2, the rest as preset 2 writes them) | 7,359 | 5,574 | 954 + 1,993 | 1,072 / 2,560 | 2.6, 5.6: none by eye |
| `mem-q1` | options `quality_preset=1` (Minimum: resolution 4) | 7,407 | 5,616 | 953 + 1,993 | 1,067 / 2,560 | 4.1, 8.4: none by eye |
| `mem-astc8` | `RX_VK_ASTC_RGBA8=1` | 7,327 | 5,586 | 950 + 1,976 | 1,058 / 2,560 | 8.5, 10.6: no visible change |
| `mem-cap0` | `RX_VK_CAPTURE_POOL_MB=0` | **7,033** | 5,421 | 950 + 1,942 | 1,072 / 2,560 | 5.9, 7.0; **rejected** (below) |
| `mem-guest6g` | `HOS_MEMORY_MB=6144` | 13,122 (crashed) | 13,057 | 9 + 10 | none | no picture; **ruled out** (below) |

Every run had 0 over-allowance warnings and 0 allocation-failure lines, and VmSwap 0 except `mem-guest6g`
(verified, each run's `mem_report.txt`).

- **Why nothing moves** (inferred from the cache figures):
  - the texture cache never reaches even 1,536 MB in the hub, so its budget never bites;
  - the larger textures are already clamped to 2048 by default;
  - the ASTC and resolution levers change what the GPU stores by less than the run-to-run spread (about ±50 MB in
    GTT).
  - Expected but not seen: `RX_VK_ASTC_RGBA8=1` was expected to cost more. Its decoded-ASTC share is 32 MB in the
    hub, too small to show (inferred).
- **`RX_VK_CAPTURE_POOL_MB=0`, rejected** (decision):
  - It saves ~330 MB: RSS −160 MB, heap 0 blocks 192 → 16 MB.
  - It also stops the captures from taking the game's small pools when they are made. Per `gpu/vk/vk_memory.cpp`'s
    note, those captures stop pools made mid-frame from flashing for a frame (inferred for this game from that note).
  - A screenshot every 300 presents cannot see a one-frame flicker, and the 330 MB isn't needed.
- **`HOS_MEMORY_MB=6144`, ruled out** (verified, its log):
  - The game sizes its heap from the total: `SetMemoryHeapSize` with a negative size, then `AllocateMemoryBlock`
    heap exhausted, then a crash on `sead::MainThread` before the title.
  - Lowering the guest's total is not a lever for this game.
  - Its default (9,809 MB) is an address window, not a commitment: the guest commits 4.5 GB of it (verified,
    RssShmem).
- **Side finding** (verified; cause **unknown**):
  - after that crash, the process did not exit. Its guest memory grew to 13 GB within 30 s and stayed there.
  - MemAvailable fell to 78 MB and system swap rose by 410 MB, until run.sh stopped it at the time limit.
  - The Deck stayed up. This is a candidate for its own task (a crashed game should exit).
- **Speed** (verified, presents in 420 s): 9,000–19,500 across the runs, with 9,900 and 13,200 for the same
  settings. Speed does not track the lever. The cause, thermal or power state, is inferred and not measured. Memory
  is not affected: the footprint levels off by 2 min in every run.

## The chosen profile

`games/raiders/deck_env.txt`:

```
HOS_HANDHELD=1
```

- **The decision:** the smallest set that meets the target is the defaults. `HOS_HANDHELD=1` is kept because every
  measured run had it (the task's baseline), and it is how the Deck is played.
- **Left out for lack of a measurement here**, for T24 to decide with its own runs:
  - `HOS_WINDOW_SIZE` (every run was headless);
  - the draft lines of `04-steam-deck.md` §8 (`HOS_FULLSCREEN`, `HOS_AUDIO_CHANNELS`, `HOOKSHOT_NO_UPDATE_CHECK`,
    `RX_VK_FRAMEGEN`).
- **How the game gets the file:**
  - `nx2/make_game.py` writes it as `<out>/hookshot_env.txt` with `--profile deck`, or on SteamOS unless
    `--profile desktop` is given;
  - it does so only when the folder has no `hookshot_env.txt` (the player's file is kept);
  - test: `tests/test_make_game_profile.py`, which also checks every line against the switch names the game reads
    and that each line cites this report.

## Headroom

- **`mem-final`** (verified, `work/runs/mem-final/mem_report.txt`; 660 s, 131 samples, the hub played to present 13,500):
  - **peak footprint 7,383 MB at 338 s:** VmRSS 5,577 + VmSwap 0 + VRAM 918 + GTT 2,040 − shared GTT 1,152;
  - **headroom 4,538 MB** to 11,921 MB.
- **The parts:**
  - peak RSS 5,577 MB (the guest's RssShmem 4,505), peak VmSwap 0;
  - own GPU 953 MB VRAM + 2,040 MB GTT; the whole GPU 3,271 MB;
  - minimum MemAvailable 6,611 MB;
  - texture cache 1,065 of its 2,560 MB.
- **Over time:** the footprint is 7.32–7.38 GB from 2 min to 11 min, with no growth from 6 min on (verified, one sample
  each 2 min).
- **A late first sample:** the report started reading when the game already held 1.2 GB. Its "before" figures for
  MemAvailable and the cross-check (6,463 MB) are therefore after the start, and too low. The footprint itself does
  not depend on them.
- **What is left inside the target (inferred):**
  - about 4.5 GB for scenes heavier than the hub and for the Steam client and overlay;
  - for comparison, the texture cache could still grow by 1.5 GB within its own budget.
  - Whether a level comes close is the stress run's question (What is left).

## Swap

- **The Deck has** (verified, `swapon`, and the game's own boot line `15590 MB of swap`):
  - zram 7.2 GB and `/home/swapfile` 8 GB, swappiness 60;
  - about 960 MB of swap is in use before any run, from earlier sessions.
- **The game uses no swap:**
  - VmSwap was 0 in every completed run;
  - system swap in use did not change during any of them (verified).
- **Recommendation: leave swap as it is** (inferred). It is not needed for the game's 7.4 GB. It is the safety
  margin that kept the Deck up when `mem-guest6g` crashed and filled memory. Shrinking it gains nothing, and growing
  it is not needed.

## Acceptance criteria

Run on 2026-11-17, real output (`DECK_HOST=deck@steamdeck.local`):

```
$ bash -n scripts/deck/mem_report.sh
bash -n: ok
$ scripts/deck/run.sh mem-final 660 --user-from /home/deck/raiders/work/t17_user_seed -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" HOS_HANDHELD=1 &
$ scripts/deck/mem_report.sh mem-final
mem_report mem-final: 131 samples every 5s over 667s; accounting: VmRSS + VmSwap + own VRAM + own GTT - own shared GTT (late: the game held over 1 GB when the first value was read)
  peak footprint 7383 MB at 338s (VmRSS 5577 + VmSwap 0 + VRAM 918 + GTT 2040 - shared GTT 1152); target 11921 MB (12.5 GB): within, headroom 4538 MB
  peak RSS 5577 MB (RssShmem, the guest's, peak 4505 MB); peak VmSwap 0 MB
  peak GPU memory (VRAM + GTT): own 953 + 2040 MB; whole GPU 3271 MB
  min MemAvailable 6611 MB (before the run 12145 MB); system swap in use peak 1119 MB (before 1119 MB)
  ...
  over-allowance warnings: 0; allocation-failure lines: 0
run mem-final: stopped at the time limit
run mem-final: 45 screenshots, log /home/deck/raiders/work/runs/mem-final/hookshot_log.txt
$ scripts/deck/fetch.sh mem-final
$ grep -ci "over the driver's video-memory allowance" work/runs/mem-final/hookshot_log.txt
0
$ .venv/bin/python -I -B tests/run_all.py make_game
5 passed, 0 failed, 0 skipped in 0 s (linux, 8 at once)
```

| Criterion | Result |
|---|---|
| `bash -n` | pass |
| peak RSS + GPU ≤ 12.5 GB (this report's accounting) | **pass**: 7,383 of 11,921 MB |
| VmSwap peak ~0 | **pass**: 0 MB |
| over-allowance lines | **pass**: 0 |
| `run_all.py make_game` | **pass**: 5 of 5 (`test_make_game_profile.py` new); `test_deck_scripts.py` also passes (its new memory-report test) |

- **The full Mac suite** (`run_all.py`, without the Homebrew header variables): `300 passed, 9 failed, 42 skipped in
  619 s`.
  - 7 of the 9 were run again by name, and they are the baseline's known Mac failures (`mem_gate`,
    `mem_gate_children`, `low_memory_notice`, `prof_symbols`, `hookshot_launch`, `linux_update`,
    `appimage_source_headers`), verified.
  - The other 2 are inferred to be the baseline's two ASan hangs (`program_cache_reader`, `seed_reader`): the run
    lasted 619 s, about their 600 s timeout.
- The run reached the hub and played the route until present 13,500 (by eye at 12,000).
- Afterwards, the Deck's options file was put back (md5 equal to its backup), and your save's md5 is unchanged
  (verified).
- Step 4 (stress) is **not done**: What is left.

## Deviations

- **No area change in the scripted runs.** The route's only load is title → hub. No scripted route enters a level
  yet, and a level is the stress run's job (step 4, needs you).
- **`HOS_INPUT_FRAME_CLOCK=1` in the lever runs**, so that screenshots at the same present number show the same
  route point. It did so only until present ~5,400 (above). `mem-final` was run without it, as written.
- **The Deck's `hookshot_options.ini` was set aside for every run:**
  - it held resolution=4, handheld_profile=1 and ultrawide=1, so it was not the defaults;
  - it was put back afterwards, md5 checked.
  - M5's figures (5.7 GB RSS) were taken with it, which may explain part of their difference from this report's.
- **`mem-final` had more than the acceptance line names:**
  - `HOS_HANDHELD=1`: the profile's line. run.sh sets `HOS_ENV_FILE`, so the game folder's `hookshot_env.txt` is not
    read, and the profile has to be passed after `--`.
  - `--user-from` the T17 seed save, so your own save is not touched (verified: its md5 is the same before and after
    all runs).
  - The run was fetched with `scripts/deck/fetch.sh` before the `grep`.
- **`RX_VK_TEX_MAX_DIM=2048`** is already the default (`gpu/vk/vk_texture.cpp`), so that lever is `mem-base`.
- **`mem_report.sh` reads the texture cache from `vk: VRAM:`**, not `vk: status:` (above).
- **The Deck build was main + T20.** T19 is not merged into main.

## What is left

- **Step 4, the stress run** (needs you at the Deck):
  - Start Steam in desktop or game mode.
  - Run the following and play the heaviest level you can reach for ten minutes, opening the Steam overlay once:
    `scripts/deck/run.sh mem-stress 660 --window --sound -- HOS_HANDHELD=1 &` then
    `scripts/deck/mem_report.sh mem-stress`, and afterwards `scripts/deck/fetch.sh mem-stress`.
  - This uses your own save (no `--user-from`) so that your levels are open.
  - The pass line is the same: footprint ≤ 11,921 MB, VmSwap ~0, 0 over-allowance warnings.
- **The crash that keeps running** (side finding above): a task of its own.
