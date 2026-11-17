#!/usr/bin/env bash
# (raiders, T20) The memory of a run on the Deck, sampled while it plays: started beside scripts/deck/run.sh with the same
# run name (run.sh ... & then mem_report.sh <name>), it waits for that run's game process, samples it every 5 s until it ends,
# and prints the peaks and the final values.
#
#     scripts/deck/mem_report.sh <name> [--wait <seconds>=180] [--every <seconds>=5]
#
# Each sample (the Deck's $DECK_ROOT/work/runs/<name>/mem.txt, one line):
#   - the game process (/proc/<pid>/status): VmRSS, VmSwap, and VmRSS's parts RssAnon, RssFile and RssShmem. The guest's memory
#     is a memfd (host/hos_main.c), so the game's committed memory is in RssShmem;
#   - the process's own GPU memory, from its DRM file descriptors' fdinfo: where its buffers are (drm-resident-* where the
#     kernel gives it, else drm-memory-*), and the part of the GTT that is shared (drm-shared-gtt: imported or exported buffers);
#   - the whole GPU's VRAM and GTT in use (amdgpu's mem_info_vram_used, mem_info_gtt_used: every process's);
#   - the system's MemAvailable and swap in use (/proc/meminfo).
#
# The accounting (what "peak footprint" is): VmRSS + VmSwap + the process's own VRAM + its own GTT, less its shared GTT.
# On the Deck the game's memory pools reach the GPU as dma-bufs of the guest memfd's own pages (gpu/vk/vk_memory.cpp, Linux):
# those pages are in RssShmem and again in GTT (an imported buffer, counted shared), so the shared GTT comes off once. The
# Deck's VRAM is a 1 GB carve-out outside MemTotal; GTT is system RAM. A cross-check that needs no attribution: the system's
# own cost of the run, (MemAvailable before - MemAvailable now) + (swap in use now - before) + (VRAM in use now - before),
# from the values read when this script started (late: when the game was already running, the line says so).
#
# From the run's log at the end: the texture cache's use against its budget ("vk: VRAM: ... textures N MB (budget M MB)",
# every 600 frames), its parts ("vk: textures: decoded ASTC ..."), the render-target pool, the driver's heaps ("vk: memory
# heaps:"), the "vk: status:" VRAM figure, the over-allowance warnings and allocation failures.
#
# The figures go to work/runs/<name>/mem_report.txt on the Mac too (fetch.sh brings the rest: it leaves that file alone).
# Only numbers: no game data.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

usage() { echo "usage: scripts/deck/mem_report.sh <name> [--wait <seconds>] [--every <seconds>]" >&2; exit 2; }
[ $# -ge 1 ] || usage
name=$1; shift
[[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "mem_report: a run name is letters, digits, . _ -" >&2; exit 2; }
wait_s=180 every=5
while [ $# -gt 0 ]; do
    case $1 in
        --wait) [ $# -ge 2 ] && [[ $2 =~ ^[0-9]+$ ]] || usage; wait_s=$2; shift ;;
        --every) [ $# -ge 2 ] && [[ $2 =~ ^[1-9][0-9]*$ ]] || usage; every=$2; shift ;;
        *) usage ;;
    esac
    shift
done

need_deck
R=$(deck_root)
mkdir -p "$REPO/work/runs/$name"
deck "bash -s -- $(quote "$R" "$name" "$wait_s" "$every")" <<'EOS' | tee "$REPO/work/runs/$name/mem_report.txt"
set -euo pipefail
R=$1 name=$2 wait_s=$3 every=$4
run=$R/work/runs/$name
# mem-report sampler BEGIN (tests/test_deck_scripts.py runs it on a stand-in process and stand-in /proc and /sys files)
PROC=${MEM_PROC:-/proc} SYSDRM=${MEM_SYSDRM:-/sys/class/drm}
meminfo() { awk -v k="$1:" '$1 == k {print $2}' "$PROC/meminfo"; }
swap_kb() { awk '/^SwapTotal:/{t=$2} /^SwapFree:/{f=$2} END{print t-f}' "$PROC/meminfo"; }
status_kb() { awk -v k="$2:" '$1 == k {print $2; f=1} END{if(!f) print 0}' "$PROC/$1/status" 2>/dev/null || echo 0; }
gpu_dev=$(ls -d "$SYSDRM"/card*/device 2>/dev/null | while read -r d; do [ -r "$d/mem_info_vram_used" ] && echo "$d" && break; done || true)
gpu_kb() { if [ -n "$gpu_dev" ]; then echo $(( $(cat "$gpu_dev/mem_info_$1_used") >> 10 )); else echo 0; fi; }
# (the process's own GPU memory: every DRM fd's fdinfo, once per drm-client-id, in kB: resident vram, resident gtt, shared gtt.
# Resident, not total: total is where a buffer was asked for, and the Deck's 1 GB of VRAM holds only part of what asks for it)
own_gpu() {
    local p=$1 fd
    for fd in "$PROC/$p"/fd/*; do
        case $(readlink "$fd" 2>/dev/null) in /dev/dri/*) cat "$PROC/$p/fdinfo/${fd##*/}" 2>/dev/null; echo "--" ;; esac
    done | awk '
        function kb(v, u) { return u == "MiB" ? v * 1024 : u == "GiB" ? v * 1048576 : u == "B" || u == "" ? int(v / 1024) : v }
        $1 == "--" { if (id != "" && !(id in seen)) { seen[id]; tv += cv; tg += cg; sg += cs } id = ""; cv = cg = cs = 0; hv = hg = 0; next }
        $1 == "drm-client-id:" { id = $2 }
        $1 == "drm-resident-vram:" { cv = kb($2, $3); hv = 1 }
        $1 == "drm-resident-gtt:"  { cg = kb($2, $3); hg = 1 }
        $1 == "drm-memory-vram:" && !hv { cv = kb($2, $3) }
        $1 == "drm-memory-gtt:"  && !hg { cg = kb($2, $3) }
        $1 == "drm-shared-gtt:"  { cs = kb($2, $3) }
        END { printf "%d %d %d\n", tv, tg, sg }'
}
# (where the resident set is, by mapping: the guest memfd, the executable and its own libraries, the driver's, other files,
# anonymous memory; in kB)
smaps_split() {
    awk '
        /^[0-9a-f]+-[0-9a-f]+ / { n = $6; for (i = 7; i <= NF; i++) n = n " " $i
            if (n ~ /hookshot-guest/) c = "guest"; else if (n ~ /\/hookshot$/) c = "exe"
            else if (n ~ /hookshot_vk\.so/) c = "vk_so"; else if (n ~ /image\.bin/) c = "image"
            else if (n ~ /(radeon|radv|vulkan|libdrm|amdgpu|LLVM|mesa)/) c = "driver"
            else if (n ~ /^\/dev\/dri/) c = "dri"; else if (n ~ /^\//) c = "files"; else c = "anon"
            next }
        $1 == "Rss:" { s[c] += $2 }
        END { printf "guest %d exe %d vk_so %d image %d driver %d dri %d files %d anon %d\n", s["guest"], s["exe"], s["vk_so"],
              s["image"], s["driver"], s["dri"], s["files"], s["anon"] }' "$PROC/$1/smaps" 2>/dev/null || echo "smaps unreadable"
}
find_game() {   # (this run's game: a hookshot process started with this run's env file)
    local d
    for d in "$PROC"/[0-9]*; do
        [ "$(cat "$d/comm" 2>/dev/null)" = hookshot ] || continue
        tr '\0' '\n' < "$d/environ" 2>/dev/null | grep -qxF "HOS_ENV_FILE=$run/env.txt" && echo "${d##*/}" && return 0
    done
    return 1
}
avail0=$(meminfo MemAvailable) swap0=$(swap_kb) vram0=$(gpu_kb vram) gtt0=$(gpu_kb gtt)
late=
deadline=$(( $(date +%s) + wait_s ))
pid=
until pid=$(find_game); do
    [ "$(date +%s)" -lt "$deadline" ] || { echo "mem_report: no game process for run $name within ${wait_s}s (run.sh not started?)" >&2; exit 1; }
    sleep 1
done
[ "$(( $(status_kb "$pid" VmRSS) ))" -gt 1048576 ] && late=" (late: the game held over 1 GB when the first value was read)"
out=$run/mem.txt start=$(date +%s)
echo "# t_s rss_kb swap_kb anon_kb file_kb shmem_kb own_vram_kb own_gtt_kb own_shared_gtt_kb gpu_vram_kb gpu_gtt_kb avail_kb sys_swap_kb footprint_kb system_kb" > "$out"
n=0 last_split= peak_split= peak_split_rss=0 next_split=0
while [ -d "$PROC/$pid" ]; do
    rss=$(status_kb "$pid" VmRSS) sw=$(status_kb "$pid" VmSwap)
    an=$(status_kb "$pid" RssAnon) fi=$(status_kb "$pid" RssFile) sh=$(status_kb "$pid" RssShmem)
    read -r ov og os < <(own_gpu "$pid")
    gv=$(gpu_kb vram) gg=$(gpu_kb gtt) av=$(meminfo MemAvailable) ss=$(swap_kb)
    [ -d "$PROC/$pid" ] || break
    t=$(( $(date +%s) - start ))
    fp=$(( rss + sw + ov + og - (os < og ? os : og) ))
    sysc=$(( avail0 - av + ss - swap0 + gv - vram0 ))
    echo "$t $rss $sw $an $fi $sh $ov $og $os $gv $gg $av $ss $fp $sysc" >> "$out"
    n=$((n + 1))
    if [ "$t" -ge "$next_split" ]; then   # (where the resident set is, once a minute; the one at the largest VmRSS is kept)
        last_split=$(smaps_split "$pid") next_split=$((t + 60))
        if [ "$rss" -gt "$peak_split_rss" ]; then peak_split=$last_split peak_split_rss=$rss peak_split_t=$t; fi
    fi
    sleep "$every"
done
[ "$n" -gt 0 ] || { echo "mem_report: run $name: the game ended before the first sample" >&2; exit 1; }
mb() { echo $(( ($1 + 512) >> 10 )); }
# (peaks over the samples: each column's own, the footprint's with its parts at that sample, the system's least MemAvailable)
read -r pk_rss pk_swap pk_shm pk_ov pk_og pk_gpu pk_fp fp_t fp_rss fp_sw fp_ov fp_og fp_os min_av pk_sys pk_sswap < <(awk '
    !/^#/ { if ($2 > r) r = $2; if ($3 > s) s = $3; if ($6 > h) h = $6; if ($7 > v) v = $7; if ($8 > g) g = $8
            if ($10 + $11 > G) G = $10 + $11
            if ($14 > f) { f = $14; ft = $1; fr = $2; fs = $3; fv = $7; fg = $8; fo = $9 }
            if (a == "" || $12 < a) a = $12; if ($15 > y) y = $15; if ($13 > q) q = $13 }
    END { print r+0, s+0, h+0, v+0, g+0, G+0, f+0, ft+0, fr+0, fs+0, fv+0, fg+0, fo+0, a+0, y+0, q+0 }' "$out")
read -r f_t f_rss f_sw f_an f_fi f_sh f_ov f_og f_os f_gv f_gg f_av f_ss f_fp f_sys < <(tail -1 "$out")
budget_kb=12207031   # (12.5 GB = 12.5e9 bytes: the target, 04-steam-deck.md section 2)
echo "mem_report $name: $n samples every ${every}s over ${f_t}s; accounting: VmRSS + VmSwap + own VRAM + own GTT - own shared GTT$late"
echo "  peak footprint $(mb "$pk_fp") MB at ${fp_t}s (VmRSS $(mb "$fp_rss") + VmSwap $(mb "$fp_sw") + VRAM $(mb "$fp_ov") + GTT $(mb "$fp_og") - shared GTT $(mb "$fp_os")); target 11921 MB (12.5 GB): $([ "$pk_fp" -le "$budget_kb" ] && echo within || echo OVER), headroom $(( (budget_kb - pk_fp) >> 10 )) MB"
echo "  peak RSS $(mb "$pk_rss") MB (RssShmem, the guest's, peak $(mb "$pk_shm") MB); peak VmSwap $(mb "$pk_swap") MB"
echo "  peak GPU memory (VRAM + GTT): own $(mb "$pk_ov") + $(mb "$pk_og") MB; whole GPU $(mb "$pk_gpu") MB"
echo "  min MemAvailable $(mb "$min_av") MB (before the run $(mb "$avail0") MB); system swap in use peak $(mb "$pk_sswap") MB (before $(mb "$swap0") MB)"
echo "  system cost of the run (cross-check) peak $(mb "$pk_sys") MB"
echo "  final: VmRSS $(mb "$f_rss") (anon $(mb "$f_an"), file $(mb "$f_fi"), shmem $(mb "$f_sh")) VmSwap $(mb "$f_sw"); own VRAM $(mb "$f_ov") GTT $(mb "$f_og") shared GTT $(mb "$f_os"); whole GPU VRAM $(mb "$f_gv") GTT $(mb "$f_gg"); MemAvailable $(mb "$f_av"); footprint $(mb "$f_fp") MB"
[ -n "$peak_split" ] && echo "  resident set by mapping at ${peak_split_t}s (kB): $peak_split"
[ -n "$last_split" ] && echo "  resident set by mapping, last (kB): $last_split"
# mem-report sampler END
log=$run/hookshot_log.txt
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$run/.started" ] || break; sleep 2; done   # (run.sh's own end: the log is complete)
if [ -f "$log" ]; then
    # mem-report log reader BEGIN (tests/test_deck_scripts.py runs it on sample log lines)
    awk '
        / vk: VRAM: / { t = ""; for (i = 1; i <= NF; i++) { if ($i == "textures" && t == "") t = $(i+1); if ($i == "(budget") b = $(i+1)
                                                     if ($i == "used" && $(i+1) == "of") { u = $(i-2); a = $(i+2) } }
                        nv++; if (t + 0 > mt) { mt = t + 0; mb = b; mu = u; ma = a }; lt = t; lb = b }
        / vk: textures: decoded ASTC / { for (i = 1; i <= NF; i++) { if ($i == "ASTC") ax = $(i+1); if ($i == "rendered") rd = $(i+1)
                                                                   if ($i == "other") ot = $(i+1) }
                                         if (ax + rd + ot > ms) { ms = ax + rd + ot; mx = ax; mr = rd; mo = ot } }
        / vk: render target images: / { for (i = 1; i <= NF; i++) if ($i == "holds") { p = $(i+2); gsub(/[^0-9]/, "", p); if (p + 0 > mp) mp = p + 0 } }
        / vk: memory heaps: / { line = $0; sub(/.*vk: memory heaps: /, "", line); hp = line }
        / vk: status: / { st = $0; sub(/.*; /, "", st) }
        /over the driver.s video-memory allowance/ { over++ }
        /out of memory|OUT_OF_.*MEMORY|[Aa]llocation failed|failed to allocate|cannot allocate/ { oom++ }
        END {
            if (nv) printf "  texture cache: peak %d MB of its %d MB budget (VRAM %s of %s MB then); last %d of %d MB; %d lines\n", mt, mb, mu, ma, lt, lb, nv
            else print "  texture cache: no \"vk: VRAM:\" line in the log (a run under 600 frames)"
            if (ms) printf "  textures at their largest: decoded ASTC %d MB, rendered %d MB, other %d MB\n", mx, mr, mo
            printf "  render-target pool: at most %d MB\n", mp
            if (hp != "") print "  driver heaps, last: " hp
            if (st != "") print "  last vk: status: " st
            printf "  over-allowance warnings: %d; allocation-failure lines: %d\n", over, oom
        }' "$log"
    # mem-report log reader END
else
    echo "  no log at $log"
fi
EOS
