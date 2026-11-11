"""(raiders) A copy of the shader census (hookshot_shaders.bin, nx2/shader_census.py) without its largest programs, for a
preparation run that fits in the Steam Deck's memory (docs/plans/reports/BLOCKER-T12-2026-11-11.md: 394 programs of
100 KB and more of code each took several GB to translate, and four at once were killed by earlyoom).

    python -I scripts/census_filter.py <hookshot_shaders.bin> --out <file> [--max-kb 100] [--list <file.tsv>] [--keys]

A program's size is the sum of its stages' code bytes. The programs over --max-kb are left out; the stages only they use
are left out too, and the others keep their bytes (so their keys in the renderer are the same) and are numbered again.
--list writes the programs left out, one a line: census index, KB, then each stage as <stage>:<census key>, and with
--keys :<renderer key> as well, the key gpu/vk/vk_shader.cpp code_key gives it (FNV-1a over the control section and
the code up to its end) and prints in "in play:" lines. Keys and sizes only: the file it writes is made from the
player's own game and stays in work/.

    file: "HKSEED01", u32 programs, u32 stages; the stages (u64 key, u32 stage, u32 control bytes, u32 code bytes,
          control, code), then the programs (u32 count, u32 stage indices)
"""
import argparse
import struct
import sys

MAGIC = b"HKSEED01"
CONTROL_SIZE = 0xD8            # (vk_shader.cpp kControlSize)
CONTROL_MAGIC = 0x98761234     # (vk_shader.cpp kControlMagic)
FNV_OFFSET, FNV_PRIME, MASK = 0xCBF29CE484222325, 0x100000001B3, (1 << 64) - 1


def read(blob):
    """(stages, programs): stages as (key, stage, control, code) byte views, programs as lists of stage indices"""
    if blob[:8] != MAGIC or len(blob) < 16:
        raise ValueError("not a shader census (HKSEED01)")
    nprog, nstage = struct.unpack_from("<II", blob, 8)
    at, stages = 16, []
    view = memoryview(blob)
    for _ in range(nstage):
        key, stage, cb, nb = struct.unpack_from("<QIII", blob, at)
        at += 20
        if at + cb + nb > len(blob):
            raise ValueError("a stage runs past the end of the file")
        stages.append((key, stage, view[at:at + cb], view[at + cb:at + cb + nb]))
        at += cb + nb
    programs = []
    for _ in range(nprog):
        (n,) = struct.unpack_from("<I", blob, at)
        idx = list(struct.unpack_from("<%dI" % n, blob, at + 4))
        if any(k >= nstage for k in idx):
            raise ValueError("a program names a stage the file does not have")
        programs.append(idx)
        at += 4 + 4 * n
    return stages, programs


def write(stages, programs):
    out = [MAGIC, struct.pack("<II", len(programs), len(stages))]
    for key, stage, ctl, code in stages:
        out += [struct.pack("<QIII", key, stage, len(ctl), len(code)), bytes(ctl), bytes(code)]
    for idx in programs:
        out += [struct.pack("<I", len(idx)), struct.pack("<%dI" % len(idx), *idx)]
    return b"".join(out)


def fnv(data, h=FNV_OFFSET):
    for b in bytes(data):
        h = ((h ^ b) * FNV_PRIME) & MASK
    return h


def renderer_key(ctl, code):
    """vk_shader.cpp code_key, or None where control_end refuses the control section (no such stage in play)"""
    if len(ctl) < CONTROL_SIZE:
        return None
    magic, = struct.unpack_from("<I", ctl, 0)
    length, = struct.unpack_from("<I", ctl, 0x38)
    c1o, end = struct.unpack_from("<II", ctl, 0x40)
    st, = struct.unpack_from("<H", ctl, 0x56)
    if magic != CONTROL_MAGIC or not length or end > 16 << 20 or c1o > end or length > end or st > 7 or end > len(code):
        return None
    return fnv(code[:end], fnv(ctl[:CONTROL_SIZE]))


def program_bytes(stages, idx):
    return sum(len(stages[k][3]) for k in idx)


def filter_census(stages, programs, max_bytes):
    """(stages, programs) kept, and the indices of the programs left out"""
    keep = [i for i, idx in enumerate(programs) if program_bytes(stages, idx) <= max_bytes]
    dropped = [i for i, idx in enumerate(programs) if program_bytes(stages, idx) > max_bytes]
    used = sorted({k for i in keep for k in programs[i]})
    renumber = {k: n for n, k in enumerate(used)}
    return [stages[k] for k in used], [[renumber[k] for k in programs[i]] for i in keep], dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("census")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-kb", type=int, default=100)
    ap.add_argument("--list")
    ap.add_argument("--keys", action="store_true")
    a = ap.parse_args(argv)
    with open(a.census, "rb") as f:
        stages, programs = read(f.read())
    kept_stages, kept_programs, dropped = filter_census(stages, programs, a.max_kb << 10)
    with open(a.out, "wb") as f:
        f.write(write(kept_stages, kept_programs))
    kinds = {}
    for i in dropped:
        kind = "+".join(str(stages[k][1] & 7) for k in sorted(programs[i], key=lambda k: stages[k][1] & 7))
        kinds[kind] = kinds.get(kind, 0) + 1
    print("census: %d programs, %d stages; kept %d programs, %d stages; left out %d programs over %d KB (stage kinds %s), "
          "%d stages" % (len(programs), len(stages), len(kept_programs), len(kept_stages), len(dropped), a.max_kb,
                         dict(sorted(kinds.items())), len(stages) - len(kept_stages)))
    if a.list:
        with open(a.list, "w", encoding="utf-8") as f:
            for i in dropped:
                cols = [str(i), str(program_bytes(stages, programs[i]) >> 10)]
                for k in programs[i]:
                    key, stage, ctl, code = stages[k]
                    col = "%d:%016x" % (stage & 7, key)
                    if a.keys:
                        rk = renderer_key(ctl, code)
                        col += ":" + ("%016x" % rk if rk is not None else "-")
                    cols.append(col)
                f.write("\t".join(cols) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
