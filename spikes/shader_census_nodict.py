"""Spike: run Hookshot's nx2/shader_census.py on a romfs that has no Pack/ZsDic.pack.zs.

Question: does Hookshot's shader walk (BNSH / BAHS / NDSR / particle sets) read Raiders' archives once the
zstd-dictionary assumption is removed?  Usage:

    .venv/bin/python -I spikes/shader_census_nodict.py <romfs> [--out work/raiders_shaders.bin]

Nothing from the game is written to the repo: --out belongs under work/ (gitignored).
"""
import os
import sys

HOOKSHOT_NX2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nx2")
sys.path.insert(0, HOOKSHOT_NX2)
import shader_census  # noqa: E402

_orig = shader_census.dictionaries


def dictionaries(romfs, zs):
    if not os.path.exists(os.path.join(romfs, "Pack", "ZsDic.pack.zs")):
        print("no Pack/ZsDic.pack.zs: plain zstd only", flush=True)
        return []
    return _orig(romfs, zs)


shader_census.dictionaries = dictionaries
sys.exit(shader_census.main())
