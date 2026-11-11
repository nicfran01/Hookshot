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
