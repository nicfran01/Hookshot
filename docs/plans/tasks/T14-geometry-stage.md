# T14 · Geometry-stage support (conditional)

**Milestone:** M4/M5 · **Depends on:** T13 · **Trigger:** a report (`M4-first-frame.md`, `M5-gameplay.md`
or `M3-shaders.md` step 5) lists program keys with "dropped stages" that are drawn in normal play **and** a
visible effect is missing or wrong because of it. Without the trigger, skip this task. · **Machine:** Mac
driving the Deck

## Context
`gpu/vk/vk_shader.cpp:2087-2090` (`program_pick`) notes "geometry/tessellation: not translated": a program
with stages 2-4 is built from its vertex and fragment stages only and a "dropped stages" line is logged.
Raiders has 160 unique programs with a geometry stage, all in `Shader/Sample.Nin_Ounce_NVN2.release.sarc.zs`
(`spikes/shader_stage_kinds.py`). No tessellation stages were found.

## Read first
- `CLAUDE.md`; the triggering report; `docs/plans/02-gap-analysis.md` §6
- `gpu/vk/vk_shader.cpp`: `program_pick`, `graphics_key`, the stage translation path for vertex and fragment,
  and how mesh stages were added (lines ~1660-1840) as the model for adding a stage kind
- `gpu/vk/eden/shader_recompiler/`: the Maxwell front end's geometry handling
  (`grep -rn "Geometry" gpu/vk/eden/shader_recompiler --include='*.cpp' --include='*.h' | head -40`),
  `frontend/ampere/lower_to_maxwell.h` (what is stage-specific), `backend/spirv` geometry emission
- `gpu/PROVENANCE.md` (the NVN2 control section layout: stage at `+0x56`)
- Prior art to check before writing anything: does Eden (Switch 2 path), Lichii or Eglantine translate Ampere
  geometry stages? If one does, port that (licence permitting: GPL-3.0-or-later is compatible; record the
  source and commit in the file header).

## Scope
1. Decide with evidence whether to implement or skip: which effects use these programs, how often they draw.
2. If implementing: lower and translate stage 2, create pipelines with a geometry stage, key programs by all
   three stages.
3. If skipping: document the visual consequence and add the program keys to the game config's skip list only
   if drawing without the geometry stage produces garbage rather than nothing.

## Non-goals
- Tessellation (no evidence it is used). Geometry stages combined with mesh programs.
- Performance tuning of geometry pipelines.

## Steps
1. Evidence: for each triggering key, find the archive entry name (the census can print names:
   extend `spikes/shader_stage_kinds.py` locally) and what the pass draws (`RX_VK_DUMP` of one frame around
   it). Decide implement or skip with the user if the effect is cosmetic.
2. Offline first: dump the geometry stages (`RX_VK_DUMP_FAILED` does not cover dropped stages; add a
   `(raiders)` switch `RX_VK_DUMP_DROPPED=<dir>` beside it) and run them through `nx2/lower_test.py` /
   `gpu/shadertool.cpp` until all 160 lower and translate to valid SPIR-V
   (`scripts/validate_spirv.py`).
   - What is geometry-specific in the lowering: input primitive type, output primitive type and max
     vertices (from the control section or the program header: find where the Maxwell path reads them from
     the SPH and what NVN2's header provides), `EmitVertex`/`EndPrimitive` opcodes, per-vertex input arrays,
     layer and viewport outputs.
3. Runtime: `program_pick` keeps `stage_code[2]`; `graphics_key` includes it; variants are cached with it;
   pipeline creation adds `VK_SHADER_STAGE_GEOMETRY_BIT`. The Deck's GPU supports geometry shaders
   (check `geometryShader` in `vulkaninfo`; record it).
   - Pitfall: the program cache (`hookshot_programs.bin`) keys by `codes[4]`
     (`{vertex or compute, fragment, 0, 0}` today): use a free slot for the geometry key and bump whatever
     version field invalidates old caches.
   - Pitfall: tests read `vk_shader.cpp` by text (`grep -rln vk_shader tests | wc -l`). Keep `program_pick`'s
     shape; add helpers.
4. Tests: a game-free test that feeds a tiny hand-written Maxwell geometry program through the path if the
   recompiler's test harness allows it (see `nx2/test_mesh_first_types.py` for how mesh was tested);
   otherwise a source-level test that the stage is no longer dropped.
5. Deck check: the effect renders; `M3-shaders.md`-style count of geometry programs translated.

## Acceptance criteria
```bash
.venv/bin/python -I -B tests/run_all.py vk_shader mesh geometry
scripts/deck/build.sh && scripts/deck/run.sh geom1 240 -- <the input script that reaches the effect> && scripts/deck/fetch.sh geom1
grep -c "dropped stages" work/runs/geom1/hookshot_log.txt            # 0 for the triggering keys
grep -ci "device lost\|validation" work/runs/geom1/hookshot_log.txt  # 0
```
For the skip outcome: the report exists and the user has agreed.

## Report
`docs/plans/reports/T14-geometry.md`: the evidence and decision; if implemented, what was ported from where
(with licence), the lowering changes, cache-key change, pass rate over the 160 programs; upstream PR
candidate (this is generic).
