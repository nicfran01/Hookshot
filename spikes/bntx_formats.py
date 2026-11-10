"""Spike: histogram of texture formats in the romfs' BNTX files (headers only).

Question: how much of Raiders' texture data is ASTC (which the Deck's GPU cannot sample natively, so Hookshot decodes and
re-encodes it) versus BCn?  Usage:

    .venv/bin/python -I spikes/bntx_formats.py <romfs> [max files]

Reads only the first 64 KB of each decompressed file; prints counts and compressed bytes per format. Writes nothing.
"""
import collections
import os
import struct
import sys

import zstandard as zs

NAMES = {0x02: "R8", 0x07: "RGB565", 0x09: "RG8", 0x0a: "R16", 0x0b: "RGBA8", 0x0c: "BGRA8", 0x0e: "RGB10A2", 0x0f: "R11G11B10F",
         0x12: "RG16", 0x14: "R32", 0x15: "RGBA16", 0x16: "RGBA32F?", 0x1a: "BC1", 0x1b: "BC2", 0x1c: "BC3", 0x1d: "BC4",
         0x1e: "BC5", 0x1f: "BC6H", 0x20: "BC7"}
for i, n in enumerate(("4x4", "5x4", "5x5", "6x5", "6x6", "8x5", "8x6", "8x8", "10x5", "10x6", "10x8", "10x10", "12x10", "12x12")):
    NAMES[0x2d + i] = "ASTC_" + n

romfs = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 0
count, size, dims = collections.Counter(), collections.Counter(), collections.Counter()
seen = bad = 0
d = zs.ZstdDecompressor()
for root, _, files in os.walk(romfs):
    for f in files:
        if ".bntx" not in f:
            continue
        p = os.path.join(root, f)
        try:
            with open(p, "rb") as fh:
                head = d.stream_reader(fh).read(65536) if f.endswith(".zs") else fh.read(65536)
        except Exception:
            bad += 1
            continue
        at = head.find(b"BRTI")
        if at < 0:
            bad += 1
            continue
        fmt = struct.unpack_from("<I", head, at + 0x1c)[0]
        w, h = struct.unpack_from("<II", head, at + 0x24)
        name = NAMES.get(fmt >> 8, "fmt_%02x" % (fmt >> 8))
        count[name] += 1
        size[name] += os.path.getsize(p)
        dims[(name, max(w, h))] += 1
        seen += 1
        if cap and seen >= cap:
            break
    if cap and seen >= cap:
        break
print("%d BNTX files read, %d unreadable" % (seen, bad))
for name, n in count.most_common():
    big = sorted((k[1], v) for k, v in dims.items() if k[0] == name)
    print("  %-12s %6d files  %8.1f MB compressed  largest side %d" % (name, n, size[name] / 2 ** 20, big[-1][0]))
