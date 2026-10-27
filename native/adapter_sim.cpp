// Standalone C++ adapter for testing. Never injects into Minecraft.
#include <iostream>
#include <string>
#include <cstdlib>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "Ws2_32.lib")
using socket_t = SOCKET;
constexpr socket_t BAD_SOCKET = INVALID_SOCKET;
#define CLOSE_SOCKET closesocket
#else
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
using socket_t = int;
constexpr socket_t BAD_SOCKET = -1;
#define CLOSE_SOCKET close
#endif

static bool send_line(socket_t sock, const std::string& line) {
    std::string payload = line + "\n";
    size_t offset = 0;
    while (offset < payload.size()) {
        int wrote = ::send(sock, payload.data() + offset, static_cast<int>(payload.size() - offset), 0);
        if (wrote <= 0) return false;
        offset += static_cast<size_t>(wrote);
    }
    return true;
}
static std::string recv_line(socket_t sock) {
    std::string line;
    while (line.size() < 4096) {
        char ch;
        if (::recv(sock, &ch, 1, 0) <= 0) return "";
        if (ch == '\n') return line;
        if (ch != '\r') line += ch;
    }
    return "";
}
int main(int argc, char* argv[]) {
    if (argc != 3) { std::cerr << "usage: adapter_sim <port> <token>\n"; return 2; }
    int port = std::atoi(argv[1]);
    if (port < 1 || port > 65535) return 2;
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 3;
#endif
    socket_t sock = ::socket(AF_INET, SOCK_STREAM, 0);
    if (sock == BAD_SOCKET) return 3;
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (::connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::cerr << "Cannot connect to JVM runtime\n";
        CLOSE_SOCKET(sock);
        return 4;
    }
    send_line(sock, std::string("HELLO ") + argv[2]);
    std::cout << recv_line(sock) << '\n';
    send_line(sock, "STATUS");
    std::cout << recv_line(sock) << '\n';
    for (int i = 0; i < 3; ++i) {
        send_line(sock, "TICK");
        std::cout << recv_line(sock) << '\n';
    }
    send_line(sock, "STOP");
    std::cout << recv_line(sock) << '\n';
    CLOSE_SOCKET(sock);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
