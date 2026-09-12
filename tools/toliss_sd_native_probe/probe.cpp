// GET-only diagnostic, not a telemetry fix. Do not install during a flight.
// ABI: https://developer.x-plane.com/sdk/XPLMDataAccess/
// Resolves only the XPLM module already loaded by X-Plane; no DLL loading.
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
using Ref = void*;
using Loop = float (*)(float, float, int, void*);
static Ref (*find_ref)(const char*);
static int (*get_types)(Ref);
static int (*get_bytes)(Ref, void*, int, int);
static int (*get_int)(Ref);
static float (*get_float)(Ref);
static void (*debug)(const char*);
static void (*register_loop)(Loop, float, void*);
static void (*unregister_loop)(Loop, void*);
static bool registered = false;
static int attempts = 0, samples = 0;
static void inspect_bytes(const char* name, Ref ref) {
    char message[1400];
    if (!ref || !(get_types(ref) & 32)) {
        snprintf(message, sizeof(message), "MS-SD-PROBE %s missing/wrong type\n", name);
        debug(message); return;
    }
    const int size = get_bytes(ref, nullptr, 0, 0);
    for (int requested : {36, 40, 256}) {
        unsigned char bytes[512];
        memset(bytes, 0xa5, sizeof(bytes));
        const int returned = get_bytes(ref, bytes, 0, requested);
        const int bounded = std::max(0, std::min(returned, requested));
        std::string hex, visible;
        for (int i = 0; i < bounded; ++i) {
            char pair[3]; snprintf(pair, sizeof(pair), "%02X", bytes[i]);
            hex += pair;
            visible += bytes[i] >= 32 && bytes[i] <= 126 ? char(bytes[i]) : '.';
        }
        int changed = 0;
        for (int i = 0; i < requested; ++i) changed += bytes[i] != 0xa5;
        bool guard_ok = true;
        for (int i = requested; i < 512; ++i) guard_ok &= bytes[i] == 0xa5;
        snprintf(message, sizeof(message),
            "MS-SD-PROBE %s size=%d request=%d returned=%d changed=%d guard=%d hex=%s text=%s\n",
            name, size, requested, returned, changed, int(guard_ok), hex.c_str(), visible.c_str());
        debug(message);
    }
}
static float sample(float, float, int, void*) {
    if (++attempts > 12) { debug("MS-SD-PROBE stopped: no eligible aircraft\n"); return 0; }
    Ref path_ref = find_ref("sim/aircraft/view/acf_relative_path");
    char path[1024] = {};
    if (path_ref && (get_types(path_ref) & 32)) get_bytes(path_ref, path, 0, 1023);
    if (!strstr(path, "ToLissA321")) return 5;
    Ref page = find_ref("AirbusFBW/SDPage");
    if (!page || !(get_types(page) & 1)) return 5;
    char message[1200];
    snprintf(message, sizeof(message), "MS-SD-PROBE sample=%d page=%d aircraft=%s\n",
             ++samples, get_int(page), path);
    debug(message);
    for (const char* name : {"AirbusFBW/SDline2g", "AirbusFBW/SDline5g",
            "AirbusFBW/SDline13g", "AirbusFBW/SDline2a", "AirbusFBW/SDline5a",
            "AirbusFBW/SDline13a", "AirbusFBW/SDline2w"})
        inspect_bytes(name, find_ref(name));
    for (const char* name : {"AirbusFBW/LeftBleedPress", "AirbusFBW/RightBleedPress",
            "AirbusFBW/Pack1Temp", "AirbusFBW/Pack2Temp"}) {
        Ref ref = find_ref(name);
        if (ref && (get_types(ref) & 2)) {
            snprintf(message, sizeof(message), "MS-SD-PROBE %s value=%.6f\n", name, get_float(ref));
            debug(message);
        }
    }
    if (samples == 3) { debug("MS-SD-PROBE finished: 3 samples; no further reads\n"); return 0; }
    return 5;
}
template<typename T> static bool resolve(HMODULE module, T& target, const char* name) {
    target = reinterpret_cast<T>(GetProcAddress(module, name));
    return target != nullptr;
}
#define EXPORT extern "C" __declspec(dllexport)
EXPORT int XPluginStart(char* name, char* signature, char* description) {
    strcpy_s(name, 256, "MuslimSim SD read-only probe");
    strcpy_s(signature, 256, "muslimsim.diagnostics.sd.readonly");
    strcpy_s(description, 256, "Bounded native SD byte reads; no aircraft or hardware writes.");
    HMODULE module = GetModuleHandleA("XPLM_64.dll");
    return module && resolve(module, find_ref, "XPLMFindDataRef")
        && resolve(module, get_types, "XPLMGetDataRefTypes")
        && resolve(module, get_bytes, "XPLMGetDatab")
        && resolve(module, get_int, "XPLMGetDatai")
        && resolve(module, get_float, "XPLMGetDataf")
        && resolve(module, debug, "XPLMDebugString")
        && resolve(module, register_loop, "XPLMRegisterFlightLoopCallback")
        && resolve(module, unregister_loop, "XPLMUnregisterFlightLoopCallback");
}
EXPORT int XPluginEnable() {
    if (!registered) {
        attempts = samples = 0; register_loop(sample, 10, nullptr); registered = true;
    }
    return 1;
}
EXPORT void XPluginDisable() {
    if (registered) { unregister_loop(sample, nullptr); registered = false; }
}
EXPORT void XPluginStop() { XPluginDisable(); }
EXPORT void XPluginReceiveMessage(int, int, void*) {}
