"""(raiders, T17b) The renderer reads every memory pool the host has, not the first 8192.

host->gpu_pools writes at most the list's length. The renderer's list was 8192 long, and Raiders has ~8,800 pools live in
the hub and more after a level: the pools past the 8192th (the highest addresses) left the renderer's pool table while the
game still drew from them, and draws whose index buffer lay there were left out (the ground missing after the gear menu).
The fixture cuts read_pool_list out of gpu/vk/vk_memory.cpp by text and drives it with a host of N pools; the callers are
checked by text. No game, no GPU.

    python -I -B tests/test_pool_list_all.py [--cxx c++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="c++")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_memory.cpp").read_text(encoding="utf-8")
    start = source.index("constexpr size_t kPoolListMax")
    fn = source[start:source.index("int read_pool_list(", start)] + block(source[start:], "int read_pool_list(")
    # (every reading of the host's pools goes through host_pool_list, and host_pool_list through read_pool_list)
    helper = block(source, "int host_pool_list(")
    if "read_pool_list(" not in helper or "host->gpu_pools(" not in helper:
        raise SystemExit("host_pool_list does not read the host's pools through read_pool_list")
    if source.count("host->gpu_pools(") != 1:
        raise SystemExit("host->gpu_pools is called outside host_pool_list: %d calls" % source.count("host->gpu_pools("))
    for marker in ("void memory_sync(", "void refresh_pool_ranges_locked("):
        if "host_pool_list(list)" not in block(source, marker):
            raise SystemExit("%s does not read the pools through host_pool_list" % marker)
    limit = int(re.search(r"kPoolListMax = 1u << (\d+);", fn).group(1))
    fixture = f'''#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
{fn}
static int calls;
struct Host {{   // (as host/nvdrv.c hos_gpu_pools: at most max of its pools, in address order; the count written)
    int pools;
    int operator()(uint64_t (*out)[2], int max) const {{
        calls++;
        int n = 0;
        for (int i = 0; i < pools && n < max; i++) out[n][0] = 0x1000000000ull + (uint64_t)i * 0x10000, out[n][1] = 0x1000, n++;
        return n;
    }}
}};
int main() {{
    for (const int pools : {{0, 1, 8191, 8192, 8193, 8823, 20000, 70000}}) {{
        std::vector<std::array<uint64_t, 2>> list(8192);
        calls = 0;
        const int n = read_pool_list(list, Host{{pools}});
        CHECK(n == pools);
        CHECK((int)list.size() >= n);
        CHECK(list[(size_t)std::max(n - 1, 0)][0] == (n ? 0x1000000000ull + (uint64_t)(n - 1) * 0x10000 : list[0][0]));   // the last one, the highest
        CHECK(calls <= 1 + 4);   // (8192 doubled to 131072 at most here)
        const int again = read_pool_list(list, Host{{pools}});   // (the list kept its length: one call)
        CHECK(again == pools);
    }}
    {{   // (an empty list starts at 8192)
        std::vector<std::array<uint64_t, 2>> list;
        CHECK(read_pool_list(list, Host{{9000}}) == 9000);
        CHECK(list.size() == 16384);
    }}
    {{   // (bounded: a host that always fills the list stops at kPoolListMax)
        std::vector<std::array<uint64_t, 2>> list(8192);
        auto full = [](uint64_t (*out)[2], int max) {{ for (int i = 0; i < max; i++) out[i][0] = 1, out[i][1] = 1; return max; }};
        CHECK(read_pool_list(list, full) == (1 << {limit}));
        CHECK(list.size() == (size_t)1 << {limit});
    }}
    {{   // (a host that answers less than 0)
        std::vector<std::array<uint64_t, 2>> list(8192);
        CHECK(read_pool_list(list, [](uint64_t (*)[2], int) {{ return -1; }}) == 0);
    }}
    std::printf("PASS: every pool the host has is read (8192 was the limit)\\n");
}}
'''
    with tempfile.TemporaryDirectory(prefix="pool-list-all-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
