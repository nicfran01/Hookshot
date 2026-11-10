# T21 · Shader preparation and pipeline caches on the Deck

**Milestone:** M7 · **Depends on:** T17, T12 · **Machine:** Mac driving the Deck; the user plays at the Deck

## Context
Hookshot removes most shader stutter with three caches beside the executable: translated programs
(`hookshot_programs.bin` + `.idx`), pipelines (`hookshot_pipelines.bin`), and a list of pipeline states seen
in play (`hookshot_pipeline_states.bin`) that a later preparation builds before the title
(`docs/design.md` §10, `nx2/pipeline_states.py`, `make_game.py:861-960`). Its README still reports stutter
the first time an area is seen. Raiders has no shipped state list. T12 measured preparation time and pass
rate. Open question: whether Steam's shader pre-caching does anything for a non-Steam native game
(`docs/plans/04-steam-deck.md` §3).

## Read first
- `CLAUDE.md`; `docs/plans/04-steam-deck.md` §3; `docs/plans/reports/M3-shaders.md`
- `nx2/pipeline_states.py` docstring; `make_game.py` `seed_pipelines`, `ship_state_list`,
  `prepare_shaders`, `prepare_skipped`, `not_prepared`
- `docs/pipeline-cache-save-check.md`; `docs/development.md` (`RX_VK_PRECOMPILE`, `RX_VK_NO_PROGRAM_CACHE`,
  `RX_VK_PIPE_SKIP`, `RX_RELEASE`)
- `gpu/vk/vk_draw.cpp`: where `hookshot_pipeline_states.bin` is written and where the cache is keyed on the
  driver (`grep -n "pipelineCacheUUID\|driverVersion\|pipeline_states" gpu/vk/*.cpp | head -30`)

## Scope
1. A measured picture of stutter on the Deck: pipeline compiles per minute of play, frame-time spikes they
   cause, first visit versus second visit.
2. A Raiders pipeline state list made from the user's play, merged and used by preparation.
3. A decision on Steam's shader pre-caching setting, from a measurement.
4. Cache invalidation behaviour on a Mesa update, and what the launcher should do.

## Non-goals
- Committing the state list (it stays in `work/` on the Deck by default: see `05-roadmap.md` open
  question 3). Changing the cache formats.

## Steps
1. Instrument, without changing behaviour: find the log line for a pipeline compiled at draw time and for a
   draw skipped while its pipeline was not ready; if there is none, add a counter printed with the periodic
   `vk: status:` line (`(raiders)`-marked; upstream candidate).
2. Baseline, cold caches (`RX_VK_NO_PROGRAM_CACHE` unset, cache files deleted): the T17 loop plus one area
   change. Record compiles, skipped draws, frame-time spikes over 50 ms (`RX_VK_FRAME_LOG`).
3. Same run again, warm: record the same. The difference is what caches already buy.
4. The user plays 30-60 minutes across the areas they can reach, with state recording on (default). Collect
   `hookshot_pipeline_states.bin`; merge: `python -I nx2/pipeline_states.py --out
   ~/raiders/work/pipeline_states.bin <lists…>`; rebuild/package so `make_game.py` ships it as
   `hookshot_pipeline_states_shipped.bin`; delete the caches; run `--prepare-shaders`; then repeat step 2.
   Target: a first visit after preparation compiles (almost) nothing.
5. Steam: with the non-Steam shortcut from Gaming Mode, repeat the cold run with *Shader Pre-caching* on and
   off (and "Allow background processing of Vulkan shaders" on and off). Record whether
   `~/.local/share/Steam/steamapps/shadercache/<shortcut id>/` appears and grows, start-up time, and
   compiles. Decide the recommended setting.
6. Invalidation: record `pipelineCacheUUID` and the Mesa version; note what the code does when the UUID
   changes. Specify for T24's launcher: if the driver version recorded beside the caches differs from the
   current one, run `--prepare-shaders` before starting the game, with a visible "Preparing shaders" message.
7. Preparation time budget on the Deck: if a full preparation is long (T12's figure), check that it shows
   progress and can be interrupted and resumed without starting over; if not, report it as a gap.

## Acceptance criteria
```bash
ssh $DECK_HOST 'ls -la ~/Games/raiders/bin/hookshot_programs.bin ~/Games/raiders/bin/hookshot_pipelines.bin ~/Games/raiders/hookshot_pipeline_states_shipped.bin 2>/dev/null || ls -la ~/Games/raiders | grep -i pipeline'
scripts/deck/run.sh cache-warm 330 -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" RX_VK_FRAME_LOG=frames.csv && scripts/deck/fetch.sh cache-warm
grep -c "<the draw-time compile line>" work/runs/cache-warm/hookshot_log.txt      # ~0 on a second visit
awk -F, 'NR>1&&$3>50{n++} END{print n+0, "frames over 50 ms"}' work/runs/cache-warm/frames.csv
git status --porcelain | grep -ci "pipeline\|\.bin"                              # 0: nothing of these is tracked
```

## Report
`docs/plans/reports/T21-shader-caches.md`: the four runs' numbers (cold, warm, after preparation with the
state list, with Steam's setting on/off), the recommended Steam setting, the invalidation rule for the
launcher, preparation time and resumability.
