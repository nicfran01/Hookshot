# T18 · Audio

**Milestone:** M6 · **Depends on:** T17 · **Machine:** Mac driving the Deck; the user listens at the Deck

## Context
Test runs so far were muted (`HOS_AUDIO=0`: the mixer runs, no device is opened). Raiders imports 238
`nn::audio` functions; 114 are implemented and 121 would be stubs, mostly effects (delay, reverb,
compressor, capture) and their setters (`work/standalone_stubbed.txt`). Hookshot's own game ran with audio
effects on the generic stub (`docs/design.md` §9). Formats: BARS/BWAV resources, Opus streams
(`UseOpus`, `OpusDecoder` strings); libopus is vendored (`third_party/opus`).

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §8
- `host/nn_audio.c` header comment and its renderer model (voices, mixes, sinks, `RequestUpdate`),
  `host/nn_codec.c` (Opus), `host/posix/display_sdl.c` (the SDL audio device)
- `readme.md` "Audio output"; `docs/development.md` (`HOS_AUDIO`, `HOS_AUDIO_CHANNELS`)
- The audio rows of `docs/plans/reports/M3-trace.md`; re-run the trace report on a gameplay log

## Scope
1. Sound on the Deck: music, effects, voices, at the right pitch and speed, without crackle or drift.
2. Stubs that returned a wrong answer are implemented: at minimum, effect "add" calls must leave the effect
   struct in a state the game's later setters and `RequestUpdate` accept.
3. Decide per effect type whether to implement its DSP or pass audio through unchanged.

## Non-goals
- Surround output (the Deck is stereo: `HOS_AUDIO_CHANNELS=2`). Microphone input. Exact reverb matching:
  a pass-through with correct levels is acceptable for accuracy-first only if the user cannot hear the
  difference in a side-by-side; otherwise implement.

## Steps
1. Unmuted run with the gameplay script and the user listening: note what is wrong (silence, missing music,
   speed, crackle, loud or dry mix).
2. Trace: list `nn::audio` and `nn::codec` stubs called during gameplay, with counts. Classify as in T09.
3. Effects: for each effect type the game adds, read how the renderer in `nn_audio.c` processes mixes and
   where an effect would sit. Implement "bypass" first (the effect exists, is enabled or disabled as asked,
   passes samples through), then DSP for delay and reverb if the dry mix is audibly wrong. Sources for DSP
   behaviour: Eden's audio renderer (GPL-3.0-or-later; cite file and commit in the header if ported).
4. Underruns: SDL's buffer size against the game's 5 ms audio frame; record the device parameters logged at
   start. If crackle correlates with frame-time spikes, raise the buffer modestly and record latency.
5. `nn::codec` stubs: the AAC and H.264 names are expected to stay uncalled; confirm from the log.
6. Tests: source-level tests for any new HLE in upstream's style; a tiny synthetic buffer through a bypassed
   effect comes out unchanged.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py audio codec
scripts/deck/run.sh audio1 660 --sound -- HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/area1_loop.txt)" && scripts/deck/fetch.sh audio1
grep -ciE "underrun|xrun" work/runs/audio1/hookshot_log.txt                    # 0, or the count and cause in the report
.venv/bin/python -I scripts/trace_report.py work/runs/audio1/hookshot_log.txt | grep -c "audio.*wrong answer\|audio.*blocking"   # 0
```
User check: ten minutes in the first area with music and effects, no crackle, correct pitch.

## Report
`docs/plans/reports/T18-audio.md`: what was wrong, effects found and how each is handled (bypass or DSP),
device parameters and latency, remaining differences from the console by ear.
