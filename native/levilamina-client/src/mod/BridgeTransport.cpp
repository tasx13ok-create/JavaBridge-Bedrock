#include "mod/BridgeTransport.h"

#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "Ws2_32.lib")
using Socket = SOCKET;
static constexpr Socket invalidSocket = INVALID_SOCKET;
static void closeSocket(Socket fd) { closesocket(fd); }
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
using Socket = int;
static constexpr Socket invalidSocket = -1;
static void closeSocket(Socket fd) { ::close(fd); }
#endif

namespace cfbridge {
namespace {
struct Config { int port = 0; std::string token; };

std::filesystem::path sessionPath() {
#ifdef _WIN32
    auto* home = std::getenv("LOCALAPPDATA");
    if (!home) return {};
    return std::filesystem::path(home) / "CFBedrockJavaBridge" / "session.conf";
#else
    auto* home = std::getenv("HOME");
    if (!home) return {};
    return std::filesystem::path(home) / ".config" / "CFBedrockJavaBridge" / "session.conf";
#endif
}
Config readConfig() {
    auto path = sessionPath();
    if (path.empty()) return {};
    std::ifstream in(path);
    Config cfg;
    std::string line;
    if (std::getline(in, line) && line.starts_with("PORT ")) {
        char* end = nullptr;
        auto raw = std::strtol(line.c_str() + 5, &end, 10);
        if (!end || *end != '\0' || raw <= 0 || raw > 65535) return {};
        cfg.port = static_cast<int>(raw);
    }
    if (std::getline(in, line) && line.starts_with("TOKEN ")) {
        cfg.token = line.substr(6);
        if (!cfg.token.empty() && cfg.token.back() == '\r') cfg.token.pop_back();
    }
    if (cfg.port <= 0 || cfg.port > 65535 || cfg.token.size() < 32 || cfg.token.size() > 256) return {};
    return cfg;
}
bool sendLine(Socket socket, std::string const& line) {
    if (line.size() > 1024) return false;
    std::string payload = line + "\n";
    for (std::size_t off = 0; off < payload.size();) {
        int wrote = ::send(socket, payload.data() + off, static_cast<int>(payload.size() - off), 0);
        if (wrote <= 0) return false;
        off += static_cast<std::size_t>(wrote);
    }
    return true;
}
std::string readLine(Socket socket) {
    std::string line;
    while (line.size() < 1024) {
        char c = 0;
        if (::recv(socket, &c, 1, 0) != 1) return {};
        if (c == '\n') return line;
        if (c != '\r') line.push_back(c);
    }
    return {};
}
void setTimeout(Socket sock) {
#ifdef _WIN32
    DWORD ms = 2000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<char*>(&ms), sizeof(ms));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<char*>(&ms), sizeof(ms));
#else
    timeval tv{}; tv.tv_sec = 2;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
}
Socket connectLocal(Config const& cfg) {
    Socket sock = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == invalidSocket) return invalidSocket;
    setTimeout(sock);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<unsigned short>(cfg.port));
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (::connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        closeSocket(sock);
        return invalidSocket;
    }
    if (!sendLine(sock, "HELLO " + cfg.token) || readLine(sock) != "OK bridge-v0") {
        closeSocket(sock);
        return invalidSocket;
    }
    return sock;
}
} // namespace

BridgeTransport::~BridgeTransport() { stop(); }
void BridgeTransport::start() {
    std::lock_guard lock(mutex_);
    if (running_) return;
    running_ = true;
    worker_ = std::thread([this] { run(); });
}
void BridgeTransport::stop() {
    {
        std::lock_guard lock(mutex_);
        if (!running_) return;
        running_ = false;
    }
    cv_.notify_all();
    if (worker_.joinable()) worker_.join();
}
void BridgeTransport::enqueue(char const* event) {
    if (std::string(event) != "TICK" && std::string(event) != "JOIN" && std::string(event) != "LEAVE") return;
    {
        std::lock_guard lock(mutex_);
        if (!running_) return;
        if (queue_.size() >= 128) { dropped_++; return; }
        queue_.emplace_back(event);
    }
    cv_.notify_one();
}
void BridgeTransport::run() {
#ifdef _WIN32
    WSADATA startup{};
    if (WSAStartup(MAKEWORD(2, 2), &startup) != 0) return;
#endif
    Socket sock = invalidSocket;
    while (true) {
        {
            std::unique_lock lock(mutex_);
            if (!running_) break;
        }
        if (sock == invalidSocket) {
            auto cfg = readConfig();
            if (cfg.port) sock = connectLocal(cfg);
            if (sock == invalidSocket) {
                std::unique_lock lock(mutex_);
                cv_.wait_for(lock, std::chrono::seconds(1), [this] { return !running_; });
                continue;
            }
        }
        std::string event;
        {
            std::unique_lock lock(mutex_);
            cv_.wait_for(lock, std::chrono::milliseconds(100), [this] { return !running_ || !queue_.empty(); });
            if (!running_) break;
            if (queue_.empty()) continue;
            event = queue_.front();
            queue_.pop_front();
        }
        if (!sendLine(sock, event) || readLine(sock).find(event + "_OK") != 0) {
            ++dropped_;
            closeSocket(sock);
            sock = invalidSocket;
        }
    }
    if (sock != invalidSocket) closeSocket(sock);
#ifdef _WIN32
    WSACleanup();
#endif
}
}
