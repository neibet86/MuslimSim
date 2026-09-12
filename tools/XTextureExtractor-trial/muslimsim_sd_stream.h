// Local, demand-driven SD readback. GPL-3.0, as the containing plugin.
// No aircraft writes, network sockets, full-atlas reads or disk frame writes.
#include <windows.h>
#include <stdint.h>
#include <stddef.h>

struct MS_SD_Header {
    uint32_t magic, version;
    volatile LONG sequence;
    uint32_t powered;
    int32_t page;
    uint32_t width, height, stride;
    uint64_t tick;
    volatile uint64_t demand;
    uint64_t capture_us, reserved;
};
static_assert(sizeof(MS_SD_Header) == 64, "SD shared header layout");
static_assert(offsetof(MS_SD_Header, demand) == 40, "SD demand offset");
static HANDLE ms_sd_handle = NULL;
static MS_SD_Header* ms_sd = NULL;
static GLuint ms_sd_fbo = 0;
static ULONGLONG ms_sd_last = 0;
static int ms_sd_page = -1;

typedef void (APIENTRY *MSGenFBO)(GLsizei, GLuint*);
typedef void (APIENTRY *MSBindFBO)(GLenum, GLuint);
typedef void (APIENTRY *MSAttachFBO)(GLenum, GLenum, GLenum, GLuint, GLint);
typedef GLenum (APIENTRY *MSCheckFBO)(GLenum);
typedef void (APIENTRY *MSBindBuffer)(GLenum, GLuint);

static void ms_sd_publish(bool powered, GLint texture, int width, int height, const char* aircraft) {
    if (!ms_sd) {
        ms_sd_handle = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE,
            0, 64 + 620 * 620 * 4, "Local\\MuslimSim.ToLiss.SD.v1");
        if (!ms_sd_handle) return;
        ms_sd = (MS_SD_Header*)MapViewOfFile(ms_sd_handle, FILE_MAP_ALL_ACCESS, 0, 0, 0);
        if (!ms_sd) { CloseHandle(ms_sd_handle); ms_sd_handle = NULL; return; }
        ms_sd->magic = 0x4d534453; ms_sd->version = 1;
        ms_sd->sequence = 0; ms_sd->powered = 0; ms_sd->tick = 0;
    }
    const ULONGLONG now = GetTickCount64();
    // This crop has been measured only for this A321 4096-square atlas.
    powered = powered && aircraft && strcmp(aircraft, "a321.acf") == 0
        && width == 4096 && height == 4096 && texture > 0;
    if (!powered) { ms_sd->powered = 0; return; }
    if (now < ms_sd->demand || now - ms_sd->demand > 1500 || now - ms_sd_last < 500) return;
    ms_sd_last = now;
    static MSGenFBO gen = (MSGenFBO)wglGetProcAddress("glGenFramebuffers");
    static MSBindFBO bind = (MSBindFBO)wglGetProcAddress("glBindFramebuffer");
    static MSAttachFBO attach = (MSAttachFBO)wglGetProcAddress("glFramebufferTexture2D");
    static MSCheckFBO check = (MSCheckFBO)wglGetProcAddress("glCheckFramebufferStatus");
    static MSBindBuffer buffer = (MSBindBuffer)wglGetProcAddress("glBindBuffer");
    static XPLMDataRef page = XPLMFindDataRef("AirbusFBW/SDPage");
    if (!gen || !bind || !attach || !check || !buffer || !page) { ms_sd->powered = 0; return; }
    int current_page = XPLMGetDatai(page);
    if (current_page != ms_sd_page) {
        // Let the native SD finish its own page change before naming pixels.
        ms_sd_page = current_page; ms_sd->powered = 0; return;
    }
    if (!ms_sd_fbo) gen(1, &ms_sd_fbo);
    GLint old_fbo, old_pbo, alignment, row_length, skip_rows, skip_pixels;
    glGetIntegerv(0x8CAA, &old_fbo); // GL_READ_FRAMEBUFFER_BINDING
    glGetIntegerv(0x88ED, &old_pbo); // GL_PIXEL_PACK_BUFFER_BINDING
    glGetIntegerv(GL_PACK_ALIGNMENT, &alignment);
    glGetIntegerv(GL_PACK_ROW_LENGTH, &row_length);
    glGetIntegerv(GL_PACK_SKIP_ROWS, &skip_rows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS, &skip_pixels);
    bind(0x8CA8, ms_sd_fbo); // GL_READ_FRAMEBUFFER; do not touch draw binding.
    attach(0x8CA8, 0x8CE0, GL_TEXTURE_2D, texture, 0);
    if (check(0x8CA8) != 0x8CD5) { bind(0x8CA8, old_fbo); ms_sd->powered = 0; return; }
    buffer(0x88EB, 0);
    glPixelStorei(GL_PACK_ALIGNMENT, 1); glPixelStorei(GL_PACK_ROW_LENGTH, 0);
    glPixelStorei(GL_PACK_SKIP_ROWS, 0); glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
    LARGE_INTEGER start, end, frequency;
    QueryPerformanceCounter(&start);
    InterlockedIncrement(&ms_sd->sequence); // odd: writer owns pixels
    ms_sd->powered = 0;
    glReadBuffer(0x8CE0);
    glReadPixels(2151, 2426, 620, 620, GL_RGBA, GL_UNSIGNED_BYTE, (char*)ms_sd + 64);
    GLenum read_error = glGetError();
    ms_sd->page = current_page; ms_sd->width = 620; ms_sd->height = 620; ms_sd->stride = 2480;
    ms_sd->tick = now;
    ms_sd->powered = read_error == GL_NO_ERROR && XPLMGetDatai(page) == current_page;
    QueryPerformanceCounter(&end); QueryPerformanceFrequency(&frequency);
    ms_sd->capture_us = (end.QuadPart - start.QuadPart) * 1000000 / frequency.QuadPart;
    InterlockedIncrement(&ms_sd->sequence); // even: complete frame
    glPixelStorei(GL_PACK_ALIGNMENT, alignment); glPixelStorei(GL_PACK_ROW_LENGTH, row_length);
    glPixelStorei(GL_PACK_SKIP_ROWS, skip_rows); glPixelStorei(GL_PACK_SKIP_PIXELS, skip_pixels);
    buffer(0x88EB, old_pbo); bind(0x8CA8, old_fbo);
}

static void ms_sd_close() {
    if (ms_sd) { ms_sd->powered = 0; UnmapViewOfFile(ms_sd); ms_sd = NULL; }
    if (ms_sd_handle) { CloseHandle(ms_sd_handle); ms_sd_handle = NULL; }
    // GL object is context-owned; deleting from plugin-stop without a current
    // GL context is unsafe. A single tiny FBO remains until context teardown.
    ms_sd_last = 0;
    ms_sd_page = -1;
}
