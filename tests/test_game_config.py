"""(raiders) The per-game layer: every games/<id>/game.py has its fields, nx2/game.py picks the game of an exefs, and the
version check says upstream's sentences for Ocarina and the game's own TITLE for another.

No dump: the exefs are made here (a main.npdm with only the header and ACI0 that nx2/npdm.py reads, and an NSO header).

python -I -B tests/test_game_config.py
"""
import argparse
import contextlib
import importlib.util
import io
import os
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import game  # noqa: E402

FIELDS = {"ID": str, "TITLE": str, "PROGRAM_ID": int, "BUILDS": dict, "MODULES": tuple, "SDK": str, "LANGUAGES": list,
          "ROMFS_MIN_FILES": (int, type(None)), "ROMFS_MIN_BYTES": (int, type(None)), "ZS_DICTIONARY": (str, type(None)),
          "DATA_DIR": str, "EXE": str, "LIFT_PATCHES": (str, type(None)), "SKIP_PROGRAMS": tuple,
          "VISUAL_WORKAROUNDS": (tuple, type(None)), "PERF_FILES": tuple}
OOT, RAIDERS = 0x0400486024DEC000, 0x0400380020056000
OOT_BUILD, RAIDERS_BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348", "abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5"


def npdm_bytes(program_id):
    """0x400 bytes: META, the ACI0 offset and size at 0x70, and the program id at ACI0+0x10 (nx2/npdm.py's reads)"""
    b = bytearray(0x400)
    b[:4] = b"META"
    struct.pack_into("<IIII", b, 0x70, 0x100, 0x40, 0x200, 0x100)
    b[0x100:0x104] = b"ACI0"
    struct.pack_into("<Q", b, 0x110, program_id)
    return bytes(b)


def nso_header(build_hex):
    h = bytearray(0x60)
    h[:4] = b"NSO0"
    h[0x40:0x40 + len(build_hex) // 2] = bytes.fromhex(build_hex)
    return bytes(h)


class Exefs:
    def __init__(self, program_id=None, build=RAIDERS_BUILD):
        self.tmp = tempfile.TemporaryDirectory(prefix="game-config-")
        self.path = self.tmp.name
        Path(self.path, "main").write_bytes(nso_header(build))
        if program_id is not None:
            Path(self.path, "main.npdm").write_bytes(npdm_bytes(program_id))

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        self.tmp.cleanup()


class Fields(unittest.TestCase):
    def test_every_game_has_every_field(self):
        ids = game.all_ids()
        self.assertEqual(ids, ["oot", "raiders"])
        for gid in ids:
            cfg = game.by_id(gid)
            for name, kind in FIELDS.items():
                self.assertTrue(hasattr(cfg, name), "%s: no %s" % (gid, name))
                self.assertIsInstance(getattr(cfg, name), kind, "%s.%s" % (gid, name))
            self.assertEqual(cfg.ID, gid)
            self.assertTrue(cfg.BUILDS)
            for build, version in cfg.BUILDS.items():
                self.assertRegex(build, r"^[0-9a-f]{40}$", gid)
                self.assertIsInstance(version, str)
            self.assertIn("main", cfg.MODULES)
            for code, name in cfg.LANGUAGES:
                self.assertIsInstance(code, str)
                self.assertIsInstance(name, str)
            self.assertEqual(len({c for c, _ in cfg.LANGUAGES}), len(cfg.LANGUAGES), gid)
            if cfg.VISUAL_WORKAROUNDS is not None:
                self.assertEqual(len(cfg.VISUAL_WORKAROUNDS), 2)
            for key in cfg.SKIP_PROGRAMS:
                self.assertRegex(key, r"^[0-9a-f]{1,16}$")
        self.assertEqual(len({game.by_id(g).PROGRAM_ID for g in ids}), len(ids))

    def test_languages_are_the_runtimes(self):
        # (each code is one host/nn_applet.c's GetDesiredLanguage table knows: a code it does not know becomes en-US)
        src = (ROOT / "host" / "nn_applet.c").read_text(encoding="utf-8")
        table = src[src.index("languages[] = {"):]
        table = table[:table.index("};")]
        known = set(re.findall(r'\{"([A-Za-z0-9-]+)", "', table))
        self.assertEqual(len(known), 16)
        for gid in game.all_ids():
            self.assertEqual({c for c, _ in game.by_id(gid).LANGUAGES} - known, set(), gid)

    def test_ocarina_keeps_upstreams_values(self):
        oot = game.by_id("oot")
        self.assertEqual(oot.TITLE, "Hookshot")
        self.assertEqual((oot.PROGRAM_ID, game.pinned(oot)), (OOT, OOT_BUILD))
        spec = importlib.util.spec_from_file_location("make_game_cfg", ROOT / "nx2" / "make_game.py")
        make_game = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make_game)
        self.assertEqual(oot.LANGUAGES, make_game.LANGUAGES)
        self.assertTrue(game.pinned(oot).startswith(make_game.BUILD_ID))


class Select(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop("HOOKSHOT_GAME", None)
        self.addCleanup(lambda: os.environ.update({"HOOKSHOT_GAME": self.saved}) if self.saved else os.environ.pop("HOOKSHOT_GAME", None))

    def test_by_program_id(self):
        with Exefs(RAIDERS) as d:
            self.assertEqual(game.program_id(d), RAIDERS)
            self.assertEqual(game.select(d).ID, "raiders")
        with Exefs(OOT, OOT_BUILD) as d:
            self.assertEqual(game.select(d).ID, "oot")

    def test_unknown_program_id_names_the_games(self):
        with Exefs(0x0100000000001000) as d, self.assertRaises(SystemExit) as e:
            game.select(d)
        self.assertEqual(str(e.exception), "program id 0100000000001000 is not a supported game (supported: oot, raiders)")

    def test_hookshot_game_wins(self):
        os.environ["HOOKSHOT_GAME"] = "oot"
        with Exefs(RAIDERS) as d:
            self.assertEqual(game.select(d).ID, "oot")
        os.environ["HOOKSHOT_GAME"] = "nope"
        with Exefs(RAIDERS) as d, self.assertRaises(SystemExit) as e:
            game.select(d)
        self.assertEqual(str(e.exception), "HOOKSHOT_GAME=nope is not a supported game (supported: oot, raiders)")

    def test_without_npdm_by_build_else_upstreams_game(self):
        # (upstream's own tests make an exefs of a bare main: it is checked against Ocarina, as before)
        with Exefs(None, RAIDERS_BUILD) as d:
            self.assertIsNone(game.program_id(d))
            self.assertEqual(game.select(d).ID, "raiders")
        with Exefs(None, "01234567") as d:
            self.assertEqual(game.select(d).ID, "oot")
        self.assertEqual(game.select().ID, "oot")


class CheckBuild(unittest.TestCase):
    def test_sentences(self):
        oot, raiders = game.by_id("oot"), game.by_id("raiders")
        # (Ocarina's are upstream's, byte for byte: tests/test_builder_status.py and the builders read them)
        self.assertEqual(game.check_build(oot, OOT_BUILD + "0" * 24),
                         (True, "This is the version Hookshot supports (build e0f3ccfa)."))
        self.assertEqual(game.check_build(oot, "abcdef01" + "0" * 56),
                         (False, "This is build abcdef01. Hookshot supports build e0f3ccfa."))
        self.assertEqual(game.check_build(raiders, RAIDERS_BUILD + "0" * 24),
                         (True, "This is the version Raiders Recomp supports (build abb30e2f)."))
        self.assertEqual(game.check_build(raiders, "12345678" + "0" * 56),
                         (False, "This is build 12345678. Raiders Recomp supports build abb30e2f."))

    def test_make_game_check_line(self):
        spec = importlib.util.spec_from_file_location("make_game_check", ROOT / "nx2" / "make_game.py")
        make_game = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make_game)
        make_game.check_windows_sdk = make_game.check_cpu = lambda: None   # (the compiler probes: not this test's)
        saved = os.environ.pop("HOOKSHOT_GAME", None)
        try:
            for program_id, build, line in ((RAIDERS, RAIDERS_BUILD, "@@check ok This is the version Raiders Recomp supports (build abb30e2f)."),
                                            (RAIDERS, "ffb30e2f" + RAIDERS_BUILD[8:], "@@check bad This is build ffb30e2f. Raiders Recomp supports build abb30e2f."),
                                            (OOT, OOT_BUILD, "@@check ok This is the version Hookshot supports (build e0f3ccfa).")):
                with Exefs(program_id, build) as d, tempfile.TemporaryDirectory() as work:
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        make_game.check(argparse.Namespace(nup=None, exefs=d), work)
                    self.assertEqual(out.getvalue().strip().splitlines()[-1], line)
            with Exefs(0x0100000000001000) as d, tempfile.TemporaryDirectory() as work:
                out = io.StringIO()
                with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                    make_game.check(argparse.Namespace(nup=None, exefs=d), work)
                self.assertIn("@@error program id 0100000000001000 is not a supported game (supported: oot, raiders)", out.getvalue())
        finally:
            if saved:
                os.environ["HOOKSHOT_GAME"] = saved


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=1))
