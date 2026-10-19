// GN2 native PS5/POSIX UDP reachability probe, not gameplay transport.
// PS5 signaling MUST use certificate-verified TLS. Never forward plaintext frames.
// SPDX-License-Identifier: MIT
#include "fe_p2p_probe.h"
#ifdef GENPLUS_NETPLAY_TLS
#include "fe_netplay_tls.h"
#endif
#include <arpa/inet.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

namespace netplay_probe {
namespace {
int tcp = -1;
int udp = -1;
std::string buffered;

void Cleanup() {
#ifdef GENPLUS_NETPLAY_TLS
    netplay_tls::Stop();
#endif
    if (tcp >= 0) close(tcp);
    if (udp >= 0) close(udp);
    tcp = -1;
    udp = -1;
    buffered.clear();
}
bool WaitFd(int fd, short events, int ms) {
    pollfd p{}; p.fd = fd; p.events = events;
    int r;
    do { r = poll(&p, 1, ms); } while (r < 0 && errno == EINTR);
    return r > 0 && (p.revents & events) && !(p.revents & (POLLERR | POLLHUP | POLLNVAL));
}
bool Resolve(const std::string& name, int port, int type, sockaddr_in& out) {
    addrinfo hints{}; hints.ai_family = AF_INET; hints.ai_socktype = type;
    addrinfo* res = nullptr;
    char service[12]; snprintf(service, sizeof(service), "%d", port);
    if (getaddrinfo(name.c_str(), service, &hints, &res) != 0 || !res) return false;
    memcpy(&out, res->ai_addr, sizeof(out));
    freeaddrinfo(res);
    return true;
}
bool ConnectTcp(const sockaddr_in& a) {
    tcp = socket(AF_INET, SOCK_STREAM, 0);
    if (tcp < 0) return false;
    int flags = fcntl(tcp, F_GETFL, 0);
    if (flags < 0 || fcntl(tcp, F_SETFL, flags | O_NONBLOCK) < 0) return false;
    int rc = connect(tcp, reinterpret_cast<const sockaddr*>(&a), sizeof(a));
    if (rc < 0 && errno == EINPROGRESS) {
        if (!WaitFd(tcp, POLLOUT, 5000)) return false;
        int so = 0; socklen_t size = sizeof(so);
        if (getsockopt(tcp, SOL_SOCKET, SO_ERROR, &so, &size) != 0 || so != 0) return false;
    } else if (rc != 0) return false;
    if (fcntl(tcp, F_SETFL, flags) != 0) return false;
    return true;
}
bool SendTcp(const std::string& data) {
    size_t off = 0;
    while (off < data.size()) {
        if (!WaitFd(tcp, POLLOUT, 4000)) return false;
        int n = -1;
#ifdef GENPLUS_NETPLAY_TLS
        n = netplay_tls::Send(data.data() + off, data.size() - off);
        if (n == -2 || n == -3) continue;
#else
        n = static_cast<int>(send(tcp, data.data() + off, data.size() - off, 0));
        if (n < 0 && errno == EINTR) continue;
#endif
        if (n <= 0) return false;
        off += static_cast<size_t>(n);
    }
    return true;
}
bool ReadTcpLine(std::string& out, int timeout_ms) {
    const int step = 250;
    int elapsed = 0;
    while (elapsed < timeout_ms) {
        size_t end = buffered.find('\n');
        if (end != std::string::npos) {
            out = buffered.substr(0, end);
            buffered.erase(0, end + 1);
            return out.size() <= 140;
        }
        if (buffered.size() > 140) return false;
        bool ready = false;
#ifdef GENPLUS_NETPLAY_TLS
        ready = netplay_tls::Pending();
#endif
        if (!ready) {
            if (!WaitFd(tcp, POLLIN, step)) {
                elapsed += step;
                continue;
            }
        }
        char data[160];
        int n = -1;
#ifdef GENPLUS_NETPLAY_TLS
        n = netplay_tls::Recv(data, sizeof(data));
        if (n == -2 || n == -3) {
            elapsed += step;
            continue;
        }
#else
        n = static_cast<int>(recv(tcp, data, sizeof(data), 0));
        if (n < 0 && errno == EINTR) continue;
#endif
        if (n <= 0) return false;
        buffered.append(data, static_cast<size_t>(n));
    }
    return false;
}
bool RoomValid(const std::string& room) {
    if (room.size() < 16 || room.size() > 32) return false;
    for (char c : room)
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
              (c >= 'a' && c <= 'z'))) return false;
    return true;
}
bool TokenValid(const char* s) {
    if (strlen(s) != 32) return false;
    for (int i=0; i<32; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return false;
    return true;
}
} // namespace

bool Run(const Config& cfg, std::string& result) {
    Cleanup();
    auto fail = [&](const char* why) {
        result = why;
        Cleanup();
        return false;
    };
    if (cfg.role != 1 && cfg.role != 2) return fail("Choose Host or Join first.");
    if (!RoomValid(cfg.room)) return fail("Use a 16-32 character alphanumeric probe room.");
    if (cfg.host.empty() || cfg.tcp_port < 1 || cfg.tcp_port > 65535 ||
        cfg.udp_port < 1 || cfg.udp_port > 65535)
        return fail("Set a valid rendezvous DNS hostname and ports.");
#ifndef GENPLUS_NETPLAY_TLS
    // CI host tests alone can use localhost, never remote plaintext signaling.
    if (cfg.host != "127.0.0.1" && cfg.host != "localhost")
        return fail("GN2 TLS is required outside localhost.");
#endif
    sockaddr_in tcp_server{};
    sockaddr_in udp_server{};
    if (!Resolve(cfg.host, cfg.tcp_port, SOCK_STREAM, tcp_server) ||
        !Resolve(cfg.host, cfg.udp_port, SOCK_DGRAM, udp_server))
        return fail("Cannot resolve the GN2 rendezvous hostname.");
    if (!ConnectTcp(tcp_server)) return fail("Could not connect to GN2 rendezvous TCP.");
#ifdef GENPLUS_NETPLAY_TLS
    if (!netplay_tls::Start(tcp, cfg.host, result)) {
        Cleanup();
        return false;
    }
#endif
    // Fixed diagnostic fingerprint. This probes a path only; the real game's
    // ROM/config hashes must be validated again by the encrypted game transport.
    const std::string hello = "GN2 " + std::string(cfg.role == 1 ? "HOST" : "JOIN") +
        " " + cfg.room + " 0000000000000000 0000000000000000\n";
    if (!SendTcp(hello)) return fail("GN2 TLS request could not be sent.");
    std::string line;
    if (!ReadTcpLine(line, 10000)) return fail("GN2 did not issue a probe token.");
    char my_token[33] = {};
    int port = 0; char extra = 0;
    if (sscanf(line.c_str(), "TOKEN %32s %d %c", my_token, &port, &extra) != 2 ||
        !TokenValid(my_token) || port != cfg.udp_port)
        return fail(("GN2 rendezvous error: " + line).c_str());

    udp = socket(AF_INET, SOCK_DGRAM, 0);
    if (udp < 0) return fail("Cannot open PS5 UDP socket.");
    sockaddr_in bind_addr{};
    bind_addr.sin_family = AF_INET;
    bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    bind_addr.sin_port = 0;
    if (bind(udp, reinterpret_cast<sockaddr*>(&bind_addr), sizeof(bind_addr)) != 0)
        return fail("Cannot bind PS5 UDP socket.");
    const std::string reg = std::string("GN2 REG ") + my_token + "\n";
    bool observed = false;
    for (int retry=0; retry<7; ++retry) {
        if (sendto(udp, reg.data(), reg.size(), 0, reinterpret_cast<sockaddr*>(&udp_server),
                   sizeof(udp_server)) < 0)
            return fail("Unable to send UDP registration.");
        if (WaitFd(udp, POLLIN, 1000)) {
            char ack[48] = {};
            sockaddr_in from{}; socklen_t flen = sizeof(from);
            int n = static_cast<int>(recvfrom(udp, ack, sizeof(ack), 0,
                                              reinterpret_cast<sockaddr*>(&from), &flen));
            if (n == 7 && memcmp(ack, "GN2 OK\n", 7) == 0 &&
                from.sin_addr.s_addr == udp_server.sin_addr.s_addr &&
                from.sin_port == udp_server.sin_port) {
                observed = true; break;
            }
        }
    }
    if (!observed) return fail("UDP mapping could not reach rendezvous server.");
    if (!ReadTcpLine(line, 80000)) return fail("Timed out waiting for second PS5 UDP registration.");

    char peer_ip[64] = {}, peer_token[33] = {};
    unsigned peer_port = 0;
    if (sscanf(line.c_str(), "PEER %63s %u %32s %c",
               peer_ip, &peer_port, peer_token, &extra) != 3 ||
        peer_port < 1 || peer_port > 65535 || !TokenValid(peer_token))
        return fail(("GN2 peer discovery: " + line).c_str());
    sockaddr_in other{};
    other.sin_family = AF_INET;
    other.sin_port = htons(static_cast<uint16_t>(peer_port));
    if (inet_pton(AF_INET, peer_ip, &other.sin_addr) != 1)
        return fail("Peer address was not IPv4.");

    const std::string punch = std::string("GN2 PUNCH ") + my_token + "\n";
    const std::string expected = std::string("GN2 PUNCH ") + peer_token + "\n";
    for (int attempt=0; attempt<35; ++attempt) {
        sendto(udp, punch.data(), punch.size(), 0, reinterpret_cast<sockaddr*>(&other),
               sizeof(other));
        if (WaitFd(udp, POLLIN, 200)) {
            char in[128] = {};
            sockaddr_in from{}; socklen_t flen = sizeof(from);
            int n = static_cast<int>(recvfrom(udp, in, sizeof(in), 0,
                                              reinterpret_cast<sockaddr*>(&from), &flen));
            if (n == static_cast<int>(expected.size()) &&
                memcmp(in, expected.data(), expected.size()) == 0 &&
                from.sin_addr.s_addr == other.sin_addr.s_addr &&
                from.sin_port == other.sin_port) {
                result = "Direct UDP route reached the other PS5! Probe only; encrypted netplay is not enabled yet.";
                Cleanup();
                return true;
            }
        }
    }
    return fail("No direct UDP path detected. Internet game support will need relay fallback.");
}
} // namespace netplay_probe
