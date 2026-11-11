"""(raiders) The button prompts' tool (nx2/prompt_assets.py) on a game with no Pack/ZsDic.pack.zs: zs_dictionary() gives None with
one line, read_zs() then reads plain zstd frames; and a game with no Font2/Scalable/External font has nothing to redraw, so the
tool says so, writes nothing and exits 0 (make_game.py's prompts step is optional: the game shows its own icons). Needs no
fontTools. Synthetic files only, no game files.

    python -I -B tests/test_prompt_assets_nodict.py
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import prompt_assets  # noqa: E402
import zstandard  # noqa: E402


def check_no_dictionary():
    with tempfile.TemporaryDirectory() as romfs:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            d = prompt_assets.zs_dictionary(romfs)
        if d is not None or err.getvalue().strip() != "prompts: no Pack/ZsDic.pack.zs: plain zstd only":
            raise SystemExit("zs_dictionary: %r, said %r" % (d, err.getvalue()))
        data = b"a plain zstd frame " * 50
        os.makedirs(os.path.join(romfs, "System"))
        with open(os.path.join(romfs, "System", "x.zs"), "wb") as f:
            f.write(zstandard.ZstdCompressor(level=3).compress(data))
        if prompt_assets.read_zs(romfs, "System/x.zs", None) != data:
            raise SystemExit("read_zs: a plain frame did not come back without a dictionary")


def check_no_font():
    with tempfile.TemporaryDirectory() as tmp:
        romfs, out = os.path.join(tmp, "romfs"), os.path.join(tmp, "prompts")
        os.makedirs(os.path.join(romfs, "Font"))
        ran = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "nx2" / "prompt_assets.py"), "--romfs", romfs, "--out", out],
                             capture_output=True, text=True)
        if ran.returncode != 0:
            raise SystemExit("no font: exit %d\n%s" % (ran.returncode, ran.stderr))
        if "prompts: nothing to do" not in ran.stderr or os.path.exists(out):
            raise SystemExit("no font: said %r, wrote %s" % (ran.stderr, os.path.exists(out)))


def main():
    check_no_dictionary()
    check_no_font()
    print("prompt assets without Pack/ZsDic.pack.zs or the icon font: ok")


if __name__ == "__main__":
    main()
