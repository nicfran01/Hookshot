"""(raiders) Is a romfs folder whole: its file count and bytes against the game's floors (games/<id>/game.py ROMFS_MIN_FILES and
ROMFS_MIN_BYTES). A romfs copied by hand (to a Steam Deck, say) can stop short, and the game then crashes much later over a file
that is not there; this says so before the build.

    python -I nx2/romfs_check.py <romfs> [--exefs <dir>]

prints the files and GiB found and "ok", or what is missing; exits 1 when short. The game is the one of --exefs (nx2/game.py
select; HOOKSHOT_GAME too), by default the exefs beside the romfs. A floor of 0 or None is no floor (upstream's game has none).
Left out of the count: *.part files (an unfinished copy's leftovers) and dotfiles and dot folders (.DS_Store, the builder's own
.hookshot_* marks).

Standard library only (make_game.py imports it).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)   # (python -I leaves the script folder off)

GIB = 1 << 30


def skipped(name):
    """A name that is not the game's: a dotfile or dot folder, or a *.part"""
    return name.startswith(".") or name.endswith(".part")


def summary(romfs):
    """(files, bytes) of the romfs, without *.part, dotfiles and dot folders"""
    files = size = 0
    for top, dirs, names in os.walk(romfs):
        dirs[:] = [d for d in dirs if not skipped(d)]
        for name in names:
            if skipped(name):
                continue
            files += 1
            size += os.path.getsize(os.path.join(top, name))
    return files, size


def check(cfg, romfs):
    """(ok, text): the romfs against cfg.ROMFS_MIN_FILES and cfg.ROMFS_MIN_BYTES (0 or None: not checked)"""
    min_files = getattr(cfg, "ROMFS_MIN_FILES", None) or 0
    min_bytes = getattr(cfg, "ROMFS_MIN_BYTES", None) or 0
    if not min_files and not min_bytes:
        return True, "ok (%s has no romfs floor)" % cfg.TITLE
    if not os.path.isdir(romfs):
        return False, "The romfs folder %s is not there: copy the romfs again." % romfs
    files, size = summary(romfs)
    found = "files %d, %.2f GiB (%d bytes)" % (files, size / GIB, size)
    short = []
    if files < min_files:
        short.append("%d files (%s expects at least %d)" % (files, cfg.TITLE, min_files))
    if size < min_bytes:
        short.append("%d bytes, %.2f GiB (%s expects at least %d, %.2f GiB)" % (size, size / GIB, cfg.TITLE, min_bytes,
                                                                                 min_bytes / GIB))
    if short:
        return False, "The romfs at %s is incomplete: it has %s. Copy the romfs again." % (romfs, " and ".join(short))
    return True, "%s: ok" % found


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("romfs")
    p.add_argument("--exefs", help="the game's exefs (default: the exefs folder beside the romfs)")
    a = p.parse_args(argv)
    import game
    exefs = a.exefs or os.path.join(os.path.dirname(os.path.abspath(a.romfs)), "exefs")
    cfg = game.select(exefs if os.path.isdir(exefs) else None)
    ok, text = check(cfg, a.romfs)
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
