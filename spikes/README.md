# Spikes

Throwaway scripts written during planning to answer feasibility questions. They are not production code and
nothing depends on them. Each imports Hookshot's tools from the repository's own `nx2/` (since T01; during
planning they read a study clone at `refs/Hookshot/nx2`, which T01 removed). Run them from the repository root.
The `refs/Hookshot/...` commands in the last table are the record of what was run during planning.

All were run on 2026-11-10 against the dump at
`/Users/nick/Downloads/Splatoon Raiders Switch 2 NSP BASE GAME` with Hookshot `88b554e`.
Outputs that contain game-derived data went to `work/` (gitignored); the scripts themselves contain none.

Common setup:

```bash
python3 -m venv .venv && .venv/bin/pip install lz4 numpy capstone zstandard
export OOT_WORK="$PWD/work" OOT_DUMP="<folder holding exefs/ and romfs/>"
```

| Spike | Question | What it proved |
|---|---|---|
| `shader_census_nodict.py` (removed by T05: `nx2/shader_census.py` now does this itself) | Does Hookshot's shader walk read Raiders' archives once the `Pack/ZsDic.pack.zs` requirement is removed? | Yes. 22,042 programs from 26,960 stages in 2 s. The only blocker was the hard `open()` of `ZsDic.pack.zs` in `nx2/shader_census.py:dictionaries`. Raiders' `.zs` files are plain zstd. |
| `shader_stage_kinds.py` | Which archives hold geometry, tessellation, task or mesh stages? | All 440 geometry programs (160 unique) and the single fragment+mesh program are in `Shader/Sample.Nin_Ounce_NVN2.release.sarc.zs`. The material shader `Hoian_UBER`, agl, gsys and the particle sets are vertex+fragment or compute only. No task stage anywhere. |
| `standalone_summary.py` | What would the standalone lift hook and stub? Who defines `nn::movie`? | 528 HLE functions, 279 OS-facing imports stubbed (Hookshot's own game: 485 and 243). `sdk` defines 604 `nn::movie` symbols, `main` imports 43 of them, `subsdk0` (NintendoSDK_movie 21.4.4) imports 67 `nn::codec` symbols. 22 sdk NVN exports route to `host/nvn2.c`. |
| `nvn_names.py` | Which `nvn*` entry-point names does `main` carry? | 734 names (66 DLSS or mesh/task). 427 are in `host/nvn_native.c`'s table; 325 are not (list: `work/nvn_missing.txt`). The list is the full name table the game loads, not what it calls: only a runtime trace says which are used. |
| `strings_probe.py` | Engine and middleware identification. | SDK/NVN 21.4.4; sead, agl, gsys, phive, Havok 2025.1, G3d2, Vfx2, Ui2d, Font, SMAA for NDSR, Pia 7.2.0 (Local, Lan, Nplnd), NPLN 1.47.0, libcurl; `subsdk0` is NintendoSDK_movie 21.4.4. |
| `bntx_formats.py` | How much texture data is ASTC? | 35,255 BNTX files: BC4 16,793, BC1 9,493, BC5 7,494, ASTC 4x4 1,213, BC6H 166, BC7 66, others 30. About 3.4% of files are ASTC. (Format codes mapped from the public BNTX layout: type byte at `BRTI+0x1c`.) |

Not a spike script, but run the same day with Hookshot's own tools, unmodified:

| Command | Result |
|---|---|
| `python -I refs/Hookshot/nx2/dump.py --dump <dump>` | Switch 2 by all seven signals; ids, modules, services (see `docs/plans/01-research-findings.md`). |
| `python -I refs/Hookshot/nx2/lift.py` (discovery and coverage only, no `--write`) | 258,115 functions, 18,409,608 instructions, 100.0000% translated, 987 jump tables, 0 `BR` without a table. 37 s on an Apple M2. Log: `work/lift_coverage.log`. |
| `python -I refs/Hookshot/nx2/imports.py --hle work/hle_names.txt --list` | 1,336 sdk symbols imported by `main` and `subsdk0` (list: `work/imports_raiders.txt`). |
