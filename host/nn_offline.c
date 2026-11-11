/* (raiders) Offline answers for the SDK's online, local-wireless and system-reporting calls a trace showed the game making
   (docs/plans/tasks/T10-offline-stubs.md Part B; docs/plans/reports/T10-offline.md). The console this runtime describes
   has no network, no local wireless partners, no amiibo activity and no friends. A function is added here only when a
   trace shows it called with a wrong answer, with the rest of its small family; each answer is checked against the
   caller or the SDK's own implementation, and failures use no invented result codes. Generic: no game check. */
#include "hos.h"
#include <stdint.h>
#include <windows.h>   /* (SRWLOCK) */

void hos_system_event_init(uint64_t key, int autoclear);   /* nn_os_sync.c: an event the os:: functions know */

/* ---- nn::prepo: play reports are dropped (host/nn_applet.c: PlayReport::Save/Send), so nothing is ever sent ------ */

/* nn::os::SystemEvent* GetOverSaveFrequencyLimitEvent(): the SDK returns a function-local static SystemEvent (0x30
   bytes), created once with ManualClear and not inter-process, signalled by the prepo service when the game saves
   reports too often. Here: the same object, created once, never signalled (nothing is saved, so never too often).
   The generated stub answered null, which the caller stores (Raiders: main 0x83cb17d8) for later waits. */
HLE(_ZN2nn5prepo30GetOverSaveFrequencyLimitEventEv) {
    static SRWLOCK lock = SRWLOCK_INIT;
    static uint64_t event;
    AcquireSRWLockExclusive(&lock);
    if (!event) {
        event = hos_sys_alloc(0x40, 0x10);   /* (zeroed, never freed or moved) */
        hos_system_event_init(event, 0);     /* EventClearMode_ManualClear, unsignalled */
    }
    ReleaseSRWLockExclusive(&lock);
    RET(event);
}
/* Result AddInternetConnectionStatus(PlayReport*, char const*, char const*, char const*): would add the console's
   connection status to the report under those keys. The report is dropped: success, nothing added. */
HLE(_ZN2nn5prepo27AddInternetConnectionStatusEPNS0_10PlayReportEPKcS4_S4_) { RET(0); }
/* Result RequestImmediateTransmission(): asks the service to send the saved reports now. Nothing is saved or sent:
   success. */
HLE(_ZN2nn5prepo28RequestImmediateTransmissionEv) { RET(0); }

/* ---- nn::ngc: the profanity filter has no system service to ask, so it finds no words ------------------------------
   Of the 7 nn::ngc functions the game imports, only Initialize reaches a service: the SDK's own (sdk 0x854adbb0) asks
   sm: for the ngc service through ngc::detail::CreateServiceByHipc, which aborts when sm: has no such service. The
   constructor, SkipAtSignCheck and CountNumbers only touch the object or the string, and Finalize, the destructor and
   MaskProfanityWordsInText do nothing but return when the object's "initialized" byte (+9) is 0: they stay the SDK's
   own code (docs/plans/reports/T10-offline.md, "Part B, second iteration"). */

/* Result ProfanityFilter::Initialize(void* work, size_t size): the SDK's result for "no ngc service" (0xd092, its own
   answer when the shared service object stays null), with the object left as the constructor made it (+9 still 0, no
   heap in the work buffer). The game ignores the result (main 0x82b7fb64); its Mask calls then get the SDK's
   "not initialized" answer with the text unchanged and the count the caller zeroed beforehand (0x82b7fec4,
   0x82b80424), so no name is treated as profane. */
HLE(_ZN2nn3ngc15ProfanityFilter10InitializeEPvm) {
    static volatile LONG said;
    if (!InterlockedExchange(&said, 1)) hos_log("ngc: profanity filter offline (no ngc service): Initialize answers 0xd092");
    RET(0xd092);
}
