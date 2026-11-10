# T22 · CPU performance on the Deck: threads, hot list, PGO, frame cap

**Milestone:** M7 · **Depends on:** T17 (measurements), T20 (memory profile) · **Machine:** Mac driving the
Deck

## Context
Hookshot's notes say the CPU saturates first: its game was CPU-bound at 30-36 fps on a 6-core desktop CPU
before tuning, with the replay thread taking about 9 ms a frame (`docs/design.md` §4 rule 7, §9, §10).
Upstream's speed comes from three artefacts made from play of its own game: a hot-function list
(`work/hot_funcs.txt`, compiled at `-O2` together in `code_hot*.c`), a link order (`work/hot_order.txt`) and
a PGO profile (`work/hookshot_pieces.prof`). None exist for Raiders, and "without them the game builds but
runs slower" (`readme.md`). The Deck has 4 cores / 8 threads. Goal: a frame rate that holds a cap of 30 fps
or better in normal play (Gate 2).

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §4; `docs/plans/reports/M5-gameplay.md`
- `docs/design.md` §4 rule 7, §10, §11; `docs/development.md` "Time and profiles", "Building"
  (`RX_PGO`, `RX_HOT_OPT`, `RX_MARCH`), "The GPU" (`HOS_VCORES`, `HOS_CORES`, `HOS_RESERVE_CORE`,
  `RX_VK_ASYNC`)
- `scripts/hotlist.py`, `scripts/crit.py`, `scripts/prof.py`, `scripts/vkprof.py` docstrings;
  `nx2/split_hot.py`, `nx2/pgo_pieces.py`; `host/pgo_rt.c` header; `host/posix/prof.c` (the Linux sampler)
- `nx2/build.py` 54-60 (hot order), 755-770 (hot flags and PGO)

## Scope
1. Where the time goes on the Deck: per-thread CPU, the replay thread, the game's main and worker threads,
   GPU time.
2. Thread configuration measured one variable at a time.
3. Raiders' own hot list and link order from a sampled Deck run; a PGO profile from an instrumented build;
   a rebuilt game using them.
4. A frame cap that holds, and the pacing settings for gamescope.

## Non-goals
- Rewriting the replay or the lifter. Frame generation. Committing the performance files (they stay in
  `~/raiders/work` on the Deck; `games/raiders/game.py` `PERF_FILES` names them).
- GPU optimisation unless measurement shows the GPU is the limit at 1280×720.

## Steps
1. Profile the T17 loop: `HOS_PROFILE=10 HOS_THREAD_TIMES=10`, `RX_VK_PASS_TIMING=1`,
   `RX_VK_SLOW_LOG=33`. Then sample all threads: `HOS_SAMPLE_ALL=<file>` (needs `HOS_PROFILE`; runs while
   `<file>.go` exists). Confirm the sampler works on Linux (`host/posix/prof.c`); read with
   `scripts/crit.py` and `scripts/vkprof.py`.
2. Thread experiments, each a named run with the same script and `RX_VK_FRAME_LOG`:
   default; `HOS_CORES=4`; `HOS_RESERVE_CORE=0`; `HOS_VCORES=0`; `RX_VK_ASYNC=1`;
   `RX_VK_CAPTURE_THREADS` (find its default). Record mean, 1% low, share of frames over 33.4 ms.
   Keep a change only if it improves the 1% low without lowering the mean.
3. Hot list: `python -I scripts/hotlist.py work/runs/<run>_all.txt ~/raiders/work/hot_funcs.txt 0.85 1500`;
   link order from the same sample (see how `hot_order.txt` is produced: `grep -rn "hot_order" scripts nx2`).
   Rebuild with `A64_HOT_FUNCS` set as `make_game.py:1316-1317` does (a relift: the hot list is part of the
   lift key).
   - Pitfall: hot pieces compile at `-O2` and need 0.8-1.7 GB each (`build.py:270`). `HOOKSHOT_JOBS=3` for
     this build if memory is tight; expect a long build (upstream: 79 minutes for the unsplit file, about 6
     after `nx2/split_hot.py`, on a desktop).
4. PGO: build with `RX_PGO=gen`; run with `HOS_PGO=<path>` in the environment (not in the env file: it is
   read earlier); create `<path>.reset` after loading and `<path>.dump` after five minutes of play
   (`docs/development.md`); convert with `llvm-profdata merge` from `~/raiders/deps/emsdk/upstream/bin`
   (LLVM 23 is required to read the profile); fit to the pieces with `python -I nx2/pgo_pieces.py`;
   rebuild with `RX_PGO=<file>`. Name the result as `PERF_FILES` says (`raiders_pieces.prof`) and make
   `make_game.py` look up the game config's names instead of `hookshot_pieces.prof` (`:1305`, `:1318`).
5. Measure after each of steps 3 and 4. Report the gain of each separately.
6. Frame cap: from the final distribution choose 60, 45, 40 or 30. Set the game's cap
   (`frame rate cap` row / its option key) and gamescope's limiter to match; `Game speed = Real time`.
   Verify animation speed against T17's stopwatch check. Record fps at 15 W and at 10 W TDP.
7. If the result is below a stable 30 fps: list the top five lifted functions and runtime functions by
   samples (addresses and SDK/runtime names only), what was tried, and options (upstream performance PRs to
   watch, `RX_MARCH`, lower `HOS_CORES`, lower resolution if the GPU contributes).

## Acceptance criteria
```bash
ssh $DECK_HOST 'wc -l ~/raiders/work/hot_funcs.txt ~/raiders/work/hot_order.txt; ls -la ~/raiders/work/raiders_pieces.prof'
scripts/deck/run.sh perf-final 330 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" RX_VK_FRAME_LOG=frames.csv && scripts/deck/fetch.sh perf-final
awk -F, -v cap=33.4 'NR>1{n++; if($3>cap)o++} END{printf "%.1f%% of %d frames over %.1f ms\n", 100*o/n, n, cap}' work/runs/perf-final/frames.csv
#   <= 5% over the chosen cap's frame time (33.4 ms for 30 fps)
.venv/bin/python -I -B tests/run_all.py make_game pgo hot
git status --porcelain | grep -ci "hot_funcs\|hot_order\|\.prof"     # 0
```

## Report
`docs/plans/reports/T22-performance.md`: the time breakdown, the thread-experiment table, gains from the hot
list and from PGO, the chosen cap and settings, fps at 15 W and 10 W, build times with the hot list, and the
Gate 2 statement (met, or not with the options).
