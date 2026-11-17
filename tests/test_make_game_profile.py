"""(raiders, T20) Game-free: nx2/make_game.py's Steam Deck profile. games/<id>/deck_env.txt becomes the game folder's
hookshot_env.txt with --profile deck, or on SteamOS (/etc/os-release ID=steamos) unless --profile desktop says otherwise;
a hookshot_env.txt already in the folder (the player's) is never replaced; a game without the file gets nothing. The
shipped deck_env.txt holds only lines the game takes from hookshot_env.txt (its own switch names, no paths, host/hos_main.c),
each with the report that set it.

Run with: python -I tests/test_make_game_profile.py
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "nx2" / "make_game.py"
spec = importlib.util.spec_from_file_location("make_game_profile_under_test", SOURCE)
make_game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_game)
DECK_ENV = ROOT / "games" / "raiders" / "deck_env.txt"


class DeckProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "game"
        self.out.mkdir()
        self.steamos = self.dir / "os-release-steamos"
        self.steamos.write_text('NAME="SteamOS"\nID=steamos\nID_LIKE=arch\nVERSION_ID=3.9.5\n')
        self.other = self.dir / "os-release-other"
        self.other.write_text('NAME="Arch Linux"\nID=arch\n')

    def tearDown(self):
        self.tmp.cleanup()

    def profile(self, profile, os_release, game="raiders"):
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            said = make_game.deck_profile(str(self.out), game, profile, str(os_release))
        return said, printed.getvalue()

    def env(self):
        return self.out / "hookshot_env.txt"

    def test_steamos_is_found(self):
        self.assertTrue(make_game.on_steamos(str(self.steamos)))
        quoted = self.dir / "quoted"
        quoted.write_text('ID="steamos"\n')
        self.assertTrue(make_game.on_steamos(str(quoted)))
        self.assertFalse(make_game.on_steamos(str(self.other)))
        self.assertFalse(make_game.on_steamos(str(self.dir / "missing")))

    def test_on_steamos_the_profile_is_written(self):
        said, printed = self.profile(None, self.steamos)
        self.assertEqual(self.env().read_bytes(), DECK_ENV.read_bytes())
        self.assertIn("SteamOS", said)
        self.assertIn("hookshot_env.txt", printed)

    def test_elsewhere_only_when_asked(self):
        self.assertIsNone(self.profile(None, self.other)[0])
        self.assertFalse(self.env().exists())
        said, _ = self.profile("deck", self.other)
        self.assertIn("--profile deck", said)
        self.assertEqual(self.env().read_bytes(), DECK_ENV.read_bytes())

    def test_desktop_wins_over_steamos(self):
        self.assertIsNone(self.profile("desktop", self.steamos)[0])
        self.assertFalse(self.env().exists())

    def test_the_players_file_is_kept(self):
        self.env().write_text("HOS_CORES=4\n")
        said, _ = self.profile("deck", self.steamos)
        self.assertIn("has its own", said)
        self.assertEqual(self.env().read_text(), "HOS_CORES=4\n")

    def test_a_game_without_the_file_gets_nothing(self):
        games = Path(make_game._game.GAMES)
        missing = next(g for g in ("t20-none", "t20-none-2") if not (games / g).exists())
        self.assertIsNone(self.profile("deck", self.steamos, game=missing)[0])
        self.assertFalse(self.env().exists())

    def test_main_passes_the_argument(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('p.add_argument("--profile", choices=("deck", "desktop")', text)
        self.assertIn('deck_profile(out, select_game(exefs).ID, getattr(a, "profile", None))', text)

    def test_the_shipped_profile_is_what_the_game_takes(self):
        lines = DECK_ENV.read_text(encoding="utf-8").splitlines()
        settings = [l for l in lines if l.strip() and not l.lstrip().startswith("#")]
        self.assertTrue(settings)
        names = set()
        for line in settings:
            m = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^\s#]*)", line)
            self.assertTrue(m, line)   # (NAME=VALUE, no trailing comment: the game would read it as part of the value)
            name, value = m.groups()
            self.assertTrue(name.startswith(("RX_", "HOS_", "HOOKSHOT_", "EDEN_", "NVN_", "TOTK_", "SDL_")), line)
            self.assertNotIn(name, ("HOS_ENV_FILE", "SDL_DYNAMIC_API"))
            self.assertFalse(set(value) & set("/\\") or value.startswith("~"), line)   # (no paths: left out by the game)
            self.assertNotIn(name, names, line)
            names.add(name)
        for name in names:   # (each switch is one the game reads)
            src = [ROOT / "host", ROOT / "gpu" / "vk"]
            found = any('"%s"' % name in p.read_text(encoding="utf-8", errors="replace")
                        for d in src for p in d.rglob("*") if p.suffix in (".c", ".cpp", ".h") and p.is_file())
            self.assertTrue(found, name)
        # (every setting cites the report that set it, on the comment line before it)
        for i, line in enumerate(lines):
            if line.strip() and not line.lstrip().startswith("#"):
                self.assertTrue(i > 0 and lines[i - 1].lstrip().startswith("#") and "reports/" in lines[i - 1], line)


if __name__ == "__main__":
    unittest.main()
