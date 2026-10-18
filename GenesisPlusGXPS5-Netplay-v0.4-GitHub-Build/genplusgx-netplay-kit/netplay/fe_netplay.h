// GN1 developmental input-delay transport: TLS relay, direct, or automatic fallback.
// Direct TCP transport is experimental and plaintext; use LAN/trusted VPN until TLS is available.
// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <string>
namespace netplay {
struct Config {
    int connection_type = 0;     // 0 = TLS relay; 1 = direct TCP; 2 = auto direct-first then TLS relay
    int mode = 0;                // 0 off, 1 host (player 1), 2 join (player 2)
    std::string host = "127.0.0.1"; // relay hostname, or peer address when directly joining
    int port = 43377;
    // Used only by automatic mode when the initial direct connection fails.
    std::string fallback_host;
    int fallback_port = 43377;
    int accept_timeout_ms = 120000; // automatic mode overrides to ~3 seconds
    int connect_timeout_ms = 5000;
    std::string room;          // 8-32 alphanumeric characters, shared out-of-band
    int delay = 6;             // emulated input delay in frames
};
bool Active();
int Role();
// Actual transport selected; Automatic may choose either one.
const char* TransportName();
// Blocking handshake; relay waits for peer, direct host accepts one peer (up to 120s).
bool Start(const Config& cfg, uint64_t game_hash, uint64_t settings_hash, std::string& error);
// At each frame, exchange local sampled inputs and obtain ordered P1/P2 bits.
// Send for frame + delay, consume pre-buffered frame. Return false on timeout.
bool Step(uint64_t frame, uint16_t local_bits, uint64_t state_digest, uint16_t& host_bits, uint16_t& join_bits, std::string& error);
void Stop();
} // namespace netplay
