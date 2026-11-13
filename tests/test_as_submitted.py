"""(raiders, T17a) Uniform buffers and lately written read-only storage buffers are copied as submitted when the pools
have no VRAM mirrors, except memory the GPU writes.

Compiles gpu/vk/as_submitted_policy.h against its cases (the switches, the two decisions, the frame-generation ring), and
checks by text that vk_draw.cpp's uniform and storage bindings take their decisions from it before they bind the pool,
that the copies are read as submitted and kept per recording only, and that vk_memory.cpp records every GPU write's
granules. No game and no GPU.
    python -I -B tests/test_as_submitted.py --cxx c++
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include "as_submitted_policy.h"
#include <cstdio>
namespace as = mkwvk::as_submitted;
static int bad = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL:%d %s\n", __LINE__, #x); bad++; } } while (0)
int main() {
    // the switches: unset follows the mirrors; a number decides; anything else is on (the old "set")
    CHECK(as::switch_on(nullptr, false));      // integrated GPU (the Deck): copied
    CHECK(!as::switch_on(nullptr, true));      // discrete GPU: the mirror already holds the submission's contents
    CHECK(!as::switch_on("0", false));
    CHECK(!as::switch_on("00", true));
    CHECK(as::switch_on("1", true));
    CHECK(as::switch_on("2", false));
    CHECK(as::switch_on("", true));
    CHECK(as::switch_on("yes", true));
    // uniform buffers: all, except memory the GPU writes
    CHECK(as::copy_uniform(true, false));
    CHECK(!as::copy_uniform(true, true));
    CHECK(!as::copy_uniform(false, false));
    // read-only storage buffers: written lately by the CPU, not the GPU, and not too big
    CHECK(as::copy_storage(true, 4096, true, false));
    CHECK(as::copy_storage(true, as::kStorageCopyMax, true, false));
    CHECK(!as::copy_storage(true, as::kStorageCopyMax + 1, true, false));
    CHECK(!as::copy_storage(true, 4096, false, false));   // (data loaded long ago)
    CHECK(!as::copy_storage(true, 4096, true, true));     // (records a GPU program writes)
    CHECK(!as::copy_storage(false, 4096, true, false));
    CHECK(!as::copy_storage(true, 0, true, false));
    // the ring: the generation as a frame began, looked up some frames later
    as::GenRing r;
    CHECK(r.before(10, 3) == 0);   // (nothing noted: 0, everything recent)
    r.note(10, 100);
    r.note(10, 150);               // (later in frame 10: its start stands)
    r.note(11, 200);
    r.note(13, 400);               // (frame 12 not noted)
    CHECK(r.before(13, 3) == 100);
    CHECK(r.before(14, 3) == 200);
    CHECK(r.before(15, 3) == 200); // (12 missing: the newest at or before it, 11)
    CHECK(r.before(16, 3) == 400);
    CHECK(r.before(2, 3) == 0);
    for (uint64_t f = 20; f < 40; f++) r.note(f, (uint32_t)(f * 10));
    CHECK(r.before(39, 3) == 360); // (old slots overwritten as the ring turns)
    CHECK(r.before(39, as::kRing + 2) == 0 || r.before(39, as::kRing + 2) <= 290);
    if (!bad) std::printf("policy: all cases\n");
    return bad != 0;
}
"""


def block(text, marker):
    start = text.index(marker)
    at = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[at] == "{") - (text[at] == "}")
        at += 1
    return text[start:at]


def need(cond, message):
    if not cond:
        raise SystemExit("FAIL: " + message)


def check_sources():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    internal = (ROOT / "gpu/vk/vk_internal.h").read_text(encoding="utf-8")
    need('#include "as_submitted_policy.h"' in draw and '#include "as_submitted_policy.h"' in memory,
         "vk_draw.cpp and vk_memory.cpp include as_submitted_policy.h")

    # uniform buffers
    uniform = block(draw, "VkDescriptorBufferInfo uniform_range(")
    ubo = uniform[uniform.index("if (index >= 3 && index < 3 + 16)"):]
    switch = 'as_submitted::switch_on(getenv("RX_VK_UB_SNAPSHOT"), memory_mirrors_on())'
    decide = "as_submitted::copy_uniform(snapshot_on, snapshot_on && memory_gpu_written(u.addr, n))"
    bind = "snapshot ? BufferRef{} : gpu_buffer_bind(u.addr, n, false)"
    need(switch in ubo and decide in ubo and bind in ubo, "uniform_range decides the copy from the policy, the mirrors and GPU writes")
    need(ubo.index(decide) < ubo.index(bind), "the uniform decision comes before the pool is bound")
    need(ubo.index("memory_read_as_submitted(u.addr, cur->mapped + at, n)") > ubo.index(bind),
         "a uniform snapshot takes the stream copy as submitted")

    # read-only storage buffers
    copy = block(draw, "BufferRef storage_as_submitted(uint64_t addr, uint64_t size) {")
    need('as_submitted::switch_on(getenv("RX_VK_SB_SNAPSHOT"), memory_mirrors_on())' in copy, "RX_VK_SB_SNAPSHOT follows the mirrors")
    need("memory_generation_before(texture_frame_no(), as_submitted::kRecentFrames)" in copy and
         "memory_written_since(guest, size, since)" in copy, "only storage the CPU wrote in the last frames is copied")
    need("as_submitted::copy_storage(on, size, true, memory_gpu_written(addr, size))" in copy, "GPU-written storage stays in place")
    need("memory_read_as_submitted(addr, cur->mapped + at, size)" in copy, "a storage copy is read as submitted")
    need("cur->sb_copies[addr] = {size, cur->stream, at};" in copy and "cur->sb_copies.find(addr)" in copy,
         "a storage copy is made once a recording")
    need("r.sb_copies.clear();" in block(draw, "void draw_begin_recording("),
         "a recording's storage copies are forgotten when its slot is used again")
    ssbo = draw[draw.index("const bool plausible = d.count == 1 ||"):]
    need("d.count == 1 && !d.is_written && !wide_n ? storage_as_submitted(base, n)" in ssbo and
         ssbo.index("storage_as_submitted(base, n)") < ssbo.index("gpu_buffer_bind(base, n, d.is_written && !bare)"),
         "only a single read-only storage buffer is asked for a copy, before it is bound in place")

    # the GPU's writes and the exports
    stamp = block(memory, "void memory_stamp_gpu(")
    need("gpu_granules[g / 64].fetch_or(" in stamp and stamp.index("gpu_granules") < stamp.index("if (!gpu_pages_on()) return;"),
         "every GPU write records its pages, whatever RX_VK_GPU_PAGES says")
    written = block(memory, "bool memory_gpu_written(")
    need("return true;   // (unknown: as written)" in written, "a range outside the window counts as GPU-written")
    need("constexpr uint64_t kGranuleShift = kPageShift;" in memory, "GPU writes are recorded by page, not coarser")
    need("return mirror_on();" in block(memory, "bool memory_mirrors_on()"), "memory_mirrors_on answers what bindings use")
    need("ring.before(frame, frames)" in block(memory, "uint32_t memory_generation_before("), "the ring answers the generation")
    for decl in ("bool memory_mirrors_on();", "bool memory_gpu_written(uint64_t gpu, uint64_t size);",
                 "uint32_t memory_generation_before(uint64_t frame, uint32_t frames);"):
        need(decl in internal, "vk_internal.h declares " + decl)
    # (the exports outside the file's anonymous namespaces, so vk_draw.cpp links to them)
    for name in ("bool memory_mirrors_on()", "bool memory_gpu_written(", "uint32_t memory_generation_before("):
        before = memory[:memory.index(name)].splitlines()
        opened = sum(1 for line in before if line.rstrip() == "namespace {")
        closed = sum(1 for line in before if line.startswith("} // namespace") or line.startswith("}  // namespace"))
        need(opened == closed, name + " is inside an anonymous namespace")
    before = draw[:draw.index("void as_submitted_count(int kind, uint64_t bytes) {")].splitlines()
    need(sum(1 for line in before if line.rstrip() == "namespace {") ==
         sum(1 for line in before if line.startswith("} // namespace") or line.startswith("}  // namespace")),
         "as_submitted_count is defined where its declaration at the top names it (mkwvk, not an anonymous namespace)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="c++")
    a = p.parse_args()
    check_sources()
    with tempfile.TemporaryDirectory(prefix="as-submitted-") as tmp:
        src = Path(tmp) / "as_submitted.cpp"
        exe = Path(tmp) / "as_submitted"
        src.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"), str(src), "-o", str(exe)],
                       check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: uniform buffers and lately written read-only storage buffers are copied as submitted where the pools are not mirrored")


if __name__ == "__main__":
    main()
