"""(raiders, T16) The per-user data folder on Linux is the game's own (host/hos_main.c saves_dir, hos_game_data_dir_name).

Builds, from host/hos_main.c as it is, hos_game_is, hos_game_data_dir_name and the Linux saves_dir with its copy_tree and
delete_tree, over a small Win32-on-POSIX layer of this file's own (so it runs on macOS too), then checks:

- the folder is $XDG_DATA_HOME/<DATA_DIR> when XDG_DATA_HOME is an absolute path, else ~/.local/share/<DATA_DIR>, as
  upstream does for its own folder ("raiders-recomp" for Raiders, "hookshot" for Ocarina);
- an image that names no data folder gets "hookshot";
- Ocarina still moves an old user/ folder from beside the executable into its folder the first time (and writes
  saves-moved.txt beside it); another game leaves that folder alone and never takes its saves;
- nothing else in hos_main.c names the hookshot data folder.

python -I -B tests/test_save_paths.py [--cc gcc]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]
RUN_ALL_SKIP = {"windows": "the Linux data folder (saves_dir is not built on Windows)"}

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def line(text, marker):
    start = text.index(marker)
    return text[start:text.index("\n", start)]


SHIM = r'''#include <dirent.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
typedef uint32_t DWORD;
typedef int BOOL;
typedef void *HANDLE;
#define MAX_PATH 4096
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)
#define FILE_ATTRIBUTE_DIRECTORY 0x10
#define FILE_ATTRIBUTE_NORMAL 0x80
#define SEP '/'
#define SEP_S "/"
typedef struct { DWORD dwFileAttributes; char cFileName[MAX_PATH]; } WIN32_FIND_DATAA;
static DWORD GetFileAttributesA(const char *p) {
    struct stat st;
    if (stat(p, &st)) return INVALID_FILE_ATTRIBUTES;
    return S_ISDIR(st.st_mode) ? FILE_ATTRIBUTE_DIRECTORY : FILE_ATTRIBUTE_NORMAL;
}
static BOOL CreateDirectoryA(const char *p, void *sa) { (void)sa; return mkdir(p, 0755) == 0; }
static BOOL DeleteFileA(const char *p) { return unlink(p) == 0; }
static BOOL RemoveDirectoryA(const char *p) { return rmdir(p) == 0; }
static BOOL MoveFileExA(const char *a, const char *b, DWORD flags) { (void)flags; return rename(a, b) == 0; }
typedef struct { DIR *d; } Find;
static BOOL next_entry(Find *f, WIN32_FIND_DATAA *fd) {
    struct dirent *e = readdir(f->d);
    if (!e) return 0;
    snprintf(fd->cFileName, sizeof fd->cFileName, "%s", e->d_name);
    fd->dwFileAttributes = 0;
    return 1;
}
static HANDLE FindFirstFileA(const char *pattern, WIN32_FIND_DATAA *fd) {   /* (only "<dir>" + "/" + "*" here) */
    char dir[MAX_PATH];
    snprintf(dir, sizeof dir, "%s", pattern);
    char *star = strrchr(dir, '/');
    if (!star || strcmp(star, "/*")) return INVALID_HANDLE_VALUE;
    *star = 0;
    Find *f = calloc(1, sizeof *f);
    if (!(f->d = opendir(dir)) || !next_entry(f, fd)) {
        if (f->d) closedir(f->d);
        free(f);
        return INVALID_HANDLE_VALUE;
    }
    return f;
}
static BOOL FindNextFileA(HANDLE h, WIN32_FIND_DATAA *fd) { return next_entry(h, fd); }
static BOOL FindClose(HANDLE h) { closedir(((Find *)h)->d); free(h); return 1; }
static void hos_log(const char *f, ...) {
    va_list a;
    va_start(a, f);
    fprintf(stderr, "log: ");
    vfprintf(stderr, f, a);
    fprintf(stderr, "\n");
    va_end(a);
}
'''

MAIN = r'''
int main(int argc, char **argv) {   /* <game id> <data dir> <beside user folder> */
    if (argc != 4) return 2;
    hos_game_id = argv[1];
    hos_game_data_dir = argv[2];
    printf("%s\n", saves_dir(argv[3]));
    return 0;
}
'''


def build(cc, out):
    main = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    pieces = [
        line(main, "int hos_game_is(const char *id) {"),
        line(main, "const char *hos_game_data_dir_name(void) {"),
        block(main, "static int is_dir(const char *p) {"),
        block(main, "static int copy_tree(const char *from, const char *to) {"),
        block(main, "static void delete_tree(const char *p) {"),
        block(main, "static const char *saves_dir(const char *beside) {"),
    ]
    # (the generated strings are arrays in gen/hos_image.c: pointers here, so one binary checks every game)
    src = SHIM + "static const char *hos_game_id, *hos_game_data_dir;\n" + "\n".join(pieces) + MAIN
    c = out / "save_paths_test.c"
    c.write_text(src, encoding="utf-8")
    exe = out / "save_paths_test"
    subprocess.run([cc, "-std=c11", "-D_DEFAULT_SOURCE", "-D_DARWIN_C_SOURCE", "-Wall", "-Werror", "-o", str(exe),
                    str(c)], check=True)
    return exe


class Check:
    def __init__(self, exe, tmp):
        self.exe, self.tmp, self.failures, self.n = exe, tmp, [], 0

    def run(self, game, data_dir, beside, **env):
        e = {k: v for k, v in os.environ.items() if k not in ("XDG_DATA_HOME", "HOME")}
        e.update({k: str(v) for k, v in env.items()})
        r = subprocess.run([str(self.exe), game, data_dir, str(beside)], env=e, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("save_paths_test exited %d: %s" % (r.returncode, r.stderr))
        return r.stdout.strip()

    def expect(self, what, got, want):
        self.n += 1
        if got != want:
            self.failures.append("%s: got %r, want %r" % (what, got, want))

    def fresh(self, name):
        d = self.tmp / name
        d.mkdir()
        return d


def text_checks(chk):
    main = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    fn = block(main, "static const char *saves_dir(const char *beside) {")
    chk.expect("saves_dir names no folder of its own", '"/hookshot"' in fn, False)
    chk.expect("saves_dir takes the game's folder", '"/%s", hos_game_data_dir_name()' in fn, True)
    chk.expect("the move is Ocarina's", fn.index('if (!hos_game_is("oot")) return dir;') < fn.index("FindFirstFileA"),
               True)
    chk.expect("one helper", main.count("const char *hos_game_data_dir_name(void) {"), 1)
    chk.expect("declared", "const char *hos_game_data_dir_name(void);" in (ROOT / "host/hos_game.h").read_text(), True)
    for gid, want in (("raiders", '"raiders-recomp"'), ("oot", '"hookshot"')):
        cfg = (ROOT / "games" / gid / "game.py").read_text(encoding="utf-8")
        chk.expect("%s DATA_DIR" % gid, line(cfg, "DATA_DIR =").split("=", 1)[1].split("#")[0].strip(), want)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    if os.name == "nt":
        print("SKIP: saves_dir is the Linux build's")
        return
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t).resolve()
        chk = Check(build(a.cc, tmp), tmp)
        text_checks(chk)

        # XDG_DATA_HOME, absolute: <it>/<DATA_DIR>
        xdg, game = chk.fresh("xdg"), chk.fresh("game1")
        got = chk.run("raiders", "raiders-recomp", game / "user", XDG_DATA_HOME=xdg, HOME=chk.fresh("home0"))
        chk.expect("XDG_DATA_HOME", got, str(xdg / "raiders-recomp"))
        chk.expect("XDG folder made", (xdg / "raiders-recomp").is_dir(), True)

        # no XDG_DATA_HOME: ~/.local/share/<DATA_DIR>, made with its parents
        home = chk.fresh("home1")
        got = chk.run("raiders", "raiders-recomp", game / "user", HOME=home)
        chk.expect("HOME", got, str(home / ".local/share/raiders-recomp"))
        chk.expect("no hookshot folder for Raiders", (home / ".local/share/hookshot").exists(), False)

        # a relative XDG_DATA_HOME is not used (the XDG rule; upstream's too)
        home = chk.fresh("home2")
        got = chk.run("raiders", "raiders-recomp", game / "user", HOME=home, XDG_DATA_HOME="rel/data")
        chk.expect("relative XDG_DATA_HOME", got, str(home / ".local/share/raiders-recomp"))

        # neither: the folder beside the executable
        got = chk.run("raiders", "raiders-recomp", game / "user")
        chk.expect("no HOME", got, str(game / "user"))

        # an image without a data folder: hookshot
        home = chk.fresh("home3")
        got = chk.run("oot", "", game / "user", HOME=home)
        chk.expect("empty DATA_DIR", got, str(home / ".local/share/hookshot"))

        # Ocarina: an old user/ folder beside the executable moves in, entry by entry, and says so
        home, game = chk.fresh("home4"), chk.fresh("game2")
        (game / "user/save/0001").mkdir(parents=True)
        (game / "user/save/0001/progress.sav").write_bytes(b"x" * 10)
        (game / "user/options.txt").write_text("a=1\n")
        got = chk.run("oot", "hookshot", game / "user", HOME=home)
        data = home / ".local/share/hookshot"
        chk.expect("Ocarina folder", got, str(data))
        chk.expect("Ocarina save moved", (data / "save/0001/progress.sav").read_bytes(), b"x" * 10)
        chk.expect("Ocarina options moved", (data / "options.txt").read_text(), "a=1\n")
        chk.expect("Ocarina old folder gone", (game / "user").exists(), False)
        chk.expect("Ocarina note", (game / "saves-moved.txt").is_file(), True)

        # Ocarina: an entry already in the new folder keeps the old place for all of them (upstream's rule, unchanged)
        home, game = chk.fresh("home5"), chk.fresh("game3")
        (home / ".local/share/hookshot").mkdir(parents=True)
        (home / ".local/share/hookshot/options.txt").write_text("new\n")
        (game / "user").mkdir()
        (game / "user/options.txt").write_text("old\n")
        got = chk.run("oot", "hookshot", game / "user", HOME=home)
        chk.expect("Ocarina kept", got, str(game / "user"))

        # Raiders: the user/ folder beside the executable is left alone, and its saves are not taken
        home, game = chk.fresh("home6"), chk.fresh("game4")
        (game / "user/save").mkdir(parents=True)
        (game / "user/save/stray.dat").write_bytes(b"y")
        got = chk.run("raiders", "raiders-recomp", game / "user", HOME=home)
        chk.expect("Raiders folder", got, str(home / ".local/share/raiders-recomp"))
        chk.expect("Raiders leaves user/", (game / "user/save/stray.dat").read_bytes(), b"y")
        chk.expect("Raiders takes nothing", os.listdir(home / ".local/share/raiders-recomp"), [])
        chk.expect("Raiders writes no note", (game / "saves-moved.txt").exists(), False)

        if chk.failures:
            print("FAIL:\n  " + "\n  ".join(chk.failures))
            sys.exit(1)
        print("OK: %d checks" % chk.n)


if __name__ == "__main__":
    main()
