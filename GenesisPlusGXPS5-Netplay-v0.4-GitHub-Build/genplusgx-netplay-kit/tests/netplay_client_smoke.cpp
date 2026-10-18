#include "fe_netplay.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <cstdlib>
int main(int argc, char** argv) {
    if (argc != 5 && argc != 6 && argc != 8) return 2;
    netplay::Config cfg;
    cfg.host=argv[1]; cfg.port=atoi(argv[2]); cfg.mode=atoi(argv[3]); cfg.room=argv[4]; cfg.delay=6;
    cfg.connection_type = argc >= 6 ? atoi(argv[5]) : 0;
    if (argc == 8) { cfg.fallback_host = argv[6]; cfg.fallback_port = atoi(argv[7]); }
    std::string error;
    if (!netplay::Start(cfg, 0x123456789abcdef0ull, 0x34567890abcdef12ull, error)) {
        fprintf(stderr, "start: %s\n", error.c_str()); return 3;
    }
    printf("transport=%s\n", netplay::TransportName()); fflush(stdout);
    for (unsigned f=0; f<60; f++) {
        uint16_t a=0, b=0;
        uint16_t local = cfg.mode == 1 ? 0x00aa : 0x0055;
        if (!netplay::Step(f, local, f == 0 ? 0xabcdeffedcba1234ull : 0, a, b, error)) {
            fprintf(stderr, "step %u: %s\n", f, error.c_str()); return 4;
        }
        if (f < 6) assert(a==0 && b==0);
        else assert(a == 0x00aa && b == 0x0055);
    }
    netplay::Stop();
    puts("60 synchronized frames OK");
    return 0;
}
