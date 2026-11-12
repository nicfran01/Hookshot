"""(raiders, T15) host/nn_hid.c: the Npad set-up log, the gyroscope zero-drift mode and the "no Joy-Con 2 mouse" answers.

The functions are cut out of host/nn_hid.c by text and compiled with a fake HLE context (guest addresses are host
pointers here) and a fake log. Checked:
- npad_seen logs each (call, value) once, and stays quiet once its table is full;
- the set-up HLEs log what the game asked for (styles, ids, hold type) and still change nothing;
- GetNpadStyleSet still answers FullKey on No.1 and nothing elsewhere;
- GetGyroscopeZeroDriftMode starts at Standard (1), reads back what SetGyroscopeZeroDriftMode set, per handle, and
  ignores a mode past Tight (2);
- the Jcms and Nmouse calls answer "none": no handle state, no mouse, no type.

python -I -B tests/test_hid_npad_setup.py [--cc gcc]
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def hle(text, name):
    return block(text, "HLE(" + name + ")")


PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint64_t x[31]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
#define G32(a) (*(uint32_t *)GP(a))
typedef long LONG;
typedef struct { int unused; } SRWLOCK;
#define SRWLOCK_INIT {0}
static void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; }
static void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; }
static LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG o = *p; *p = v; return o; }
static char logged[64][160];
static int nlogged;
static void hos_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#include <stdarg.h>
static void hos_log(const char *fmt, ...) {
    va_list a;
    va_start(a, fmt);
    if (nlogged < 64) vsnprintf(logged[nlogged++], sizeof logged[0], fmt, a);
    va_end(a);
}
static int failures;
#define CHECK(x) do { if (!(x)) { printf("FAIL line %d: %s\n", __LINE__, #x); failures++; } } while (0)
"""

MAIN = r"""
static int count_logged(const char *needle) {
    int n = 0;
    for (int i = 0; i < nlogged; i++) n += strstr(logged[i], needle) != NULL;
    return n;
}
int main(void) {
    Ctx ctx = {{0}}, *c = &ctx;
    uint32_t id = 0, ids[3] = {0, 1, 0x20}, mode = 0, handle = 0x100, other = 0x101, out = 7;

    /* the set-up calls: each value logged once */
    c->x[0] = 0x3f;
    imp__ZN2nn3hid24SetSupportedNpadStyleSetENS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE(c);
    c->x[0] = 0x3f;
    imp__ZN2nn3hid24SetSupportedNpadStyleSetENS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE(c);
    CHECK(count_logged("SetSupportedNpadStyleSet, styles 0x3f") == 1);
    c->x[0] = (uint64_t)(uintptr_t)ids, c->x[1] = 3;
    imp__ZN2nn3hid22SetSupportedNpadIdTypeEPKjm(c);
    CHECK(count_logged("SetSupportedNpadIdType, count 0x3") == 1);
    CHECK(count_logged("SetSupportedNpadIdType, id 0 ") == 1);
    CHECK(count_logged("SetSupportedNpadIdType, id 0x1 ") == 1);
    CHECK(count_logged("SetSupportedNpadIdType, id 0x20 ") == 1);
    c->x[0] = 1;
    imp__ZN2nn3hid18SetNpadJoyHoldTypeENS0_15NpadJoyHoldTypeE(c);
    CHECK(count_logged("SetNpadJoyHoldType 0x1 ") == 1);

    /* GetNpadStyleSet: FullKey on No.1 only, as before; each id asked for logged once */
    id = 0, c->x[0] = (uint64_t)(uintptr_t)&id;
    imp__ZN2nn3hid15GetNpadStyleSetERKj(c);
    CHECK(c->x[0] == 1);
    id = 0x20, c->x[0] = (uint64_t)(uintptr_t)&id;
    imp__ZN2nn3hid15GetNpadStyleSetERKj(c);
    CHECK(c->x[0] == 0);
    c->x[0] = (uint64_t)(uintptr_t)&id;
    imp__ZN2nn3hid15GetNpadStyleSetERKj(c);
    CHECK(count_logged("GetNpadStyleSet, npad 0x20 ") == 1);

    /* a full table stays quiet */
    for (uint32_t v = 0; v < 100; v++) npad_seen("fill", v, 0);
    const int before = nlogged;
    npad_seen("fill", 1000, 0);
    CHECK(nlogged == before);
    CHECK(count_logged("fill") < 32);

    /* zero-drift mode: Standard first, then what was set, per handle; past Tight ignored */
    c->x[0] = (uint64_t)(uintptr_t)&handle;
    imp__ZN2nn3hid25GetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleE(c);
    CHECK(c->x[0] == 1);
    mode = 2, c->x[0] = (uint64_t)(uintptr_t)&handle, c->x[1] = (uint64_t)(uintptr_t)&mode;
    imp__ZN2nn3hid25SetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleERKNS0_22GyroscopeZeroDriftModeE(c);
    c->x[0] = (uint64_t)(uintptr_t)&handle;
    imp__ZN2nn3hid25GetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleE(c);
    CHECK(c->x[0] == 2);
    c->x[0] = (uint64_t)(uintptr_t)&other;
    imp__ZN2nn3hid25GetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleE(c);
    CHECK(c->x[0] == 1);
    mode = 9, c->x[0] = (uint64_t)(uintptr_t)&handle, c->x[1] = (uint64_t)(uintptr_t)&mode;
    imp__ZN2nn3hid25SetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleERKNS0_22GyroscopeZeroDriftModeE(c);
    c->x[0] = (uint64_t)(uintptr_t)&handle;
    imp__ZN2nn3hid25GetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleE(c);
    CHECK(c->x[0] == 2);

    /* no Joy-Con 2 mouse */
    c->x[0] = 0x1234, c->x[1] = 0x4000;
    imp__ZN2nn3hid14InitializeJcmsEPvm(c);
    c->x[0] = 99;
    imp__ZN2nn3hid13GetJcmsStatesEPNS0_9JcmsStateEiRKNS0_10JcmsHandleE(c);
    CHECK(c->x[0] == 0);
    c->x[0] = 99;
    imp__ZN2nn3hid13GetJcmsHandleERKjRKNS0_8JcmsTypeE(c);
    CHECK(c->x[0] == 0);
    c->x[0] = 99, c->x[1] = 2, c->x[2] = 0;
    imp__ZN2nn3hid16GetNmouseHandlesEPNS0_12NmouseHandleEij(c);
    CHECK(c->x[0] == 0);
    c->x[0] = (uint64_t)(uintptr_t)&out;
    imp__ZN2nn3hid16GetNmouseTypeSetEPNS_4util10BitFlagSetILi32ENS0_10NmouseTypeEEENS0_12NmouseHandleE(c);
    CHECK(out == 0);
    imp__ZN2nn3hid9StartJcmsERKNS0_10JcmsHandleE(c);
    imp__ZN2nn3hid8StopJcmsERKNS0_10JcmsHandleE(c);
    imp__ZN2nn3hid12FinalizeJcmsEv(c);
    imp__ZN2nn3hid14FinalizeNmouseEv(c);

    if (failures) return 1;
    puts("PASS: npad set-up logged once per value; zero-drift mode kept per handle; no Joy-Con 2 mouse");
    return 0;
}
"""

NAMES = (
    "_ZN2nn3hid24SetSupportedNpadStyleSetENS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE",
    "_ZN2nn3hid22SetSupportedNpadIdTypeEPKjm",
    "_ZN2nn3hid18SetNpadJoyHoldTypeENS0_15NpadJoyHoldTypeE",
    "_ZN2nn3hid15GetNpadStyleSetERKj",
    "_ZN2nn3hid25GetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleE",
    "_ZN2nn3hid25SetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleERKNS0_22GyroscopeZeroDriftModeE",
    "_ZN2nn3hid14InitializeJcmsEPvm",
    "_ZN2nn3hid12FinalizeJcmsEv",
    "_ZN2nn3hid9StartJcmsERKNS0_10JcmsHandleE",
    "_ZN2nn3hid8StopJcmsERKNS0_10JcmsHandleE",
    "_ZN2nn3hid13GetJcmsHandleERKjRKNS0_8JcmsTypeE",
    "_ZN2nn3hid13GetJcmsStatesEPNS0_9JcmsStateEiRKNS0_10JcmsHandleE",
    "_ZN2nn3hid16GetNmouseHandlesEPNS0_12NmouseHandleEij",
    "_ZN2nn3hid16GetNmouseTypeSetEPNS_4util10BitFlagSetILi32ENS0_10NmouseTypeEEENS0_12NmouseHandleE",
    "_ZN2nn3hid14FinalizeNmouseEv",
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
    for name in NAMES:
        if hid.count("HLE(" + name + ")") != 1:
            raise SystemExit("FAIL: host/nn_hid.c must define HLE(%s) once" % name)
    defines = ""
    for name in ("NPAD_NO1", "STYLE_FULLKEY"):
        found = re.findall(r"^#define " + name + r"\s+[^\n]+", hid, re.M)
        assert len(found) == 1, name
        defines += found[0] + "\n"
    drift = re.search(r"^static volatile LONG zero_drift_mode\[16\] = \{[^}]*\};", hid, re.M)
    if not drift:
        raise SystemExit("FAIL: no zero_drift_mode table in host/nn_hid.c")
    source = "\n".join([PRELUDE, defines, block(hid, "static void npad_seen("), drift.group(0)] +
                       [hle(hid, name) for name in NAMES] + [MAIN])
    flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0

    def run(command):
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                creationflags=flags)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        result.check_returncode()

    with tempfile.TemporaryDirectory(prefix="hid-npad-") as tmp:
        folder = Path(tmp).resolve()
        (folder / "hid_npad_test.c").write_text(source, encoding="utf-8")
        exe = folder / "fixture.exe"
        run([a.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-function",
             str(folder / "hid_npad_test.c"), "-o", str(exe)])
        run([str(exe)])


if __name__ == "__main__":
    main()
