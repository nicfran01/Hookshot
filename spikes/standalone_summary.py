"""Spike: what Hookshot's standalone lift would hook and stub for Raiders, without lifting anything.

Question: of the SDK functions Raiders reaches, how many does Hookshot's host/ replace natively (HLE), how many
OS-facing imports would get generated stubs, and which module defines nn::movie?  Usage:

    OOT_WORK=$PWD/work OOT_DUMP=<dump> .venv/bin/python -I spikes/standalone_summary.py

Writes work/standalone_stubbed.txt (mangled names only; gitignored).
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "nx2"))
import kit          # noqa: E402
import nso          # noqa: E402
import standalone   # noqa: E402
import imports      # noqa: E402

mods = nso.load_exefs(kit.need_exefs())
hle, stubbed = standalone.hle_set(mods)
print("standalone: %d HLE functions in host/, %d OS-facing imports stubbed" % (len(hle), len(stubbed)))
by = collections.Counter(imports.namespace(n) for n in stubbed)
for ns, n in by.most_common(40):
    print("  stubbed %-24s %4d" % (ns, n))
with open(os.path.join(kit.WORK, "standalone_stubbed.txt"), "w") as f:
    f.write("\n".join(sorted(stubbed)) + "\n")
for m in mods:
    defs = [s["name"] for s in m.symbols if s["defined"] and s["name"] and "2nn5movie" in s["name"]]
    und = [s["name"] for s in m.symbols if not s["defined"] and s["name"] and "2nn5movie" in s["name"]]
    und_codec = [s["name"] for s in m.symbols if not s["defined"] and s["name"] and "2nn5codec" in s["name"]]
    print("%-8s defines %3d nn::movie symbols, imports %3d; imports %3d nn::codec" % (m.name, len(defs), len(und), len(und_codec)))
try:
    print("nvn exports routed to host/nvn2.c:", len(standalone.nvn_exports(mods)))
except Exception as e:   # (reported, not fatal: the spike is a survey)
    print("nvn_exports failed:", e)
