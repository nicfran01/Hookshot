"""(raiders) scripts/census_filter.py: a census copy without its largest programs reads back with the same stage bytes,
the stages only the dropped programs used are gone and the rest numbered again, and the renderer keys it lists are
vk_shader.cpp's code_key (FNV-1a 64 over the control section, then the code up to its end). Synthetic data only, no game
files.

    python -I -B tests/test_census_filter.py
"""
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import census_filter as cf  # noqa: E402


def control(stage, end):
    c = bytearray(cf.CONTROL_SIZE)
    struct.pack_into("<I", c, 0, cf.CONTROL_MAGIC)
    struct.pack_into("<I", c, 0x38, 0x10)
    struct.pack_into("<II", c, 0x40, 0, end)
    struct.pack_into("<H", c, 0x56, stage)
    return bytes(c)


def census():
    """4 stages, 3 programs: a small vertex+fragment pair, a big pair sharing the small vertex stage, a small compute"""
    sizes = [(0, 0x400), (1, 0x800), (1, 0x30000), (5, 0x200)]
    stages = [(0x1000 + n, st, control(st, size), bytes((n * 7 + i) & 0xFF for i in range(size))) for n, (st, size) in enumerate(sizes)]
    return stages, [[0, 1], [0, 2], [3]]


class CensusFilterTests(unittest.TestCase):
    def test_fnv_is_fnv1a_64(self):
        self.assertEqual(cf.fnv(b""), 0xCBF29CE484222325)
        self.assertEqual(cf.fnv(b"a"), 0xAF63DC4C8601EC8C)   # (the published FNV-1a 64 test vector)

    def test_round_trip(self):
        stages, programs = census()
        back_stages, back_programs = cf.read(cf.write(stages, programs))
        self.assertEqual(back_programs, programs)
        self.assertEqual([(k, s, bytes(c), bytes(d)) for k, s, c, d in back_stages], stages)

    def test_the_big_program_and_its_own_stage_go(self):
        stages, programs = census()
        kept_stages, kept_programs, dropped = cf.filter_census(stages, programs, 100 << 10)
        self.assertEqual(dropped, [1])
        self.assertEqual([s[0] for s in kept_stages], [0x1000, 0x1001, 0x1003])   # (the shared vertex stage stays)
        self.assertEqual(kept_programs, [[0, 1], [2]])
        self.assertEqual(cf.filter_census(stages, programs, 1 << 30)[2], [])

    def test_renderer_key(self):
        stages, _ = census()
        _, _, ctl, code = stages[1]
        self.assertEqual(cf.renderer_key(ctl, code), cf.fnv(code[:0x800], cf.fnv(ctl)))
        self.assertEqual(cf.renderer_key(b"\0" * cf.CONTROL_SIZE, code), None)   # (no control magic: no stage in play)
        self.assertEqual(cf.renderer_key(ctl, code[:0x10]), None)   # (code shorter than its end)

    def test_command_line(self):
        stages, programs = census()
        with tempfile.TemporaryDirectory() as tmp:
            src, out, lst = Path(tmp, "in.bin"), Path(tmp, "out.bin"), Path(tmp, "left_out.tsv")
            src.write_bytes(cf.write(stages, programs))
            r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "census_filter.py"), str(src), "--out", str(out),
                                "--list", str(lst), "--keys"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("kept 2 programs, 3 stages; left out 1 programs over 100 KB", r.stdout)
            self.assertEqual(len(cf.read(out.read_bytes())[1]), 2)
            cols = lst.read_text().strip().split("\t")
            self.assertEqual(cols[:2], ["1", str((0x400 + 0x30000) >> 10)])
            self.assertEqual(cols[2], "0:%016x:%016x" % (0x1000, cf.renderer_key(stages[0][2], stages[0][3])))
            with self.assertRaises(ValueError):
                cf.read(b"NOTSEED!" + bytes(8))


if __name__ == "__main__":
    unittest.main()
