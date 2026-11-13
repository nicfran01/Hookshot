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

    # (raiders, T17b) the world: events outside the HUD's blocks
    def test_world_mask(self):
        m = log.world_mask()
        self.assertEqual(m.shape, (9, 16))
        self.assertEqual(int(m.sum()), 144 - 10 - 3 - 8)   # bottom-left HUD, prompts, counter
        for r, c in ((7, 0), (8, 4), (8, 13), (8, 15), (0, 12), (1, 15)):
            self.assertFalse(m[r, c], (r, c))
        for r, c in ((7, 5), (8, 12), (7, 13), (2, 12), (3, 8), (0, 0)):
            self.assertTrue(m[r, c], (r, c))

    def test_parse_span(self):
        self.assertEqual(log.parse_span("60-270"), (60.0, 270.0))
        self.assertEqual(log.parse_span("0.5-1"), (0.5, 1.0))
        for bad in ("270-60", "5-5", "a-b", "5", "-1-3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                log.parse_span(bad)

    def test_world_counts(self):
        # (seconds in, brighter blocks, darker blocks) per eligible triplet; each sign with a block is an event
        world = [(1.0, 3, 0), (5.0, 0, 0), (12.0, 1, 4), (31.0, 9, 3), (40.0, 0, 36), (95.0, 2, 0)]
        n, sizes, bins, spans = log.world_counts(world, 10.0, 30.0, [(0.0, 30.0), (30.0, 60.0), (200.0, 300.0)])
        self.assertEqual(n, 4)   # from 10 s: 12, 31, 40, 95
        self.assertEqual(sizes[(1, 2)], (2, 500.0))     # 12 s brighter 1, 95 s brighter 2
        self.assertEqual(sizes[(3, 8)], (2, 500.0))     # 12 s darker 4, 31 s darker 3
        self.assertEqual(sizes[(9, 35)], (1, 250.0))    # 31 s brighter 9
        self.assertEqual(sizes[(36, 144)], (1, 250.0))  # 40 s darker 36
        self.assertEqual(bins, [2, 3, 0, 0])            # bins of 30 s from 0, events of 3+ blocks; 95 s: 2 blocks only
        self.assertEqual(spans, [(3, 2, 2000.0 / 3), (2, 3, 1500.0), (0, 0, 0.0)])
        self.assertEqual(log.world_counts([], 0.0, 30.0, []), (0, {k: (0, 0.0) for k in log.WORLD_SIZES}, [], []))

    def test_cli_world(self):
        frames = [grey() for _ in range(10)]
        paint(frames[2], 7, 1, 250)   # HUD only: not the world
        for c in (5, 6, 7):
            paint(frames[3], 2, c, 250)   # 3 world blocks brighter
        for c in (0, 1, 2, 3):
            paint(frames[5], 4, c, 0)     # 4 world blocks darker
        paint(frames[5], 0, 13, 250)      # and a counter block: not the world
        self.write(frames)
        result = self.run_cli("--regions", "0", "--world-bin", "4", "--span", "0-4", "--span", "4-9")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        # centres 1-8, at 1-8 s after the first record
        self.assertIn("world (outside the HUD blocks) from 0.0 s: 8 eligible triplets; by blocks: 1-2 0 (0.0 per 1,000), "
                      "3-8 2 (250.0 per 1,000), 9-35 0 (0.0 per 1,000), 36-144 0 (0.0 per 1,000)", out)
        self.assertIn("world events of 3+ blocks per 4 s: 1 1 0", out)   # 3 s; 5 s; nothing in 8 s
        self.assertIn("world span 0-4 s: 3 eligible triplets, 1 with 3+ blocks, 333.3 per 1,000", out)
        self.assertIn("world span 4-9 s: 5 eligible triplets, 1 with 3+ blocks, 200.0 per 1,000", out)
        bad = self.run_cli("--regions", "0", "--span", "9-4")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("a span is A-B", bad.stderr)
        self.assertNotIn("Traceback", bad.stderr)

    def test_cli_without_regions_unchanged_and_bad_region(self):
        frames = [grey() for _ in range(4)]
        paint(frames[1], 0, 0, 250)
        self.write(frames)
        plain = self.run_cli()
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("region", plain.stdout)
        self.assertNotIn("world", plain.stdout)
        self.assertIn("frame 1 (game) brighter 1 blocks, peak 150", plain.stdout)
        bad = self.run_cli("--regions", "0", "--region", "x=0-20,0-1")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("a region is NAME=R0-R1,C0-C1", bad.stderr)
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
