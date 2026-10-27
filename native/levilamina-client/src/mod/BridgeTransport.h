#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <string>
#include <thread>

namespace cfbridge {
/** Sends events to Java sidecar; never does network I/O on gameplay callbacks. */
class BridgeTransport {
public:
    BridgeTransport() = default;
    ~BridgeTransport();
    BridgeTransport(BridgeTransport const&) = delete;
    BridgeTransport& operator=(BridgeTransport const&) = delete;
    void start();
    void stop();
    void enqueue(char const* event);
    std::size_t dropped() const { return dropped_.load(); }
private:
    void run();
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<std::string> queue_;
    std::thread worker_;
    std::atomic<std::size_t> dropped_{0};
    bool running_ = false;
};
}
