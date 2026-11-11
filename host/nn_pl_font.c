/* (raiders) nn::pl's built-in fonts (the Switch 2 SDK's GetBuiltInFontData, Ounce and Nx overloads): a stand-in font file.
   The console's own fonts are system data and are never read or shipped; the answer is an OFL font compiled in by the
   build (nx2/host_font.py: third_party/fonts/libertinus/LibertinusSans-Regular.ttf), or the .ttf/.otf file
   HOS_BUILTIN_FONT names (from the environment only: hookshot_env.txt takes no paths). Glyphs the file lacks (CJK, the
   system's button symbols) show as the font engine's missing glyph. Generic: no game check.

   What a game sees (from the SDK's own implementations, docs/plans/reports/T09a-font.md): a 0x18-byte struct, +0 and +1
   two bytes of the service's answer, +8 the font's address, +0x10 its size; the result is true when the font is there.
   The SDK writes the struct only when it is; Splatoon Raiders' font-container callback ignores the result and reads +8
   and +0x10 anyway, and the font loader accepts plain TrueType/OpenType data by its first four bytes. */
#include "hos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>   /* (SRWLOCK) */

extern const unsigned char hos_builtin_font[];   /* gen/host_font.c (nx2/host_font.py) */
extern const unsigned hos_builtin_font_size;

static SRWLOCK font_lock = SRWLOCK_INIT;
static uint64_t font_addr, font_size;

/* the user's file (HOS_BUILTIN_FONT), whole, or NULL */
static unsigned char *read_font(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    unsigned char *data = NULL;
    long n = fseek(f, 0, SEEK_END) == 0 ? ftell(f) : -1;
    if (n >= 12 && fseek(f, 0, SEEK_SET) == 0 && (data = (unsigned char *)malloc((size_t)n)) &&
        fread(data, 1, (size_t)n, f) != (size_t)n)
        free(data), data = NULL;
    fclose(f);
    *size = data ? (size_t)n : 0;
    return data;
}

/* The font in guest memory: copied once, page-aligned, never moved or freed (hos_sys_alloc) */
static void font_once(void) {
    AcquireSRWLockExclusive(&font_lock);
    if (!font_addr) {
        const unsigned char *src = hos_builtin_font;
        size_t size = hos_builtin_font_size;
        unsigned char *own = NULL;
        const char *path = getenv("HOS_BUILTIN_FONT");
        if (path && *path) {
            own = read_font(path, &size);
            if (own) src = own;
            else size = hos_builtin_font_size, hos_log("pl: HOS_BUILTIN_FONT: could not read %s: the included font instead", path);
        }
        const uint64_t a = hos_sys_alloc((size + 0xFFF) & ~(uint64_t)0xFFF, 0x1000);
        memcpy(GP(a), src, size);
        const unsigned char *g = (const unsigned char *)GP(a);
        hos_log("pl: built-in fonts answered with %s (%u bytes, signature %02x%02x%02x%02x)", own ? path : "the included font",
                (unsigned)size, g[0], g[1], g[2], g[3]);
        free(own);
        font_size = size;
        __atomic_store_n(&font_addr, a, __ATOMIC_RELEASE);
    }
    ReleaseSRWLockExclusive(&font_lock);
}

/* fills a BuiltInFontData* (Ounce or Nx: the same layout) and answers true; each overload and type logged once */
static void builtin_font(Ctx *c, int nx) {
    static volatile LONG seen[2][16];
    if (!__atomic_load_n(&font_addr, __ATOMIC_ACQUIRE)) font_once();
    const uint64_t out = ARG(0);
    const uint32_t type = (uint32_t)ARG(1);
    if (out) {
        memset(GP(out), 0, 0x18);
        G64(out + 8) = font_addr;
        G64(out + 0x10) = font_size;
    }
    if (type < 16 && !InterlockedExchange(&seen[nx][type], 1))
        hos_log("pl: GetBuiltInFontData(%s, type %u, %d) -> the stand-in font (lr %#llx)", nx ? "Nx" : "Ounce", type,
                (int)(ARG(2) & 1), (unsigned long long)c->x[30]);
    RET(1);
}

/* bool GetBuiltInFontData(BuiltInFontDataOunce* out, BuiltInFontTypeOunce type, bool) -> the stand-in font, true */
HLE(_ZN2nn2pl18GetBuiltInFontDataEPNS0_20BuiltInFontDataOunceENS0_20BuiltInFontTypeOunceEb) { builtin_font(c, 0); }
/* bool GetBuiltInFontData(BuiltInFontDataNx* out, BuiltInFontTypeNx type, bool) -> the same font, true */
HLE(_ZN2nn2pl18GetBuiltInFontDataEPNS0_17BuiltInFontDataNxENS0_17BuiltInFontTypeNxEb) { builtin_font(c, 1); }
/* void RequestLoadNxFont(void* buffer, size_t size): the SDK lends the buffer to the pl service to load the Nx fonts into.
   Nothing to load: the Nx answers point at the stand-in, not into the buffer. */
HLE(_ZN2nn2pl17RequestLoadNxFontEPvm) {
    static volatile LONG logged;
    if (!InterlockedExchange(&logged, 1))
        hos_log("pl: RequestLoadNxFont(%#llx, %#llx): nothing loaded (the stand-in font answers)", (unsigned long long)ARG(0),
                (unsigned long long)ARG(1));
}
