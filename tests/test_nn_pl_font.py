"""(raiders) The built-in fonts' stand-in (host/nn_pl_font.c, nx2/host_font.py): both GetBuiltInFontData overloads fill the
0x18-byte struct (the font's address at +8, its size at +0x10, nothing past +0x18) and answer true; the font is the
included TrueType file, copied once into page-aligned memory and reused; RequestLoadNxFont touches nothing;
HOS_BUILTIN_FONT serves the named file instead, and an unreadable one falls back to the included font. The runtime's file
compiled with stand-in helpers; no game files.

    python -I -B tests/test_nn_pl_font.py [--cc gcc]
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "third_party" / "fonts" / "libertinus" / "LibertinusSans-Regular.ttf"
OUNCE = "_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb"
NX = "_ZN2nn2pl18GetBuiltInFontDataEPNS0_17BuiltInFontDataNxENS0_17BuiltInFontTypeNxEb"
REQUEST = "_ZN2nn2pl17RequestLoadNxFontEPvm"

HOS_H = r'''
#pragma once
#include <stdint.h>
typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
#define G64(a) (*(uint64_t *)GP(a))
void hos_log(const char *fmt, ...);
uint64_t hos_sys_alloc(uint64_t size, uint64_t align);
'''
WINDOWS_H = r'''
#pragma once
typedef int SRWLOCK;
typedef int LONG;
#define SRWLOCK_INIT 0
static inline void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; }
static inline void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; }
#define InterlockedExchange(p, v) __atomic_exchange_n((p), (v), __ATOMIC_SEQ_CST)
'''
FIXTURE = r'''
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nn_pl_font.c"

static int allocs, logs, font_logs;
static char last_log[512];
void hos_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_log, sizeof last_log, fmt, ap);
    va_end(ap);
    logs++;
    if (strstr(last_log, "GetBuiltInFontData(")) font_logs++;
}
uint64_t hos_sys_alloc(uint64_t size, uint64_t align) {
    allocs++;
    void *p = aligned_alloc((size_t)align, (size_t)size);
    memset(p, 0, (size_t)size);
    return (uint64_t)(uintptr_t)p;
}
static uint64_t call(void (*fn)(Ctx *), uint64_t a0, uint64_t a1, uint64_t a2) {
    Ctx c;
    memset(&c, 0x5A, sizeof c);
    c.x[0] = a0, c.x[1] = a1, c.x[2] = a2, c.x[30] = 0x80001234;
    fn(&c);
    return c.x[0];
}
#define CHECK(x) do { if (!(x)) { printf("FAIL %s (line %d)\n", #x, __LINE__); return 1; } } while (0)

int main(int argc, char **argv) {
    unsigned char s[0x20], t[0x20];
    memset(s, 0xAA, sizeof s);
    memset(t, 0xAA, sizeof t);
    uint64_t r = call(imp_OUNCE, (uint64_t)(uintptr_t)s, 0, 0);
    uint64_t addr, size;
    memcpy(&addr, s + 8, 8);
    memcpy(&size, s + 0x10, 8);
    CHECK(r == 1);
    CHECK(s[0] == 0 && s[1] == 0 && s[7] == 0);   /* (+0..+7 zeroed) */
    CHECK(s[0x18] == 0xAA && s[0x1F] == 0xAA);    /* (nothing past the 0x18-byte struct) */
    CHECK(addr != 0 && (addr & 0xFFF) == 0);
    printf("size %llu\n", (unsigned long long)size);
    fwrite((const void *)(uintptr_t)addr, 1, (size_t)size, fopen(argv[1], "wb")) ;
    /* the Nx overload: the same copy; another type: no new copy */
    CHECK(call(imp_NX, (uint64_t)(uintptr_t)t, 5, 0) == 1);
    CHECK(memcmp(s, t, 0x18) == 0);
    CHECK(call(imp_OUNCE, (uint64_t)(uintptr_t)t, 3, 1) == 1 && memcmp(s, t, 0x18) == 0);
    CHECK(call(imp_OUNCE, (uint64_t)(uintptr_t)t, 0, 0) == 1);
    CHECK(allocs == 1);
    CHECK(font_logs == 3);   /* (Ounce 0, Nx 5, Ounce 3: each once) */
    /* a null struct pointer: still true, nothing written */
    CHECK(call(imp_OUNCE, 0, 1, 0) == 1);
    /* RequestLoadNxFont: the game's buffer stays as it was; logged once */
    unsigned char buf[64];
    memset(buf, 0x77, sizeof buf);
    int before = logs;
    call(imp_REQUEST, (uint64_t)(uintptr_t)buf, sizeof buf, 0);
    call(imp_REQUEST, (uint64_t)(uintptr_t)buf, sizeof buf, 0);
    CHECK(logs == before + 1);
    for (unsigned i = 0; i < sizeof buf; i++) CHECK(buf[i] == 0x77);
    printf("ok\n");
    return 0;
}
'''


def build(cc, folder):
    folder = Path(folder)
    (folder / "hos.h").write_text(HOS_H, encoding="utf-8")
    (folder / "windows.h").write_text(WINDOWS_H, encoding="utf-8")
    # (the runtime's file beside the stand-in headers, so its #include "hos.h" finds them)
    (folder / "nn_pl_font.c").write_text((ROOT / "host" / "nn_pl_font.c").read_text(encoding="utf-8"), encoding="utf-8")
    fixture = FIXTURE.replace("imp_OUNCE", "imp_" + OUNCE).replace("imp_NX", "imp_" + NX).replace(
        "imp_REQUEST", "imp_" + REQUEST)
    (folder / "fixture.c").write_text(fixture, encoding="utf-8")
    host_font = load_host_font()
    host_font.write(str(folder / "host_font.c"))
    exe = folder / "font_test"
    subprocess.run([cc, "-std=c11", "-D_ISOC11_SOURCE", "-Wall", "-Werror", "-Wno-unused-function", "-I", str(folder),
                    str(folder / "fixture.c"), str(folder / "host_font.c"), "-o", str(exe)],
                   check=True)
    return exe


def load_host_font():
    spec = importlib.util.spec_from_file_location("host_font", ROOT / "nx2" / "host_font.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(exe, out, font=None):
    env = dict(os.environ)
    env.pop("HOS_BUILTIN_FONT", None)
    if font is not None:
        env["HOS_BUILTIN_FONT"] = font
    return subprocess.run([str(exe), str(out)], capture_output=True, text=True, env=env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default="gcc")
    a = ap.parse_args()
    failures = []

    def check(ok, what):
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    font = FONT.read_bytes()
    host_font = load_host_font()
    text = host_font.source()
    check("const unsigned hos_builtin_font_size = %d;" % len(font) in text, "the generated file's size is the font's")
    check(font[:4] == b"\x00\x01\x00\x00", "the included font starts with the TrueType signature")
    with tempfile.TemporaryDirectory(prefix="hookshot-pl-font-") as folder:
        out = Path(folder) / "host_font.c"
        host_font.write(str(out))
        stamp = out.stat().st_mtime_ns
        host_font.write(str(out))
        check(out.stat().st_mtime_ns == stamp and out.read_text(encoding="utf-8") == text, "an unchanged file is not rewritten")

        exe = build(a.cc, folder)
        served = Path(folder) / "served.bin"
        r = run(exe, served)
        check(r.returncode == 0 and "ok" in r.stdout, "the included font: struct, true, one copy, logs (%s)" % r.stdout.strip())
        check(served.read_bytes() == font, "the served bytes are the included font's, %d bytes" % len(font))

        own = Path(folder) / "own.otf"
        own.write_bytes(b"OTTO" + bytes(range(60)))
        r = run(exe, served, str(own))
        check(r.returncode == 0 and served.read_bytes() == own.read_bytes(), "HOS_BUILTIN_FONT serves the named file")
        r = run(exe, served, str(Path(folder) / "missing.ttf"))
        check(r.returncode == 0 and served.read_bytes() == font, "an unreadable HOS_BUILTIN_FONT falls back to the included font")

    build_py = (ROOT / "nx2" / "build.py").read_text(encoding="utf-8")
    check("host_srcs.append(host_font.write(os.path.join(gen_dir, \"host_font.c\")))" in build_py and
          "import host_font" in build_py, "nx2/build.py compiles the generated font into the runtime")
    provenance = (ROOT / "third_party" / "fonts" / "PROVENANCE.md").read_text(encoding="utf-8")
    check("nx2/host_font.py" in provenance, "third_party/fonts/PROVENANCE.md names the runtime's use")
    if failures:
        raise SystemExit("%d failed" % len(failures))


if __name__ == "__main__":
    main()
