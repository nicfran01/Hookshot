"""(raiders) The Legend of Zelda: Ocarina of Time (Switch 2): upstream Hookshot's game, with upstream's values, so that
selecting it changes nothing. Plain data: no imports, read by nx2/game.py."""

ID = "oot"
TITLE = "Hookshot"   # (the name in the version check's sentences: tests/test_builder_status.py asserts them)
PROGRAM_ID = 0x0400486024DEC000   # (readme.md, CONTRIBUTING.md)
# main's build id (the NSO's first 20 id bytes, lower-case hex) -> display version. The first entry is the pinned one; the
# check compares its first 8 digits, as nx2/make_game.py's BUILD_ID always has (docs/design.md section 9 has the whole id)
BUILDS = {"e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348": "update v131072"}
MODULES = ("rtld", "main", "subsdk0", "sdk")   # (docs/design.md section 9)
SDK = "22.2.8"
# (the 16 of nx2/make_game.py's LANGUAGES and host/nn_applet.c's table, in that order)
LANGUAGES = [("en-US", "English (US)"), ("en-GB", "English (UK)"), ("fr", "French (France)"), ("fr-CA", "French (Canada)"), ("de", "German"),
             ("it", "Italian"), ("es", "Spanish (Spain)"), ("es-419", "Spanish (Latin America)"), ("pt-BR", "Portuguese (Brazil)"), ("nl", "Dutch"),
             ("pl", "Polish"), ("ru", "Russian"), ("ja", "Japanese"), ("ko", "Korean"), ("zh-Hans", "Chinese (Simplified)"),
             ("zh-Hant", "Chinese (Traditional)")]
# (T05: the romfs floors. Upstream checks the .nup's unpack its own way and has no floor: None)
ROMFS_MIN_FILES = None
ROMFS_MIN_BYTES = None
ZS_DICTIONARY = "Pack/ZsDic.pack.zs"   # (T05: a record: the three readers look for this path themselves)
DATA_DIR = "hookshot"                  # (T16: ~/.local/share/hookshot, host/hos_main.c)
EXE = "hookshot"
LIFT_PATCHES = "games.oot.patches"     # (T06: wraps nx2/oot_wide, oot_jitter, oot_occlusion, oot_patches; not written yet)
# (T07: RX_VK_SKIP_PROG's default, gpu/vk/vk_draw.cpp: left out while its targets have no view)
SKIP_PROGRAMS = ("53509044401d78d2",)
# (T07: (fog, exposure) of gpu/vk/vk_shader.cpp oot_visual(), applied only with RX_VK_OOT_VISUAL=1)
VISUAL_WORKAROUNDS = (0.08, 1.0)
# (T22: the performance data make_game.py copies from work/ when it is there, all optional)
PERF_FILES = ("hot_funcs.txt", "hot_order.txt", "hookshot_pieces.prof", "hookshot.res")
