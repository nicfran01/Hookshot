"""(raiders) The Steam Deck scripts (scripts/deck/), read as text: the standalone run starts the game on the standalone lift's
image (work/sa/image/image.bin, the one nx2/make_game.py ships), not the emulator lift's; the default build times each of
its three steps (/usr/bin/time -v: wall time and peak memory) and stops at the first that fails; run.sh --net-check samples
the game's sockets and its classifier (awk) fails a non-loopback peer and lists Unix sockets. The run passes --args
words to the executable after its own arguments and notes the peak resident set (T12: --prepare-shaders), checked by running
the Deck side of run.sh on a stand-in executable. bash -n on each script where bash exists. No Deck, no game files.

    python -I -B tests/test_deck_scripts.py
"""
import os
import shutil
import subprocess
import tempfile
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

    def test_the_run_rejects_odd_args_before_the_deck(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        env = dict(os.environ, DECK_HOST="nobody@invalid.invalid")
        for argv in (["x", "5", "--args"], ["x", "5", "--args", "--prepare-shaders;rm"], ["x", "5", "--args", "$(id)"]):
            r = subprocess.run([bash, str(DECK / "run.sh")] + argv, capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(r.returncode, 2, (argv, r.stderr))   # (usage: before any SSH)

    def test_the_run_passes_args_after_its_own(self):
        bash, timeout = shutil.which("bash"), shutil.which("timeout")
        if not bash or not timeout:
            self.skipTest("no bash or timeout")
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        body = run[run.index("<<'EOS'\n") + len("<<'EOS'\n"):run.rindex("EOS\n")]   # (what runs on the Deck)
        with tempfile.TemporaryDirectory() as tmp:
            root, home = Path(tmp, "r"), Path(tmp, "home")
            exe = root / "work" / "sa" / "build" / "hookshot"
            exe.parent.mkdir(parents=True)
            home.mkdir()
            exe.write_text('#!/bin/sh\nfor a in "$@"; do echo "arg $a"; done\necho "env $HOS_ENV_FILE"\n')
            exe.chmod(0o755)
            r = subprocess.run([bash, "-s", "--", str(root), "t1", "20", "0", "0", "0", "--prepare-shaders --x", "A=1"],
                               input=body, capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = root / "work" / "runs" / "t1"
            args = [l[4:] for l in (out / "hookshot_log.txt").read_text().splitlines() if l.startswith("arg ")]
            self.assertEqual(args, [str(root / "work/sa/image/image.bin"), "--romfs", str(root / "dump/romfs"), "--user",
                                    str(home / ".local/share/raiders-recomp"), "--prepare-shaders", "--x"])
            self.assertIn("A=1", (out / "env.txt").read_text().splitlines())
            if shutil.which("python3"):
                self.assertRegex((out / "peak_rss_kb.txt").read_text(), r"^\d+\n$")
            self.assertIn("exited with 0", r.stdout)
            r = subprocess.run([bash, "-s", "--", str(root), "t2", "20", "0", "0", "0", ""], input=body, capture_output=True,
                               text=True, env=dict(os.environ, HOME=str(home)), timeout=60)   # (no --args: as before)
            self.assertEqual(r.returncode, 0, r.stderr)
            args = [l for l in (root / "work/runs/t2/hookshot_log.txt").read_text().splitlines() if l.startswith("arg ")]
            self.assertEqual(len(args), 5, args)

    def test_the_window_finds_the_wayland_desktop(self):   # (raiders, T13: a windowed run started over SSH)
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        window = run[run.index('if [ "$window" = 1 ]; then\n    export DISPLAY'):]
        window = window[:window.index("\nfi\n") + 4]
        self.assertIn('[ -S "$XDG_RUNTIME_DIR/wayland-0" ]; then export WAYLAND_DISPLAY=wayland-0; fi', window)
        self.assertIn('[ -z "${WAYLAND_DISPLAY:-}" ]', window)   # (one the caller set wins)

    def test_the_scripts_parse(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        for script in sorted(DECK.glob("*.sh")):
            r = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (script.name, r.stderr))

    # (raiders, T10) run.sh --net-check: the game's sockets every 5 s into net.txt
    def test_the_net_check_option(self):
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        self.assertIn("--net-check) netcheck=1 ;;", run)
        self.assertIn('R=$1 name=$2 secs=$3 sound=$4 window=$5 netcheck=$6 extra=$7; shift 7', run)
        self.assertIn('"$window" "$netcheck" "$extra" ${env[@]+"${env[@]}"}', run)   # (passed in the same order)
        self.assertIn("ss -tuxanpH", run)
        self.assertIn('wait "$game"', run)
        # (a run without the option must still end with status 0: no bare `test && cmd` as the last line)
        body = run[run.index("<<'EOS'"):run.rindex("EOS")]
        self.assertFalse(body.rstrip().split("\n")[-1].lstrip().startswith("["), body.rstrip().split("\n")[-1])

    def test_the_net_check_classifier(self):
        awk = shutil.which("awk")
        if not awk:
            self.skipTest("no awk")
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        block = run[run.index("# net-check classifier BEGIN"):run.index("# net-check classifier END")]
        program = block[block.index("NET_AWK='") + len("NET_AWK='"):block.rindex("'")]
        lines = {
            'tcp ESTAB 0 0 192.168.1.20:41234 140.82.112.5:443 users:(("hookshot",pid=7,fd=9))': "FAIL",
            'tcp ESTAB 0 0 [2001:db8::1]:1 [2606:4700::1111]:443 users:(("hookshot",pid=7,fd=9))': "FAIL",
            'udp ESTAB 0 0 10.0.0.2:5000 10.0.0.9:53 users:(("hookshot",pid=7,fd=9))': "FAIL",
            'tcp ESTAB 0 0 127.0.0.1:5000 127.0.0.1:631 users:(("hookshot",pid=7,fd=9))': "ok",
            'tcp ESTAB 0 0 [::1]:5000 [::1]:631 users:(("hookshot",pid=7,fd=9))': "ok",
            'tcp ESTAB 0 0 [::ffff:127.0.0.1]:1 [::ffff:127.0.0.1]:2 users:(("hookshot",pid=7,fd=9))': "ok",
            'udp UNCONN 0 0 0.0.0.0:5353 0.0.0.0:* users:(("hookshot",pid=7,fd=9))': "ok",
            'tcp LISTEN 0 0 [::]:80 [::]:* users:(("hookshot",pid=7,fd=9))': "ok",
            'u_str ESTAB 0 0 /run/user/1000/wayland-0 1234 * 5678 users:(("hookshot",pid=7,fd=3))': "unix",
        }
        r = subprocess.run([awk, "-v", "t=5", program], input="\n".join(lines) + "\n", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = r.stdout.strip().split("\n")
        self.assertEqual(len(got), len(lines))
        for (line, want), out in zip(lines.items(), got):
            self.assertTrue(out.startswith("t=5s %s " % want), (line, out))


if __name__ == "__main__":
    unittest.main()
