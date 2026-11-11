"""Every instruction form the game uses, in Unicorn and as lifted C: a64-kit's tests/insn_test.py with the Switch 2
additions.

Differences from running the vendored test as is:
  - the Switch 2 forms translate (insn.install()), and RETAx are returns (not sampled, like RET);
  - Unicorn runs its "max" CPU model, which has the ARMv8.1+ forms (the default Cortex-A72 rejects LSE, CAS, LDAPR);
  - the harness is built with -mcx16 (CASP on 128 bits);
  - (raiders) off Windows the harness's Windows lines become POSIX ones (posix_harness): the vendored test is Windows only
    as written, and third_party/ is not modified;
  - PAC and MTE forms are left out: here they are the identity by design (see insn.py), not the hardware's result;
  - memory operands based on x29 / x30 get their scratch address too: capstone names them fp / lr, which
    insn_test.mem_regs does not parse, so those cases ran on a random (often tiny) address that the harness
    does not reset between cases (a false LDADD [x29] failure, 2026-10-31).

Usage:  python -I nx2/test_insn.py [--modules main,sdk,...] [--per 6] [--states 12] [--only lse]
  (--modules: every code module of the exefs but rtld by default)
  Needs the module images of nso.py in <work>/modules (made on first use).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import kit
import insn

insn.install()
sys.path.insert(0, os.path.join(kit.KIT, "tests"))
import insn_test   # noqa: E402
import toolchain   # noqa: E402
import unicorn     # noqa: E402
from unicorn import arm64_const as A   # noqa: E402

# (the game: this runs the lifted code of a real dump against Unicorn)
RUN_ALL_SKIP = {
    "linux": "needs the game's modules (work/dump) and Unicorn",
    "windows": "needs the game's modules (work/dump) and Unicorn",
}


class _Unicorn:
    """insn_test's view of the unicorn module: every engine it makes runs the ARMv8.x "max" CPU"""
    UcError = unicorn.UcError
    UC_ARCH_ARM64 = unicorn.UC_ARCH_ARM64
    UC_MODE_ARM = unicorn.UC_MODE_ARM

    @staticmethod
    def Uc(arch, mode):
        uc = unicorn.Uc(arch, mode)
        uc.ctl_set_cpu_model(A.UC_CPU_ARM64_MAX)
        return uc


ONLY = {"lse": lambda w: (w & 0x3F200C00) == 0x38200000 or (w & 0x3FA07C00) == 0x08A07C00
        or (w & 0xBFA07C00) == 0x08207C00,
        "nx2": lambda w: insn.emit(w) is not None}


def mem_regs(w):
    md = insn_test.capstone.Cs(insn_test.capstone.CS_ARCH_ARM64, insn_test.capstone.CS_MODE_ARM)
    md.detail = True
    ins = next(md.disasm(insn_test.struct.pack("<I", w), insn_test.CODE), None)
    alias = {"fp": 29, "lr": 30, "x29": 29, "x30": 30}
    for op in ins.operands if ins else ():
        if op.type == insn_test.capstone.arm64.ARM64_OP_MEM:
            def num(r):
                if r is None:
                    return None
                name = ins.reg_name(r)
                if name in ("sp", "wsp"):
                    return "sp"
                if name in alias:
                    return alias[name]
                return int(name[1:]) if name[1:].isdigit() else None
            return num(op.mem.base or None), num(op.mem.index or None)
    return None


# (raiders) the vendored harness's Windows lines (insn_test.build_harness) and their POSIX equivalents: the guest memory
# mapped at A64_MEM (0x1000_0000_0000, a64.h) with mmap in place of VirtualAlloc, the same return code when it is not there
WIN_INCLUDE = "#include <windows.h>"
POSIX_INCLUDE = ("#include <string.h>\n#include <sys/mman.h>\n#ifndef MAP_FIXED_NOREPLACE\n"
                 "#define MAP_FIXED_NOREPLACE 0x100000   /* (Linux 4.17; glibc names it from 2.28) */\n#endif")
WIN_ALLOC = re.compile(r"if \(VirtualAlloc\(A64_MEM, (\d+), MEM_RESERVE \| MEM_COMMIT, PAGE_READWRITE\) != A64_MEM\) return 3;")
POSIX_ALLOC = ("if (mmap(A64_MEM, \\1, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0) "
               "!= (void *)A64_MEM) return 3;")


def posix_harness(text):
    """(raiders) The harness's text with its Windows lines made POSIX. Stops when either is not there exactly once: an
    upstream change to the harness must not leave this doing nothing"""
    if text.count(WIN_INCLUDE) != 1 or len(WIN_ALLOC.findall(text)) != 1:
        raise SystemExit("test_insn: insn_test's harness no longer has the one %r and the one VirtualAlloc line this "
                         "rewrites for POSIX (nx2/test_insn.py posix_harness)" % WIN_INCLUDE)
    text = text.replace(WIN_INCLUDE, POSIX_INCLUDE)
    text = WIN_ALLOC.sub(POSIX_ALLOC, text)
    if "windows.h" in text or "VirtualAlloc" in text:
        raise SystemExit("test_insn: the POSIX harness still has Windows text")
    return text


def posix_build_harness(base):
    """(raiders) insn_test.build_harness, its harness.c made POSIX after it is written and before clang reads it"""
    def build_harness(tmp, picked):
        real = insn_test.subprocess

        class Compile:   # (only the compile in build_harness goes through here; main runs the harness with the real one)
            def __getattr__(self, name):
                return getattr(real, name)

            @staticmethod
            def run(cmd, *a, **k):
                path = os.path.join(tmp, "harness.c")
                with open(path, encoding="utf-8") as f:
                    text = posix_harness(f.read())
                with open(path, "w", newline="\n", encoding="utf-8") as f:
                    f.write(text)
                return real.run(cmd, *a, **k)
        insn_test.subprocess = Compile()
        try:
            return base(tmp, picked)
        finally:
            insn_test.subprocess = real
    return build_harness


def main():
    kit.wait_for_quiet('the instruction test')
    only = None
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        only = ONLY[sys.argv[i + 1]]
        del sys.argv[i:i + 2]
    modules = os.path.join(kit.WORK, "modules")
    if not os.path.exists(os.path.join(modules, "main.json")):
        subprocess.run([sys.executable, "-I", os.path.join(kit.KIT, "tools", "nso.py"), kit.need_exefs(), modules],
                       check=True, stdout=subprocess.DEVNULL)
    if "--modules" not in sys.argv:
        sys.argv += ["--modules", ",".join(kit.game_modules())]
    insn_test.unicorn = _Unicorn
    insn_test.mem_regs = mem_regs
    base_target = toolchain.native_target
    toolchain.native_target = lambda *a, **k: base_target(*a, **k) + ["-mcx16"]
    base_sample = insn_test.sample

    def sample(image_dir, mods, per, rng):
        picked = [(k, w) for k, w in base_sample(image_dir, mods, per, rng) if not insn.is_identity_model(w)]
        return [(k, w) for k, w in picked if only(w)] if only else picked

    insn_test.sample = sample
    if os.name != "nt":   # (raiders)
        insn_test.build_harness = posix_build_harness(insn_test.build_harness)
    sys.argv = [sys.argv[0], modules] + sys.argv[1:]
    return insn_test.main()


if __name__ == "__main__":
    sys.exit(main())
