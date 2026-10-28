#include "mod/BridgeTransport.h"
#include <chrono>
#include <iostream>
#include <thread>

int main() {
    cfbridge::BridgeTransport transport;
    transport.start();
    std::this_thread::sleep_for(std::chrono::milliseconds(150));
    transport.enqueue("JOIN");
    transport.enqueue("TICK");
    transport.enqueueBlockBreak(10, 64, -7);
    transport.enqueue("LEAVE");
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    auto logs = transport.drainLogs();
    auto chats = transport.drainChats();
    transport.stop();
    for (auto const& item : logs) std::cout << "LOG_RELAY=" << item << '\n';
    for (auto const& item : chats) std::cout << "CHAT_RELAY=" << item << '\n';
    std::cout << "RELAY_DROPPED=" << transport.dropped() << '\n';
    return transport.dropped() == 0 ? 0 : 1;
}
