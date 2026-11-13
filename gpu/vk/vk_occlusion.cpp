// (raiders) NVN's samples-passed counter from Vulkan occlusion queries: vk_occlusion.h says why and how.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <mutex>
#include <thread>
#include <vector>

#include "vk_occlusion.h"
#include "vk_game.h"
#include "vk_state.h"
#include "vk_work.h"   // (after the others: the query commands go through RX_VK_RECORDER with the draws around them)

namespace mkwvk {
namespace {

constexpr uint32_t kOcc = 1u << 18;              // queries in the ring
constexpr uint32_t kSeqMask = 0x7fffffffu;       // query numbers: 31 bits, as NvnState::samples_passed holds two of them
constexpr uint32_t kOccMaxBracket = 4096;        // draws a bracket counts
constexpr uint64_t kOn = 1ull << 63;             // samples_passed: a bracket is counting; bits 32-62 its first number, 0-30 the next
constexpr uint64_t kTagRecorded = 1ull << 40;    // tags: the query of that number was recorded (begun, or empty: bit 32)
constexpr uint64_t kTagEmpty = 1ull << 32;

VkQueryPool pool = VK_NULL_HANDLE;
VkQueryControlFlags control = 0;
std::atomic<uint64_t> tags[kOcc];                // per query: the number it was last recorded for (0: not since its reset)
std::mutex reset_mu;
uint32_t seq_next = 0;                           // (the replay thread's: replay_mu)
std::atomic<uint32_t> seq_high{0};               // (the same, for the collector)
thread_local int64_t armed = -1;                 // (the draw's query that draw() is to begin)
thread_local uint32_t open_query = 0;

std::atomic<int64_t> st_reports{0}, st_dropped{0};
struct Pending {
    uint32_t first, end;                         // the bracket's numbers so far
    uint64_t addr, ts;
    int64_t queued_us;                           // (T17: when the replay queued it, for RX_VK_OCC_LAG)
};
int64_t now_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
// (T17) RX_VK_OCC_LAG=<n>: every n reports written, how long after the replay queued them (the game's submit) the collector
// wrote their words: the median, the 95th percentile and the longest, in ms. The game polls the timestamp word, so a report
// written within one frame time is there for the game's next frame
void lag_note(int64_t us) {
    static const int n = getenv("RX_VK_OCC_LAG") ? std::max(0, atoi(getenv("RX_VK_OCC_LAG"))) : 0;
    static std::vector<int64_t> lags;
    if (!n) return;
    lags.push_back(us);
    if ((int)lags.size() < n) return;
    std::sort(lags.begin(), lags.end());
    logf("vk: occlusion: %d reports written %.2f ms after they were queued (median), 95%% within %.2f ms, the longest %.2f ms; "
         "%lld given up so far", n, lags[lags.size() / 2] / 1000.0, lags[lags.size() * 95 / 100] / 1000.0, lags.back() / 1000.0,
         (long long)st_dropped.load());
    lags.clear();
}
std::mutex pend_mu;
std::condition_variable pend_cv;
std::vector<Pending> pending;

bool on(const NvnState& s) { return (s.samples_passed & kOn) != 0; }
uint32_t first_of(const NvnState& s) { return (uint32_t)(s.samples_passed >> 32) & kSeqMask; }
uint32_t next_of(const NvnState& s) { return (uint32_t)s.samples_passed & kSeqMask; }
void set(NvnState& s, bool counting, uint32_t first, uint32_t next) {
    s.samples_passed = (counting ? kOn : 0) | (uint64_t)(first & kSeqMask) << 32 | (next & kSeqMask);
}
uint64_t tag_of(uint32_t q, bool empty) { return kTagRecorded | (empty ? kTagEmpty : 0) | q; }

bool make_pool() {
    if (!dev.vk12.hostQueryReset) {
        logf("vk: occlusion: no host query reset on this GPU: samples-passed reports keep the fixed value");
        return false;
    }
    VkQueryPoolCreateInfo qi{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};
    qi.queryType = VK_QUERY_TYPE_OCCLUSION;
    qi.queryCount = kOcc;
    if (vkCreateQueryPool(dev.device, &qi, nullptr, &pool) != VK_SUCCESS) {
        logf("vk: occlusion: no query pool: samples-passed reports keep the fixed value");
        pool = VK_NULL_HANDLE;
        return false;
    }
    vkResetQueryPool(dev.device, pool, 0, kOcc);
    for (uint32_t i = 0; i < kOcc; i++) tags[i].store(0, std::memory_order_relaxed);
    control = dev.features.occlusionQueryPrecise ? VK_QUERY_CONTROL_PRECISE_BIT : 0;
    logf("vk: occlusion: samples-passed reports from occlusion queries (%u, %s)", kOcc,
         control ? "precise" : "not precise: any count above 0 may be inexact");
    return true;
}

/// The bracket's sum once every query in it is recorded and available (false: not yet)
bool sum_of(const Pending& p, uint64_t* sum) {
    uint64_t total = 0;
    for (uint32_t q = p.first; q != p.end; q = (q + 1) & kSeqMask) {
        const uint32_t i = q % kOcc;
        const uint64_t t = tags[i].load(std::memory_order_acquire);
        if (t != tag_of(q, false) && t != tag_of(q, true)) return false;   // (its draw not recorded yet: a segment still being made)
        if (t & kTagEmpty) continue;
        uint64_t v = 0;
        const VkResult r = vkGetQueryPoolResults(dev.device, pool, i, 1, sizeof v, &v, sizeof v, VK_QUERY_RESULT_64_BIT);
        if (r != VK_SUCCESS) return false;   // (VK_NOT_READY: the GPU has not run it yet)
        total += v;
    }
    *sum = total;
    return true;
}

void collector() {
    static const int log_n = getenv("RX_VK_OCC_LOG") ? atoi(getenv("RX_VK_OCC_LOG")) : 0;
    static int logged = 0;
    std::vector<Pending> work, left;
    for (;;) {
        {
            std::unique_lock lk(pend_mu);
            if (pending.empty()) pend_cv.wait(lk, [] { return !pending.empty(); });
            work.swap(pending);
        }
        left.clear();
        const uint32_t high = seq_high.load(std::memory_order_relaxed);
        for (const Pending& p : work) {
            uint64_t sum = 0;
            if (!sum_of(p, &sum)) {
                if (((high - p.first) & kSeqMask) > kOcc / 2) {   // (its queries handed out again since: never)
                    if (st_dropped++ < 20) logf("vk: occlusion: a report at %#llx given up (queries %u-%u)", (unsigned long long)p.addr, p.first, p.end);
                    continue;
                }
                left.push_back(p);
                continue;
            }
            const uint64_t rec[2] = {sum, p.ts};
            guest_cpu_write(p.addr, rec, sizeof rec);   // (through the wrapper: the write-back diff's shadows hear of it)
            memory_cpu_owned(host->gpu_guest(p.addr), sizeof rec);
            st_reports++;
            lag_note(now_us() - p.queued_us);
            if (logged < log_n) {
                logged++;
                logf("vk: occlusion: report at %#llx: %llu samples from %u queries", (unsigned long long)p.addr,
                     (unsigned long long)sum, (p.end - p.first) & kSeqMask);
            }
        }
        work.clear();
        if (!left.empty()) {
            std::lock_guard lk(pend_mu);
            pending.insert(pending.begin(), left.begin(), left.end());
        }
        if (!left.empty()) std::this_thread::sleep_for(std::chrono::microseconds(500));   // (the GPU's results: polled)
    }
}

} // namespace

bool occ_real() {
    static const bool v = [] {
        bool want;
        if (const char* e = getenv("RX_VK_OCC_REAL")) want = atoi(e) != 0;
        else want = !getenv("RX_VK_OCC_FIXED") && !vk_game_oot.load(std::memory_order_relaxed);
        if (!want) return false;
        if (!make_pool()) return false;
        std::thread(collector).detach();
        return true;
    }();
    return v;
}

void occ_sync(NvnState& s) {
    if (!occ_real() || next_of(s) == seq_next) return;
    // (another command buffer or queue took numbers since: a bracket open across them would take those in, so it stops
    // counting, and its reports get the fixed value)
    set(s, false, seq_next, seq_next);
}

void occ_reset(NvnState& s) {
    if (!occ_real()) return;
    set(s, true, next_of(s), next_of(s));
}

int64_t occ_before_draw(NvnState& s, bool dry, bool worker) {
    if (!occ_real() || !on(s)) return -1;
    const uint32_t first = first_of(s), q = next_of(s);
    if (((q - first) & kSeqMask) >= kOccMaxBracket) {
        set(s, false, q, q);
        return -1;
    }
    set(s, true, first, (q + 1) & kSeqMask);
    if (!worker) {   // (the dry pass and the serial replay hand out numbers in stream order)
        seq_next = next_of(s);
        seq_high.store(seq_next, std::memory_order_relaxed);
    }
    if (!dry) {   // (the one that records the draw: its query reset, armed for draw())
        const uint32_t i = q % kOcc;
        {
            std::lock_guard lk(reset_mu);
            vkResetQueryPool(dev.device, pool, i, 1);
        }
        tags[i].store(0, std::memory_order_release);
        armed = q;
    }
    return q;
}

void occ_after_draw(int64_t q, bool dry) {
    if (q < 0 || dry) return;
    if (armed == q) {   // (draw() left it out before its draw command: it counts 0)
        tags[(uint32_t)q % kOcc].store(tag_of((uint32_t)q, true), std::memory_order_release);
        armed = -1;
    }
}

bool occ_report(NvnState& s, uint64_t addr, bool dry) {
    if (!occ_real() || !on(s)) return false;
    if (dry) return true;   // (the worker that records it queues it)
    const uint64_t ns = host->ticks() * 32;   // (as NOP_REPORT_COUNTER's timestamp, unscaled; never 0: the game polls that word)
    const uint64_t ts = std::max<uint64_t>(1, ns * 12 / 625);
    memory_cpu_owned(host->gpu_guest(addr), 16);   // (kept out of the write-backs from now: the collector writes them)
    if (first_of(s) == next_of(s)) {   // (nothing drawn since the reset: 0 now)
        const uint64_t rec[2] = {0, ts};
        guest_cpu_write(addr, rec, sizeof rec);
        return true;
    }
    {
        std::lock_guard lk(pend_mu);
        pending.push_back({first_of(s), next_of(s), addr, ts, now_us()});
    }
    pend_cv.notify_one();
    return true;
}

bool occ_begin(VkCommandBuffer cmd) {
    if (armed < 0) return false;
    const uint32_t q = (uint32_t)armed, i = q % kOcc;
    armed = -1;
    vkCmdBeginQuery(cmd, pool, i, control);
    tags[i].store(tag_of(q, false), std::memory_order_release);
    open_query = i;
    return true;
}

void occ_end(VkCommandBuffer cmd) { vkCmdEndQuery(cmd, pool, open_query); }

} // namespace mkwvk
