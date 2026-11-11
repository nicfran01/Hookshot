"""(raiders) The runtime opens no network connection of its own: host/ and gpu/vk/ (comments left out) have no call that opens
one (sockets, name lookups, WinHTTP / WinINet, libcurl, a curl or wget command line) outside the allowlist below, each entry with
its reason. An upstream merge that adds networking fails here. Also checks that the Discord status (the one local IPC to another
program, which publishes what is being played) still starts only for upstream's game. No game files.

    python -I -B tests/test_no_network.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("host", "gpu/vk")
SUFFIXES = {".c", ".cpp", ".h", ".hpp", ".cc", ".inl"}

# what opens or prepares a network connection
PATTERNS = {
    "socket(": re.compile(r"\bsocket\s*\("),
    "connect(": re.compile(r"\bconnect\s*\("),
    "getaddrinfo(": re.compile(r"\bgetaddrinfo\s*\("),
    "gethostbyname(": re.compile(r"\bgethostbyname\s*\("),
    "sendto(": re.compile(r"\bsendto\s*\("),
    "WSAStartup": re.compile(r"\bWSAStartup\b"),
    "curl_": re.compile(r"\bcurl_\w+\s*\("),
    "WinHttp": re.compile(r"\bWinHttp\w+\s*\("),
    "WinINet": re.compile(r"\b(InternetOpen|InternetConnect|HttpOpenRequest|URLDownloadTo)\w*\s*\("),
    "curl/wget command": re.compile(r"\"[^\"\n]*\b(curl|wget)\s"),
}

# (file, pattern) -> why it is allowed
ALLOWED = {
    ("host/discord_rpc.c", "socket("): "the Discord status: an AF_UNIX socket to a Discord client on this machine (local IPC, no "
                                       "network); started only for upstream's game (checked below)",
    ("host/discord_rpc.c", "connect("): "the same socket's connect, to the discord-ipc-N path",
    ("host/hos_update.c", "WinHttp"): "upstream's update offer: one HTTPS GET to api.github.com (not a Nintendo service), only in a "
                                      "game folder with hookshot_version.txt; HOOKSHOT_NO_UPDATE_CHECK=1 turns it off",
    ("host/hos_update.c", "curl/wget command"): "the same offer on Linux, through the curl command",
    ("host/nn_audio_in.c", "connect("): "a function of its own named connect (it opens the microphone), not the socket call",
}


def strip_comments(text):
    """C and C++ comments out (string literals kept), line count kept"""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"' or c == "'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * text.count("\n", i, j))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def findings(root=ROOT):
    """[(file, line, pattern)] of every match outside comments"""
    hits = []
    for top in SCANNED:
        for path in sorted((root / top).rglob("*")):
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
            for no, line in enumerate(text.split("\n"), 1):
                for name, pattern in PATTERNS.items():
                    if pattern.search(line):
                        hits.append((rel, no, name))
    return hits


class NoNetwork(unittest.TestCase):
    def test_no_network_call_outside_the_allowlist(self):
        bad = [h for h in findings() if (h[0], h[2]) not in ALLOWED]
        self.assertEqual(bad, [], "network calls in the runtime: add a reason to ALLOWED only if it reaches no network, or "
                                  "is not a Nintendo service and can be turned off")

    def test_every_allowance_is_used(self):
        used = {(f, p) for f, _, p in findings()}
        self.assertEqual(sorted(set(ALLOWED) - used), [], "allowlist entries that match nothing: remove them")

    def test_the_patterns_catch_what_they_should(self):
        sample = strip_comments('int s = socket(AF_INET, 1, 0); /* socket( in a comment */\n'
                                '// connect( in a comment\nconnect (s, a, n);\nWinHttpOpen(L"x");\n'
                                'snprintf(cmd, n, "curl -s %s", url);\ncurl_easy_init();\n')
        got = {name for line in sample.split("\n") for name, p in PATTERNS.items() if p.search(line)}
        self.assertEqual(got, {"socket(", "connect(", "WinHttp", "curl/wget command", "curl_"})
        self.assertEqual(strip_comments("a /* x\ny */ b").count("\n"), 1)   # (line numbers kept)

    def test_discord_status_starts_only_for_upstreams_game(self):
        # (the status names Ocarina of Time under Hookshot's Discord application: for any other game it stays off, and the
        # option that turns it on is read after this check)
        src = (ROOT / "host" / "discord_rpc.c").read_text(encoding="utf-8")
        start = src[src.index("void hos_discord_start(void) {"):]
        body = start[:start.index("\n}\n")]
        lines = [l.strip() for l in body.split("\n")[1:] if l.strip()]
        self.assertTrue(lines[0].startswith('if (!hos_game_is("oot")) return;'), lines[:2])
        self.assertLess(body.index('hos_game_is("oot")'), body.index('getenv("HOS_DISCORD")'))


if __name__ == "__main__":
    unittest.main()
