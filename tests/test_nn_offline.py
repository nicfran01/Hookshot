"""(raiders) The offline answers (host/nn_offline.c), family by family, compiled with stand-in helpers (no game files):
nn::prepo's GetOverSaveFrequencyLimitEvent gives one event, made once, manual-clear and never signalled, not null;
AddInternetConnectionStatus and RequestImmediateTransmission succeed and touch nothing. nn::ngc's
ProfanityFilter::Initialize answers the SDK's "no ngc service" result, leaves the object and its work buffer as they
were (so the SDK's own Mask, Finalize and destructor take their "not initialized" paths) and logs once. Also: every HLE in the file has a
comment above it, and the lift's list of implemented functions (nx2/standalone.py) finds every one.

    python -I -B tests/test_nn_offline.py [--cc gcc]
"""
import argparse
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "host" / "nn_offline.c"
EVENT = "_ZN2nn5prepo30GetOverSaveFrequencyLimitEventEv"
STATUS = "_ZN2nn5prepo27AddInternetConnectionStatusEPNS0_10PlayReportEPKcS4_S4_"
SEND = "_ZN2nn5prepo28RequestImmediateTransmissionEv"
NGC_INIT = "_ZN2nn3ngc15ProfanityFilter10InitializeEPvm"

HOS_H = r'''
#pragma once
#include <stdint.h>
typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
uint64_t hos_sys_alloc(uint64_t size, uint64_t align);
void hos_log(const char *fmt, ...);
'''
WINDOWS_H = r'''
#pragma once
typedef int SRWLOCK;
#define SRWLOCK_INIT 0
static int locked;
static inline void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; locked++; }
static inline void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; locked--; }
typedef long LONG;
static inline LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG o = *p; *p = v; return o; }
'''
FIXTURE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nn_offline.c"

static int allocs, inits, last_clear = -1, logs;
void hos_log(const char *fmt, ...) { (void)fmt; logs++; }
static uint64_t last_key, last_size;
uint64_t hos_sys_alloc(uint64_t size, uint64_t align) {
    allocs++, last_size = size;
    void *p = aligned_alloc((size_t)align, (size_t)size);
    memset(p, 0, (size_t)size);
    return (uint64_t)(uintptr_t)p;
}
void hos_system_event_init(uint64_t key, int autoclear) { inits++, last_key = key, last_clear = autoclear; }
static uint64_t call(void (*fn)(Ctx *), uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3) {
    Ctx c;
    memset(&c, 0x5A, sizeof c);
    c.x[0] = a0, c.x[1] = a1, c.x[2] = a2, c.x[3] = a3;
    fn(&c);
    return c.x[0];
}
#define CHECK(x) do { if (!(x)) { printf("FAIL %s (line %d)\n", #x, __LINE__); return 1; } } while (0)

int main(void) {
    /* GetOverSaveFrequencyLimitEvent: an event, not null; made once; manual-clear; at least the SDK's 0x30 bytes */
    uint64_t e = call(imp_EVENT, 0, 0, 0, 0);
    CHECK(e != 0 && (e & 0xF) == 0);
    CHECK(inits == 1 && last_key == e && last_clear == 0);
    CHECK(last_size >= 0x30);
    CHECK(call(imp_EVENT, 0, 0, 0, 0) == e && allocs == 1 && inits == 1);
    CHECK(locked == 0);
    /* AddInternetConnectionStatus(PlayReport*, key, key, key): success; the report's bytes stay as they were */
    unsigned char report[64];
    memset(report, 0x33, sizeof report);
    CHECK(call(imp_STATUS, (uint64_t)(uintptr_t)report, (uint64_t)(uintptr_t)"a", (uint64_t)(uintptr_t)"b",
               (uint64_t)(uintptr_t)"c") == 0);
    for (unsigned i = 0; i < sizeof report; i++) CHECK(report[i] == 0x33);
    /* RequestImmediateTransmission(): success */
    CHECK(call(imp_SEND, 0, 0, 0, 0) == 0);
    CHECK(allocs == 1);
    /* ProfanityFilter::Initialize(void*, size_t): 0xd092 (the SDK's own "no ngc service"); the object (+9 is its
       "initialized" byte) and the work buffer stay as they were; one log line however often it is called */
    unsigned char filter[0x30], work[256];
    memset(filter, 0, sizeof filter);
    memset(work, 0x44, sizeof work);
    CHECK(call(imp_NGC_INIT, (uint64_t)(uintptr_t)filter, (uint64_t)(uintptr_t)work, 0x20000, 0) == 0xd092);
    CHECK(call(imp_NGC_INIT, (uint64_t)(uintptr_t)filter, (uint64_t)(uintptr_t)work, 0x20000, 0) == 0xd092);
    for (unsigned i = 0; i < sizeof filter; i++) CHECK(filter[i] == 0);
    for (unsigned i = 0; i < sizeof work; i++) CHECK(work[i] == 0x44);
    CHECK(logs == 1 && allocs == 1);
    printf("ok\n");
    return 0;
}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default="gcc")
    a = ap.parse_args()
    failures = []

    def check(ok, what):
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    source = SOURCE.read_text(encoding="utf-8")
    names = re.findall(r"^HLE\((\w+)\)", source, re.M)
    check(set(names) == {EVENT, STATUS, SEND, NGC_INIT}, "the file implements the traced nn::prepo family and nn::ngc's "
          "Initialize (%d HLEs)" % len(names))
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("HLE("):
            above = lines[i - 1].rstrip()
            check(above.endswith("*/"), "%s has its comment (signature and answer) above it" % line[4:line.index(")")])
    # (the lift's own list of what host/ implements: what it finds is hooked, so no generated stub answers it)
    spec = importlib.util.spec_from_file_location("standalone", ROOT / "nx2" / "standalone.py")
    sys.path.insert(0, str(ROOT / "nx2"))
    standalone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(standalone)
    check({"imp_" + n for n in names} <= standalone.implemented(), "nx2/standalone.py finds them, so the lift hooks them")

    with tempfile.TemporaryDirectory(prefix="hookshot-offline-") as folder:
        folder = Path(folder)
        (folder / "hos.h").write_text(HOS_H, encoding="utf-8")
        (folder / "windows.h").write_text(WINDOWS_H, encoding="utf-8")
        (folder / "nn_offline.c").write_text(source, encoding="utf-8")
        fixture = FIXTURE.replace("imp_EVENT", "imp_" + EVENT).replace("imp_STATUS", "imp_" + STATUS).replace(
            "imp_SEND", "imp_" + SEND).replace("imp_NGC_INIT", "imp_" + NGC_INIT)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / "offline_test"
        b = subprocess.run([a.cc, "-std=c11", "-D_ISOC11_SOURCE", "-Wall", "-Werror", "-Wno-unused-function", "-I", str(folder),
                            str(folder / "fixture.c"), "-o", str(exe)], capture_output=True, text=True)
        check(b.returncode == 0, "nn_offline.c compiles with the stand-in helpers" + (": " + b.stderr if b.returncode else ""))
        if b.returncode == 0:
            r = subprocess.run([str(exe)], capture_output=True, text=True)
            check(r.returncode == 0 and r.stdout.strip() == "ok", "nn::prepo and nn::ngc answers (%s)" % r.stdout.strip())
    if failures:
        raise SystemExit("%d failed" % len(failures))


if __name__ == "__main__":
    main()
