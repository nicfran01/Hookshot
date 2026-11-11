"""(raiders) Ocarina of Time's lift-time patches, reached through the per-game layer (games/oot/game.py LIFT_PATCHES; nx2/lift.py
and nx2/chunks.py edit_c call these). Upstream's modules, unchanged, in upstream's order:

    install(L, img)                      before discovery: nx2/oot_wide.py, oot_jitter.py, oot_occlusion.py add C after some
                                         of main's instructions (each checks its sites' words and leaves out what differs)
    supported(meta, standalone)          the gate lift.py had: the standalone lift of main build oot_patches.LIFE_BUILD_ID
    edit_c(gen, stats, supported, whole) after the C is written: nx2/oot_patches.py apply (and through it oot_native_resolution)

The oot_* modules are imported when called, as lift.py and chunks.py did, so this file loads with the standard library alone.
"""


def install(L, img):
    import oot_wide   # (hookshot) widescreen and ultrawide: C after a few of the game's instructions
    oot_wide.install(L, img)
    import oot_jitter   # (the temporal upscalers' camera jitter, DLSS's and FSR 3.1's: none unless one runs, host/rx_backend.c)
    oot_jitter.install(L, img)
    import oot_occlusion   # (no occlusion queries when HOOKSHOT_OCCLUSION_OFF=1: Fritchii's Occlusion Off)
    oot_occlusion.install(L, img)


def supported(meta, standalone):
    import oot_patches
    main_build = next((m["build_id"] for m in meta["modules"] if m["name"] == "main"), "")
    return bool(standalone) and main_build == oot_patches.LIFE_BUILD_ID


def edit_c(gen, stats, supported, whole):
    import oot_patches
    oot_patches.apply(gen, protect_hearts=supported, required=supported and whole)
