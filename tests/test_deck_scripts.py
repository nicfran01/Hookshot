"""(raiders) The Steam Deck scripts (scripts/deck/), read as text: the standalone run starts the game on the standalone lift's
image (work/sa/image/image.bin, the one nx2/make_game.py ships), not the emulator lift's; the default build times each of
its three steps (/usr/bin/time -v: wall time and peak memory) and stops at the first that fails; run.sh --net-check samples
the game's sockets and its classifier (awk) fails a non-loopback peer and lists Unix sockets. The run passes --args
words to the executable after its own arguments and notes the peak resident set (T12: --prepare-shaders), checked by running
the Deck side of run.sh on a stand-in executable. steam_launch.sh (T15), a Steam shortcut's target, starts the same image
with its switches and, with --raw-deck-pad, takes only the Deck's own controller off Steam's SDL ignore list. T17: a relative
RX_VK_FRAME_LOG / RX_VK_FRAMELOG / HOS_PRESENT_TRACE goes in the run's folder (with the frame log's .go file), --user-from runs
on a copy of a user folder and leaves the original alone, and --rss samples the game's resident set into rss.txt. bash -n on
each script where bash exists. No Deck, no game files.

    python -I -B tests/test_deck_scripts.py
"""
import os
import shutil
import subprocess
import tempfile
import time
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
            r = subprocess.run([bash, "-s", "--", str(root), "t1", "20", "0", "0", "0", "--prepare-shaders --x", "0", "", "A=1"],
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
            r = subprocess.run([bash, "-s", "--", str(root), "t2", "20", "0", "0", "0", "", "0", ""], input=body, capture_output=True,
                               text=True, env=dict(os.environ, HOME=str(home)), timeout=60)   # (no --args: as before)
            self.assertEqual(r.returncode, 0, r.stderr)
            args = [l for l in (root / "work/runs/t2/hookshot_log.txt").read_text().splitlines() if l.startswith("arg ")]
            self.assertEqual(len(args), 5, args)

    # (raiders, T15) steam_launch.sh: a shortcut's run, on the Deck, as run.sh starts the game
    def test_the_steam_launch_runs_like_run(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        script = str(DECK / "steam_launch.sh")
        with tempfile.TemporaryDirectory() as tmp:
            root, home = Path(tmp, "r"), Path(tmp, "home")
            exe = root / "work" / "sa" / "build" / "hookshot"
            exe.parent.mkdir(parents=True)
            home.mkdir()
            exe.write_text('#!/bin/sh\nfor a in "$@"; do echo "arg $a"; done\necho "env $HOS_ENV_FILE"\n'
                           'echo "ignore $SDL_GAMECONTROLLER_IGNORE_DEVICES"\n')
            exe.chmod(0o755)
            env = dict(os.environ, HOME=str(home), DECK_ROOT=str(root), SteamAppId="0", SDL_GAMECONTROLLER_IGNORE_DEVICES="0x28de/0x1205")
            for argv in ([], ["../x"], ["g1", "not-a-switch"]):
                r = subprocess.run([bash, script] + argv, capture_output=True, text=True, env=env, timeout=30)
                self.assertEqual(r.returncode, 2, (argv, r.stderr))
            r = subprocess.run([bash, script, "gyro_b", "B=2"], capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = root / "work" / "runs" / "gyro_b"
            log = (out / "hookshot_log.txt").read_text().splitlines()
            args = [l[4:] for l in log if l.startswith("arg ")]
            self.assertEqual(args, [str(root / "work/sa/image/image.bin"), "--romfs", str(root / "dump/romfs"), "--user",
                                    str(home / ".local/share/raiders-recomp")])
            self.assertIn("env " + str(out / "env.txt"), log)
            switches = (out / "env.txt").read_text().splitlines()
            for want in ("HOS_MOTION_DEBUG=1", "HOS_HANDHELD=1", "HOOKSHOT_NO_UPDATE_CHECK=1", "B=2"):
                self.assertIn(want, switches)
            seen = (out / "steam_env.txt").read_text().splitlines()
            self.assertEqual(seen, ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x28de/0x1205", "SteamAppId=0"])
            self.assertIn("ignore 0x28de/0x1205", log)   # (Steam's list as it was, without --raw-deck-pad)
            # --raw-deck-pad: the Deck's own controller off Steam's list (any case), the rest kept in order
            env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = "0x28de/0x1204,0x28DE/0x1205,0x28de/0x1205,0x054c/0x0ce6"
            r = subprocess.run([bash, script, "gyro_d", "--raw-deck-pad", "C=3"], capture_output=True, text=True, env=env,
                               timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = root / "work" / "runs" / "gyro_d"
            log = (out / "hookshot_log.txt").read_text().splitlines()
            self.assertIn("ignore 0x28de/0x1204,0x054c/0x0ce6", log)
            self.assertIn("C=3", (out / "env.txt").read_text().splitlines())
            self.assertEqual(len([l for l in log if l.startswith("arg ")]), 5)
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        self.assertIn('args=("$R/work/sa/image/image.bin" --romfs "$R/dump/romfs")', run)   # (the same image as run.sh's)

    # (raiders, T17) relative output files in the run's folder, --user-from's copy, --rss's samples
    def test_the_run_keeps_its_outputs_and_the_save_apart(self):
        bash, timeout = shutil.which("bash"), shutil.which("timeout")
        if not bash or not timeout or not shutil.which("pgrep") or not Path("/proc/self/status").exists():
            self.skipTest("no bash, timeout, pgrep or /proc")
        run = (DECK / "run.sh").read_text(encoding="utf-8")
        body = run[run.index("<<'EOS'\n") + len("<<'EOS'\n"):run.rindex("EOS\n")]
        with tempfile.TemporaryDirectory() as tmp:
            root, home, seed = Path(tmp, "r"), Path(tmp, "home"), Path(tmp, "seed")
            exe = root / "work" / "sa" / "build" / "hookshot"
            exe.parent.mkdir(parents=True)
            home.mkdir()
            (seed / "save" / "u").mkdir(parents=True)
            (seed / "save" / "u" / "save.dat").write_bytes(b"old")
            # (the stand-in writes its save through --user, as the game does, and lives long enough for a sample)
            exe.write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do [ "$1" = --user ] && u=$2; echo "arg $1"; shift; done\n'
                           'printf new > "$u/save/u/save.dat"; sleep 6\n')
            exe.chmod(0o755)
            r = subprocess.run([bash, "-s", "--", str(root), "t3", "30", "0", "0", "0", "", "1", str(seed),
                                "RX_VK_FRAME_LOG=frames.csv", "RX_VK_FRAMELOG=framelog", "HOS_PRESENT_TRACE=/abs/p.csv", "B=x"],
                               input=body, capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=90)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = root / "work" / "runs" / "t3"
            env = (out / "env.txt").read_text().splitlines()
            for want in ("RX_VK_FRAME_LOG=%s/frames.csv" % out, "RX_VK_FRAMELOG=%s/framelog" % out, "HOS_PRESENT_TRACE=/abs/p.csv", "B=x"):
                self.assertIn(want, env)
            self.assertTrue((out / "framelog.go").exists())
            self.assertEqual((seed / "save" / "u" / "save.dat").read_bytes(), b"old")   # (the original untouched)
            self.assertEqual((out / "user" / "save" / "u" / "save.dat").read_bytes(), b"new")
            args = [l[4:] for l in (out / "hookshot_log.txt").read_text().splitlines() if l.startswith("arg ")]
            self.assertEqual(args[args.index("--user") + 1], str(out / "user"))
            rss = (out / "rss.txt").read_text().splitlines()
            self.assertRegex(rss[-1], r"^# rss: [1-9]\d* samples every 5 s; peak VmRSS [1-9]\d* kB")
            self.assertRegex(rss[1], r"^\d+ [1-9]\d* [1-9]\d* \d+ \d+$")
            self.assertIn("# rss:", r.stdout)
            r = subprocess.run([bash, "-s", "--", str(root), "t4", "30", "0", "0", "0", "", "0", str(Path(tmp, "nope"))],
                               input=body, capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=60)
            self.assertNotEqual(r.returncode, 0)   # (a missing folder is refused)
            r = subprocess.run([bash, "-s", "--", str(root), "t5", "30", "0", "0", "0", "", "0", str(root / "work/runs/t5/user")],
                               input=body, capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=60)
            self.assertNotEqual(r.returncode, 0)   # (nor one inside the run's folder, which is emptied first)
        bash_env = dict(os.environ, DECK_HOST="nobody@invalid.invalid")
        for argv in (["x", "5", "--user-from"], ["x", "5", "--user-from", "rel/dir"], ["x", "5", "--user-from", "/a;b"]):
            r = subprocess.run([bash, str(DECK / "run.sh")] + argv, capture_output=True, text=True, env=bash_env, timeout=30)
            self.assertEqual(r.returncode, 2, (argv, r.stderr))   # (usage: before any SSH)

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
        self.assertIn('R=$1 name=$2 secs=$3 sound=$4 window=$5 netcheck=$6 extra=$7 rss=$8 userfrom=$9; shift 9', run)
        self.assertIn('"$window" "$netcheck" "$extra" "$rss" "$userfrom" ${env[@]+"${env[@]}"}', run)   # (passed in the same order)
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

    # (raiders, T20) mem_report.sh: the Deck side, on a stand-in game process with stand-in /proc and /sys files and log lines
    def test_the_memory_report(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        script = (DECK / "mem_report.sh").read_text(encoding="utf-8")
        body = script[script.index("<<'EOS'") + len("<<'EOS'"):script.rindex("EOS\n")].split("\n", 1)[1]
        self.assertIn("# mem-report sampler BEGIN", body)
        self.assertIn("# mem-report log reader BEGIN", body)
        self.assertIn('"$R" "$name" "$wait_s" "$every"', script)   # (passed in the order the Deck side reads them)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, proc, drm = tmp / "r", tmp / "proc", tmp / "drm"
            run = root / "work" / "runs" / "m1"
            run.mkdir(parents=True)
            other = proc / "4321"   # (another game's run: not this one)
            other.mkdir(parents=True)
            (other / "comm").write_text("hookshot\n")
            (other / "environ").write_bytes(b"HOS_ENV_FILE=" + str(run.parent / "m0" / "env.txt").encode() + b"\0")
            p = proc / "1234"   # (the game: found by its name and its run's env file)
            (p / "fd").mkdir(parents=True)
            (p / "fdinfo").mkdir()
            (p / "comm").write_text("hookshot\n")
            (p / "environ").write_bytes(b"A=1\0HOS_ENV_FILE=" + str(run / "env.txt").encode() + b"\0")
            (p / "status").write_text("VmRSS:\t6000000 kB\nVmSwap:\t0 kB\nRssAnon:\t2000000 kB\nRssFile:\t500000 kB\n"
                                      "RssShmem:\t3500000 kB\n")
            (p / "smaps").write_text("7f00-7f10 rw-s 00000000 00:01 5 /memfd:hookshot-guest (deleted)\nRss: 3500000 kB\n"
                                     "5600-5700 r-xp 00000000 00:01 6 /home/deck/raiders/work/sa/build/hookshot\nRss: 400000 kB\n"
                                     "7e00-7e10 rw-p 00000000 00:00 0 \nRss: 2100000 kB\n")
            fdinfo = ("drm-client-id:\t3\ndrm-total-gtt:\t1000 KiB\ndrm-shared-gtt:\t1400 MiB\ndrm-resident-gtt:\t2867200 KiB\n"
                      "drm-total-vram:\t5000 KiB\ndrm-resident-vram:\t921600 KiB\ndrm-memory-vram:\t1 KiB\n")   # (as amdgpu writes it)
            for fd in ("5", "6"):   # (two descriptors of one client: counted once)
                os.symlink("/dev/dri/renderD128", str(p / "fd" / fd))
                (p / "fdinfo" / fd).write_text(fdinfo)
            os.symlink("/dev/null", str(p / "fd" / "1"))
            (proc / "meminfo").write_text("MemTotal: 15153000 kB\nMemAvailable: 9000000 kB\nSwapTotal: 15964000 kB\n"
                                          "SwapFree: 15964000 kB\n")
            dev = drm / "card1" / "device"
            dev.mkdir(parents=True)
            (dev / "mem_info_vram_used").write_text("%d\n" % (900 << 20))
            (dev / "mem_info_gtt_used").write_text("%d\n" % (2900 << 20))
            (run / "hookshot_log.txt").write_text("\n".join((
                "[hos Presentation Thread] vk: VRAM: 1505 MB used of 5235 MB allowed (190 MB of it free in the blocks); "
                "textures 1062 MB (budget 2560 MB), 1641 textures",
                "[hos Presentation Thread] vk: textures: decoded ASTC 32 MB, rendered 502 MB (28 drawn in one frame, kept: "
                "14803 KB), other 472 MB; used in the last 8 presents 611 MB",
                "[hos Presentation Thread] vk: render target images: 23 reused from the pool, 195 made new, 109 destroyed "
                "from it; it holds 3 (41 MB)",
                "[hos Presentation Thread] vk: VRAM: 1400 MB used of 5235 MB allowed (10 MB of it free in the blocks); "
                "textures 900 MB (budget 2560 MB), 1500 textures",
                "[hos Presentation Thread] vk: status: 600 frames, the slowest 61.2 ms; VRAM 1.5 of 5.1 GB",
                "[hos Presentation Thread] vk: over the driver's video-memory allowance (5.2 of 5.1 GB)", "")))
            deck_side = tmp / "deck_side.sh"
            deck_side.write_text(body)
            r = subprocess.Popen([bash, str(deck_side), str(root), "m1", "10", "1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=dict(os.environ, MEM_PROC=str(proc), MEM_SYSDRM=str(drm)))
            time.sleep(3.5)
            shutil.rmtree(p)   # (the game ends)
            out, err = r.communicate(timeout=30)
            self.assertEqual(r.returncode, 0, err)
            # 6000000 + 0 + 921600 + 2867200 - 1433600 kB = 8355200 kB, 8159 MB
            self.assertIn("peak footprint 8159 MB", out)
            self.assertIn("(VmRSS 5859 + VmSwap 0 + VRAM 900 + GTT 2800 - shared GTT 1400)", out)
            self.assertIn("within, headroom", out)
            self.assertIn("peak RSS 5859 MB (RssShmem, the guest's, peak 3418 MB); peak VmSwap 0 MB", out)
            self.assertIn("own 900 + 2800 MB; whole GPU 3800 MB", out)
            self.assertIn("min MemAvailable 8789 MB", out)
            self.assertIn("guest 3500000 exe 400000 vk_so 0 image 0 driver 0 dri 0 files 0 anon 2100000", out)
            self.assertIn("texture cache: peak 1062 MB of its 2560 MB budget (VRAM 1505 of 5235 MB then); last 900 of 2560 MB; 2 lines", out)
            self.assertIn("decoded ASTC 32 MB, rendered 502 MB, other 472 MB", out)
            self.assertIn("render-target pool: at most 41 MB", out)
            self.assertIn("last vk: status: VRAM 1.5 of 5.1 GB", out)
            self.assertIn("over-allowance warnings: 1; allocation-failure lines: 0", out)
            samples = [l for l in (run / "mem.txt").read_text().splitlines() if not l.startswith("#")]
            self.assertGreaterEqual(len(samples), 2)
            self.assertEqual(samples[0].split()[13], "8355200")


if __name__ == "__main__":
    unittest.main()
