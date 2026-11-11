"""(raiders) The lifter's differential tests on Linux (nx2/test_leaf.py, nx2/test_insn.py): their harnesses were Windows only
(windows.h, VirtualAlloc, __try / __except). Game-free:

- nx2/test_leaf.py HARNESS: its Windows text (the _WIN32 branches) is byte for byte upstream's (git show upstream/main when
  the remote is there, else the hash of upstream's text below); its POSIX text has no windows.h, VirtualAlloc, __try or
  GetExceptionCode. On Linux x86-64 with a C compiler it is compiled with three stand-in functions and run: one returns
  (x0 = 42 comes back), one faults on a bad address and one on an illegal instruction, and each reads as the Windows
  exception code of its kind (0xC0000005, 0xC000001D), the run going on after each.
- nx2/test_insn.py posix_harness: the vendored harness's Windows lines become POSIX ones, and an unexpected harness stops it.
  With a64-kit's lifter library (a64emit) and Unicorn there, the harness insn_test.build_harness writes is made POSIX by the
  wrapper, its Windows text being third_party's own (unchanged: git diff upstream/main -- third_party/); on Linux x86-64 it
  is compiled and started on an empty input (the guest memory mapped at A64_MEM).

    python -I -B tests/test_lifter_harness_posix.py
"""
import ast
import hashlib
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LEAF = ROOT / "nx2" / "test_leaf.py"
# (sha256 of upstream's HARNESS in nx2/test_leaf.py, upstream/main 78e1112, before the POSIX branches)
UPSTREAM_LEAF_HARNESS = "246f59378b19bcd28cd7a3adbf94d5db432f74997bcbb83d5183e532bc4be29b"
STATE_SIZE = 808   # (nx2/test_leaf.py STATE: "<32Q4B4xQQ64QQQ")
LINUX_X64 = sys.platform.startswith("linux") and platform.machine() in ("x86_64", "AMD64")


def harness_of(source):
    """The HARNESS string of a test_leaf.py source, without importing it (it needs numpy and Unicorn)"""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "HARNESS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no HARNESS in test_leaf.py")


def branch(text, windows):
    """The text with only the _WIN32 (windows) or the other branches of its #ifdef _WIN32 / #else / #endif blocks, and the
    directives of those blocks taken out. Other preprocessor lines are left as they are"""
    out, stack = [], []   # stack: per open block, [is a _WIN32 block, in its #else]
    for line in text.split("\n"):
        s = line.strip()
        if s == "#ifdef _WIN32":
            stack.append([True, False])
            continue
        if stack and stack[-1][0] and s == "#else":
            stack[-1][1] = True
            continue
        if s.startswith("#if"):
            stack.append([False, False])
        elif s == "#endif" and stack:
            top = stack.pop()
            if top[0]:
                continue
        keep = all(not win or (inside_else != windows) for win, inside_else in stack)
        if keep:
            out.append(line)
    return "\n".join(out)


def upstream_source(rel):
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "show", "upstream/main:" + rel], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def compiler():
    return shutil.which("clang") or shutil.which("cc")


class LeafHarnessTests(unittest.TestCase):
    def setUp(self):
        self.harness = harness_of(LEAF.read_text(encoding="utf-8"))

    def test_the_windows_text_is_upstreams(self):
        windows = branch(self.harness, True)
        self.assertEqual(hashlib.sha256(windows.encode()).hexdigest(), UPSTREAM_LEAF_HARNESS)
        upstream = upstream_source("nx2/test_leaf.py")
        if upstream is not None:
            self.assertEqual(windows, harness_of(upstream))

    def test_the_posix_text_has_no_windows(self):
        posix = branch(self.harness, False)
        for word in ("windows.h", "VirtualAlloc", "__try", "__except", "GetExceptionCode", "MEM_COMMIT"):
            self.assertNotIn(word, posix)
        for word in ("#include <sys/mman.h>", "MAP_FIXED_NOREPLACE", "sigaltstack", "SA_ONSTACK", "sigsetjmp", "siglongjmp"):
            self.assertIn(word, posix)
        self.assertEqual(posix.count("return 3;"), 1)
        self.assertEqual(posix.count("return 4;"), 1)
        self.assertNotIn("%", re.sub(r"%(\(\w+\)[ds]|%)", "", self.harness))   # (a stray % would break the formatting)

    @unittest.skipUnless(LINUX_X64 and compiler(), "Linux x86-64 with a C compiler")
    def test_it_runs_and_catches_faults(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        try:
            import kit  # noqa: F401  (a64-kit on the path)
            import rtgen
            import a64_rtgen
        except ImportError as e:
            self.skipTest("the lifter's runtime generators: %s" % e)
        img_base, img_size, scr_base, scr_size = 0x80000000, 0x10000, 0x1000000000, 0x10000
        with tempfile.TemporaryDirectory() as tmp:
            a64_rtgen.write(tmp)
            open(os.path.join(tmp, "a64_fpx.h"), "w").close()
            rt = rtgen.write(os.path.join(tmp, "rt64"))
            funcs = ("void f_ok(Ctx *c) { c->x[0] = 42; }\n"
                     "void f_segv(Ctx *c) { (void)c; *(volatile int *)16 = 1; }\n"
                     "void f_ill(Ctx *c) { (void)c; __builtin_trap(); }\n")
            src = '#include "a64.h"\n' + funcs + self.harness % {
                "table": "f_ok,f_segv,f_ill", "regions": "{%#xULL,%#xULL}" % (scr_base, scr_base + scr_size),
                "scratch": scr_size, "scratch_base": scr_base, "img_base": img_base, "img_size": img_size,
                "state": STATE_SIZE}
            path, exe = os.path.join(tmp, "harness.c"), os.path.join(tmp, "harness")
            with open(path, "w", newline="\n") as f:
                f.write(src)
            build = subprocess.run([compiler(), "-O1", "-g0", "-mcx16", "-Wno-everything", "-DA64_POLLING", "-I" + rt,
                                    "-I" + tmp, path, os.path.join(tmp, "a64_suyu.c"), "-o", exe],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr[-2000:])
            img, inp, outp = (os.path.join(tmp, n) for n in ("img.bin", "in.bin", "out.bin"))
            with open(img, "wb") as f:
                f.write(bytes(img_size))
            state = bytearray(STATE_SIZE)
            struct.pack_into("<Q", state, 31 * 8, scr_base + scr_size - 0x1000)   # (sp)
            with open(inp, "wb") as f:
                for idx in (0, 1, 2, 0):
                    f.write(struct.pack("<IQ", idx, 7) + bytes(state))
            run = subprocess.run([exe, img, inp, outp], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            got = []
            with open(outp, "rb") as f:
                for _ in range(4):
                    halted, fault = struct.unpack("<ii", f.read(8))
                    x0 = struct.unpack("<Q", f.read(STATE_SIZE)[:8])[0]
                    ndiff = struct.unpack("<I", f.read(4))[0]
                    f.read(16 * ndiff)
                    got.append((halted, fault & 0xFFFFFFFF, x0))
            self.assertEqual(got, [(0, 0, 42), (0, 0xC0000005, 0), (0, 0xC000001D, 0), (0, 0, 42)])


class InsnHarnessTests(unittest.TestCase):
    WINDOWS = ('#include "a64.h"\n#include <stdio.h>\n#include <stdlib.h>\n#include <windows.h>\nint main(int argc, char **argv) {\n'
               "    if (VirtualAlloc(A64_MEM, 1114112, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) != A64_MEM) return 3;\n}\n")

    def setUp(self):
        try:
            sys.path.insert(0, str(ROOT / "nx2"))
            import test_insn
        except ImportError as e:   # (Unicorn, capstone or the lifter library missing: nothing to wrap here)
            self.skipTest("nx2/test_insn.py does not import here: %s" % e)
        self.test_insn = test_insn

    def test_the_lines_are_made_posix(self):
        out = self.test_insn.posix_harness(self.WINDOWS)
        self.assertNotIn("windows.h", out)
        self.assertNotIn("VirtualAlloc", out)
        self.assertIn("#include <sys/mman.h>", out)
        self.assertIn("if (mmap(A64_MEM, 1114112, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, "
                      "-1, 0) != (void *)A64_MEM) return 3;", out)
        self.assertEqual(out.replace(self.test_insn.POSIX_INCLUDE, "#include <windows.h>").split("\n")[:4],
                         self.WINDOWS.split("\n")[:4])   # (nothing else moved)

    def test_an_unexpected_harness_stops(self):
        for text in (self.WINDOWS.replace("#include <windows.h>\n", ""), self.WINDOWS.replace("VirtualAlloc", "Valloc"),
                     self.WINDOWS + self.WINDOWS):
            with self.assertRaises(SystemExit):
                self.test_insn.posix_harness(text)

    def test_the_vendored_harness(self):
        insn_test = self.test_insn.insn_test
        upstream = upstream_source("third_party/a64-kit/tests/insn_test.py")
        if upstream is not None:
            self.assertEqual((ROOT / "third_party/a64-kit/tests/insn_test.py").read_text(encoding="utf-8"), upstream)
        picked = [(("nop", ()), 0xD503201F)]
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(insn_test.a64emit, "translate", return_value=(["c->x[0] = 1;"], [0])), \
                    mock.patch("subprocess.run") as run:
                insn_test.build_harness(tmp, picked)   # (as written: the Windows text)
                windows = Path(tmp, "harness.c").read_text(encoding="utf-8")
                self.test_insn.posix_build_harness(insn_test.build_harness)(tmp, picked)
                posix = Path(tmp, "harness.c").read_text(encoding="utf-8")
                self.assertEqual(run.call_count, 2)
            self.assertIs(insn_test.subprocess, subprocess)   # (put back after the build)
            self.assertIn("#include <windows.h>", windows)
            self.assertEqual(posix, self.test_insn.posix_harness(windows))
            if not (LINUX_X64 and compiler()):
                return
            with mock.patch.object(insn_test.a64emit, "translate", return_value=(["c->x[0] = 1;"], [0])), \
                    mock.patch.object(insn_test.toolchain, "find", return_value=compiler()):
                exe, _ = self.test_insn.posix_build_harness(insn_test.build_harness)(tmp, picked)
            inp, outp = os.path.join(tmp, "in.bin"), os.path.join(tmp, "out.bin")
            open(inp, "wb").close()
            r = subprocess.run([exe, inp, outp], capture_output=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)   # (3: the guest memory was not mapped at A64_MEM)


if __name__ == "__main__":
    unittest.main()
