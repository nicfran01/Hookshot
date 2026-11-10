"""Spike: which shader archives hold programs with geometry (2), tessellation (3, 4), task (6) or mesh (7) stages.

Question: Hookshot drops geometry/tessellation stages (gpu/vk/vk_shader.cpp program_pick, "dropped stages"). Are Raiders'
geometry programs in shipping archives or only in debug/sample ones?  Usage:

    .venv/bin/python -I spikes/shader_stage_kinds.py <romfs>

Prints, per archive, the count of programs by stage set. Writes nothing.
"""
import collections
import os
import sys

HOOKSHOT_NX2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nx2")
sys.path.insert(0, HOOKSHOT_NX2)
import shader_census as sc  # noqa: E402

current = [None]
kinds = collections.defaultdict(collections.Counter)
_archives, _programs_in = sc.archives, sc.programs_in


def archives(romfs):
    for path in _archives(romfs):
        current[0] = "Effect/*" if os.path.basename(os.path.dirname(path)) == "Effect" else os.path.basename(path)
        yield path


def programs_in(data, stats):
    for stages in _programs_in(data, stats):
        kinds[current[0]][tuple(sorted({s[0] for s in stages}))] += 1
        yield stages


sc.archives, sc.programs_in = archives, programs_in
sc.dictionaries = lambda romfs, zs: []
sys.argv = [sys.argv[0], sys.argv[1]]
import contextlib, io  # noqa: E402
with contextlib.redirect_stdout(io.StringIO()):
    sc.main()
for name, c in kinds.items():
    print("%-60s %s" % (name[:60], dict(c)))
