"""(raiders, T19) nn::os TLS slots in host/hos_thread.c: AllocateTlsSlot, SdkAllocateTlsSlot, FreeTlsSlot, Get/SetTlsValue
share one table. nn::movie's Initialize takes an SDK slot and its Finalize frees it, once per movie: run as the sdk's code,
SdkAllocateTlsSlot took from the sdk's own table and FreeTlsSlot (host) never gave the slot back, so after 11 movies the
next one found none and aborted.

The block from `slot_used` to the ticks section is cut out of hos_thread.c by text and compiled with stand-ins for the
runtime (HLE, ARG, RET, G32, the thread list, SRW locks):
- SdkAllocateTlsSlot exists and takes from the top, AllocateTlsSlot from the bottom;
- 100 SDK take/free cycles never run out (the movie menu opened and closed);
- a slot taken again reads 0 in every thread, as the console's TlsManager does (SetZeroToAllThreadsTlsSafe);
- with all 32 taken, both answer os::ResultOutOfResource (0x2C01).

No game files.

    python -I -B tests/test_movie_tls_slots.py [--cc gcc]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int32_t LONG;
typedef pthread_rwlock_t SRWLOCK;
#define SRWLOCK_INIT PTHREAD_RWLOCK_INITIALIZER
#define AcquireSRWLockShared pthread_rwlock_rdlock
#define ReleaseSRWLockShared pthread_rwlock_unlock
#define InterlockedCompareExchange(p, x, c) __sync_val_compare_and_swap((p), (c), (x))
#define HOS_TLS_SLOTS 32
typedef struct { uint64_t x[32]; } Ctx;
typedef struct { uint64_t tls_slots[HOS_TLS_SLOTS]; } HosThread;
static uint8_t guest[64];
#define HLE(sym) static void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define G32(a) (*(uint32_t *)(guest + (a)))
static SRWLOCK threads_lock = SRWLOCK_INIT;
static HosThread t0, t1, *threads[2] = {&t0, &t1};
static int nthreads = 2;
static HosThread *cur = &t0;

/*BLOCK*/

static int fails;
#define CHECK(ok, what) do { if (!(ok)) { printf("FAIL %s\n", what); fails++; } else printf("ok   %s\n", what); } while (0)
static uint64_t sdk_alloc(void) { Ctx c = {{0}}; c.x[0] = 0; imp__ZN2nn2os18SdkAllocateTlsSlotEPNS0_7TlsSlotEPFvmE(&c); return c.x[0]; }
static uint64_t alloc(void) { Ctx c = {{0}}; c.x[0] = 0; imp__ZN2nn2os15AllocateTlsSlotEPNS0_7TlsSlotEPFvmE(&c); return c.x[0]; }
static uint32_t slot(void) { return G32(0); }
static void fre(uint32_t s) { Ctx c = {{0}}; c.x[0] = s; imp__ZN2nn2os11FreeTlsSlotENS0_7TlsSlotE(&c); }
static void set(uint32_t s, uint64_t v) { Ctx c = {{0}}; c.x[0] = s; c.x[1] = v; imp__ZN2nn2os11SetTlsValueENS0_7TlsSlotEm(&c); }
static uint64_t get(uint32_t s) { Ctx c = {{0}}; c.x[0] = s; imp__ZN2nn2os11GetTlsValueENS0_7TlsSlotE(&c); return c.x[0]; }

int main(void) {
    CHECK(alloc() == 0 && slot() == 0, "AllocateTlsSlot: the first game slot is 0");
    const uint32_t game = slot();
    CHECK(sdk_alloc() == 0 && slot() == HOS_TLS_SLOTS - 1, "SdkAllocateTlsSlot: from the top (31)");
    const uint32_t s = slot();
    int ok = 1;
    for (int i = 0; i < 100 && ok; i++) {   /* (the gadget preview opened and closed) */
        fre(s);
        ok = sdk_alloc() == 0 && slot() == s;
    }
    CHECK(ok, "100 SDK take/free cycles: the same slot each time, never out of slots");
    cur = &t0; set(s, 0x1111);
    cur = &t1; set(s, 0x2222);
    set(game, 0x3333);
    fre(s);
    CHECK(sdk_alloc() == 0 && slot() == s, "the slot taken again");
    cur = &t0; uint64_t a = get(s);
    cur = &t1; uint64_t b = get(s);
    CHECK(a == 0 && b == 0, "a slot taken again reads 0 in every thread (SetZeroToAllThreadsTlsSafe)");
    CHECK(get(game) == 0x3333, "another slot's value is left alone");
    int n = 2;
    while (alloc() == 0) n++;
    CHECK(n == HOS_TLS_SLOTS, "32 slots in all");
    CHECK(alloc() == 0x2C01 && sdk_alloc() == 0x2C01, "then both answer os::ResultOutOfResource");
    printf(fails ? "%d failed\n" : "all passed\n", fails);
    return fails != 0;
}
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cc", default="cc")
    a = p.parse_args()
    src = (ROOT / "host" / "hos_thread.c").read_text(encoding="utf-8")
    start = src.index("static volatile LONG slot_used[HOS_TLS_SLOTS];")
    end = src.index("/* ---- ticks", start)
    block = src[start:end]
    for name in ("_ZN2nn2os15AllocateTlsSlotEPNS0_7TlsSlotEPFvmE", "_ZN2nn2os18SdkAllocateTlsSlotEPNS0_7TlsSlotEPFvmE",
                 "_ZN2nn2os11FreeTlsSlotENS0_7TlsSlotE", "_ZN2nn2os11GetTlsValueENS0_7TlsSlotE",
                 "_ZN2nn2os11SetTlsValueENS0_7TlsSlotEm"):
        if "HLE(%s)" % name not in block:
            print("FAIL hos_thread.c's TLS block has no HLE(%s)" % name)
            return 1
    with tempfile.TemporaryDirectory(prefix="tls-slots-") as tmp:
        c = Path(tmp) / "t.c"
        c.write_text(HARNESS.replace("/*BLOCK*/", block), encoding="utf-8")
        exe = Path(tmp) / "t"
        subprocess.run([a.cc, "-std=gnu11", "-Wall", "-Wno-unused-function", str(c), "-o", str(exe), "-lpthread"],
                       check=True)
        return subprocess.run([str(exe)]).returncode


if __name__ == "__main__":
    sys.exit(main())
