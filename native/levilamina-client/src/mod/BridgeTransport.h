#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

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
    void enqueueBlockBreak(int x, int y, int z);
    std::size_t dropped() const { return dropped_.load(); }
    /** Drain validated Java LOG actions on the caller (game) thread. */
    std::vector<std::string> drainLogs();
    /** Drain requested player chat announcements from the Java sidecar. */
    std::vector<std::string> drainChats();
private:
    void run();
    void enqueueFrame(std::string event);
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<std::string> queue_;
    std::deque<std::string> logs_;
    std::deque<std::string> chats_;
    std::thread worker_;
    std::atomic<std::size_t> dropped_{0};
    bool running_ = false;
};
}
