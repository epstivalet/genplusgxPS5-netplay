// TLS transport for PS5 Genesis Plus GX GN1. Verify public-CA chain and DNS hostname.
// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>
#include <string>
namespace netplay_tls {
// The fd stays owned by the caller; only the TLS session is cleaned up here.
bool Start(int fd, const std::string& hostname, std::string& error);
int Send(const char* data, std::size_t size); // >=0 bytes, -2 WANT_WRITE, -3 WANT_READ, -1 error
int Recv(char* data, std::size_t size);       // >=0 bytes, -2 WANT_WRITE, -3 WANT_READ, -1 error
bool Pending(); // application data buffered inside Mbed TLS
void Stop();
}
