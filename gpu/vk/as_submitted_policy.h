/* (raiders, T17a) Which buffer ranges a draw reads as they were at their submission, copied into the recording's
 * stream, rather than bound in guest memory where the GPU reads them when it gets there.
 *
 * Without VRAM mirrors (integrated GPUs: the Steam Deck), a buffer bound in an imported pool is read by the GPU from
 * guest memory at execution time, while the game's threads already write the next frames' data into it. Raiders' 2D
 * layer came out with another frame's data for one frame in two (T17a): with its constants, flat white or black shapes,
 * a counter partly drawn, the water warning missing, the respawn wipe the wrong size; with its read-only storage
 * buffers, another string's letters in the button prompts. docs/design.md rule 2: nothing the replay reads comes from
 * live guest memory. With mirrors, the mirror's sync at the submission's start already gives that, so nothing is copied.
 *
 * - Uniform buffers (small): all of them, unless the GPU itself writes that memory (a copy taken now would hold the
 *   CPU's older bytes, before the GPU's write the draw must see). RX_VK_UB_SNAPSHOT.
 * - Single read-only storage buffers: those the CPU wrote in the last kRecentFrames frames, up to kStorageCopyMax
 *   bytes, not GPU-written. Data loaded once stays where it is. RX_VK_SB_SNAPSHOT.
 * Each switch: unset, on exactly when the pools are not mirrored; a number, 0 never, anything else always (any other
 * value: always, as RX_VK_UB_SNAPSHOT's old "set" meant).
 */
#pragma once

#include <cstdint>
#include <cstdlib>

namespace mkwvk::as_submitted {

constexpr uint64_t kStorageCopyMax = 4ull << 20;
constexpr uint32_t kRecentFrames = 3;
constexpr uint32_t kRing = 8;   // (frames whose starting memory generation is kept)

inline bool switch_on(const char* env, bool mirrors_on) {
    if (!env) return !mirrors_on;
    char* end = nullptr;
    const long v = std::strtol(env, &end, 10);
    return end == env || v != 0;
}

inline bool copy_uniform(bool on, bool gpu_written) {
    return on && !gpu_written;
}

inline bool copy_storage(bool on, uint64_t size, bool cpu_written_lately, bool gpu_written) {
    return on && size && size <= kStorageCopyMax && cpu_written_lately && !gpu_written;
}

/// The memory generation as frame `frame` began, noted in a ring of kRing frames (at: the frame of each slot, gen: its
/// generation), and the one `frames` frames before it. A frame not noted: the newest noted one at or before it, else 0
/// (everything counts as recent: copied, which is the safe side).
struct GenRing {
    uint64_t at[kRing]{};
    uint32_t gen[kRing]{};
    bool any[kRing]{};
    void note(uint64_t frame, uint32_t generation) {
        const uint32_t s = (uint32_t)(frame % kRing);
        if (any[s] && at[s] == frame) return;   // (the first look in a frame is its start)
        at[s] = frame, gen[s] = generation, any[s] = true;
    }
    uint32_t before(uint64_t frame, uint32_t frames) const {
        if (frame < frames) return 0;
        const uint64_t want = frame - frames;
        uint64_t best_at = 0;
        uint32_t best = 0;
        bool found = false;
        for (uint32_t s = 0; s < kRing; s++)
            if (any[s] && at[s] <= want && (!found || at[s] > best_at)) best_at = at[s], best = gen[s], found = true;
        return found ? best : 0;
    }
};

} // namespace mkwvk::as_submitted
