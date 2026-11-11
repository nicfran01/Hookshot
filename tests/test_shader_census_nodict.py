"""(raiders) The shader census on a game with no Pack/ZsDic.pack.zs (its .zs files plain zstd): dictionaries() says so in one line
and gives none, unpack() still reads a plain frame, and the whole census runs and writes its HKSEED01 file. With the pack there,
its dictionaries are read as before. Synthetic files only, no game files.

    python -I -B tests/test_shader_census_nodict.py
"""
import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import shader_census as sc  # noqa: E402
import zstandard as zs  # noqa: E402

LINE = "no Pack/ZsDic.pack.zs: plain zstd only"


def sarc(files):
    """A SARC of these files' bytes, as dictionaries() reads one: +0x0c the data start, +0x1a the count, the nodes from +0x20"""
    header = 0x14 + 12 + 16 * len(files) + 8
    nodes, data = b"", b""
    for f in files:
        nodes += struct.pack("<IIII", 0, 0, len(data), len(data) + len(f))
        data += f
    head = b"SARC" + struct.pack("<HHII", 0x14, 0xFEFF, header + len(data), header) + b"\0\1\0\0"
    return head + b"SFAT" + struct.pack("<HHI", 12, len(files), 0x65) + nodes + b"SFNT\x08\0\0\0" + data


def check_no_pack():
    with tempfile.TemporaryDirectory() as romfs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dicts = sc.dictionaries(romfs, zs)
        if dicts != []:
            raise SystemExit("no pack: dictionaries %r, expected []" % (dicts,))
        if out.getvalue().strip() != LINE:
            raise SystemExit("no pack: said %r, expected %r" % (out.getvalue(), LINE))
    data = bytes(range(256)) * 40
    if sc.unpack(zs.ZstdCompressor(level=3).compress(data), [], zs) != data:
        raise SystemExit("unpack: a plain zstd frame did not come back")
    if sc.unpack(data, [], zs) != data:
        raise SystemExit("unpack: data that is not zstd is not given back as it is")


def check_pack_still_read():
    with tempfile.TemporaryDirectory() as romfs:
        os.makedirs(os.path.join(romfs, "Pack"))
        files = [b"first dictionary bytes", b"second"]
        with open(os.path.join(romfs, "Pack", "ZsDic.pack.zs"), "wb") as f:
            f.write(zs.ZstdCompressor().compress(sarc(files)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dicts = sc.dictionaries(romfs, zs)
    if dicts != files or out.getvalue():
        raise SystemExit("with the pack: %r and %r, expected %r and nothing said" % (dicts, out.getvalue(), files))


def check_census_runs():
    with tempfile.TemporaryDirectory() as tmp:
        romfs = os.path.join(tmp, "romfs")
        os.makedirs(os.path.join(romfs, "Shader"))
        with open(os.path.join(romfs, "Shader", "Tiny.bfsha.zs"), "wb") as f:
            f.write(zs.ZstdCompressor().compress(b"no shaders in here" * 8))
        seed = os.path.join(tmp, "seed.bin")
        ran = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "nx2" / "shader_census.py"), romfs, "--out", seed],
                             capture_output=True, text=True)
        if ran.returncode != 0:
            raise SystemExit("census: exit %d\n%s" % (ran.returncode, ran.stdout + ran.stderr))
        lines = ran.stdout.splitlines()
        if lines[0] != LINE or "0 programs from 0 stages" not in lines or "skipped" in ran.stdout:
            raise SystemExit("census said:\n" + ran.stdout)
        with open(seed, "rb") as f:
            if f.read() != b"HKSEED01" + struct.pack("<II", 0, 0):
                raise SystemExit("census: the seed file is not an empty HKSEED01")


def main():
    check_no_pack()
    check_pack_still_read()
    check_census_runs()
    print("shader census without Pack/ZsDic.pack.zs: plain zstd ok")


if __name__ == "__main__":
    main()
