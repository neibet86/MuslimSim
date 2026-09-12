#include "probe.cpp"
#include <cassert>
#include <vector>
static std::vector<std::string> messages;
static int requests = 0, unregistered = 0;
static Ref fake_find(const char* name) { return const_cast<char*>(name); }
static int fake_types(Ref ref) {
    const std::string name = static_cast<const char*>(ref);
    if (name == "AirbusFBW/SDPage") return 1;
    return name.find("SDline") != std::string::npos || name.find("acf_relative_path") != std::string::npos ? 32 : 2;
}
static int fake_bytes(Ref ref, void* out, int, int maximum) {
    const std::string name = static_cast<const char*>(ref);
    if (name.find("acf_relative_path") != std::string::npos) {
        const char* path = "Aircraft/ToLissA321_V1p8/a321.acf";
        if (out) memcpy(out, path, std::min(maximum, int(strlen(path) + 1)));
        return int(strlen(path) + 1);
    }
    if (!out) return 36;
    ++requests; memset(out, 0, std::min(maximum, 36));
    // Synthetic provider with a buffer-size differential, NOT live evidence.
    if (maximum >= 40) memcpy(static_cast<char*>(out) + 4, "210", 3);
    return std::min(maximum, 36);
}
static int fake_int(Ref) { return 1; }
static float fake_float(Ref) { return 65.0f; }
static void fake_debug(const char* text) { messages.emplace_back(text); }
static void fake_unregister(Loop, void*) { ++unregistered; }
int main() {
    find_ref = fake_find; get_types = fake_types; get_bytes = fake_bytes;
    get_int = fake_int; get_float = fake_float; debug = fake_debug;
    unregister_loop = fake_unregister;
    assert(sample(0,0,0,nullptr) == 5);
    assert(sample(0,0,0,nullptr) == 5);
    assert(sample(0,0,0,nullptr) == 0);
    assert(samples == 3 && requests == 63);
    bool saw_small = false, saw_large = false;
    for (auto& line : messages) {
        if (line.find("request=36") != std::string::npos) {
            assert(line.find("text=....................................") != std::string::npos);
            saw_small = true;
        }
        if (line.find("request=40") != std::string::npos) {
            assert(line.find("text=....210") != std::string::npos);
            assert(line.find("guard=1") != std::string::npos); saw_large = true;
        }
    }
    assert(saw_small && saw_large);
    registered = true; XPluginDisable(); XPluginStop();
    assert(unregistered == 1 && !registered);
    puts("Native SD probe: bounded reads, bytes, buffer differential and shutdown passed.");
}
