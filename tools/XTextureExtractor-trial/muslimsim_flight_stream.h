// GPL-3.0. Additional measured native crops; SD v1 stays unchanged.
// Uses the MS_SD_Header and GL function types declared by muslimsim_sd_stream.h.
struct MS_FlightStream {
    const char* name;
    int page, x, y, side;
    HANDLE handle;
    MS_SD_Header* data;
};
static MS_FlightStream ms_flight[] = {
    {"Local\\MuslimSim.ToLiss.PFD.v1",100,6,2834,750,NULL,NULL},
    {"Local\\MuslimSim.ToLiss.ND.v1",101,764,2834,750,NULL,NULL},
    {"Local\\MuslimSim.ToLiss.EWD.v1",102,1521,2426,620,NULL,NULL}
};
static GLuint ms_flight_fbo = 0;
static ULONGLONG ms_flight_last = 0;
static int ms_flight_next = 0;

static void ms_flight_close() {
    for (auto& s : ms_flight) {
        if (s.data) { s.data->powered=0; UnmapViewOfFile(s.data); s.data=NULL; }
        if (s.handle) { CloseHandle(s.handle); s.handle=NULL; }
    }
    ms_flight_last=0;
}

static void ms_flight_publish(bool powered, GLint texture, int width, int height, const char* aircraft) {
    const ULONGLONG now=GetTickCount64();
    powered=powered && aircraft && strcmp(aircraft,"a321.acf")==0
        && width==4096 && height==4096 && texture>0;
    // Three fixed slots, never a scan of instruments/devices/project catalogues.
    for (auto& s : ms_flight) {
        if (!s.data) {
            s.handle=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,
                0,64+s.side*s.side*4,s.name);
            if (!s.handle) continue;
            s.data=(MS_SD_Header*)MapViewOfFile(s.handle,FILE_MAP_ALL_ACCESS,0,0,0);
            if (!s.data) { CloseHandle(s.handle); s.handle=NULL; continue; }
            s.data->magic=0x4D534649; s.data->version=1; s.data->sequence=0;
            s.data->powered=0; s.data->tick=0; s.data->page=s.page;
            s.data->width=s.side; s.data->height=s.side; s.data->stride=s.side*4;
        }
        if (!powered || now<s.data->demand || now-s.data->demand>1500)
            s.data->powered=0;
    }
    // Aggregate cap: adding a second LCD never doubles the readback rate.
    if (!powered || now-ms_flight_last<500) return;
    MS_FlightStream* selected=NULL;
    for (int i=0;i<3;++i) {
        int index=(ms_flight_next+i)%3;
        auto& s=ms_flight[index];
        if (s.data && s.data->demand && now>=s.data->demand && now-s.data->demand<=1500) {
            selected=&s; ms_flight_next=(index+1)%3; break;
        }
    }
    if (!selected) return;
    ms_flight_last=now;
    static MSGenFBO gen=(MSGenFBO)wglGetProcAddress("glGenFramebuffers");
    static MSBindFBO bind=(MSBindFBO)wglGetProcAddress("glBindFramebuffer");
    static MSAttachFBO attach=(MSAttachFBO)wglGetProcAddress("glFramebufferTexture2D");
    static MSCheckFBO check=(MSCheckFBO)wglGetProcAddress("glCheckFramebufferStatus");
    static MSBindBuffer buffer=(MSBindBuffer)wglGetProcAddress("glBindBuffer");
    auto& s=*selected;
    if (!gen || !bind || !attach || !check || !buffer) { s.data->powered=0; return; }
    if (!ms_flight_fbo) gen(1,&ms_flight_fbo);
    GLint old_fbo,old_pbo,alignment,row_length,skip_rows,skip_pixels;
    glGetIntegerv(0x8CAA,&old_fbo); glGetIntegerv(0x88ED,&old_pbo);
    glGetIntegerv(GL_PACK_ALIGNMENT,&alignment); glGetIntegerv(GL_PACK_ROW_LENGTH,&row_length);
    glGetIntegerv(GL_PACK_SKIP_ROWS,&skip_rows); glGetIntegerv(GL_PACK_SKIP_PIXELS,&skip_pixels);
    bind(0x8CA8,ms_flight_fbo); attach(0x8CA8,0x8CE0,GL_TEXTURE_2D,texture,0);
    if (check(0x8CA8)!=0x8CD5) { bind(0x8CA8,old_fbo); s.data->powered=0; return; }
    buffer(0x88EB,0);
    glPixelStorei(GL_PACK_ALIGNMENT,1); glPixelStorei(GL_PACK_ROW_LENGTH,0);
    glPixelStorei(GL_PACK_SKIP_ROWS,0); glPixelStorei(GL_PACK_SKIP_PIXELS,0);
    LARGE_INTEGER start,end,frequency;
    QueryPerformanceCounter(&start);
    InterlockedIncrement(&s.data->sequence); s.data->powered=0;
    glReadBuffer(0x8CE0);
    glReadPixels(s.x,s.y,s.side,s.side,GL_RGBA,GL_UNSIGNED_BYTE,(char*)s.data+64);
    s.data->powered=glGetError()==GL_NO_ERROR; s.data->tick=now;
    QueryPerformanceCounter(&end); QueryPerformanceFrequency(&frequency);
    s.data->capture_us=(end.QuadPart-start.QuadPart)*1000000/frequency.QuadPart;
    InterlockedIncrement(&s.data->sequence);
    glPixelStorei(GL_PACK_ALIGNMENT,alignment); glPixelStorei(GL_PACK_ROW_LENGTH,row_length);
    glPixelStorei(GL_PACK_SKIP_ROWS,skip_rows); glPixelStorei(GL_PACK_SKIP_PIXELS,skip_pixels);
    buffer(0x88EB,old_pbo); bind(0x8CA8,old_fbo);
}
