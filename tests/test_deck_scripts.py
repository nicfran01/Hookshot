"""(raiders) The Steam Deck scripts (scripts/deck/), read as text: the standalone run starts the game on the standalone lift's
image (work/sa/image/image.bin, the one nx2/make_game.py ships), not the emulator lift's; the default build times each of
its three steps (/usr/bin/time -v: wall time and peak memory) and stops at the first that fails. bash -n on each script
where bash exists. No Deck, no game files.

    python -I -B tests/test_deck_scripts.py
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "scripts" / "deck"


class DeckScriptTests(unittest.TestCase):
    def test_the_run_takes_the_standalone_image(self):
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        self.assertIn('args=("$R/work/sa/image/image.bin" --romfs "$R/dump/romfs")', run)
        self.assertNotIn("$R/work/image/image.bin", run)
        ship = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
        self.assertIn('os.path.join(work, "sa", "image", "image.bin")', ship)   # (the same file the game folder gets)

    def test_the_build_times_each_step(self):
        build = (DECK / "build.sh").read_text(encoding="utf-8")
        lift = build[build.index("        lift)\n"):build.index("        full)\n")]
        self.assertIn("timed() { /usr/bin/time -v \"$@\"; }", lift)
        steps = [l.strip() for l in lift.splitlines() if l.strip().startswith("timed \"$PY\"")]
        self.assertEqual(len(steps), 3, steps)
        for want, line in zip(("nx2/make_game.py --check", "nx2/lift.py --standalone --write", "nx2/build.py --standalone"), steps):
            self.assertIn(want, line)
        self.assertTrue(steps[0].endswith("&&") and steps[1].endswith("&&"), steps)   # (a failed step stops the next)
        self.assertIn("set -euo pipefail", build)
        self.assertIn('mkdir -p "$OOT_WORK/image"', lift)   # (the chunk boundaries' folder, as make_game.py makes it)
        self.assertLess(lift.index('mkdir -p "$OOT_WORK/image"'), lift.index("nx2/lift.py"))

    def test_the_scripts_parse(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        for script in sorted(DECK.glob("*.sh")):
            r = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (script.name, r.stderr))


if __name__ == "__main__":
    unittest.main()
