"""(raiders, T17a) scripts/framelog.py --regions: one-frame jumps per block region, and the large-event list.

Synthetic captures only (flat grey frames with painted blocks): no game output.
"""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

RUN_ALL_MODULES = ["numpy"]

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "framelog.py"
spec = importlib.util.spec_from_file_location("framelog", SCRIPT)
log = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log)


def grey(v=100):
    return np.full((log.H, log.W, 4), v, dtype=np.uint8)


def paint(img, row, col, v):
    img[row * 20:(row + 1) * 20, col * 20:(col + 1) * 20, :3] = v
    return img


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="hookshot-framelog-regions-")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "framelog"

    def write(self, frames):
        with self.path.open("wb") as file:
            for i, img in enumerate(frames):
                file.write(struct.pack("<QII", (i + 1) * 1_000_000_000, i, 0))   # one second apart
                file.write(img.tobytes())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), str(self.path), *args],
                              capture_output=True, text=True)

    def test_parse_region(self):
        self.assertEqual(log.parse_region("a=7-8,0-4"), ("a", (7, 8, 0, 4)))
        for bad in ("a=8-7,0-4", "a=0-9,0-1", "a=0-1,0-16", "=0-1,0-1", "a", "a=0-1", "a=x-1,0-1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                log.parse_region(bad)

    def test_jump_rule_matches_flash_rule(self):
        prev, cur, nxt = (log.blocks(grey().astype(np.float32)[..., :3]) for _ in range(3))
        cur = cur.copy()
        cur[7, 0] += 50    # brighter than both neighbours, which agree: a flash
        cur[0, 0] += 10    # under the 12-level threshold
        (up, up_hit), (down, down_hit) = log.jumps(prev, cur, nxt)
        self.assertTrue(up_hit[7, 0])
        self.assertEqual(int(up_hit.sum()), 1)
        self.assertFalse(down_hit.any())
        self.assertAlmostEqual(float(up[7, 0]), 50.0, places=3)
        moving = nxt.copy()
        moving[7, 0] += 60  # the neighbours themselves differ more: an edge moving past, not a flash
        (_, up_hit), _ = log.jumps(prev, cur, moving)
        self.assertFalse(up_hit[7, 0])

    def test_region_counts(self):
        hits = [np.zeros((9, 16), dtype=bool) for _ in range(4)]
        hits[0][7, 0] = True
        hits[1][8, 4] = True
        hits[1][3, 6] = True
        hits[2][6, 0] = True   # outside every default region
        res = log.region_counts(hits, log.REGIONS)
        self.assertEqual(res["hud_bottom_left"], (2, 500.0))
        self.assertEqual(res["control_middle"], (1, 250.0))
        self.assertEqual(res["control_bottom_centre"], (0, 0.0))
        self.assertEqual(log.region_counts([], log.REGIONS)["hud_bottom_left"], (0, 0.0))

    def test_cli_regions_and_large_events(self):
        frames = [grey() for _ in range(10)]
        paint(frames[2], 7, 1, 250)   # a HUD flash (frame 2, 2 s after the first record)
        paint(frames[4], 8, 3, 0)     # a darker one (frame 4)
        paint(frames[4], 3, 8, 250)   # and a control-region flash in the same frame
        frames[7][..., :3] = 20       # the whole picture dark for one frame: 144 blocks
        self.write(frames)
        result = self.run_cli("--regions", "1.5", "--region", "corner=0-0,0-0")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("regions from 1.5 s: 7 eligible triplets", out)     # centres 2-8
        self.assertIn("region hud_bottom_left (rows 7-8, columns 0-4): 3, 428.6 per 1,000", out)  # 2, 4 and 7
        self.assertIn("region control_middle (rows 3-4, columns 6-10): 2, 285.7 per 1,000", out)  # 4 and 7
        self.assertIn("region control_bottom_centre (rows 7-8, columns 6-10): 1, 142.9 per 1,000", out)
        self.assertIn("region corner (rows 0-0, columns 0-0): 1, 142.9 per 1,000", out)
        self.assertIn("events of 36+ blocks from 1.5 s: 1", out)
        self.assertIn("large frame 7 (game) darker 144 blocks", out)
        later = self.run_cli("--regions", "5")   # centres 5-8
        self.assertIn("regions from 5.0 s: 4 eligible triplets", later.stdout)
        self.assertIn("region hud_bottom_left (rows 7-8, columns 0-4): 1, 250.0 per 1,000", later.stdout)
        self.assertNotIn("region corner", later.stdout)

    def test_cli_without_regions_unchanged_and_bad_region(self):
        frames = [grey() for _ in range(4)]
        paint(frames[1], 0, 0, 250)
        self.write(frames)
        plain = self.run_cli()
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("region", plain.stdout)
        self.assertIn("frame 1 (game) brighter 1 blocks, peak 150", plain.stdout)
        bad = self.run_cli("--regions", "0", "--region", "x=0-20,0-1")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("a region is NAME=R0-R1,C0-C1", bad.stderr)
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
