import sys, re, collections
sys.path.insert(0, "nx2")
import kit, nso
mods = {m.name: m for m in nso.load_exefs(kit.need_exefs())}
def strs(m, pat, limit=40):
    data = bytes(m.image); out = []
    for h in re.finditer(pat, data):
        s = h.group(0).rstrip(b"\0").decode("ascii", "replace")
        if s not in out: out.append(s)
        if len(out) >= limit: break
    return out
main, sdk, sub = mods["main"], mods["sdk"], mods["subsdk0"]
print("MW main:", strs(main, rb"SDK MW\+[^\0]{4,120}\0", 80))
print("MW sub :", strs(sub, rb"SDK MW\+[^\0]{4,120}\0", 80))
print("MW sdk :", strs(sdk, rb"SDK MW\+[^\0]{4,120}\0", 80))
for label, pat in [("havok", rb"[Hh]avok[^\0]{0,60}\0"), ("engine ns", rb"(?:gsys|agl|sead|engine|Lp|Game|phive)::[A-Za-z0-9_:]{3,60}\0"),
                   ("dlss", rb"[^\0]{0,30}(?:Dlss|DLSS)[^\0]{0,40}\0"), ("astc", rb"[^\0]{0,30}(?:ASTC|Astc)[^\0]{0,30}\0"),
                   ("webm/movie", rb"[^\0]{0,40}(?:\.webm|\.mp4|Movie/)[^\0]{0,40}\0"), ("opus", rb"[^\0]{0,30}[Oo]pus[^\0]{0,30}\0"),
                   ("Blitz/Hoian", rb"[^\0]{0,30}(?:Blitz|Hoian|Thunder|Raiders|Splatoon)[^\0]{0,40}\0"),
                   ("services", rb"(?:[a-z]{2,8}:[a-z0-9]{1,4}|fsp-srv)\0")]:
    print("##", label, strs(main, pat, 30))
print("## subsdk0 sample", strs(sub, rb"[A-Za-z_:]{12,60}\0", 40))
