"""(raiders) The romfs floor (nx2/romfs_check.py): a whole folder passes; one with too few files or bytes fails with the counts found
and expected and "Copy the romfs again"; *.part files, dotfiles and dot folders are not counted; a game with no floor (upstream's)
is not checked. make_game.py checks it right after the build check, before the lift. Temporary folders only, no game files.

    python -I -B tests/test_romfs_check.py
"""
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import game  # noqa: E402
import romfs_check  # noqa: E402


def tree(root, files):
    """files: {relative path: size in bytes}"""
    for rel, size in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"\0" * size)


def cfg(files, size, title="Test Game"):
    return types.SimpleNamespace(TITLE=title, ROMFS_MIN_FILES=files, ROMFS_MIN_BYTES=size)


GAME = {"Pack/a.pack.zs": 100, "Shader/b.bfsha.zs": 200, "Effect/c.zs": 300, "System/d.txt": 50}


class RomfsCheckTests(unittest.TestCase):
    def test_summary_skips_part_and_dotfiles(self):
        with tempfile.TemporaryDirectory() as romfs:
            tree(romfs, dict(GAME, **{"Effect/c.zs.part": 2048, ".DS_Store": 6148, "Shader/.hidden": 9,
                                      ".hookshot_marks/e.zs": 4096}))
            self.assertEqual(romfs_check.summary(romfs), (4, 650))

    def test_ok(self):
        with tempfile.TemporaryDirectory() as romfs:
            tree(romfs, GAME)
            ok, text = romfs_check.check(cfg(4, 650), romfs)
            self.assertTrue(ok, text)
            self.assertTrue(text.startswith("files 4, ") and text.endswith(": ok"), text)

    def test_too_few_files(self):
        with tempfile.TemporaryDirectory() as romfs:
            tree(romfs, GAME)
            ok, text = romfs_check.check(cfg(5, 0), romfs)
            self.assertFalse(ok)
            self.assertIn("4 files (Test Game expects at least 5)", text)
            self.assertIn("Copy the romfs again.", text)
            self.assertNotIn("bytes", text)

    def test_too_few_bytes(self):
        with tempfile.TemporaryDirectory() as romfs:
            tree(romfs, GAME)
            ok, text = romfs_check.check(cfg(4, 651), romfs)
            self.assertFalse(ok)
            self.assertIn("650 bytes", text)
            self.assertIn("expects at least 651", text)
            self.assertIn("Copy the romfs again.", text)

    def test_a_part_file_does_not_make_up_the_count(self):
        with tempfile.TemporaryDirectory() as romfs:
            tree(romfs, dict(GAME, **{"Effect/f.zs.part": 5000}))
            ok, text = romfs_check.check(cfg(5, 0), romfs)
            self.assertFalse(ok, text)
            ok, text = romfs_check.check(cfg(0, 651), romfs)
            self.assertFalse(ok, text)

    def test_no_floor_is_not_checked(self):
        for floors in ((0, 0), (None, None)):
            ok, text = romfs_check.check(cfg(*floors), "/no/such/romfs")
            self.assertTrue(ok, text)

    def test_missing_folder(self):
        ok, text = romfs_check.check(cfg(1, 0), "/no/such/romfs")
        self.assertFalse(ok)
        self.assertIn("copy the romfs again", text)

    def test_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            romfs = os.path.join(tmp, "romfs")
            tree(romfs, GAME)
            out = io.StringIO()
            old = os.environ.get("HOOKSHOT_GAME")
            os.environ["HOOKSHOT_GAME"] = "raiders"
            try:
                with contextlib.redirect_stdout(out):
                    code = romfs_check.main([romfs])
            finally:
                if old is None:
                    os.environ.pop("HOOKSHOT_GAME")
                else:
                    os.environ["HOOKSHOT_GAME"] = old
            self.assertEqual(code, 1)
            self.assertIn("4 files (Raiders Recomp expects at least 46000)", out.getvalue())

    def test_the_games_floors(self):
        raiders, oot = game.by_id("raiders"), game.by_id("oot")
        self.assertGreater(raiders.ROMFS_MIN_FILES, 0)
        self.assertGreater(raiders.ROMFS_MIN_BYTES, 0)
        self.assertIsNone(oot.ROMFS_MIN_FILES)
        self.assertIsNone(oot.ROMFS_MIN_BYTES)

    def test_make_game_checks_before_the_lift(self):
        body = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
        main = body[body.index("def main("):]
        build, romfs, lift = (main.index("    check_supported_build(exefs)\n"), main.index("    check_romfs(exefs, romfs)"),
                              main.index('say("stage", "lift"'))
        self.assertLess(build, romfs)
        self.assertLess(romfs, lift)
        self.assertIn("_romfs_check.check(select_game(exefs), romfs)", body)


if __name__ == "__main__":
    unittest.main()
