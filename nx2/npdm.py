"""main.npdm, the program's metadata: its header, ACI0 (program id, services, SVCs) and the ACID's layout.

(raiders) Moved out of nx2/dump.py unchanged, so that a reader of the program id (nx2/game.py, run by make_game.py and
the game-free tests) needs only the standard library: dump.py imports numpy and a64-kit's nso (lz4) for its other parts.
dump.py imports it from here.
"""
import struct


def npdm(path):
    b = open(path, "rb").read()
    out = {"size": len(b)}
    if b[:4] != b"META":
        out["error"] = "no META magic"
        return out
    flags = b[0xC]
    out["is64"] = bool(flags & 1)
    out["address_space"] = {0: "32-bit", 1: "36-bit", 2: "32-bit (no reserved)", 3: "39-bit"}.get((flags >> 1) & 7,
                                                                                                    "type %d" % ((flags >> 1) & 7))
    out["main_thread_priority"] = b[0xE]
    out["main_thread_core"] = b[0xF]
    out["system_resource_size"] = struct.unpack_from("<I", b, 0x14)[0]
    out["version"] = struct.unpack_from("<I", b, 0x18)[0]
    out["main_thread_stack"] = struct.unpack_from("<I", b, 0x1C)[0]
    out["name"] = b[0x20:0x30].split(b"\0")[0].decode("ascii", "replace")
    out["product_code"] = b[0x30:0x40].split(b"\0")[0].decode("ascii", "replace")
    aoff, asz, doff, dsz = struct.unpack_from("<IIII", b, 0x70)
    aci = b[aoff:aoff + asz]
    if aci[:4] == b"ACI0":
        out["program_id"] = struct.unpack_from("<Q", aci, 0x10)[0]
        sacoff, sacsz = struct.unpack_from("<II", aci, 0x28)
        sac, i, names = aci[sacoff:sacoff + sacsz], 0, []
        while i < len(sac):
            c = sac[i]
            n = (c & 7) + 1
            names.append(sac[i + 1:i + 1 + n].decode("ascii", "replace") + (" (host)" if c & 0x80 else ""))
            i += 1 + n
        out["services"] = names
        kacoff, kacsz = struct.unpack_from("<II", aci, 0x30)
        kac = struct.unpack_from("<%dI" % (kacsz // 4), aci, kacoff)
        svcs = set()
        for d in kac:
            low = (~d & (d + 1)) & 0xFFFFFFFF   # the descriptor type is the count of trailing ones
            if low == 1 << 4:                   # 0b01111: enabled SVCs, 24 per descriptor
                idx = (d >> 29) & 7
                mask = (d >> 5) & 0xFFFFFF
                svcs |= {idx * 24 + j for j in range(24) if mask >> j & 1}
        out["svcs"] = sorted(svcs)
    acid = b[doff:doff + dsz]
    out["acid_switch1_layout"] = acid[0x200:0x204] == b"ACID"
    return out
