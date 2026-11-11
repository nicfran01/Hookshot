// (raiders) NVN's samples-passed counter as the GPU counts it: Vulkan occlusion queries around the draws between a
// nvnCommandBufferResetCounter(SAMPLES_PASSED) and the reports after it, summed and written to the report's address once the
// GPU has them.
//
// Why: the replay wrote 4096 for every samples-passed report (vk_replay.cpp NOP_REPORT_COUNTER, upstream's fix for Ocarina's
// sun). Splatoon Raiders counts pixels with these reports (its collision-paint code draws a mesh between a reset and a report,
// "countup"), and from the counts decides the ink under the player: with 4096 everywhere the ground read as enemy ink (slow
// walk, health drain, no swimming in one's own ink; docs/plans/reports/M4-first-frame.md, session 5).
//
// How:
//  - A reset opens a bracket; each draw after it gets the next query of a ring (a sequence number in stream order); a report
//    closes nothing (NVN's counter keeps counting) and asks for the sum of the bracket's queries so far. A bracket stops counting
//    after kOccMaxBracket draws (a game that resets once and draws all frame): its later reports get the fixed value.
//  - The numbers come from the dry pass and the serial replay (stream order, replay_mu held); a parallel segment's worker gets
//    the same ones from its state snapshot, so the worker that records a draw begins and ends its query.
//  - The bookkeeping lives in NvnState::samples_passed (unused by this path otherwise): vk_state.h is part of the shader
//    caches' stamp, and a new field there would make every game recompile its shaders.
//  - The report's words are written by a collector thread once all the queries are available (the game polls the timestamp
//    word: Raiders' reader, 0x811eb380 in its build, takes a result only once that word is not 0).
//
// RX_VK_OCC_REAL=1 / 0 chooses; the default is on for games other than Ocarina (vk_game.h), and RX_VK_OCC_FIXED set is off
// (that switch keeps its meaning). RX_VK_OCC_LOG=<n>: the first n collected reports, with their counts.
#pragma once

#include <cstdint>

#include "vk_internal.h"

namespace mkwvk {

struct NvnState;

/// Real samples-passed counts (the switch above)
bool occ_real();
/// The replay thread, before a command buffer's replay (and before its parallel segments' first state is copied): the state's
/// next query number follows the ones handed out by other command buffers and queues
void occ_sync(NvnState& s);
/// NOP_RESET_COUNTER of SAMPLES_PASSED (every mode)
void occ_reset(NvnState& s);
/// Before a draw (every mode): its query number, or -1 when it is not counted. Not dry: the number is armed for occ_begin.
/// worker: a parallel segment's replay (the numbers are its snapshot's); else the dry pass or the serial replay hand them out
int64_t occ_before_draw(NvnState& s, bool dry, bool worker);
/// After it: an armed query that draw() did not begin is recorded as empty (a draw left out counts 0)
void occ_after_draw(int64_t q, bool dry);
/// NOP_REPORT_COUNTER of SAMPLES_PASSED. Not dry: the report is queued for the collector. False: no bracket is counting (the
/// caller writes the fixed value as before)
bool occ_report(NvnState& s, uint64_t addr, bool dry);
/// In draw(), with the pass open, right before the draw command: begins the armed query (true), or nothing
bool occ_begin(VkCommandBuffer cmd);
void occ_end(VkCommandBuffer cmd);

/// draw(): begins the armed query for the draw command after it, ends it when draw() returns
struct OccQuery {
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    explicit OccQuery(VkCommandBuffer c) {
        if (occ_begin(c)) cmd = c;
    }
    ~OccQuery() {
        if (cmd) occ_end(cmd);
    }
    OccQuery(const OccQuery&) = delete;
    OccQuery& operator=(const OccQuery&) = delete;
};

} // namespace mkwvk
