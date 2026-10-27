#include "mod/BridgeMod.h"
#include "ll/api/mod/RegisterHelper.h"
#include "ll/api/event/EventBus.h"
#include "ll/api/event/world/ServerLevelTickEvent.h"
#include "ll/api/event/client/ClientJoinLevelEvent.h"
#include "ll/api/event/client/ClientExitLevelEvent.h"

namespace cfbridge {
BridgeMod& BridgeMod::getInstance() {
    static BridgeMod instance;
    return instance;
}
bool BridgeMod::load() { return true; }
bool BridgeMod::enable() {
    transport_.start();
    auto& bus = ll::event::EventBus::getInstance();
    tick_ = bus.emplaceListener<ll::event::ServerLevelTickEvent>([this](auto&) { transport_.enqueue("TICK"); });
    join_ = bus.emplaceListener<ll::event::ClientJoinLevelEvent>([this](auto&) { transport_.enqueue("JOIN"); });
    leave_ = bus.emplaceListener<ll::event::ClientExitLevelEvent>([this](auto&) { transport_.enqueue("LEAVE"); });
    if (!tick_ || !join_ || !leave_) {
        disable();
        return false;
    }
    getSelf().getLogger().info("JavaBridge relay enabled; external Java host required");
    return true;
}
bool BridgeMod::disable() {
    auto& bus = ll::event::EventBus::getInstance();
    if (tick_) bus.removeListener(tick_);
    if (join_) bus.removeListener(join_);
    if (leave_) bus.removeListener(leave_);
    tick_.reset(); join_.reset(); leave_.reset();
    transport_.stop();
    return true;
}
}
LL_REGISTER_MOD(cfbridge::BridgeMod, cfbridge::BridgeMod::getInstance());
