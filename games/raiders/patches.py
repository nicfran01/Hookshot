"""(raiders) Splatoon Raiders' lift-time patches (games/raiders/game.py LIFT_PATCHES): none. The same three hooks as
games/oot/patches.py, each doing nothing, so the lift runs no other game's patch. A patch for this game goes here."""


def install(L, img):
    """Before discovery: nothing to add to the lifter"""


def supported(meta, standalone):
    """No build has required edits"""
    return False


def edit_c(gen, stats, supported, whole):
    """After the C is written: nothing to edit"""
