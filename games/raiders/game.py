"""(raiders) Splatoon Raiders (Switch 2), base game. Plain data: no imports, read by nx2/game.py
(docs/plans/03-architecture.md section 3)."""

ID = "raiders"
TITLE = "Raiders Recomp"   # (the window title and launcher name: no Nintendo marks)
PROGRAM_ID = 0x0400380020056000
# main's build id (the NSO's first 20 id bytes, lower-case hex) -> display version. The first entry is the pinned one.
BUILDS = {"abb30e2fb1cdf3bf618a0da346b6e4274ea1e4f5": "1.0.0 (base)"}
MODULES = ("rtld", "main", "subsdk0", "sdk")
SDK = "21.4.4"
# (System/RegionLangMask.txt's 13 region languages, as the codes of host/nn_applet.c's table: each is one of its 16. The
# runtime's pt-BR, pl and ru are not among the game's)
LANGUAGES = [("ja", "Japanese"), ("en-US", "English (US)"), ("es-419", "Spanish (Latin America)"),
             ("fr-CA", "French (Canada)"), ("en-GB", "English (UK)"), ("es", "Spanish (Spain)"),
             ("fr", "French (France)"), ("de", "German"), ("it", "Italian"), ("nl", "Dutch"),
             ("ko", "Korean"), ("zh-Hans", "Chinese (Simplified)"), ("zh-Hant", "Chinese (Traditional)")]
ROMFS_MIN_FILES = 46_000             # (T05: the base game has 46,340, one stray *.part ignored)
ROMFS_MIN_BYTES = 13_600_000_000     # (T05: 12.69 GiB)
ZS_DICTIONARY = None                 # (T05: no Pack/ZsDic.pack.zs)
DATA_DIR = "raiders-recomp"          # (T16: ~/.local/share/raiders-recomp)
EXE = "hookshot"                     # (upstream's name until M8, T24)
LIFT_PATCHES = "games.raiders.patches"   # (T06: its hooks do nothing until a patch is needed)
SKIP_PROGRAMS = ()                   # (T07: no default RX_VK_SKIP_PROG for this game)
VISUAL_WORKAROUNDS = None            # (T07: off)
PERF_FILES = ("hot_funcs.txt", "hot_order.txt", "raiders_pieces.prof")   # (T22: looked for in work/, all optional)
