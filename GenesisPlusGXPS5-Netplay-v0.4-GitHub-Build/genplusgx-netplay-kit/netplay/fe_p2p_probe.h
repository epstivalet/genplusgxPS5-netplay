// GN2 reachability diagnostic ONLY. It does not carry emulator/game inputs.
// SPDX-License-Identifier: MIT
#pragma once
#include <string>
namespace netplay_probe {
struct Config {
    std::string host;             // Public TLS DNS name on PS5, loopback in host tests.
    int tcp_port = 43380;         // Rendezvous signaling.
    int udp_port = 43379;         // UDP mapping discovery on the same server.
    int role = 0;                 // 1 HOST, 2 JOIN.
    std::string room;            // 16-32 alphanumeric characters (private test room).
};
bool Run(const Config& cfg, std::string& result); // Blocking, 90-second cap.
} // namespace netplay_probe
