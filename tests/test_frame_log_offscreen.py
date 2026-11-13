"""(raiders, T17) RX_VK_FRAME_LOG in a headless run: do_present's offscreen present returned before present_image, so
present_out's frame-time line was never written and the file stayed empty (the Deck's scripted runs are headless). The CSV
is one function, frame_time_log, called by present_out and by do_present when offscreen. Checked as text (both calls, the
offscreen one before the return) and by compiling the function itself with a driver that presents three times. No GPU.

    python -I -B tests/test_frame_log_offscreen.py [--cxx clang++]
"""
import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
p.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
a = p.parse_args()
replay = (a.source.resolve() / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")


def function(head):
    start = replay.index(head)
    return replay[start:replay.index("\n}\n", start) + 3]


log = function("static void frame_time_log() {")
assert 'getenv("RX_VK_FRAME_LOG")' in log, "frame_time_log does not open RX_VK_FRAME_LOG"
out = function("static void present_out(uint32_t index, std::unique_lock<std::mutex>& qk) {")
assert "frame_time_log();" in out, "present_out no longer writes the frame-time line"
assert 'getenv("RX_VK_FRAME_LOG")' not in out, "present_out has a second copy of the frame-time line"
present = function("void do_present(const nvn_tex* t, const int crop[4]) {")
offscreen = present.index("if (dev.offscreen) frame_time_log();")
ret = present.index("if (dev.offscreen || interpolated) return;")
assert offscreen < ret, "the offscreen frame-time line comes after do_present's offscreen return"
assert replay.index("static void frame_time_log() {") < replay.index("void do_present(const nvn_tex* t, const int crop[4]) {")

cxx = shutil.which(a.cxx)
if not cxx:
    print("frame log offscreen: text checks passed; no %s, the compiled check skipped" % a.cxx)
    raise SystemExit(0)
with tempfile.TemporaryDirectory() as tmp:
    src, exe, csv = Path(tmp, "t.cpp"), Path(tmp, "t"), Path(tmp, "frames.csv")
    src.write_text("#include <chrono>\n#include <cstdio>\n#include <cstdlib>\n#include <thread>\n" + log +
                   "int main() {\n    for (int i = 0; i < 3; i++) { frame_time_log(); "
                   "std::this_thread::sleep_for(std::chrono::milliseconds(20)); }\n    return 0;\n}\n")
    r = subprocess.run([cxx, "-std=c++17", "-o", str(exe), str(src)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([str(exe)], env=dict(os.environ, RX_VK_FRAME_LOG=str(csv)), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    lines = csv.read_text().splitlines()
    assert lines[0] == "frame,time_s,frametime_ms", lines
    assert len(lines) == 4, lines   # (the header and three presents, flushed at exit)
    for n, line in enumerate(lines[1:]):
        m = re.fullmatch(r"(\d+),(\d+\.\d{4}),(\d+\.\d{3})", line)
        assert m and int(m[1]) == n, line
        if n:
            assert float(m[3]) >= 15.0, line   # (the 20 ms between presents)
print("frame log offscreen: OK (text and compiled checks)")
