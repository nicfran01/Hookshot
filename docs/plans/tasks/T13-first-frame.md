# T13 · First frame and title screen (Gate 1)

**Milestone:** M4 · **Depends on:** T09a, T10 (Part A), T11 (device limits), T12, T08a · **Machine:** Mac driving the Deck; the user at the Deck
for the final check

## Context
After M3 the boot reaches its first present with offline answers in place and the shader pass rate known.
This task gets from "presents happen" to "the title screen is on screen and correct". Hookshot's game showed
black for about 23 s of loading, then its title (`docs/design.md` §9, S3). This is an iterative
debug task: it may take more than one session; each session ends with a report update.

## Read first
- `CLAUDE.md`; `docs/plans/reports/M3-trace.md`, `M3-shaders.md`, `T11-nvn2.md`
- `docs/design.md` §4 (all seven rules), §9 S3 and S4 notes, §10
- `docs/development.md` "Pictures and frames", "The GPU"
- `docs/plans/04-steam-deck.md` §4

## Stops before the first present (added 2026-11-10)
The first trace stopped long before any submit, and T10 Part B and T11 are trace-driven, so this task is
where most missing calls will first appear. For each stop caused by a stub or a missing NVN proc, look up
its owner in T10's "Ownership of traced calls" table:
- owner is T10 Part B or T11 → end this session's attempt there, record the call in `M3-trace.md`
  (regenerate it from the run's log), and run that task next as its own session;
- owner is "the task whose run met it" → fix it here only if it is one function whose answer was checked
  against the caller (disassemble the traced `lr` on the Mac); otherwise write a blocker report.
Each relift costs about 45 minutes on the Deck (T08: 2,544 s): batch `HLE()` additions.

## Scope
1. Reach the title screen in a headless run and in a windowed run on the Deck.
2. Fix what prevents it: missing NVN ops deferred from T11, wrong formats, missing texture kinds, passes that
   need ordering fixes covered by upstream's rules.
3. Record Raiders' render facts: handheld and docked render sizes, dynamic resolution behaviour, queues,
   whether a DLSS/NDSR network is evaluated, frame time.

## Non-goals
- Getting past the title (T15). Audio (T18). Performance tuning (T22), beyond recording numbers.
- Geometry-stage support: only record whether "dropped stages" appears and for which program keys (T14).

## Method
Loop: run → look → narrow → fix.
1. `scripts/deck/run.sh titleN 180 -- HOS_NO_MOVIES=1 HOS_HANDHELD=1 RX_VK_SHOT_EVERY=120` then
   `scripts/deck/fetch.sh titleN`; open the PNGs in `work/runs/titleN/shots/` with the Read tool.
2. Black or wrong picture: use the tools in this order.
   - Log first: "device lost", validation errors (`RX_VK_VALIDATION`), programs that failed to translate
     (cross-check `M3-shaders.md`), "dropped stages".
   - `RX_VK_PASS_TRACE=1` and `RX_VK_PROBE=2` (centre texel after every pass; `scripts/probe.py`) to find the
     first pass that goes wrong.
   - `RX_VK_DUMP=<present>` for every step of one frame as PNGs (large; Deck only; fetch selectively).
   - `RX_VK_PIPE_SKIP=0` so draws are not left out while pipelines compile.
3. For a wrong pass, identify its program key and look at which feature it uses that Hookshot's games did
   not. Fix in `gpu/vk/` following the existing structure; a fix that is specific to a Raiders program key
   goes behind the game config, not inline.
4. When the title is visible headless, run windowed from the Deck (the user starts it from Desktop Mode):
   `HOS_WINDOW_SIZE=1280x720`. Check picture, colours, text, animation speed.

## Pitfalls
- Screenshots are game output: they stay in `work/runs/`. Describe them in words in the report.
- RADV-specific behaviour: upstream notes several (`gpu/vk/vk_replay.cpp:145`, `vk_memory.cpp:127`,
  `vk_draw.cpp:5131`). Search the file for "RADV" before debugging something that looks driver-shaped.
- Dynamic resolution is fed by fake GPU time (`RX_VK_TS_SCALE`, `docs/design.md` §4 rule 4). If the picture
  is very low resolution, read the render size the game picks before touching scaling.
- A neural upscale without NVIDIA's cooperative-matrix path falls back to linear (`04-steam-deck.md` §4): a
  soft picture may be that, not a bug. Record it.
- One game run at a time on the Deck.

## Acceptance criteria
```bash
scripts/deck/run.sh title 180 -- HOS_NO_MOVIES=1 HOS_HANDHELD=1 && scripts/deck/fetch.sh title
ls work/runs/title/shots/*.png | tail -3                    # the last screenshot shows the title screen (state what it shows)
grep -ci "device lost" work/runs/title/hookshot_log.txt     # 0
ssh $DECK_HOST 'journalctl -k -b | grep -cE "gfx_|amdgpu.*timeout"'   # 0
grep -n "dropped stages" work/runs/title/hookshot_log.txt | head      # recorded for T14 (may be empty)
.venv/bin/python -I -B tests/run_all.py
```
Final check by the user at the Deck: the title screen matches the console (layout, colours, motion). Gate 1
is passed when the user confirms.

## Report
`docs/plans/reports/M4-first-frame.md`: each problem found and its fix (file:line), render sizes and the
dynamic-resolution behaviour, queues and event waits per frame, upscaler/AA path in use on the Deck, frame
time and fps at the title, memory at the title (RSS and the `vk: status:` line), "dropped stages" program
keys, open visual differences. If the gate is not passed in the session, list what remains and an estimate.
