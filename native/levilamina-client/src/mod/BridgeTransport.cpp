#include "mod/BridgeTransport.h"

#include <array>
#include <utility>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <string_view>

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
std::vector<std::string> BridgeTransport::drainLogs() {
    std::lock_guard lock(mutex_);
    std::vector<std::string> result;
    result.reserve(logs_.size());
    while (!logs_.empty()) {
        result.push_back(std::move(logs_.front()));
        logs_.pop_front();
    }
    return result;
}
static int hexDigit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
static bool decodeLog(std::string const& wire, std::string& result) {
    constexpr std::string_view prefix = "ACTION LOG ";
    if (!wire.starts_with(prefix)) return false;
    auto payload = std::string_view(wire).substr(prefix.size());
    if (payload.empty() || payload.size() > 480 || payload.size() % 2) return false;
    result.clear();
    for (std::size_t p = 0; p < payload.size(); p += 2) {
        int hi = hexDigit(payload[p]), lo = hexDigit(payload[p + 1]);
        if (hi < 0 || lo < 0) return false;
        char byte = static_cast<char>((hi << 4) | lo);
        // Avoid injecting control characters into plugin log output.
        if (static_cast<unsigned char>(byte) < 0x20 && byte != '\t') return false;
        result.push_back(byte);
    }
    return true;
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
        if (!sendLine(sock, event)) {
            ++dropped_;
            closeSocket(sock);
            sock = invalidSocket;
            continue;
        }
        bool acknowledged = false;
        // Per event: at most sixteen Java sidecar action messages, then ACK.
        for (int responseCount = 0; responseCount < 17; ++responseCount) {
            std::string line = readLine(sock);
            if (line.starts_with(event + "_OK")) {
                acknowledged = true;
                break;
            }
            std::string message;
            if (!decodeLog(line, message)) break;
            {
                std::lock_guard lock(mutex_);
                if (logs_.size() == 128) ++dropped_;
                else logs_.push_back(std::move(message));
            }
        }
        if (!acknowledged) {
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
