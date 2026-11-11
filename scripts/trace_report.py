"""(raiders) What a run of the game called that the runtime does not have, from its log (hookshot_log.txt): a Markdown
report for the offline-stub and NVN tasks (docs/plans/tasks/T09-trace-report.md).

    python -I scripts/trace_report.py <log> [<log> ...] [--stubs work/standalone_stubbed.txt] [--md out.md]

Sections: (1) generated OS stubs called, (2) NVN procs called without an implementation, (3) NVN procs called with one,
(4) services opened by name, (5) queues and event waits, (6) the last 20 runtime lines, (7) read-back candidates called.
Each log is one column of the tables, named after its folder (work/runs/<name>/hookshot_log.txt -> <name>).

It parses the fixed prefixes the runtime prints, and nothing else:
  [a64] unimplemented import <sym> (lr <x>)                      third_party/a64-kit/rt/a64_rt.c a64_unimplemented
  [hos <thread>] nvn: <proc> is not implemented: answered <n> (... lr <x>)       host/nvn_native.c unimplemented
  [hos <thread>] FATAL: native NVN: NVN <proc> is not implemented (...)          the same, HOS_NVN_STRICT=1
  [hos <thread>] hostcall <proc>(...)                 host/hos_hostcall.c: HOS_TRACE=1, the first 3 calls of each
  [hos] host calls: / "  <count>  <name>"             host/hos_hostcall.c hos_hostcall_stats: HOS_HOSTCALL_STATS=1
  [hos <thread>] ipc: ConnectToNamedPort("<name>")    host/hos_svc.c svc 0x1F
  [hos <thread>] nvdrv: open <path> -> <fd>           host/nvdrv.c: HOS_TRACE=1
  [hos <thread>] nvn: CommandBufferWaitEvent #<k>: event <x> ... (lr <x>)  host/nvn_native.c: calls 1-40, then every 5000
  [hos <thread>] nvn: CommandBufferWaitSync #<k>      the same
  [hos <thread>] vi: <n> frames presented             host/nn_vi.c
  [hos <thread>] CRASH: ... / FATAL: ...              host/mkw_glue.c report_crash, host/hos_thread.c hos_fatal

The stub's log line goes straight to stderr while hos_log lines are queued (host/hos_thread.c log_queue), so their order in
the log is exact only with HOS_LOG_SYNC=1. The NVN call counts are exact only with HOS_HOSTCALL_STATS=1; with HOS_TRACE=1
alone a count is "at least" (the trace logs the first 3 calls).

With --md, the file's text outside the generated block (between the BEGIN and END markers) is kept, and so are the
Class, Owner and Note cells of rows that are still there: the hand annotations survive a new run. Section 6 leaves out
file paths and quoted strings (game text) except service names.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = "<!-- trace_report.py: generated, BEGIN (edit outside, or the Class / Owner / Note cells) -->"
END = "<!-- trace_report.py: generated, END -->"
TAIL = 20

HOS = re.compile(r"^\[hos (?P<thread>.*?)\] (?P<msg>.*)$")
HOS_BARE = re.compile(r"^\[hos\] (?P<msg>.*)$")
STUB = re.compile(r"^\[a64\] unimplemented import (?P<sym>\S+) \(lr (?P<lr>0x[0-9a-f]+|0)\)")
NVN_MISSING = re.compile(r"^nvn: (?P<proc>\w+) is not implemented: answered (?P<ret>-?\d+) \(.*lr (?P<lr>0x[0-9a-f]+|0)\)")
NVN_STRICT = re.compile(r"^FATAL: native NVN: NVN (?P<proc>\w+) is not implemented")
HOSTCALL = re.compile(r"^hostcall (?P<name>\w+)\(")
STATS_ROW = re.compile(r"^  +(?P<n>\d+)  (?P<name>\S+)$")
RECENT_ROW = re.compile(r"^  +\d+ \w+\(.*\) lr ")
IPC = re.compile(r'^ipc: ConnectToNamedPort\("(?P<name>[^"]*)"\)')
NVDRV = re.compile(r"^nvdrv: open (?P<path>\S+) -> (?P<fd>-?\d+)")
WAIT_EVENT = re.compile(r"^nvn: CommandBufferWaitEvent #(?P<k>\d+): event (?P<ev>0x[0-9a-f]+|0)\b.*\(lr (?P<lr>0x[0-9a-f]+|0)\)")
WAIT_SYNC = re.compile(r"^nvn: CommandBufferWaitSync #(?P<k>\d+)")
FRAMES = re.compile(r"^vi: (?P<n>\d+) frames presented")
# register and guest-memory rows of a crash report or a thread dump: not runtime events, and memory is game data
DUMP_ROW = re.compile(r"\] CRASH: +x\d|\] CRASH: \[x\d|\] thread \S.*:   x\d+ ")

# NVN procs through which the CPU can see what the GPU wrote (work/nvn_main.txt names): T17's ink read-back question
READBACK = re.compile(r"ReadTexels|InvalidateTexels|InvalidateMappedRange|(Buffer|MemoryPool)Map(Virtual)?$|CopyTextureToBuffer|"
                      r"CopyBufferToBuffer|ReportCounter|ReportValue|EventGetValue|SyncWait|QueueFinish")


class Trace:
    """What one log says"""

    def __init__(self, label):
        self.label = label
        self.lines = 0
        self.stubs = {}          # sym -> (order, lr, line)
        self.missing = {}        # proc -> (order, answered, lr, line, strict)
        self.traced = {}         # proc -> hostcall lines seen (at most 3 each)
        self.counts = None       # proc -> calls, from the last HOS_HOSTCALL_STATS table
        self.ports = {}          # name -> times
        self.nvdrv = {}          # path -> times
        self.wait_events = 0     # the highest WaitEvent number logged
        self.wait_event_ids = set()
        self.wait_event_lrs = set()
        self.wait_syncs = 0
        self.frames = 0          # the highest "vi: N frames presented"
        self.first_present = None
        self.end = None          # (line, kind, text): the first CRASH or FATAL
        self.tail = []           # the runtime lines, without the stats tables and register / memory rows


def parse(lines, label):
    t = Trace(label)
    in_stats = False
    for no, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        t.lines = no
        bare = HOS_BARE.match(line)
        if bare:
            msg = bare.group("msg")
            if msg == "host calls:":
                in_stats, t.counts = True, {}
                continue
            if msg.startswith("last ") and "host calls" in msg:
                in_stats = "recent"
                continue
        if in_stats:
            row = STATS_ROW.match(line) if in_stats is True else None
            if row:
                t.counts[row.group("name")] = int(row.group("n"))
                continue
            if in_stats == "recent" and RECENT_ROW.match(line):
                continue
            in_stats = False
        if not DUMP_ROW.search(line):
            t.tail.append((no, line))
        m = STUB.match(line)
        if m:
            t.stubs.setdefault(m.group("sym"), (len(t.stubs) + 1, m.group("lr"), no))
            continue
        h = HOS.match(line) or bare
        if not h:
            continue
        msg = h.group("msg")
        m = NVN_MISSING.match(msg)
        if m:
            t.missing.setdefault(m.group("proc"), (len(t.missing) + 1, int(m.group("ret")), m.group("lr"), no, False))
            continue
        m = NVN_STRICT.match(msg)
        if m:
            t.missing.setdefault(m.group("proc"), (len(t.missing) + 1, None, None, no, True))
        if msg.startswith(("CRASH:", "FATAL:")) and t.end is None:
            t.end = (no, msg.split(":", 1)[0], msg)
            continue
        m = HOSTCALL.match(msg)
        if m:
            name = m.group("name")
            t.traced[name] = t.traced.get(name, 0) + 1
            if name == "nvnQueuePresentTexture" and t.first_present is None:
                t.first_present = no
            continue
        m = IPC.match(msg)
        if m:
            t.ports[m.group("name")] = t.ports.get(m.group("name"), 0) + 1
            continue
        m = NVDRV.match(msg)
        if m:
            t.nvdrv[m.group("path")] = t.nvdrv.get(m.group("path"), 0) + 1
            continue
        m = WAIT_EVENT.match(msg)
        if m:
            t.wait_events = max(t.wait_events, int(m.group("k")))
            t.wait_event_ids.add(m.group("ev"))
            t.wait_event_lrs.add(m.group("lr"))
            continue
        m = WAIT_SYNC.match(msg)
        if m:
            t.wait_syncs = max(t.wait_syncs, int(m.group("k")))
            continue
        m = FRAMES.match(msg)
        if m:
            t.frames = max(t.frames, int(m.group("n")))
            if t.first_present is None:
                t.first_present = no
    return t


def calls(t, proc):
    """(count, exact): the stats table's count, else the traced calls (a lower bound), else (0, exact or not)"""
    if t.counts is not None:
        return t.counts.get(proc, 0), True
    return t.traced.get(proc, 0), False


def presents(t):
    n, exact = calls(t, "nvnQueuePresentTexture")
    return max(n, t.frames), exact or t.frames > 0


def namespace(sym):
    """nn::pl for _ZN2nn2pl18GetBuiltInFontData...: the nested name's components but the last; C names: "(C)" """
    m = re.match(r"_ZN[KVr]*", sym)
    if not m:
        return "(C)" if not sym.startswith("_Z") else "(global)"
    i, parts = m.end(), []
    while i < len(sym) and sym[i].isdigit():
        j = i
        while j < len(sym) and sym[j].isdigit():
            j += 1
        n = int(sym[i:j])
        parts.append(sym[j:j + n])
        i = j + n
    return "::".join(parts[:-1]) if len(parts) > 1 else "(global)"


def demangle(syms, tool=None):
    """sym -> demangled name, through c++filt when this machine has it (else the names map to themselves)"""
    syms = sorted(set(syms))
    tool = tool if tool is not None else shutil.which("c++filt")
    if not tool or not syms:
        return {s: s for s in syms}
    try:
        # (-n: the names as they are; Apple's c++filt otherwise takes a Mach-O leading underscore off first)
        out = subprocess.run([tool, "-n"], input="\n".join(syms) + "\n", capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {s: s for s in syms}
    names = out.splitlines()
    return dict(zip(syms, names)) if len(names) == len(syms) else {s: s for s in syms}


def redact(msg):
    """A runtime line without game text: file paths and quoted strings left out (service names kept)"""
    if msg.startswith("fs:"):
        m = re.match(r"fs: (\w+)", msg)
        return "fs: %s (path left out)" % (m.group(1) if m else "…")
    if not msg.startswith("ipc: ConnectToNamedPort"):
        msg = re.sub(r'-> ".*$', '-> "…"', msg)   # (hos_thread_dump: the text a register leads to)
        msg = re.sub(r'"[^"]*"', '"…"', msg)
    return re.sub(r"\S*/\S*", "<path>", msg)


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def code(s):
    return "`%s`" % str(s).replace("`", "'") if s not in ("", None) else ""


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


def seen_in(traces, get):
    """'trace1 #3, trace2 #3' for a key's first-call order in each log that has it"""
    return ", ".join("%s #%d" % (t.label, get(t)[0]) for t in traces if get(t))


ANNOTATED = ("Class", "Owner", "Note")


def render(traces, stubbed=None, dm=None):
    """The generated block, as lines"""
    syms = sorted({s for t in traces for s in t.stubs}, key=lambda s: min(t.stubs[s][0] for t in traces if s in t.stubs))
    dm = dm if dm is not None else demangle(syms)
    out = [BEGIN, ""]
    out.append("Logs: " + ", ".join("`%s` (%d lines)" % (t.label, t.lines) for t in traces) + ".")
    for t in traces:
        p, exact = presents(t)
        end = ("line %d, %s" % (t.end[0], t.end[1])) if t.end else "no crash or fatal error logged (time limit or exit)"
        out.append("- `%s`: end: %s; first present: %s; NVN counts: %s." % (
            t.label, end, ("line %d" % t.first_present) if t.first_present else "none",
            "exact (HOS_HOSTCALL_STATS)" if t.counts is not None else "at least, from HOS_TRACE" if t.traced else "not logged"))

    out += ["", "### 1. Generated OS stubs called", ""]
    if stubbed is not None:
        hit = [s for s in syms if s in stubbed]
        out.append("%d of the %d stubbed imports in the stub list were called; %d called stub(s) not in it." % (
            len(hit), len(stubbed), len(syms) - len(hit)))
        out.append("")
    rows = []
    for k, s in enumerate(syms, 1):
        first = next(t.stubs[s] for t in traces if s in t.stubs)
        rows.append([k, code(s), code(dm.get(s, s)) if dm.get(s, s) != s else "", namespace(s), code(first[1]),
                     seen_in(traces, lambda t, s=s: t.stubs.get(s)), "", "", ""])
    out += table(["#", "Mangled", "Demangled", "Namespace", "lr", "Runs (order)"] + list(ANNOTATED), rows)
    if not rows:
        out.append("| | none | | | | | | | |")

    out += ["", "### 2. NVN procs called without an implementation", ""]
    procs = sorted({p for t in traces for p in t.missing},
                   key=lambda p: min(t.missing[p][0] for t in traces if p in t.missing))
    rows = []
    for k, p in enumerate(procs, 1):
        first = next(t.missing[p] for t in traces if p in t.missing)
        how = "stopped (HOS_NVN_STRICT)" if first[4] else "answered %d" % first[1]
        rows.append([k, code(p), how, code(first[2] or ""), seen_in(traces, lambda t, p=p: t.missing.get(p)), "", "", ""])
    out += table(["#", "Proc", "Answer", "lr", "Runs (order)"] + list(ANNOTATED), rows)
    if not rows:
        out.append("| | none | | | | | | |")

    out += ["", "### 3. NVN procs called with an implementation", ""]
    missing = set(procs)
    names = set()
    for t in traces:
        names |= {n for n in (t.counts or {}) if t.counts[n]} | set(t.traced)
    names = sorted(n for n in names if n.startswith("nvn") and n not in missing)
    rows = []
    for n in names:
        row = [code(n)]
        for t in traces:
            c, exact = calls(t, n)
            row.append(str(c) if exact else ">= %d" % c if c else "")
        rows.append(row)
    out.append("%d procs." % len(names))
    out.append("")
    out += table(["Proc"] + ["calls (%s)" % t.label for t in traces], rows)
    if not rows:
        out.append("| none |" + " |" * len(traces))

    out += ["", "### 4. Services opened by name", ""]
    rows = []
    for t in traces:
        rows += [[t.label, "ConnectToNamedPort", code(n), c] for n, c in sorted(t.ports.items())]
        rows += [[t.label, "nvdrv open", code(n), c] for n, c in sorted(t.nvdrv.items())]
    out += table(["Run", "How", "Name", "Times"], rows)
    if not rows:
        out.append("| | none | | |")
    out.append("")
    out.append("`sm:` service lookups by name are not logged by the runtime: host/hos_svc.c logs `ConnectToNamedPort` only, "
               "and the SDK's service clients are mostly replaced by HLE functions.")

    out += ["", "### 5. Queues and event waits", ""]
    rows = []
    for t in traces:
        def n(proc, t=t):
            c, exact = calls(t, proc)
            return str(c) if exact else ">= %d" % c
        p, exact = presents(t)
        per = ("%.2f" % (t.wait_events / p)) if p and exact else ""
        rows.append([t.label, n("nvnQueueInitialize"), n("nvnQueueSubmitCommands"), n("nvnEventInitialize"),
                     t.wait_events, len(t.wait_event_ids), len(t.wait_event_lrs), t.wait_syncs,
                     p if exact else ">= %d" % p, per])
    out += table(["Run", "Queues initialised", "Submits", "Events initialised", "WaitEvent calls (highest #)",
                  "Distinct events (logged)", "Distinct callers (logged)", "WaitSync calls", "Presents",
                  "WaitEvent per present"], rows)
    out.append("")
    out.append("WaitEvent calls are logged one by one up to 40, then every 5000th (host/nvn_native.c): the distinct "
               "events and callers are among the logged ones.")

    out += ["", "### 6. The last %d runtime lines" % TAIL, "",
            "Without the call-count tables, register and guest-memory rows; file paths and strings left out.", ""]
    for t in traces:
        out.append("`%s`:" % t.label)
        out.append("")
        out.append("```text")
        for no, line in t.tail[-TAIL:]:
            h, bare = HOS.match(line), HOS_BARE.match(line)
            if bare:
                text = "[hos] " + redact(bare.group("msg"))
            elif h:
                text = "[hos %s] %s" % (h.group("thread"), redact(h.group("msg")))
            else:
                text = redact(line)
            out.append("%6d  %s" % (no, text))
        out.append("```")
        out.append("")

    out += ["### 7. Read-back candidates called", ""]
    rows = []
    for t in traces:
        cand = set(n for n in (t.counts or {}) if t.counts[n]) | set(t.traced) | set(t.missing)
        for n in sorted(c for c in cand if c.startswith("nvn") and READBACK.search(c)):
            c, exact = calls(t, n)
            rows.append([t.label, code(n), "no" if n in t.missing else "yes", str(c) if exact else ">= %d" % c])
    out += table(["Run", "Proc", "Implemented", "Calls"], rows)
    if not rows:
        out.append("| | none | | |")
    out += ["", END]
    return out


def annotations(text):
    """(section, key) -> {Class, Owner, Note} from the tables of an earlier report"""
    keep, section, head = {}, None, None
    for line in text.splitlines():
        if line.startswith("### "):
            section, head = line[4:].split(".", 1)[0], None
            continue
        if not line.startswith("|"):
            head = None
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        if head is None:
            head = cells
            continue
        if set(line) <= set("|-: "):
            continue
        if any(a in head for a in ANNOTATED) and len(cells) == len(head) and len(head) > 1:
            key = cells[1]
            got = {a: cells[head.index(a)] for a in ANNOTATED if a in head and cells[head.index(a)]}
            if got:
                keep[(section, key)] = got
    return keep


def merge(old, block):
    """The new generated block in place of the old one, the text around it and the hand annotations kept"""
    keep = annotations(old[old.find(BEGIN):old.find(END)] if BEGIN in old and END in old else "")
    section, head, out = None, None, []
    for line in block:
        if line.startswith("### "):
            section, head = line[4:].split(".", 1)[0], None
        elif line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if head is None:
                head = cells
            elif not set(line) <= set("|-: ") and (section, cells[1] if len(cells) > 1 else "") in keep:
                for a, v in keep[(section, cells[1])].items():
                    if a in head and len(cells) == len(head):
                        cells[head.index(a)] = v
                line = "| " + " | ".join(cells) + " |"
        else:
            head = None
        out.append(line)
    text = "\n".join(out) + "\n"
    if BEGIN in old and END in old:
        return old[:old.find(BEGIN)] + text.rstrip("\n") + old[old.find(END) + len(END):]
    if old.strip():
        return old.rstrip("\n") + "\n\n" + text
    return "# M3 · Trace report\n\n" + text


def label_of(path):
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parent if os.path.basename(path) == "hookshot_log.txt" and parent else os.path.basename(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("logs", nargs="+", help="hookshot_log.txt files")
    ap.add_argument("--stubs", help="the stubbed imports, one per line (default: work/standalone_stubbed.txt if present)")
    ap.add_argument("--md", help="write (or update) this Markdown file instead of printing")
    a = ap.parse_args(argv)
    traces = []
    for path in a.logs:
        with open(path, encoding="utf-8", errors="replace") as f:
            traces.append(parse(f, label_of(path)))
    stubs = a.stubs or os.path.join(ROOT, "work", "standalone_stubbed.txt")
    stubbed = None
    if os.path.exists(stubs):
        with open(stubs, encoding="utf-8") as f:
            stubbed = {l.strip() for l in f if l.strip()}
    elif a.stubs:
        sys.exit("trace_report: no stub list at %s" % stubs)
    block = render(traces, stubbed)
    if not a.md:
        print("\n".join(block))
        return 0
    old = open(a.md, encoding="utf-8").read() if os.path.exists(a.md) else ""
    with open(a.md, "w", encoding="utf-8", newline="\n") as f:
        f.write(merge(old, block))
    print("trace_report: %s (%d logs, %d stubs, %d NVN procs missing)" % (
        a.md, len(traces), len({s for t in traces for s in t.stubs}), len({p for t in traces for p in t.missing})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
