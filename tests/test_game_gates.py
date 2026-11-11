"""(raiders) Ocarina of Time's own code runs only when the game is Ocarina (host/hos_game.h hos_game_is, from gen/hos_image.c).

Read from the sources, as upstream's tests read them:
- every hos_oot_* function host/ defines (found, not listed: an upstream merge that adds one without the guard fails here),
  and the Discord status, return at their first statement unless hos_game_is("oot"); a definition whose whole body is
  (void) casts (oot_menu.c's builds without the menus' mouse) does nothing to guard;
- the host tells the renderer the game before the renderer's start (host/rx_backend.c load_vulkan, HOS_OPT_GAME_OOT), and the
  renderer keeps it (vk_menu.cpp menu_option_set, gpu/vk/vk_game.h);
- the renderer's Ocarina parts ask it: the Debug tab's tools and their switch (cheats_on, row_shown), the visual workaround
  (vk_shader.cpp oot_visual) and the default program skip (vk_draw.cpp), with RX_VK_SKIP_PROG set still winning;
- hos.h's HOS_GAME_TITLE is the game's title, and a test's own definition of it still comes first;
- MKWVK_API_VERSION is unchanged: HOS_OPT_GAME_OOT is an option id, not a field.
No game files.

    python -I -B tests/test_game_gates.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = re.compile(r'^\s*if \(!hos_game_is\("oot"\)\) return( 0)?;')


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def body(text, head):
    """The function from its head to its closing brace at column 0"""
    start = text.index(head)
    end = text.index("\n}\n", start)
    return text[start:end + 2]


def first_statement(text, start):
    """The first line of the body after the definition at start that is not a preprocessor line or blank"""
    lines = text[start:].split("\n")[1:]
    for line in lines:
        if line.strip() and not line.lstrip().startswith("#"):
            return line
    return ""


class HostGateTests(unittest.TestCase):
    def test_every_ocarina_entry_point_returns_for_another_game(self):
        found = []
        for path in sorted((ROOT / "host").rglob("*.c")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"^(?:int|void|float|uint64_t|const char \*)\s+(hos_oot_\w+)\([^;{]*\)\s*\{(.*)$", text, re.M):
                name, rest = m.group(1), m.group(2)
                rel = path.relative_to(ROOT).as_posix()
                if rest.strip():   # (a one-line definition)
                    inner = rest.strip().rstrip("}").strip()
                    self.assertRegex(inner, r"^(\(void\)\w+(, \(void\)\w+)*;)?$",
                                     "%s %s: a one-line body that does something, without the guard" % (rel, name))
                    continue
                found.append((rel, name))
                self.assertRegex(first_statement(text, m.start()), GUARD,
                                 "%s %s: its first statement is not the Ocarina guard" % (rel, name))
        names = {n for _, n in found}
        for want in ("hos_oot_hearts_enabled", "hos_oot_is_player", "hos_oot_flight_shortcut_ready", "hos_oot_flight_rotation",
                     "hos_oot_flight_pose", "hos_oot_lift_player", "hos_oot_free_view", "hos_oot_menu_focus",
                     "hos_oot_menu_tick"):
            self.assertIn(want, names)
        self.assertEqual(len(found), 9, found)

    def test_discord_status(self):
        text = read("host/discord_rpc.c")
        self.assertRegex(first_statement(text, text.index("void hos_discord_start(void) {")), GUARD)

    def test_the_helpers(self):
        h = read("host/hos_game.h")
        for decl in ("extern const char hos_game_id[];", "extern const char hos_game_title[];",
                     "extern const char hos_game_data_dir[];", "int hos_game_is(const char *id);",
                     "const char *hos_game_window_title(void);"):
            self.assertIn(decl, h)
        main = read("host/hos_main.c")
        self.assertIn('int hos_game_is(const char *id) { return id && !strcmp(hos_game_id, id); }', main)
        self.assertIn('const char *hos_game_window_title(void) { return hos_game_title[0] ? hos_game_title : "Hookshot"; }', main)
        hos = read("host/hos.h")
        self.assertIn('#include "hos_game.h"', hos)
        self.assertRegex(hos, r"#ifndef HOS_GAME_TITLE\b[^\n]*\n#define HOS_GAME_TITLE hos_game_window_title\(\)\n#endif")
        # (the two windows take the title through the macro, and the display test defines its own)
        self.assertIn("HOS_GAME_TITLE", read("host/display.c"))
        self.assertIn("HOS_GAME_TITLE", read("host/posix/display_sdl.c"))
        self.assertIn('#define HOS_GAME_TITLE "authored window"', read("tests/display_startup_failure_test.cpp"))

    def test_the_lift_writes_the_identity(self):
        self.assertIn("hos_game_id[]", read("nx2/standalone.py"))


class RendererGateTests(unittest.TestCase):
    def test_the_host_says_before_the_start(self):
        rx = read("host/rx_backend.c")
        load = body(rx, "static const MkwVkRenderer *load_vulkan(")
        say = load.index('r->option_set(HOS_OPT_GAME_OOT, hos_game_is("oot"))')
        self.assertLess(load.index("r->version != MKWVK_API_VERSION"), say)
        self.assertLess(say, load.rindex("return r;"))
        self.assertLess(rx.index("load_vulkan(dll)"), rx.index("r->start(hwnd)"))   # (said in load, started after)

    def test_the_renderer_keeps_it(self):
        api = read("gpu/vk/vk_api.h")
        self.assertIn("enum { HOS_OPT_GAME_OOT = 4089 };", api)
        self.assertRegex(api, r"#define MKWVK_API_VERSION 13\b")   # (an option id, no new field)
        game = read("gpu/vk/vk_game.h")
        self.assertIn("inline std::atomic<bool> vk_game_oot{true};", game)
        menu = read("gpu/vk/vk_menu.cpp")
        setter = body(menu, "void menu_option_set(int id, int value) {")
        self.assertIn("if (id == HOS_OPT_GAME_OOT) {", setter)
        self.assertLess(setter.index("HOS_OPT_GAME_OOT"), setter.index("save()"))   # (before anything saved)
        # (no id clash with the ids the setter already takes: 7, the cheats' and the inventory's)
        items = read("gpu/vk/oot_cheat_items.h")
        self.assertIn("#define OOT_CHEAT_ITEM_BASE 4096", items)
        self.assertIn("#define OOT_CHEAT_AGE_ID 4090", items)

    def test_the_debug_tools_are_ocarinas(self):
        menu = read("gpu/vk/vk_menu.cpp")
        self.assertIn('#include "vk_game.h"', menu)
        self.assertRegex(menu, r"bool cheats_on\(\) \{ return vk_game_oot\.load\(std::memory_order_relaxed\) && "
                               r"\(cheats_env \|\| opts\.debug_tools\); \}")
        shown = body(menu, "bool row_shown(int i) {")
        self.assertIn("(rows[i].cheat < 0 || cheats_on())", shown)
        self.assertIn("(v != &opts.debug_tools || vk_game_oot.load(std::memory_order_relaxed))", shown)

    def test_the_visual_workaround_is_ocarinas(self):
        shader = read("gpu/vk/vk_shader.cpp")
        self.assertIn('#include "vk_game.h"', shader)
        visual = body(shader, "void oot_visual(Shader::IR::Program& program, uint64_t key) {")
        self.assertIn("if (!on || !vk_game_oot.load(std::memory_order_relaxed)) return;", visual)
        self.assertLess(visual.index("vk_game_oot"), visual.index("ApplyOotVisualWorkaround"))

    def test_the_default_skip_is_ocarinas(self):
        draw = read("gpu/vk/vk_draw.cpp")
        self.assertIn('#include "vk_game.h"', draw)
        self.assertIn('static const bool skip_env_unset = !getenv("RX_VK_SKIP_PROG");', draw)
        self.assertIn("const bool default_list = skip_env_unset && vk_game_oot.load(std::memory_order_relaxed);", draw)
        self.assertRegex(draw, r"default_list && cp->key == 0x53509044401d78d2ull && !at\.n")
        # (the explicit list is read whatever the game)
        self.assertIn('const char* list = getenv("RX_VK_SKIP_PROG") && strcmp(getenv("RX_VK_SKIP_PROG"), "-") ? '
                      'getenv("RX_VK_SKIP_PROG") : "";', draw)


if __name__ == "__main__":
    unittest.main()
