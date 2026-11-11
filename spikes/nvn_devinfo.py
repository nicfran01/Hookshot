"""Spike (T11): this game's NVN driver device limits against host/nvn_native.c devinfo[].

Question: does the game's own NVN driver (in `sdk`) answer nvnDeviceGetInteger as the shared table does? The table came
from Mario Kart World's 21.4.0 driver, run under Unicorn with a zeroed device (nvn_native.c's comment above devinfo[]);
the harness it names is not in the repository, so this is that method again, for the standalone lift's image:

- nvnDeviceGetInteger has no exported name in NVN2: it is found as the game finds it, through the driver's exported
  nvnBootstrapLoader("nvnDeviceGetProcAddress") and then nvnDeviceGetProcAddress(NULL, "nvnDeviceGetInteger");
- every nn::os function the driver calls on the way (a mutex, a TLS slot) answers 0, and an svc answers 0;
- each id 0..0xCF is asked of a zeroed device; the ids whose answer reads the device are marked (their 0 is not the
  driver's answer on hardware, so the table keeps its value for them, as the original extraction did).

Prints the id, the table's value, the driver's, and why they differ: numbers only. Needs the standalone lift's image
(work/sa/image/image.bin and image.json; lift.py --standalone --write) and Unicorn 2.1. Usage:

    .venv/bin/python -I spikes/nvn_devinfo.py
"""
import json
import os
import re
import struct
import sys

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_UNMAPPED, \
    UC_PROT_ALL
from unicorn.arm64_const import UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, \
    UC_ARM64_REG_CPACR_EL1, UC_ARM64_REG_TPIDRRO_EL0, UC_ARM64_REG_TPIDR_EL0, UC_CPU_ARM64_MAX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("OOT_WORK", os.path.join(ROOT, "work"))
BASE = 0x80000000
STACK, SCRATCH, DEVICE, RETURN, TLS = 0x10000000, 0x20000000, 0x30000000, 0x40000000, 0x50000000
LAST_ID = 0xCF


def emulator(image):
    mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    mu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)   # (pointer authentication: the driver's pacibsp / retab)
    mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF, UC_PROT_ALL)
    mu.mem_write(BASE, image)
    for a in (STACK, SCRATCH, DEVICE, RETURN, TLS):
        mu.mem_map(a, 0x100000, UC_PROT_ALL)
    mu.mem_write(RETURN, struct.pack("<I", 0xD4200000))                 # brk #0: the call's end
    mu.mem_write(TLS + 0x1F8, struct.pack("<Q", TLS + 0x1000))         # the current thread object
    mu.mem_write(TLS + 0x1000 + 0x1B0, struct.pack("<I", 0x1234))      # its handle (critical sections)
    mu.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
    mu.reg_write(UC_ARM64_REG_TPIDRRO_EL0, TLS)
    mu.reg_write(UC_ARM64_REG_TPIDR_EL0, TLS)
    return mu


def call(mu, fn, args, watch_device=False):
    """x0 after fn(args), and the device offsets it read; an error stops the spike"""
    for i, a in enumerate(args):
        mu.reg_write(UC_ARM64_REG_X0 + i, a)
    mu.reg_write(UC_ARM64_REG_SP, STACK + 0xF0000)
    mu.reg_write(UC_ARM64_REG_LR, RETURN)
    reads, hooks = set(), []
    if watch_device:
        hooks.append(mu.hook_add(UC_HOOK_MEM_READ, lambda uc, acc, a, size, v, ud: reads.add(a - DEVICE),
                                 begin=DEVICE, end=DEVICE + 0xFFFFF))
    mu.emu_start(fn, RETURN, count=5_000_000)
    for h in hooks:
        mu.hook_del(h)
    if mu.reg_read(UC_ARM64_REG_PC) != RETURN:
        sys.exit("stopped at %#x" % mu.reg_read(UC_ARM64_REG_PC))
    return mu.reg_read(UC_ARM64_REG_X0), sorted(reads)


def main():
    image = open(os.path.join(WORK, "sa", "image", "image.bin"), "rb").read()
    meta = json.load(open(os.path.join(WORK, "sa", "image", "image.json")))
    sdk = next(m for m in meta["modules"] if m["name"] == "sdk")
    exports = meta["exports"]
    mu = emulator(image)
    os_functions = {v for k, v in exports.items() if k.startswith("_ZN2nn2os")}

    def answer_zero(uc, addr, size, ud):
        if addr in os_functions:
            uc.reg_write(UC_ARM64_REG_X0, 0)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
    for a in os_functions:
        mu.hook_add(UC_HOOK_CODE, answer_zero, begin=a, end=a)
    mu.hook_add(UC_HOOK_INTR, lambda uc, intno, ud: uc.reg_write(UC_ARM64_REG_X0, 0))
    mu.hook_add(UC_HOOK_MEM_UNMAPPED, lambda uc, acc, a, size, v, ud: sys.exit(
        "unmapped %#x at %#x" % (a, uc.reg_read(UC_ARM64_REG_PC))))

    def proc(fn, *args, name):
        mu.mem_write(SCRATCH, name + b"\0")
        return call(mu, fn, list(args) + [SCRATCH] if not args else [args[0], SCRATCH])[0]
    get_proc = proc(exports["nvnBootstrapLoader"], name=b"nvnDeviceGetProcAddress")
    get_integer = proc(get_proc, 0, name=b"nvnDeviceGetInteger")
    print("nvnDeviceGetProcAddress sdk+%#x, nvnDeviceGetInteger sdk+%#x" % (get_proc - sdk["base"], get_integer - sdk["base"]))

    src = open(os.path.join(ROOT, "host", "nvn_native.c"), encoding="utf-8").read()
    body = src[src.index("static const int devinfo[] = {"):src.index("NV(nvnDeviceGetInteger)")]
    table = {int(k, 16): int(v) for k, v in re.findall(r"\[0x([0-9A-Fa-f]+)\] = (-?\d+)", body)}
    out = SCRATCH + 0x800
    same = 0
    for w in range(LAST_ID + 1):
        mu.mem_write(DEVICE, bytes(0x10000))
        mu.mem_write(out, struct.pack("<i", -12345))
        _, reads = call(mu, get_integer, [DEVICE, w, out], watch_device=True)
        v = struct.unpack("<i", bytes(mu.mem_read(out, 4)))[0]
        old = table.get(w)
        if old == v and not reads:
            same += 1
            continue
        why = ("reads the device at " + ", ".join("%#x" % r for r in reads[:4])) if reads else \
              ("past the table" if old is None else "differs")
        print("%#04x  table %-11s driver %-11s %s" % (w, old, v, why))
    print("%d of %d ids the same" % (same, LAST_ID + 1))


if __name__ == "__main__":
    main()
