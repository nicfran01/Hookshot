import sys, os, re
sys.path.insert(0, "nx2")
import kit
import nso
mods = nso.load_exefs(kit.need_exefs())
out = {}
for m in mods:
    data = bytes(m.image)
    names = sorted(set(h.group(0)[:-1].decode() for h in re.finditer(rb"nvn[A-Z][A-Za-z0-9]{3,80}\0", data)))
    out[m.name] = names
    print(m.name, len(names))
open("work/nvn_main.txt", "w").write("\n".join(out["main"]) + "\n")
open("work/nvn_sdk.txt", "w").write("\n".join(out["sdk"]) + "\n")
