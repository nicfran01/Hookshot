"""The flashes in a frame log (RX_VK_FRAMELOG, gpu/vk/vk_replay.cpp): capture samples, 320x180.

Timestamps sample command recording before GPU submission.

    python -I scripts/framelog.py <file> [out.png]
    python -I scripts/framelog.py <file> --inspect
    python -I scripts/framelog.py <file> --regions <from seconds> [--region NAME=R0-R1,C0-C1 ...] [--span A-B ...]

A frame is a flash where a part of the picture goes brighter (or darker) than BOTH its neighbours by more than they differ
from each other, with the brightness of that part back within reach the next frame. Blocks of 20x20, so that an edge moving
past counts little; a block must jump in brightness, not only in detail. Prints the events by size, with whether the frame was
the game's or a made one, and writes the worst as rows of (before, frame, after).
Only consecutive sequence numbers form a triplet: dropped records cannot establish a one-frame flash. Inspect a
completed, stable capture; --inspect validates its headers without NumPy. Sequence numbers may wrap at uint32;
nonadvancing headers, partial records and captures shorter than three frames are rejected.
(raiders, T17a) --regions <s> counts, from <s> seconds after the first record, the triplets in which a region (block rows
and columns of the 16x9 grid, both ends included) has at least one block that jumps by that rule, per 1,000 eligible
triplets, and lists every event of LARGE blocks or more after <s>. The default regions are Raiders' HUD bottom left and
counter, and two regions with no HUD as controls; --region adds or replaces one.
(raiders, T17b) With --regions, the world: events outside the HUD's blocks (WORLD_HUD), an event being a triplet's blocks
that jump one way (brighter, or darker: as the events above), by their number of blocks (WORLD_SIZES), per 1,000 eligible
triplets from <s>; the events of WORLD_MIN or more blocks per 30 s of the whole capture (--world-bin), and per 1,000 eligible
triplets in each --span A-B (seconds after the first record) asked for.
"""
import argparse
import mmap
from pathlib import Path
import struct
from typing import NamedTuple

W, H = 320, 180
SIZE = 16 + W * H * 4
MASK = (1 << 32) - 1


class CaptureInfo(NamedTuple):
    timestamps: list[int]
    sequences: list[int]
    kinds: list[int]
    missing: int
    centres: list[int]


def triplet_centres(sequences):
    """Only stored consecutive frames can establish a one-frame brightness jump."""
    return [i for i in range(1, len(sequences) - 1)
            if ((sequences[i] - sequences[i - 1]) & MASK) == 1
            and ((sequences[i + 1] - sequences[i]) & MASK) == 1]


def capture_info(path):
    size = Path(path).stat().st_size
    count, tail = divmod(size, SIZE)
    if tail:
        raise ValueError("truncated record %d: %d bytes, expected %d" % (count + 1, tail, SIZE))
    if count < 3:
        raise ValueError("need at least 3 frames for flash analysis; got %d" % count)
    timestamps, sequences, kinds = [], [], []
    missing = 0
    with open(path, "rb") as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as raw:
        for i in range(count):
            t, s, k = struct.unpack_from("<QII", raw, i * SIZE)
            if k not in (0, 1):
                raise ValueError("invalid frame kind %d at record %d (expected 0 or 1)" % (k, i + 1))
            if timestamps and t <= timestamps[-1]:
                raise ValueError("timestamp does not advance at record %d" % (i + 1))
            if sequences:
                delta = (s - sequences[-1]) & MASK
                if not delta or delta >= (1 << 31):
                    raise ValueError("sequence does not advance at record %d" % (i + 1))
                missing += delta - 1
            timestamps.append(t), sequences.append(s), kinds.append(k)
    return CaptureInfo(timestamps, sequences, kinds, missing, triplet_centres(sequences))


# (raiders, T17a) block rows r0-r1, columns c0-c1 (inclusive) of the 16x9 grid
REGIONS = {
    "hud_bottom_left": (7, 8, 0, 4),
    "counter_top_right": (0, 1, 12, 15),
    "control_bottom_centre": (7, 8, 6, 10),
    "control_middle": (3, 4, 6, 10),
}
LARGE = 36   # (a quarter of the picture: T17's large-event class)
# (raiders, T17b) the world: every block but the HUD's (T17a's scratch count): the bottom-left HUD, the bottom-right button
# prompts and the counter top right. An event counts from WORLD_MIN blocks in the per-30-s and span lines
WORLD_HUD = ((7, 8, 0, 4), (8, 8, 13, 15), (0, 1, 12, 15))
WORLD_SIZES = ((1, 2), (3, 8), (9, 35), (36, 144))
WORLD_MIN = 3


def world_mask():
    """the blocks of the 16x9 grid outside WORLD_HUD"""
    import numpy as np
    m = np.ones((H // 20, W // 20), dtype=bool)
    for r0, r1, c0, c1 in WORLD_HUD:
        m[r0:r1 + 1, c0:c1 + 1] = False
    return m


def parse_span(text):
    """A-B (seconds) -> (a, b), a < b"""
    try:
        a, b = (float(v) for v in text.split("-"))
    except ValueError:
        raise ValueError("a span is A-B in seconds: %s" % text) from None
    if not 0 <= a < b:
        raise ValueError("a span is A-B with 0 <= A < B: %s" % text)
    return a, b


def world_counts(world, since, bin_s, spans):
    """world: per eligible triplet, (seconds after the first record, blocks outside the HUD that jump brighter, those that
    jump darker); each sign with a block is an event. -> (from `since`: eligible triplets, {size class: (events, per 1,000
    triplets)}; per bin of bin_s seconds from 0: events of WORLD_MIN+ blocks; per span: (eligible triplets, events of
    WORLD_MIN+ blocks, per 1,000 triplets))"""
    big = lambda signs: sum(1 for c in signs if c >= WORLD_MIN)
    after = [signs for t, *signs in world if t >= since]
    n = len(after)
    sizes = {}
    for lo, hi in WORLD_SIZES:
        c = sum(1 for signs in after for v in signs if lo <= v <= hi)
        sizes[(lo, hi)] = (c, 1000.0 * c / n if n else 0.0)
    bins = {}
    for t, *signs in world:
        b = int(t // bin_s)
        bins[b] = bins.get(b, 0) + big(signs)
    per_span = []
    for a, b in spans:
        inside = [signs for t, *signs in world if a <= t < b]
        e = sum(big(signs) for signs in inside)
        per_span.append((len(inside), e, 1000.0 * e / len(inside) if inside else 0.0))
    return n, sizes, [bins.get(k, 0) for k in range(max(bins) + 1 if bins else 0)], per_span


def parse_region(text):
    """NAME=R0-R1,C0-C1 -> (name, (r0, r1, c0, c1)), checked against the grid"""
    name, sep, spec = text.partition("=")
    try:
        rows, cols = spec.split(",")
        r0, r1 = (int(v) for v in rows.split("-"))
        c0, c1 = (int(v) for v in cols.split("-"))
    except ValueError:
        raise ValueError("a region is NAME=R0-R1,C0-C1: %s" % text) from None
    if not sep or not name or not (0 <= r0 <= r1 < H // 20 and 0 <= c0 <= c1 < W // 20):
        raise ValueError("a region is NAME=R0-R1,C0-C1 inside rows 0-%d, columns 0-%d: %s" % (H // 20 - 1, W // 20 - 1, text))
    return name, (r0, r1, c0, c1)


def jumps(prev, cur, nxt):
    """[(jump, hit) brighter, (jump, hit) darker]: per block, how far it moves against both neighbours, and whether that
    counts as a flash"""
    import numpy as np
    span = np.abs(prev - nxt)
    return [(jump, (jump > 12) & (jump > span * 1.5))
            for jump in (np.minimum(cur - prev, cur - nxt), np.minimum(prev - cur, nxt - cur))]


def region_counts(hits, regions):
    """hits: per eligible triplet, a bool block mask (either sign). -> {name: (triplets with a hit, per 1,000)}"""
    n = len(hits)
    res = {}
    for name, (r0, r1, c0, c1) in regions.items():
        c = sum(1 for h in hits if h[r0:r1 + 1, c0:c1 + 1].any())
        res[name] = (c, 1000.0 * c / n if n else 0.0)
    return res


def blocks(a):
    """luma means of 20x20 blocks"""
    l = a[..., 0] * 0.3 + a[..., 1] * 0.6 + a[..., 2] * 0.1
    return l[:H // 20 * 20, :].reshape(H // 20, 20, W // 20, 20).mean(axis=(1, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("out", nargs="?", help="write the worst events to this PNG")
    parser.add_argument("--inspect", action="store_true", help="validate metadata and report eligible triplets without NumPy")
    parser.add_argument("--regions", type=float, metavar="SECONDS",
                        help="(raiders) one-frame jumps per region per 1,000 triplets from this many seconds in")
    parser.add_argument("--region", action="append", default=[], metavar="NAME=R0-R1,C0-C1",
                        help="(raiders) a region of block rows and columns for --regions (adds, or replaces by name)")
    parser.add_argument("--world-bin", type=float, default=30.0, metavar="SECONDS",
                        help="(raiders) the world's events per this many seconds, with --regions (default 30)")
    parser.add_argument("--span", action="append", default=[], metavar="A-B",
                        help="(raiders) the world's events per 1,000 triplets between A and B seconds in, with --regions")
    args = parser.parse_args()
    regions = dict(REGIONS)
    try:
        for text in args.region:
            name, box = parse_region(text)
            regions[name] = box
        spans = [parse_span(text) for text in args.span]
        if args.world_bin <= 0:
            raise ValueError("--world-bin is a number of seconds above 0")
    except ValueError as error:
        parser.error(str(error))
    path, out = args.path, args.out
    try:
        info = capture_info(path)
    except (OSError, ValueError, struct.error) as error:
        parser.error(str(error))
    n = len(info.sequences)
    print(n, "frames")
    eligible = set(info.centres)
    print("flash triplets: %d eligible, %d skipped across sequence gaps; missing %d frames" % (
        len(eligible), n - 2 - len(eligible), info.missing))
    if args.inspect:
        return 0
    try:
        import numpy as np
    except ImportError:
        parser.error("image analysis requires NumPy; --inspect validates capture metadata without it")
    raw = np.memmap(path, dtype=np.uint8, mode="r")
    ts = np.array(info.timestamps, dtype=np.uint64)
    kinds = np.array(info.kinds)
    d = np.diff(ts) / 1e6
    print("capture samples apart: median %.1f ms, 99%% %.1f, worst %.1f; made %d of %d; missing %d" % (
        np.median(d), np.percentile(d, 99), d.max(), kinds.sum(), n, info.missing))
    frame = lambda i: np.asarray(raw[i * SIZE + 16:(i + 1) * SIZE]).reshape(H, W, 4)[..., :3].astype(np.float32)
    prev = blocks(frame(0))
    cur = blocks(frame(1))
    events = []
    since = None if args.regions is None else ts[0] + np.uint64(max(0.0, args.regions) * 1e9)
    hits = []   # (raiders, T17a) per eligible triplet from --regions on: the blocks that jump, either sign
    world = []   # (raiders, T17b) per eligible triplet: (seconds in, blocks outside the HUD that jump brighter, darker)
    wmask = world_mask() if since is not None else None
    for i in range(1, n - 1):
        nxt = blocks(frame(i + 1))
        if i in eligible:
            both = None
            outside = []
            for sign, (jump, hit) in zip((1, -1), jumps(prev, cur, nxt)):
                both = hit if both is None else both | hit
                if wmask is not None:
                    outside.append(int((hit & wmask).sum()))
                c = int(hit.sum())
                if c:
                    events.append((float(jump[hit].sum()), i, sign, c, float(jump.max())))
            if since is not None and ts[i] >= since:
                hits.append(both)
            if since is not None:
                world.append((float(ts[i] - ts[0]) / 1e9, *outside))
        prev, cur = cur, nxt
    events.sort(reverse=True)
    tot = {0: 0, 1: 0}
    for e in events:
        tot[int(kinds[e[1]])] += 1
    print("events: %d on the game's frames, %d on made frames" % (tot[0], tot[1]))
    for size, i, sign, c, peak in events[:24]:
        print("frame %d (%s) %s %d blocks, peak %.0f, at %.2f s" % (i, "made" if kinds[i] else "game", "brighter" if sign > 0 else "darker",
                                                                     c, peak, (ts[i] - ts[0]) / 1e9))
    if since is not None:
        print("regions from %.1f s: %d eligible triplets" % (args.regions, len(hits)))
        for name, (c, per) in region_counts(hits, regions).items():
            r0, r1, c0, c1 = regions[name]
            print("region %s (rows %d-%d, columns %d-%d): %d, %.1f per 1,000" % (name, r0, r1, c0, c1, c, per))
        large = sorted((e for e in events if e[3] >= LARGE and ts[e[1]] >= since), key=lambda e: e[1])
        print("events of %d+ blocks from %.1f s: %d" % (LARGE, args.regions, len(large)))
        for size, i, sign, c, peak in large:
            print("large frame %d (%s) %s %d blocks, peak %.0f, at %.2f s" % (
                i, "made" if kinds[i] else "game", "brighter" if sign > 0 else "darker", c, peak, (ts[i] - ts[0]) / 1e9))
        n_after, sizes, bins, per_span = world_counts(world, args.regions, args.world_bin, spans)
        print("world (outside the HUD blocks) from %.1f s: %d eligible triplets; by blocks: %s" % (
            args.regions, n_after, ", ".join("%d-%d %d (%.1f per 1,000)" % (lo, hi, c, per) for (lo, hi), (c, per) in sizes.items())))
        print("world events of %d+ blocks per %g s: %s" % (WORLD_MIN, args.world_bin, " ".join(str(v) for v in bins)))
        for (a, b), (m, e, per) in zip(spans, per_span):
            print("world span %g-%g s: %d eligible triplets, %d with %d+ blocks, %.1f per 1,000" % (a, b, m, e, WORLD_MIN, per))
    if out and events:
        from PIL import Image
        rows = events[:8]
        im = Image.new("RGB", (W * 3, H * len(rows)))
        for r, e in enumerate(rows):
            for k in range(3):
                im.paste(Image.fromarray(frame(e[1] - 1 + k).astype(np.uint8)), (k * W, r * H))
        im.save(out)


if __name__ == "__main__":
    raise SystemExit(main())
