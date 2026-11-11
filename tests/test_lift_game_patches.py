"""(raiders) The lift's game patches go through the per-game layer (games/<id>/patches.py, nx2/game.py patches) and Ocarina's
are exactly what nx2/lift.py and nx2/chunks.py did before: oot_wide, oot_jitter, oot_occlusion installed in that order with
(L, img); oot_patches.apply(gen, protect_hearts=supported, required=supported and whole) with supported the standalone lift of
oot_patches.LIFE_BUILD_ID. Raiders' hooks do nothing. The oot_* modules are stand-ins here (sys.modules), so the calls
are what is checked, not their effect; no game files. Also: the game's identity in hos_image.c, and games/ in the lift key.

    python -I -B tests/test_lift_game_patches.py
"""
import importlib.util
import os
import re
import struct
import sys
import tempfile
import types
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(1, str(ROOT / "third_party" / "a64-kit" / "tools"))
import game  # noqa: E402
import oot_patches  # noqa: E402  (the real one: its LIFE_BUILD_ID)

LIFE = oot_patches.LIFE_BUILD_ID


def fakes(calls):
    """Stand-ins for the oot_* modules: each records (name, args)"""
    def module(name, *funcs):
        m = types.ModuleType(name)
        for f in funcs:
            setattr(m, f, lambda *a, _n=name + "." + f, **k: calls.append((_n, a, k)))
        return m
    out = {n: module(n, "install") for n in ("oot_wide", "oot_jitter", "oot_occlusion")}
    fake = module("oot_patches", "apply")
    fake.LIFE_BUILD_ID = LIFE
    out["oot_patches"] = fake
    return out


def meta(build):
    return {"modules": [{"name": "rtld", "build_id": "00" * 20}, {"name": "main", "build_id": build}]}


class GamePatchesTests(unittest.TestCase):
    def test_the_games_modules(self):
        self.assertEqual(game.by_id("oot").LIFT_PATCHES, "games.oot.patches")
        self.assertEqual(game.by_id("raiders").LIFT_PATCHES, "games.raiders.patches")
        for gid in game.all_ids():
            p = game.patches(game.by_id(gid))
            for hook in ("install", "supported", "edit_c"):
                self.assertTrue(callable(getattr(p, hook)), (gid, hook))
        self.assertIs(game.patches(game.by_id("oot")), game.patches(game.by_id("oot")))   # (loaded once)

    def test_no_patches_and_a_bad_name(self):
        none = game.patches(types.SimpleNamespace(LIFT_PATCHES=None))
        self.assertIsNone(none.install(object(), object()))
        self.assertFalse(none.supported(meta(LIFE), True))
        self.assertIsNone(none.edit_c("gen", Counter(), True, True))
        for bad in ("os.path", "games.nothere.patches", "games..x"):
            with self.assertRaises(SystemExit):
                game.patches(types.SimpleNamespace(LIFT_PATCHES=bad))

    def test_ocarina_installs_upstreams_three_in_order(self):
        calls, L, img = [], object(), object()
        with mock.patch.dict(sys.modules, fakes(calls)):
            game.patches(game.by_id("oot")).install(L, img)
        self.assertEqual(calls, [("oot_wide.install", (L, img), {}), ("oot_jitter.install", (L, img), {}),
                                 ("oot_occlusion.install", (L, img), {})])

    def test_ocarina_gate_is_upstreams(self):
        p = game.patches(game.by_id("oot"))
        for build, standalone, want in ((LIFE, True, True), (LIFE, False, False), ("ab" * 20, True, False),
                                        ("", True, False)):
            self.assertIs(p.supported(meta(build), standalone), want, (build, standalone))
        self.assertFalse(p.supported({"modules": [{"name": "sdk", "build_id": LIFE}]}, True))
        self.assertEqual(LIFE, game.pinned(game.by_id("oot")))   # (the pin and the patches' build agree)

    def test_ocarina_edit_c_is_upstreams_apply(self):
        p = game.patches(game.by_id("oot"))
        for supported in (True, False):
            for whole in (True, False):
                calls = []
                with mock.patch.dict(sys.modules, fakes(calls)):
                    p.edit_c("gen", Counter(), supported, whole)
                self.assertEqual(calls, [("oot_patches.apply", ("gen",),
                                          {"protect_hearts": supported, "required": supported and whole})])

    def test_raiders_runs_nothing(self):
        p, calls = game.patches(game.by_id("raiders")), []
        with mock.patch.dict(sys.modules, fakes(calls)):
            p.install(object(), object())
            self.assertFalse(p.supported(meta(LIFE), True))
            p.edit_c("gen", Counter(), True, True)
        self.assertEqual(calls, [])

    def test_chunks_edit_c(self):
        import chunks
        with tempfile.TemporaryDirectory() as d:
            for patches, want in ((None, [("oot_patches.apply", (d,), {"protect_hearts": True, "required": False})]),
                                  (game.patches(game.by_id("oot")),
                                   [("oot_patches.apply", (d,), {"protect_hearts": True, "required": False})]),
                                  (game.patches(game.by_id("raiders")), [])):
                calls = []
                with mock.patch.dict(sys.modules, fakes(calls)), mock.patch("a64_lift.group_marks") as marks:
                    chunks.edit_c(d, Counter(), True, False, patches=patches)
                self.assertEqual(calls, want, patches)
                marks.assert_called_once()   # (the groups for every game: not a game's patch)

    def test_lift_reaches_them_through_the_game(self):
        src = (ROOT / "nx2" / "lift.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*(import|from)\s+oot_", src, re.M))
        self.assertNotIn("oot_patches", src)
        self.assertIn("cfg = _game.select(a.exefs)", src)
        self.assertIn("patches.install(L, img)", src)
        self.assertIn("chunks.edit_c(gen, L.stats, patches.supported(meta, a.standalone), whole=not a.max_func, patches=patches)",
                      src)
        self.assertLess(src.index("patches.install(L, img)"), src.index("L.discover("))
        chunks_src = (ROOT / "nx2" / "chunks.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*(import|from)\s+oot_", chunks_src, re.M))

    def test_hos_image_has_the_games_identity(self):
        import standalone
        npdm = bytearray(0x400)
        npdm[:4] = b"META"
        struct.pack_into("<IIII", npdm, 0x70, 0x100, 0x40, 0x200, 0x100)
        npdm[0x100:0x104] = b"ACI0"
        struct.pack_into("<Q", npdm, 0x110, game.by_id("raiders").PROGRAM_ID)
        img_meta = {"exports": {}, "modules": [], "base": 0x80000000, "end": 0x90000000}
        with tempfile.TemporaryDirectory() as d:
            exefs, gen = os.path.join(d, "exefs"), os.path.join(d, "gen")
            os.makedirs(exefs)
            os.makedirs(gen)
            with open(os.path.join(exefs, "main.npdm"), "wb") as f:
                f.write(npdm)
            for cfg, ids in ((game.by_id("raiders"), ('"raiders"', '"Raiders Recomp"', '"raiders-recomp"')),
                             (None, ('"raiders"', '"Raiders Recomp"', '"raiders-recomp"')),   # (by main.npdm)
                             (game.by_id("oot"), ('"oot"', '"Hookshot"', '"hookshot"'))):
                env = {k: v for k, v in os.environ.items() if k != "HOOKSHOT_GAME"}
                with mock.patch.dict(os.environ, env, clear=True):
                    standalone.write_image_c(gen, object(), img_meta, exefs, game=cfg)
                with open(os.path.join(gen, "hos_image.c")) as f:
                    text = f.read()
                for name, value in zip(("hos_game_id", "hos_game_title", "hos_game_data_dir"), ids):
                    self.assertRegex(text, r"(?m)^const char %s\[\] = %s;" % (name, re.escape(value)))
                self.assertLess(text.index("hos_main_build_id"), text.index("hos_game_id"))
        self.assertEqual(standalone.c_string('a"b\\c'), '"a\\042b\\134c"')

    def test_a_change_under_games_lifts_again(self):
        spec = importlib.util.spec_from_file_location("make_game_under_test", ROOT / "nx2" / "make_game.py")
        make_game = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make_game)
        with tempfile.TemporaryDirectory() as d:
            exefs, work = os.path.join(d, "exefs"), os.path.join(d, "work")
            os.makedirs(exefs)
            os.makedirs(os.path.join(work, "image"))
            with open(os.path.join(exefs, "main"), "wb") as f:
                f.write(b"NSO0")
            env = {k: v for k, v in os.environ.items() if not k.startswith(("A64_", "OOT_", "RX_"))}
            with mock.patch.dict(os.environ, env, clear=True):
                key = make_game.lift_key(exefs, work, {})
                real_open = open
                changed = str(ROOT / "games" / "raiders" / "patches.py")

                def edited(path, *a, **k):
                    if os.path.abspath(path) == changed:
                        import io
                        return io.BytesIO(b"# an edit\n")
                    return real_open(path, *a, **k)
                with mock.patch("builtins.open", edited):
                    self.assertNotEqual(make_game.lift_key(exefs, work, {}), key)
                self.assertEqual(make_game.lift_key(exefs, work, {}), key)


if __name__ == "__main__":
    unittest.main()
