"""(raiders, T19) OS-facing imports a game leaves to the sdk's own code: games/<id>/game.py SDK_LIFTED, read by
nx2/standalone.py sdk_lifted / hle_set.

- hle_set on made-up modules: a game module's nn::movie imports the sdk defines are stubbed with no game (upstream's
  behaviour) and not stubbed with a game that lists them; other stubs are unchanged;
- sdk_lifted stops the lift for a name the sdk does not define, a name the sdk defines as data, and a name host/ replaces;
- Raiders' SDK_LIFTED is the three nn::movie functions, each one os_facing would otherwise stub;
- nx2/lift.py passes the game to hle_set.

No game files.

    python -I -B tests/test_movie_sdk_lifted.py
"""
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))   # (standalone.py imports kit and toolchain by name)

FAILS = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sym(name, defined, type_="func"):
    return {"name": name, "defined": defined, "type": type_ if defined else "notype"}


INIT = "_ZN2nn5movie10InitializeEv"
IS_INIT = "_ZN2nn5movie13IsInitializedEv"
FINI = "_ZN2nn5movie8FinalizeEv"
OTHER = "_ZN2nn3ldn10InitializeEv"     # (an OS-facing import no module defines: stays a stub)
DATA = "_ZN2nn5movie9SomeTableE"        # (not a function)


def modules():
    sdk = types.SimpleNamespace(name="sdk", symbols=[sym(INIT, True), sym(IS_INIT, True), sym(FINI, True),
                                                     sym(DATA, True, "object")])
    main = types.SimpleNamespace(name="main", symbols=[sym(INIT, False), sym(IS_INIT, False), sym(FINI, False),
                                                       sym(OTHER, False)])
    return [main, sdk]


def stops(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def main():
    st = load("standalone", ROOT / "nx2" / "standalone.py")
    st.implemented = lambda host=None: set()   # (host/'s HLE list is the real lift's business, not this test's)
    mods = modules()

    _, stubbed = st.hle_set(mods)
    check(stubbed == {INIT, IS_INIT, FINI, OTHER}, "no game: the three nn::movie imports and ldn are stubbed (upstream)")
    game = types.SimpleNamespace(ID="t", SDK_LIFTED=(INIT, IS_INIT, FINI))
    _, stubbed = st.hle_set(mods, game=game)
    check(stubbed == {OTHER}, "SDK_LIFTED: the three are left to the sdk, ldn is still stubbed")
    _, stubbed = st.hle_set(mods, game=types.SimpleNamespace(ID="t"))
    check(stubbed == {INIT, IS_INIT, FINI, OTHER}, "a game with no SDK_LIFTED: as upstream")

    check(stops(lambda: st.sdk_lifted(mods, types.SimpleNamespace(ID="t", SDK_LIFTED=(OTHER,)))),
          "a name the sdk does not define stops the lift")
    check(stops(lambda: st.sdk_lifted(mods, types.SimpleNamespace(ID="t", SDK_LIFTED=(DATA,)))),
          "a name the sdk defines as data stops the lift")
    check(stops(lambda: st.sdk_lifted(mods, game, hle={INIT})), "a name host/ replaces stops the lift")

    raiders = load("raiders_game", ROOT / "games" / "raiders" / "game.py")
    names = tuple(getattr(raiders, "SDK_LIFTED", ()))
    check(names == (INIT, IS_INIT, FINI), "Raiders' SDK_LIFTED is nn::movie's Initialize, IsInitialized, Finalize")
    check(all(st.os_facing(n) for n in names), "each is one os_facing would stub")
    oot = load("oot_game", ROOT / "games" / "oot" / "game.py")
    check(not getattr(oot, "SDK_LIFTED", None), "Ocarina has none (upstream's stubs unchanged)")

    lift = (ROOT / "nx2" / "lift.py").read_text(encoding="utf-8")
    check("standalone.hle_set(nso.load_exefs(a.exefs), game=cfg)" in lift, "nx2/lift.py passes the game to hle_set")

    print("%d failed" % len(FAILS) if FAILS else "all passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
