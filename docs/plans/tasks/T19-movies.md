# T19 · Movies: the `nn::movie` path to VP9 decoding

**Milestone:** M6 · **Depends on:** T17 · **Machine:** Mac driving the Deck

## Context
Raiders ships 16 small VP9 WebM clips in `romfs/UI/Movie/` (gadget previews shown in a menu) and names an
`Event/Movie/` folder that the base game does not contain. Hookshot decodes VP9 by replacing `nn::codec`'s
video decoder functions with FFmpeg (`host/nn_video.c:734-749`). The front end differs from Hookshot's games:
in Raiders `main` imports 43 `nn::movie` functions that `sdk` defines, and `subsdk0` (NintendoSDK_movie
21.4.4) imports 67 `nn::codec` symbols (`spikes/standalone_summary.py`). Expected chain: `main` → `nn::movie`
(lifted `sdk`) → `subsdk0` (lifted) → `nn::codec` (host). Three `nn::movie` functions are stubbed as
OS-facing. Whether the chain works without talking to a media service over IPC is unknown.
Boots so far used `HOS_NO_MOVIES=1`.

## Read first
- `CLAUDE.md`; `docs/plans/02-gap-analysis.md` §11
- `host/nn_video.c` header comment (how the movie library uses the decoder) and the HLE list; the meaning of
  `HOS_NO_MOVIES` and `HOS_VIDEO_LOG` (`grep -rn "HOS_NO_MOVIES\|HOS_VIDEO_LOG" host`)
- `grep "2nn5movie" work/standalone_stubbed.txt` and `grep "2nn5movie" work/imports_raiders.txt`
- `docs/design.md` §5 (movies row) and §9 (S4: movies in Hookshot's game)

## Scope
1. A clip plays in its menu at normal speed with correct colours.
2. The three stubbed `nn::movie` functions and anything else the trace flags in this path.
3. `HOS_NO_MOVIES=1` keeps working as a skip.

## Non-goals
- Neural movie upscaling (the clips are small UI previews). AV1 (not used by Raiders). Audio tracks in
  movies unless a clip turns out to have one. H.264/AAC decoders unless the log shows them called.

## Steps
1. Find where the clips are shown: with the user, the menu path to a gadget preview; add it to an input
   script (`games/raiders/scripts/gadget_movie.txt`).
2. Run without `HOS_NO_MOVIES`, with `HOS_VIDEO_LOG=1` and `HOS_TRACE=1` for the movie screen only (trace is
   verbose: keep the run short). Read the log for: `nn::movie` stub first-calls; `nn::codec` decoder
   lifecycle (`InitializeVp9Decoder*`, `Register*Buffer`, `Submit*`, `Acquire*`); any IPC attempt
   (`ConnectToNamedPort`, `sm:` lookups for a media service).
3. Cases:
   - The chain reaches `nn::codec` and frames decode: check presentation (how decoded images reach NVN:
     `ReadDecoderOutputImageRgba/Nv12` copies versus a native image handle
     (`AcquireVp9DecoderOutputBuffer` returns a `gs::NativeSyncHandle`); colour space; timing against the
     clip's timestamps).
   - The chain stops in `nn::movie` (lifted `sdk`) at a service call: replace at the lowest `nn::movie` level
     that keeps `subsdk0` running as lifted code, or, if `sdk`'s `nn::movie` is itself the player, HLE the
     small set the game uses (`MediaExtractor`, `MediaProperty`, buffers: the 43 imports) on FFmpeg's
     demuxer. Choose the smaller surface and justify it in the report.
   - A stub returns a wrong answer: implement it.
4. Looping and teardown: open and close the preview ten times in one run; decoder and pool objects are
   released (`FinalizeVp9Decoder`, `FinalizeDecoderImagePool` counts match initialisations).
5. Tests: source-level tests for new HLEs.

## Pitfalls
- FFmpeg must be built with VP9 (`scripts/linux/deps.sh` builds libavcodec with dav1d for AV1 and "VP8 / VP9
  too"): confirm `ffmpeg/` in `~/raiders/deps` has the VP9 decoder (`strings libavcodec.a | grep -c vp9`).
- The clips are game assets: never copy them off the Deck or the Mac's dump folder; never attach frames to
  a report.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py video movie
scripts/deck/run.sh movie1 240 -- HOS_VIDEO_LOG=1 HOS_INPUT_SCRIPT="$(cat games/raiders/scripts/gadget_movie.txt)" && scripts/deck/fetch.sh movie1
grep -c "VP9" work/runs/movie1/hookshot_log.txt                         # decoder initialised and frames submitted
grep -n "nn5movie.*first call" work/runs/movie1/hookshot_log.txt | wc -l # 0 remaining stubs on this path
ls work/runs/movie1/shots | tail -2                                     # a preview frame is visible in the menu (describe it)
```
User check: a gadget preview plays smoothly at normal speed and loops.

## Report
`docs/plans/reports/T19-movies.md`: the observed call chain, which case applied, what was implemented,
frame timing, and whether `Event/Movie/` is referenced at run time in the base game.
