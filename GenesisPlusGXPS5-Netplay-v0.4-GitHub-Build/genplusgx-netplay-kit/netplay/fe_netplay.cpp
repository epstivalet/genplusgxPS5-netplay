// PS5 / POSIX TCP transport for the GN1 TLS relay and experimental direct P2P.
// SPDX-License-Identifier: MIT
#include "fe_netplay.h"
#ifdef GENPLUS_NETPLAY_TLS
#include "fe_netplay_tls.h"
#endif
#include <arpa/inet.h>
#include <cerrno>
#include <deque>
#include <fcntl.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

namespace netplay {
namespace {
int fd = -1;
int role = 0;
int delay = 6;
std::string buffer;
bool direct = false;
struct Packet { uint64_t frame; uint16_t buttons; uint64_t digest; };
std::deque<Packet> sent_frames;

bool Wait(short events, int ms) {
    pollfd p{}; p.fd = fd; p.events = events;
    while (true) {
        int n = poll(&p, 1, ms);
        if (n < 0 && errno == EINTR) continue;
        return n > 0 && (p.revents & events) && !(p.revents & (POLLERR | POLLHUP | POLLNVAL));
    }
}
bool WriteAll(const std::string& s, std::string& err) {
    size_t off = 0;
    while (off < s.size()) {
        ssize_t n = 0;
#ifdef GENPLUS_NETPLAY_TLS
        if (!direct) {
            n = netplay_tls::Send(s.data() + off, s.size() - off);
            if (n == -2 || n == -3) {
                if (!Wait(n == -2 ? POLLOUT : POLLIN, 3000)) { err = "TLS write timeout"; return false; }
                continue;
            }
        } else
#endif
        {
            if (!Wait(POLLOUT, 3000)) { err = "peer send timeout"; return false; }
            n = send(fd, s.data() + off, s.size() - off, MSG_NOSIGNAL);
        }
        if (n <= 0) { if (n < 0 && errno == EINTR) continue; err = "relay send failed"; return false; }
        off += (size_t)n;
    }
    return true;
}
bool ReadLine(std::string& out, int timeout_ms, std::string& err) {
    // newline-framed ASCII protocol, bounded memory use
    for (;;) {
        size_t pos = buffer.find('\n');
        if (pos != std::string::npos) {
            out = buffer.substr(0, pos);
            buffer.erase(0, pos + 1);
            return true;
        }
        if (buffer.size() > 160) { err = "oversized relay reply"; return false; }
#ifdef GENPLUS_NETPLAY_TLS
        if ((direct || !netplay_tls::Pending()) && !Wait(POLLIN, timeout_ms)) {
            err = "peer read timeout or disconnected"; return false;
        }
#else
        if (!Wait(POLLIN, timeout_ms)) { err = "peer read timeout or disconnected"; return false; }
#endif
        char chunk[160];
        ssize_t n = 0;
#ifdef GENPLUS_NETPLAY_TLS
        if (!direct) {
            n = netplay_tls::Recv(chunk, sizeof(chunk));
            if (n == -2 || n == -3) {
                if (!Wait(n == -2 ? POLLOUT : POLLIN, timeout_ms)) { err = "TLS read timeout"; return false; }
                continue;
            }
        } else
#endif
        {
            n = recv(fd, chunk, sizeof(chunk), 0);
        }
        if (n <= 0) { if (n < 0 && errno == EINTR) continue; err = "relay disconnected"; return false; }
        buffer.append(chunk, (size_t)n);
    }
}
bool Connect(const std::string& host, int port, int timeout_ms, std::string& err) {
    addrinfo hints{}; hints.ai_family = AF_INET; hints.ai_socktype = SOCK_STREAM;
    addrinfo* results = nullptr;
    char service[10]; snprintf(service, sizeof(service), "%d", port);
    if (getaddrinfo(host.c_str(), service, &hints, &results) != 0) {
        err = "cannot resolve relay address"; return false;
    }
    for (auto* p = results; p; p = p->ai_next) {
        int candidate = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (candidate < 0) continue;
        timeval tv{}; tv.tv_sec = 5;
        setsockopt(candidate, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
        setsockopt(candidate, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        int one = 1;
        setsockopt(candidate, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
#ifdef SO_NOSIGPIPE
        setsockopt(candidate, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one));
#endif
        // Nonblocking connect with a bounded timeout, especially important when
        // automatic mode probes an unreachable peer before falling back.
        const int flags = fcntl(candidate, F_GETFL, 0);
        if (flags < 0 || fcntl(candidate, F_SETFL, flags | O_NONBLOCK) != 0) {
            close(candidate); continue;
        }
        int rc = connect(candidate, p->ai_addr, p->ai_addrlen);
        if (rc != 0 && errno == EINPROGRESS) {
            pollfd q{}; q.fd = candidate; q.events = POLLOUT;
            do { rc = poll(&q, 1, timeout_ms); } while (rc < 0 && errno == EINTR);
            if (rc > 0) {
                int socket_error = 0; socklen_t n = sizeof(socket_error);
                rc = getsockopt(candidate, SOL_SOCKET, SO_ERROR, &socket_error, &n) == 0 && socket_error == 0 ? 0 : -1;
            } else rc = -1;
        }
        if (rc == 0 && fcntl(candidate, F_SETFL, flags) == 0) { fd = candidate; break; }
        close(candidate);
    }
    freeaddrinfo(results);
    if (fd < 0) { err = "could not connect to relay"; return false; }
    return true;
}
std::string Hex64(uint64_t x) {
    char b[20]; snprintf(b, sizeof(b), "%016llx", (unsigned long long)x); return b;
}
// Only the host listens. The port forwarded by a router is this gameplay port,
// NEVER the PS5 jailbreak loader/helper port. Timeout keeps the menu responsive.
bool Listen(int port, int timeout_ms, std::string& err) {
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) { err = "cannot create direct host socket"; return false; }
    int yes = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    sockaddr_in a{}; a.sin_family = AF_INET; a.sin_addr.s_addr = htonl(INADDR_ANY);
    a.sin_port = htons(static_cast<uint16_t>(port));
    if (bind(listener, reinterpret_cast<sockaddr*>(&a), sizeof(a)) != 0 || listen(listener, 1) != 0) {
        err = "cannot bind direct host port (already in use?)";
        close(listener); return false;
    }
    pollfd p{}; p.fd = listener; p.events = POLLIN;
    int n;
    do { n = poll(&p, 1, timeout_ms); } while (n < 0 && errno == EINTR);
    if (n > 0 && (p.revents & POLLIN)) fd = accept(listener, nullptr, nullptr);
    close(listener);
    if (fd < 0) { err = "direct host timed out or cannot accept peer"; return false; }
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
#ifdef SO_NOSIGPIPE
    setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &yes, sizeof(yes));
#endif
    return true;
}

bool ParseFrame(const std::string& s, Packet& p) {
    unsigned long long f=0, d=0;
    unsigned b=0; char extra=0;
    if (sscanf(s.c_str(), "FRAME %llu %4x %16llx %c", &f, &b, &d, &extra) != 3)
        return false;
    p.frame=static_cast<uint64_t>(f); p.buttons=static_cast<uint16_t>(b);
    p.digest=static_cast<uint64_t>(d);
    return true;
}
} // namespace

bool Active() { return fd >= 0 && role != 0; }
int Role() { return role; }
const char* TransportName() { return Active() ? (direct ? "direct" : "relay") : "offline"; }
void Stop() {
#ifdef GENPLUS_NETPLAY_TLS
    netplay_tls::Stop();
#endif
    if (fd >= 0 && direct && role == 1) {
        // The guest pipelined `delay` FRAME records ahead. Closing with unread
        // TCP data can send RST and discard the host's final PAIR. Half-close,
        // briefly drain, then release; never hold the PS5 UI indefinitely.
        shutdown(fd, SHUT_WR);
        for (int i=0; i<8; ++i) {
            pollfd p{}; p.fd = fd; p.events = POLLIN;
            if (poll(&p, 1, 75) <= 0) break;
            char scratch[512];
            if (recv(fd, scratch, sizeof(scratch), 0) <= 0) break;
        }
    }
    if (fd >= 0) close(fd);
    fd = -1;
    role = 0;
    direct = false;
    buffer.clear();
    sent_frames.clear();
}
bool Start(const Config& cfg, uint64_t game_hash, uint64_t settings_hash, std::string& error) {
    // Auto is a transport choice only: it never changes emulator frame logic.
    // Both peers must choose Auto (or otherwise coordinate their choices).
    // Direct is plaintext and for trusted LAN/VPN only; do not port-forward it.
    if (cfg.connection_type == 2) {
        Config first = cfg;
        first.connection_type = 1;
        first.accept_timeout_ms = 3500;
        first.connect_timeout_ms = 2200;
        std::string direct_error = "direct endpoint not configured";
        const bool can_try_direct = cfg.mode == 1 ||
            (!cfg.host.empty() && cfg.host != "127.0.0.1" && cfg.host != "localhost") ||
            cfg.host == "127.0.0.1" || cfg.host == "localhost";
        if (can_try_direct && Start(first, game_hash, settings_hash, direct_error)) {
            error.clear(); return true;
        }
        // Close the entire attempted direct session before contacting the relay.
        Stop();
        Config relay = cfg;
        relay.connection_type = 0;
        relay.host = cfg.fallback_host;
        relay.port = cfg.fallback_port;
        if (Start(relay, game_hash, settings_hash, error)) {
            error.clear(); return true;
        }
        error = "Auto failed: direct (" + direct_error + "); relay (" + error + ")";
        return false;
    }
    Stop();
    if (cfg.mode < 1 || cfg.mode > 2 || cfg.connection_type < 0 || cfg.connection_type > 1) {
        error = "invalid netplay role or connection type"; return false;
    }
    if (cfg.port < 1 || cfg.port > 65535 || cfg.delay < 1 || cfg.delay > 15 || cfg.accept_timeout_ms < 1 || cfg.connect_timeout_ms < 1) {
        error = "invalid port or delay"; return false;
    }
    if (cfg.room.size() < 8 || cfg.room.size() > 32) {
        error = "set an 8-32 character netplay room in genplus-ps5.ini"; return false;
    }
    for (char c: cfg.room)
        if (!(c >= '0' && c <= '9') && !(c >= 'A' && c <= 'Z') && !(c >= 'a' && c <= 'z')) {
            error = "room code must be alphanumeric"; return false;
        }
    direct = cfg.connection_type == 1;
    if (direct && cfg.mode == 2 && cfg.host.empty()) {
        error = "set the direct host IP or hostname"; Stop(); return false;
    }
    // Direct prototype is deliberately not marketed as secure Internet hosting:
    // room handshake and game inputs are plaintext. Test on trusted LAN / VPN.
#ifndef GENPLUS_NETPLAY_TLS
    if (!direct && cfg.host != "127.0.0.1" && cfg.host != "localhost") {
        error = "plaintext GN1 relay builds are restricted to localhost"; Stop(); return false;
    }
#endif
    if (direct && cfg.mode == 1) {
        if (!Listen(cfg.port, cfg.accept_timeout_ms, error)) { Stop(); return false; }
    } else {
        if (!Connect(cfg.host, cfg.port, cfg.connect_timeout_ms, error)) { Stop(); return false; }
    }
#ifdef GENPLUS_NETPLAY_TLS
    if (!direct && !netplay_tls::Start(fd, cfg.host, error)) { Stop(); return false; }
#endif
    role = cfg.mode;
    delay = cfg.delay;
    if (direct) {
        std::string reply;
        if (role == 1) {
            if (!ReadLine(reply, 10000, error)) { Stop(); return false; }
            char code[33] = {}, rom[17] = {}, options[17] = {}, extra=0;
            const int n=sscanf(reply.c_str(), "GN1 JOIN %32s %16s %16s %c", code, rom, options, &extra);
            if (n != 3 || cfg.room != code) {
                error = "peer room code mismatch";
                WriteAll("ERROR room_mismatch\n", error); Stop(); return false;
            }
            if (Hex64(game_hash) != rom || Hex64(settings_hash) != options) {
                error = "peer ROM or settings mismatch";
                WriteAll("ERROR game_or_settings_mismatch\n", error); Stop(); return false;
            }
            if (!WriteAll("READY\n", error)) { Stop(); return false; }
        } else {
            const std::string hello = "GN1 JOIN " + cfg.room + " " + Hex64(game_hash) + " " + Hex64(settings_hash) + "\n";
            if (!WriteAll(hello, error) || !ReadLine(reply, 10000, error)) { Stop(); return false; }
            if (reply != "READY") { error = "direct peer: " + reply; Stop(); return false; }
        }
    } else {
        const std::string hello = "GN1 " + std::string(role == 1 ? "HOST" : "JOIN") + " " + cfg.room + " " +
            Hex64(game_hash) + " " + Hex64(settings_hash) + "\n";
        if (!WriteAll(hello, error)) { Stop(); return false; }
        std::string response;
        if (!ReadLine(response, 10000, error)) { Stop(); return false; }
        if (response == "WAIT") {
            if (!ReadLine(response, 120000, error)) { Stop(); return false; }
        }
        if (response != "READY") {
            error = "relay: " + response;
            Stop(); return false;
        }
    }
    // Prebuffer delay zero-input frames. Both peers follow the same frame numbering.
    for (int f = 0; f < delay; ++f) {
        char line[48]; snprintf(line, sizeof(line), "FRAME %d 0000 0000000000000000\n", f);
        if ((!direct || role == 2) && !WriteAll(line, error)) { Stop(); return false; }
        if (direct && role == 1) sent_frames.push_back(Packet{static_cast<uint64_t>(f), 0, 0});
    }
    return true;
}

bool Step(uint64_t frame, uint16_t local_bits, uint64_t state_digest, uint16_t& host_bits, uint16_t& join_bits, std::string& error) {
    if (!Active()) { error = "netplay not connected"; return false; }
    char line[70];
    snprintf(line, sizeof(line), "FRAME %llu %04x %016llx\n", (unsigned long long)(frame + delay), (unsigned)local_bits,
        (unsigned long long)state_digest);
    if ((!direct || role == 2) && !WriteAll(line, error)) { Stop(); return false; }
    if (direct && role == 1) {
        sent_frames.push_back(Packet{frame + static_cast<uint64_t>(delay), local_bits, state_digest});
        std::string peer_line;
        if (!ReadLine(peer_line, 10000, error)) { Stop(); return false; }
        Packet other{};
        if (!ParseFrame(peer_line, other) || other.frame != frame || sent_frames.empty() || sent_frames.front().frame != frame) {
            error = "malformed or out-of-order direct peer frame"; Stop(); return false;
        }
        const Packet mine = sent_frames.front();
        sent_frames.pop_front();
        if (mine.digest && other.digest && mine.digest != other.digest) {
            std::string ignored;
            WriteAll("ERROR emulator_state_desynchronized\n", ignored);
            error = "emulator state desynchronized"; Stop(); return false;
        }
        host_bits = mine.buttons; join_bits = other.buttons;
        snprintf(line, sizeof(line), "PAIR %llu %04x %04x\n", (unsigned long long)frame,
            (unsigned)host_bits, (unsigned)join_bits);
        if (!WriteAll(line, error)) { Stop(); return false; }
        return true;
    }
    std::string response;
    if (!ReadLine(response, 10000, error)) { Stop(); return false; }
    unsigned long long received = 0;
    unsigned a = 0, b = 0;
    char extra=0;
    if (sscanf(response.c_str(), "PAIR %llu %4x %4x %c", &received, &a, &b, &extra) != 3 ||
        received != frame || a > 65535 || b > 65535) {
        error = "bad or mismatched " + std::string(direct ? "peer" : "relay") + " frame: " + response;
        Stop(); return false;
    }
    host_bits = static_cast<uint16_t>(a); join_bits = static_cast<uint16_t>(b);
    return true;
}
} // namespace netplay
