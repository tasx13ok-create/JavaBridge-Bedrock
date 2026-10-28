#include "mod/BridgeMod.h"
#include "ll/api/mod/RegisterHelper.h"
#include "ll/api/event/EventBus.h"
#include "ll/api/event/world/ServerLevelTickEvent.h"
#include "ll/api/event/client/ClientJoinLevelEvent.h"
#include "ll/api/event/client/ClientExitLevelEvent.h"
#include "ll/api/event/player/PlayerDestroyBlockEvent.h"
#include "mc/world/level/Level.h"
#include "mc/world/actor/player/Player.h"

namespace cfbridge {
BridgeMod& BridgeMod::getInstance() {
    static BridgeMod instance;
    return instance;
}
bool BridgeMod::load() { return true; }
bool BridgeMod::enable() {
    transport_.start();
    auto& bus = ll::event::EventBus::getInstance();
    auto flush = [this] {
        // In-game event callbacks occur on the Bedrock event thread.
        // Worker thread NEVER invokes Bedrock logger or game APIs directly.
        for (auto const& message : transport_.drainLogs())
            getSelf().getLogger().info("JavaBridge Java action: {}", message);
    };
    tick_ = bus.emplaceListener<ll::event::ServerLevelTickEvent>([this, flush](auto& event) {
        transport_.enqueue("TICK");
        flush();
        // Only the Bedrock event thread may interact with Player/Level.
        for (auto const& announcement : transport_.drainChats()) {
            event.level().forEachPlayer([&announcement](Player& player) -> bool {
                player.sendMessage(announcement);
                return true;
            });
        }
    });
    join_ = bus.emplaceListener<ll::event::ClientJoinLevelEvent>([this, flush](auto&) { transport_.enqueue("JOIN"); flush(); });
    leave_ = bus.emplaceListener<ll::event::ClientExitLevelEvent>([this, flush](auto&) { transport_.enqueue("LEAVE"); flush(); });
    break_ = bus.emplaceListener<ll::event::PlayerDestroyBlockEvent>([this](auto& event) {
        auto const& p = event.pos();
        transport_.enqueueBlockBreak(p.x, p.y, p.z);
    });
    if (!tick_ || !join_ || !leave_ || !break_) {
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
    if (break_) bus.removeListener(break_);
    tick_.reset(); join_.reset(); leave_.reset(); break_.reset();
    transport_.stop();
    return true;
}
}
LL_REGISTER_MOD(cfbridge::BridgeMod, cfbridge::BridgeMod::getInstance());
