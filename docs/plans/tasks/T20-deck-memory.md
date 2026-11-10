# T20 · Deck memory budget and default profile

**Milestone:** M7 · **Depends on:** T17 · **Machine:** Mac driving the Deck

## Context
The Deck's 16 GB are shared by the CPU and the GPU. A Hookshot run uses about 10 GB of RAM on desktop plus
video memory (`readme.md`). Upstream already caps the texture cache at 2,560 MB on integrated GPUs
(`gpu/vk/vk_texture.cpp:3338-3344`) and suggests `RX_VK_TEX_MAX_DIM=1024` for the Deck (`:1702`).
T17 measured Raiders' real use. Target: process RSS + GPU memory ≤ 12.5 GB with Steam running
(`docs/plans/04-steam-deck.md` §2).

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §2, §8; `docs/plans/reports/M5-gameplay.md` (measurements)
- `docs/development.md` "The GPU" (`RX_VK_VRAM_MB`, `RX_VK_MIRROR`, `RX_VK_MIRROR_MB`,
  `RX_VK_CAPTURE_POOL_MB`), "The options file" (`quality_preset`)
- `gpu/vk/vk_texture.cpp` around 1690-1710 and 3330-3350; `gpu/vk/astc_bc_policy.h`;
  `host/hos_mem.c` 36-55; `docs/compiler-memory-accounting.md`
- `gpu/vk/vk_menu.cpp`: what each Quality preset sets

## Scope
1. A memory breakdown of a gameplay run on the Deck: guest heap committed, lifted image, texture cache,
   render targets, pool imports and captures, pipeline and program caches, driver.
2. The smallest set of switches that meets the target without visible loss at 1280×720, written into
   `games/raiders/deck_env.txt` (and an options-file template if a preset is used).
3. A regression check: a script that reports peak RSS and GPU memory for a run.

## Non-goals
- Changing the texture cache's design. Lowering visual quality below what the console's handheld mode shows,
  unless the target cannot be met otherwise (then report the trade-off and let the user choose).
- System swap changes (user action; give the command and the reason if recommended).

## Steps
1. `scripts/deck/mem_report.sh <name>` (new): during a run, sample every 5 s `VmRSS`, `VmSwap`
   (`/proc/<pid>/status`), `mem_info_vram_used` and `mem_info_gtt_used` under
   `/sys/class/drm/card*/device/`, and `MemAvailable`; print peak and final values. Parse the game's
   `vk: status:` lines for the texture cache's use against its allowance.
   - Note: on an integrated GPU "VRAM" is a small carve-out and most GPU memory is GTT (system RAM): report
     both, and avoid double counting RSS with GTT where imported host memory is involved (pools are imported
     host pointers: `gpu/vk/vk_memory.cpp:127`). State the accounting method.
2. Baseline: defaults + `HOS_HANDHELD=1`, the T17 gameplay loop for five minutes plus one area change.
3. Try levers one at a time, each as its own named run, recording peak memory and a picture check
   (screenshots at fixed points of the scripted route compared by eye and by mean absolute difference):
   `RX_VK_VRAM_MB=2048/1536`, `RX_VK_TEX_MAX_DIM=2048/1024`, `quality_preset=2 (Low)` / `1 (Minimum)`,
   ASTC policy default versus `RX_VK_ASTC_RGBA8=1` (expect more memory: 1,213 ASTC 4x4 textures),
   `RX_VK_CAPTURE_POOL_MB`, and `HOS_MEMORY_MB` only if the guest heap is the dominant term.
   - Pitfall: `HOS_MEMORY_MB` changes what the game believes it has. If lowered, run the full scripted route
     and an area change; any allocation failure in the log rules it out.
4. Stress: the heaviest scene the user can reach, ten minutes, with Steam's overlay opened once.
5. Choose the profile; write it to `deck_env.txt` with a comment per line citing this report's run names.
   `make_game.py` copies `games/<id>/deck_env.txt` to `<out>/hookshot_env.txt` only when no such file exists
   and only when running on a Deck (detect `/etc/os-release` `ID=steamos` or a `--profile deck` argument;
   prefer the explicit argument).

## Acceptance criteria
```bash
bash -n scripts/deck/mem_report.sh
scripts/deck/run.sh mem-final 660 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" & 
scripts/deck/mem_report.sh mem-final          # prints peak RSS, peak GPU memory (VRAM + GTT), min MemAvailable
#   peak RSS + GPU memory (by the report's stated accounting) <= 12.5 GB; VmSwap peak ~0
grep -ci "over the driver's video-memory allowance" work/runs/mem-final/hookshot_log.txt   # 0
.venv/bin/python -I -B tests/run_all.py make_game
```

## Report
`docs/plans/reports/T20-memory.md`: the accounting method, the breakdown, the lever table (run, setting,
peak memory, picture effect), the chosen profile, headroom left, and a recommendation on swap size for the
user.
