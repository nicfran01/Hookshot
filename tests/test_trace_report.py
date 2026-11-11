"""(raiders) scripts/trace_report.py on a synthetic log written here, in the runtime's own line formats (the generated
stub's first call, the NVN layer's unimplemented and strict lines, HOS_TRACE's hostcall lines, the HOS_HOSTCALL_STATS
table, ConnectToNamedPort, the event wait log, the crash report). No game, no real log.

    python -I -B tests/test_trace_report.py
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("trace_report", ROOT / "scripts" / "trace_report.py")
tr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tr)

STUB_A = "_ZN2nn3foo10InitializeEv"
STUB_B = "_ZN2nn3bar3sdk8GetStateEPNS0_5StateE"
LOG = """[hos host] hookshot 0.0.0
[hos MainThread] boot: nnMain (0x80001000)
[hos Main Thread] hostcall nvnDeviceInitialize(0x1000, 0x2000, 0, 0)
[a64] unimplemented import {a} (lr 0x80002000)
[hos Main Thread] fs: OpenFile(rom:/Some/Game/File.bin)
[hos Main Thread] hostcall nvnQueueInitialize(0x1100, 0x1200, 0, 0)
[hos Main Thread] hostcall nvnQueueInitialize(0x1300, 0x1200, 0, 0)
[hos Main Thread] nvn: nvnFooSetBar is not implemented: answered 0 (x0 0x10 x1 0 x2 0, lr 0x80003000)
[hos Main Thread] nvn: nvnFooInitialize is not implemented: answered 1 (x0 0x10 x1 0 x2 0, lr 0x80003100)
[hos Main Thread] ipc: ConnectToNamedPort("sm:") -> session 0x7e000001 (requests answered empty) (lr 0x80004000)
[hos Main Thread] ipc: ConnectToNamedPort("sm:") -> session 0x7e000002 (requests answered empty) (lr 0x80004000)
[hos Main Thread] nvdrv: open /dev/nvhost-ctrl -> 3
[a64] unimplemented import {b} (lr 0x80005000)
[a64] unimplemented import {a} (lr 0x80002000)
[hos Render] nvn: CommandBufferWaitEvent #1: event 0x500 mode 0 value 1 (now 0) (lr 0x80006000)
[hos Render] nvn: CommandBufferWaitEvent #2: event 0x600 mode 0 value 1 (now 0) (lr 0x80006100)
[hos Render] nvn: CommandBufferWaitEvent #5000: event 0x500 mode 0 value 9 (now 8) (lr 0x80006000)
[hos Render] nvn: CommandBufferWaitSync #3 (lr 0x80006200)
[hos Render] hostcall nvnQueuePresentTexture(0x1100, 0x1400, 0, 0)
[hos Render] SetThreadName says "Some Text"
[hos] host calls:
           1  nvnDeviceInitialize
           0  nvnQueueFinish
[hos] host calls:
           1  nvnDeviceInitialize
           2  nvnQueueInitialize
          40  nvnQueueSubmitCommands
           4  nvnEventInitialize
         100  nvnQueuePresentTexture
           7  nvnTextureReadTexels
           0  nvnQueueFinish
           3  nvnFooSetBar
[hos] last 2 host calls (oldest first): thread, call(x0, x1, x2, x3) lr
    1234 nvnQueuePresentTexture(0x1100, 0x1400, 0, 0) lr 0x80007000
    1234 nvnQueueSubmitCommands(0x1100, 0x1, 0, 0) lr 0x80007100
[hos Main Thread] CRASH: exception 0xc0000005 (read 0, guest 0) at hookshot+0x1234
[hos Main Thread] CRASH: thread Main Thread, sp 0x10000
[hos Main Thread] CRASH:   x0  0000000000000006  x1  0000000000000000  x2  0000000000000039  x3  00000000010e79f8
[hos Main Thread] CRASH: [x19+00000] 0000000000000004 00000000010ffe9c 000000000000e634 000000000000e638
[hos Render] thread Render:   x3 0x1000 -> "Some Text with a \" quote"
""".format(a=STUB_A, b=STUB_B)

STRICT = """[hos Main Thread] hostcall nvnDeviceInitialize(0x1000, 0x2000, 0, 0)
[a64] unimplemented import {a} (lr 0x80002000)
[hos Main Thread] FATAL: native NVN: NVN nvnFooSetBar is not implemented (x0 0x10 x1 0 x2 0) (lr 0x80003000 sp 0x10000)
[hos] guest backtrace: lr 0x80003000 0x80001000
""".format(a=STUB_A)


class TraceReportTests(unittest.TestCase):
    def setUp(self):
        self.t = tr.parse(LOG.splitlines(True), "trace1")
        self.s = tr.parse(STRICT.splitlines(True), "trace2")

    def test_stubs_in_first_call_order_once_each(self):
        self.assertEqual(list(self.t.stubs), [STUB_A, STUB_B])
        self.assertEqual(self.t.stubs[STUB_A][:2], (1, "0x80002000"))
        self.assertEqual(self.t.stubs[STUB_B][:2], (2, "0x80005000"))

    def test_nvn_missing_lenient_and_strict(self):
        self.assertEqual(self.t.missing["nvnFooSetBar"][:3], (1, 0, "0x80003000"))
        self.assertEqual(self.t.missing["nvnFooInitialize"][:3], (2, 1, "0x80003100"))
        self.assertTrue(self.s.missing["nvnFooSetBar"][4])
        self.assertEqual(self.s.end[1], "FATAL")

    def test_counts_from_the_last_stats_table(self):
        self.assertEqual(self.t.counts["nvnQueueInitialize"], 2)
        self.assertEqual(self.t.counts["nvnQueuePresentTexture"], 100)
        self.assertEqual(tr.calls(self.t, "nvnQueueSubmitCommands"), (40, True))
        # without a table: the traced calls, a lower bound
        self.assertIsNone(self.s.counts)
        self.assertEqual(tr.calls(self.s, "nvnDeviceInitialize"), (1, False))

    def test_stats_tables_are_not_runtime_lines(self):
        tail = [l for _, l in self.t.tail]
        self.assertFalse(any("nvnQueueFinish" in l or "1234 nvnQueue" in l for l in tail))
        self.assertTrue(tail[-1].endswith("CRASH: thread Main Thread, sp 0x10000"))   # (no register or memory rows)
        self.assertEqual(tr.redact('thread Render:   x3 0x1000 -> "Some Text with a \\" quote"'), 'thread Render:   x3 0x1000 -> "…"')

    def test_services_waits_presents_end(self):
        self.assertEqual(self.t.ports, {"sm:": 2})
        self.assertEqual(self.t.nvdrv, {"/dev/nvhost-ctrl": 1})
        self.assertEqual(self.t.wait_events, 5000)
        self.assertEqual(self.t.wait_event_ids, {"0x500", "0x600"})
        self.assertEqual(len(self.t.wait_event_lrs), 2)
        self.assertEqual(self.t.wait_syncs, 3)
        self.assertEqual(tr.presents(self.t), (100, True))
        self.assertEqual(self.t.first_present, 19)
        self.assertEqual(self.t.end[:2], (36, "CRASH"))

    def test_namespace(self):
        self.assertEqual(tr.namespace(STUB_A), "nn::foo")
        self.assertEqual(tr.namespace(STUB_B), "nn::bar::sdk")
        self.assertEqual(tr.namespace("_ZNK2nn3baz3GetEv"), "nn::baz")
        self.assertEqual(tr.namespace("nnsocketPoll"), "(C)")
        self.assertEqual(tr.namespace("_Z3fooi"), "(global)")

    def test_readback_names(self):
        for name in ("nvnTextureReadTexels", "nvnBufferMap", "nvnMemoryPoolMapVirtual", "nvnBufferInvalidateMappedRange",
                     "nvnCommandBufferCopyTextureToBuffer", "nvnCommandBufferReportCounter", "nvnEventGetValue"):
            self.assertTrue(tr.READBACK.search(name), name)
        for name in ("nvnCommandBufferComputeDirtyTileMap", "nvnTextureWriteTexels", "nvnBufferGetAddress"):
            self.assertFalse(tr.READBACK.search(name), name)

    def test_demangle_without_a_tool_is_the_identity(self):
        self.assertEqual(tr.demangle([STUB_A], tool=""), {STUB_A: STUB_A})

    def test_redact_leaves_out_paths_and_strings(self):
        self.assertEqual(tr.redact("fs: OpenFile(rom:/Some/Game/File.bin)"), "fs: OpenFile (path left out)")
        self.assertEqual(tr.redact('SetThreadName says "Some Text"'), 'SetThreadName says "…"')
        self.assertEqual(tr.redact("boot: romfs /home/x/romfs ok"), "boot: romfs <path> ok")
        self.assertIn('"sm:"', tr.redact('ipc: ConnectToNamedPort("sm:") -> session 0x7e000001'))

    def test_render_has_every_section_and_no_game_text(self):
        md = "\n".join(tr.render([self.t, self.s], stubbed={STUB_A, "_ZN2nn3foo5OtherEv"}, dm={}))
        for k in range(1, 8):
            self.assertIn("### %d. " % k, md)
        self.assertIn("1 of the 2 stubbed imports in the stub list were called; 1 called stub(s) not in it.", md)
        self.assertIn("| 1 | `%s` |  | nn::foo | `0x80002000` | trace1 #1, trace2 #1 |" % STUB_A, md)
        self.assertIn("| `nvnFooSetBar` | answered 0 | `0x80003000` | trace1 #1, trace2 #1 |", md)
        self.assertIn("| `nvnQueueInitialize` | 2 |  |", md)            # (trace2 has no count for it)
        self.assertIn("| `nvnDeviceInitialize` | 1 | >= 1 |", md)        # (trace2's from HOS_TRACE: at least)
        self.assertNotIn("`nvnQueueFinish`", md)                          # (0 calls in the table: not called)
        self.assertIn("| trace1 | 2 | 40 | 4 | 5000 | 2 | 2 | 3 | 100 | 50.00 |", md)
        self.assertIn("| trace1 | `nvnTextureReadTexels` | yes | 7 |", md)
        self.assertNotIn("Some/Game", md)
        self.assertNotIn("Some Text", md)

    def test_rows_in_one_order_for_two_logs(self):
        # (two logs whose stubs tie on first-call order: the rows come out in one order, whatever the hash seed)
        one = tr.parse(["[a64] unimplemented import _ZN2nn1b1fEv (lr 0x1)\n"], "one")
        two = tr.parse(["[a64] unimplemented import _ZN2nn1a1fEv (lr 0x2)\n"], "two")
        rows = [l for l in tr.render([one, two], dm={}) if l.startswith("| 1 |") or l.startswith("| 2 |")]
        self.assertIn("`_ZN2nn1a1fEv`", rows[0])
        self.assertIn("`_ZN2nn1b1fEv`", rows[1])

    def test_merge_keeps_text_and_annotations(self):
        block = tr.render([self.t], dm={})
        first = tr.merge("", block)
        self.assertTrue(first.startswith("# M3 · Trace report\n"))
        row = next(l for l in first.splitlines() if l.startswith("| 1 | `%s`" % STUB_A))
        annotated = first.replace(row, row[:-len("|  |  |  |")] + "| safe | T10 | offline answer |")
        annotated = "# Title\n\nHand intro.\n\n" + annotated[annotated.index(tr.BEGIN):] + "\n## Hand notes\n\nkept\n"
        again = tr.merge(annotated, block)
        self.assertEqual(again, annotated)                       # (a new run of the same log changes nothing)
        self.assertIn("| safe | T10 | offline answer |", again)
        self.assertIn("Hand intro.", again)
        self.assertIn("## Hand notes\n\nkept\n", again)

    def test_main_writes_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "trace1"
            run.mkdir(parents=True)
            (run / "hookshot_log.txt").write_text(LOG, encoding="utf-8")
            stubs = Path(d) / "stubbed.txt"
            stubs.write_text(STUB_A + "\n", encoding="utf-8")
            out = Path(d) / "out.md"
            self.assertEqual(tr.main([str(run / "hookshot_log.txt"), "--stubs", str(stubs), "--md", str(out)]), 0)
            md = out.read_text(encoding="utf-8")
            self.assertIn("`trace1` (40 lines)", md)
            self.assertGreater(sum(l.startswith("|") for l in md.splitlines()), 20)


if __name__ == "__main__":
    unittest.main()
