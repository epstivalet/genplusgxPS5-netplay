#include "fe_p2p_probe.h"
#include <cstdio>
#include <cstdlib>
#include <string>
int main(int argc, char** argv) {
    if (argc != 6) return 2;
    netplay_probe::Config cfg;
    cfg.host = argv[1];
    cfg.tcp_port = atoi(argv[2]);
    cfg.udp_port = atoi(argv[3]);
    cfg.role = atoi(argv[4]);
    cfg.room = argv[5];
    std::string message;
    const bool connected = netplay_probe::Run(cfg, message);
    fprintf(connected ? stdout : stderr, "%s\n", message.c_str());
    return connected ? 0 : 1;
}
