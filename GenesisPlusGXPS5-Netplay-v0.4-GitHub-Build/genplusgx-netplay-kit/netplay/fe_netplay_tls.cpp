// Native PS5 TLS input transport using the upstream vendored Mbed TLS 3.x.
// Uses Mozilla's CA roots already bundled with the Genesis Plus GX PS5 helper.
// No certificate verification bypass is supported.
// SPDX-License-Identifier: MIT
#include "fe_netplay_tls.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/error.h"
#include "mbedtls/ssl.h"
#include "mbedtls/x509_crt.h"
#include "psa/crypto.h"
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#if defined(__linux__)
#include <sys/random.h>
#else
#include <sys/sysctl.h>
#endif

#define GN1_INCBIN(sym, path) \
  __asm__(".section .rodata\n.global " #sym "_begin\n.balign 16\n" #sym "_begin:\n.incbin \"" path "\"\n.global " #sym "_end\n" #sym "_end:\n.previous\n"); \
  extern "C" const char sym##_begin[]; \
  extern "C" const char sym##_end[];
GN1_INCBIN(gn1_cacert, CACERT_PEM)

// Upstream fe_tlshttp.cpp defines this in the helper binary. The GN1 app
// is a separate executable, therefore it supplies its own hardware entropy.
extern "C" int mbedtls_hardware_poll(void*, unsigned char* output, size_t len, size_t* olen) {
  *olen = 0;
#if defined(__linux__)
  while (*olen < len) {
    ssize_t n = getrandom(output + *olen, len - *olen, 0);
    if (n <= 0) break;
    *olen += static_cast<size_t>(n);
  }
#else
  while (*olen < len) {
    int mib[2] = {CTL_KERN, KERN_ARND};
    size_t n = len - *olen > 256 ? 256 : len - *olen;
    if (sysctl(mib, 2, output + *olen, &n, nullptr, 0) != 0 || n == 0) break;
    *olen += n;
  }
#endif
  if (*olen < len) {
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd >= 0) {
      while (*olen < len) {
        ssize_t n = read(fd, output + *olen, len - *olen);
        if (n <= 0) break;
        *olen += static_cast<size_t>(n);
      }
      close(fd);
    }
  }
  return *olen == len ? 0 : MBEDTLS_ERR_ENTROPY_SOURCE_FAILED;
}

namespace netplay_tls {
namespace {
  struct TlsState {
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context rng;
    mbedtls_x509_crt ca;
    mbedtls_ssl_config cfg;
    mbedtls_ssl_context ssl;
    int fd = -1;
    bool live = false;
    TlsState() {
      mbedtls_entropy_init(&entropy);
      mbedtls_ctr_drbg_init(&rng);
      mbedtls_x509_crt_init(&ca);
      mbedtls_ssl_config_init(&cfg);
      mbedtls_ssl_init(&ssl);
    }
    ~TlsState() {
      mbedtls_ssl_free(&ssl);
      mbedtls_ssl_config_free(&cfg);
      mbedtls_x509_crt_free(&ca);
      mbedtls_ctr_drbg_free(&rng);
      mbedtls_entropy_free(&entropy);
    }
  };
  TlsState* g = nullptr;
  int SendCallback(void* ctx, const unsigned char* buf, size_t n) {
    const int fd = *static_cast<int*>(ctx);
#ifdef MSG_NOSIGNAL
    ssize_t r = send(fd, buf, n, MSG_NOSIGNAL);
#else
    ssize_t r = send(fd, buf, n, 0);
#endif
    if (r >= 0) return static_cast<int>(r);
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR ? MBEDTLS_ERR_SSL_WANT_WRITE : MBEDTLS_ERR_SSL_INTERNAL_ERROR;
  }
  int RecvCallback(void* ctx, unsigned char* buf, size_t n) {
    const int fd = *static_cast<int*>(ctx);
    ssize_t r = recv(fd, buf, n, 0);
    if (r > 0) return static_cast<int>(r);
    if (r == 0) return 0;
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR ? MBEDTLS_ERR_SSL_WANT_READ : MBEDTLS_ERR_SSL_INTERNAL_ERROR;
  }
  bool Poll(int fd, short events, int ms) {
    pollfd p{}; p.fd = fd; p.events = events;
    int r;
    do { r = poll(&p, 1, ms); } while (r < 0 && errno == EINTR);
    return r > 0 && (p.revents & events) != 0 && !(p.revents & (POLLHUP | POLLERR | POLLNVAL));
  }
  std::string Explain(int code) {
    char msg[180] = {};
    mbedtls_strerror(code, msg, sizeof(msg));
    return msg;
  }
}
void Stop() { delete g; g = nullptr; }
bool Start(int fd, const std::string& host, std::string& error) {
  Stop();
  if (fd < 0 || host.empty() || host.size() > 253) { error = "invalid TLS relay hostname"; return false; }
  // SNI/host verification requires a DNS hostname, not an IP literal.
  if (host.find('.') == std::string::npos || host.find(':') != std::string::npos) {
    error = "TLS relay must use a valid public DNS hostname"; return false;
  }
  g = new TlsState();
  g->fd = fd;
  if (psa_crypto_init() != PSA_SUCCESS) { error = "TLS crypto initialization failed"; Stop(); return false; }
  static const unsigned char personal[] = "GenesisPlusGXPS5 GN1";
  int rc = mbedtls_ctr_drbg_seed(&g->rng, mbedtls_entropy_func, &g->entropy, personal, sizeof(personal)-1);
  if (rc != 0) { error = "TLS random seed: " + Explain(rc); Stop(); return false; }
  const size_t n = static_cast<size_t>(gn1_cacert_end - gn1_cacert_begin);
  std::string roots(gn1_cacert_begin, n);
  rc = mbedtls_x509_crt_parse(&g->ca, reinterpret_cast<const unsigned char*>(roots.c_str()), roots.size() + 1);
  if (rc < 0 || !g->ca.raw.len) { error = "TLS CA roots unavailable"; Stop(); return false; }
  rc = mbedtls_ssl_config_defaults(&g->cfg, MBEDTLS_SSL_IS_CLIENT, MBEDTLS_SSL_TRANSPORT_STREAM, MBEDTLS_SSL_PRESET_DEFAULT);
  if (rc != 0) { error = "TLS configuration failed"; Stop(); return false; }
  mbedtls_ssl_conf_authmode(&g->cfg, MBEDTLS_SSL_VERIFY_REQUIRED);
  mbedtls_ssl_conf_ca_chain(&g->cfg, &g->ca, nullptr);
  mbedtls_ssl_conf_rng(&g->cfg, mbedtls_ctr_drbg_random, &g->rng);
  mbedtls_ssl_conf_min_tls_version(&g->cfg, MBEDTLS_SSL_VERSION_TLS1_2);
  rc = mbedtls_ssl_setup(&g->ssl, &g->cfg);
  if (rc == 0) rc = mbedtls_ssl_set_hostname(&g->ssl, host.c_str());
  if (rc != 0) { error = "TLS setup: " + Explain(rc); Stop(); return false; }
  mbedtls_ssl_set_bio(&g->ssl, &g->fd, SendCallback, RecvCallback, nullptr);
  // Bound handshake; avoid leaving a blocking console menu indefinitely.
  timeval short_wait{}; short_wait.tv_usec = 250000;
  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &short_wait, sizeof(short_wait));
  setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &short_wait, sizeof(short_wait));
  for (int attempt=0; attempt<120; ++attempt) {
    rc = mbedtls_ssl_handshake(&g->ssl);
    if (rc == 0) break;
    if (rc == MBEDTLS_ERR_SSL_WANT_READ && Poll(fd, POLLIN, 250)) continue;
    if (rc == MBEDTLS_ERR_SSL_WANT_WRITE && Poll(fd, POLLOUT, 250)) continue;
    if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
    error = "TLS handshake: " + Explain(rc); Stop(); return false;
  }
  if (rc != 0 || mbedtls_ssl_get_verify_result(&g->ssl) != 0) {
    error = "TLS handshake or certificate verification failed"; Stop(); return false;
  }
  g->live = true;
  return true;
}
bool Pending() { return g && g->live && mbedtls_ssl_check_pending(&g->ssl) != 0; }
int Send(const char* data, size_t size) {
  if (!g || !g->live) return -1;
  int rc = mbedtls_ssl_write(&g->ssl, reinterpret_cast<const unsigned char*>(data), size);
  if (rc == MBEDTLS_ERR_SSL_WANT_READ) return -3;
  if (rc == MBEDTLS_ERR_SSL_WANT_WRITE) return -2;
  return rc < 0 ? -1 : rc;
}
int Recv(char* data, size_t size) {
  if (!g || !g->live) return -1;
  int rc = mbedtls_ssl_read(&g->ssl, reinterpret_cast<unsigned char*>(data), size);
  if (rc == MBEDTLS_ERR_SSL_WANT_READ) return -3;
  if (rc == MBEDTLS_ERR_SSL_WANT_WRITE) return -2;
  return rc < 0 ? -1 : rc;
}
} // namespace netplay_tls
