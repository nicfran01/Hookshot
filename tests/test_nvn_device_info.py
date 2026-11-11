"""(raiders, T11) Per-game device limits: nvnDeviceGetInteger answers from host/nvn_native.c devinfo[] unless the game's config
(games/<id>/game.py NVN_DEVICE_INFO) names the id, through the table nx2/standalone.py nvn_device_info_c writes into
gen/hos_image.c.

- nvn_device_info_c: Raiders' overrides in id order, ending at -1; a game with no field gets only the end; a bad id or value
  stops the lift;
- the real devinfo[] and NV(nvnDeviceGetInteger), cut out of nvn_native.c by text and compiled against the generator's own
  output: an overridden id answers the game's value, every other id the shared table's, an id past the table still stops.

No game files.

    python -I -B tests/test_nvn_device_info.py [--cc gcc]
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def block(text, marker):
    """the text from marker to its balanced closing brace (as tests/test_nvn_null_pool.py's)"""
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


FIXTURE = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint64_t x[32]; } Ctx;
#define U32(i) ((uint32_t)c->x[i])
#define P(i) ((void *)(uintptr_t)c->x[i])
#define NV(name) static void n_##name(Ctx *c, void *u_)
static void die(const char *fmt, ...) { (void)fmt; exit(86); }
static void hos_log(const char *fmt, ...) { (void)fmt; }
@OVERRIDES@
@TABLE@;
@FUNCTION@
static int ask(unsigned id) {
    Ctx c;
    int out = -12345;
    memset(&c, 0, sizeof c);
    c.x[1] = id, c.x[2] = (uint64_t)(uintptr_t)&out;
    n_nvnDeviceGetInteger(&c, NULL);
    return out;
}
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) printf("%d\n", ask((unsigned)strtoul(argv[i], NULL, 0)));
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

    sys.path.insert(0, str(ROOT / "nx2"))
    standalone = load("standalone", ROOT / "nx2" / "standalone.py")
    raiders = load("raiders_game", ROOT / "games" / "raiders" / "game.py")
    oot = load("oot_game", ROOT / "games" / "oot" / "game.py")

    line = standalone.nvn_device_info_c(raiders)
    check(line.startswith("const int hos_game_nvn_devinfo[][2] = {{0x31, 0}, {-1, 0}};"), "Raiders' overrides: " + line)
    empty = standalone.nvn_device_info_c(oot)
    check(empty.startswith("const int hos_game_nvn_devinfo[][2] = {{-1, 0}};"), "a game with no field gets only the end")
    two = standalone.nvn_device_info_c(types.SimpleNamespace(ID="t", NVN_DEVICE_INFO={0x40: 7, 0x02: -1}))
    check("{{0x2, -1}, {0x40, 7}, {-1, 0}}" in two, "overrides are written in id order")
    for bad in ({0x100: 1}, {-1: 1}, {"1": 1}, {1: 2**31}, {1: 1.5}):
        try:
            standalone.nvn_device_info_c(types.SimpleNamespace(ID="t", NVN_DEVICE_INFO=bad))
            check(False, "a bad override stops the lift: %r" % bad)
        except SystemExit:
            check(True, "a bad override stops the lift: %r" % bad)
    check("nvn_device_info_c(game)" in (ROOT / "nx2" / "standalone.py").read_text(encoding="utf-8"),
          "write_image_c writes the table into gen/hos_image.c")
    check("extern const int hos_game_nvn_devinfo[][2];" in (ROOT / "host" / "hos_game.h").read_text(encoding="utf-8"),
          "host/hos_game.h declares it")

    source = (ROOT / "host" / "nvn_native.c").read_text(encoding="utf-8")
    table = block(source, "static const int devinfo[] = {")
    function = block(source, "NV(nvnDeviceGetInteger)")
    with tempfile.TemporaryDirectory(prefix="hookshot-devinfo-") as folder:
        results = {}
        for name, overrides in (("raiders", line), ("none", empty)):
            c = Path(folder) / ("%s.c" % name)
            c.write_text(FIXTURE.replace("@OVERRIDES@", overrides).replace("@TABLE@", table)
                         .replace("@FUNCTION@", function), encoding="utf-8")
            exe = Path(folder) / name
            b = subprocess.run([a.cc, "-std=c11", "-Wall", "-Werror", "-Wno-unused-function", str(c), "-o", str(exe)],
                               capture_output=True, text=True)
            check(b.returncode == 0, "nvnDeviceGetInteger compiles (%s)%s" % (name, ": " + b.stderr if b.returncode else ""))
            if b.returncode:
                continue
            r = subprocess.run([str(exe), "0x31", "0x00", "0x01", "0x2e", "0x04"], capture_output=True, text=True)
            results[name] = r.stdout.split()
            r = subprocess.run([str(exe), "0xc0"], capture_output=True, text=True)
            check(r.returncode == 86, "an id past the table still stops (%s)" % name)
        check(results.get("raiders") == ["0", "231", "40", "201", "256"],
              "with Raiders' overrides: 0x31 -> 0, the rest from devinfo[] (%s)" % results.get("raiders"))
        check(results.get("none") == ["5", "231", "40", "201", "256"],
              "with none: devinfo[] as it was (%s)" % results.get("none"))
    if failures:
        raise SystemExit("%d failed" % len(failures))


if __name__ == "__main__":
    main()
