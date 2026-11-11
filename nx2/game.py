"""(raiders) The per-game configuration: which game a dump is, and the data the tools take from it (games/<id>/game.py).

    select(exefs=None)            the game: HOOKSHOT_GAME=<id> when set; else the one whose PROGRAM_ID is exefs/main.npdm's;
                                  with no program id to read (no main.npdm), the one whose BUILDS has main's build id, else
                                  upstream's game (oot, as before there was a choice). An unknown id stops with SystemExit.
    check_build(cfg, build_id)    (ok, the sentence the version check says)
    by_id(id), all_ids()          a game's config; every game's id
    patches(cfg)                  the game's lift-time patches (its LIFT_PATCHES, games/<id>/patches.py): install(L, img),
                                  supported(meta, standalone), edit_c(gen, stats, supported, whole); hooks that do nothing
                                  when it has none
    program_id(exefs)             main.npdm's program id, None without one

Standard library only (make_game.py and the game-free tests import it): the npdm reader is nx2/npdm.py, not dump.py.
The game modules are loaded by path, so python -I needs nothing on sys.path.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(os.path.dirname(HERE), "games")
if HERE not in sys.path:
    sys.path.insert(0, HERE)   # (python -I leaves the script folder off)
import npdm as _npdm  # noqa: E402

DEFAULT = "oot"   # (upstream's game: an exefs with no program id and no known build is checked against it, as before)
_loaded = {}


def all_ids():
    """Every game with a games/<id>/game.py, sorted"""
    return sorted(d for d in os.listdir(GAMES) if os.path.isfile(os.path.join(GAMES, d, "game.py")))


def _unsupported(what):
    return SystemExit("%s is not a supported game (supported: %s)" % (what, ", ".join(all_ids())))


def by_id(game_id):
    """games/<id>/game.py as a module (loaded once)"""
    if game_id not in _loaded:
        if game_id not in all_ids():
            raise _unsupported("game %r" % game_id)
        spec = importlib.util.spec_from_file_location("games_%s_game" % game_id, os.path.join(GAMES, game_id, "game.py"))
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        _loaded[game_id] = cfg
    return _loaded[game_id]


class _NoPatches:
    """A game with LIFT_PATCHES None: the hooks, doing nothing"""
    @staticmethod
    def install(L, img):
        pass

    @staticmethod
    def supported(meta, standalone):
        return False

    @staticmethod
    def edit_c(gen, stats, supported, whole):
        pass


def patches(cfg):
    """cfg.LIFT_PATCHES ("games.<id>.patches", a module under the repository) loaded by path, once; the do-nothing hooks for None"""
    name = getattr(cfg, "LIFT_PATCHES", None)
    if not name:
        return _NoPatches
    if name not in _loaded:
        parts = name.split(".")
        if parts[0] != "games" or not all(p.isidentifier() for p in parts):
            raise SystemExit("LIFT_PATCHES %r is not a module under games/" % name)
        path = os.path.join(os.path.dirname(GAMES), *parts) + ".py"
        if not os.path.isfile(path):
            raise SystemExit("LIFT_PATCHES %r: no %s" % (name, path))
        spec = importlib.util.spec_from_file_location("_".join(parts), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _loaded[name] = mod
    return _loaded[name]


def program_id(exefs):
    """exefs/main.npdm's program id (an int), None when there is no main.npdm or it has none"""
    path = os.path.join(exefs, "main.npdm")
    if not os.path.isfile(path):
        return None
    return _npdm.npdm(path).get("program_id")


def _main_build_id(exefs):
    path = os.path.join(exefs, "main")
    try:
        with open(path, "rb") as f:
            head = f.read(0x60)
    except OSError:
        return None
    return head[0x40:0x60].hex() if head[:4] == b"NSO0" else None


def _matches(cfg, main_build_id):
    # (the first 8 digits, as the version check has always compared them: "build e0f3ccfa")
    return any(main_build_id[:8] == b[:8] for b in cfg.BUILDS)


def select(exefs=None):
    """The game config for this exefs (see the docstring at the top)"""
    forced = os.environ.get("HOOKSHOT_GAME")
    if forced:
        if forced not in all_ids():
            raise _unsupported("HOOKSHOT_GAME=%s" % forced)
        return by_id(forced)
    if exefs:
        pid = program_id(exefs)
        if pid is not None:
            for gid in all_ids():
                if by_id(gid).PROGRAM_ID == pid:
                    return by_id(gid)
            raise _unsupported("program id %016X" % pid)
        bid = _main_build_id(exefs)
        if bid:
            for gid in all_ids():
                if _matches(by_id(gid), bid):
                    return by_id(gid)
    return by_id(DEFAULT)


def pinned(cfg):
    """The build the game's tools are made for: the first of its BUILDS"""
    return next(iter(cfg.BUILDS))


def check_build(cfg, main_build_id):
    """(ok, sentence): is main's build id one this game supports. The sentences are the builders' (@@check, make_game.py)"""
    if _matches(cfg, main_build_id):
        return True, "This is the version %s supports (build %s)." % (cfg.TITLE, main_build_id[:8])
    return False, "This is build %s. %s supports build %s." % (main_build_id[:8], cfg.TITLE, pinned(cfg)[:8])
