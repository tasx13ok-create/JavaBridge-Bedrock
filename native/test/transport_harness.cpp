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
    transport.enqueue("LEAVE");
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    auto logs = transport.drainLogs();
    transport.stop();
    for (auto const& item : logs) std::cout << "LOG_RELAY=" << item << '\n';
    std::cout << "RELAY_DROPPED=" << transport.dropped() << '\n';
    return transport.dropped() == 0 ? 0 : 1;
}
