#pragma once

#include "ll/api/mod/NativeMod.h"
#include "ll/api/event/ListenerBase.h"
#include "mod/BridgeTransport.h"

namespace cfbridge {
class BridgeMod {
public:
    static BridgeMod& getInstance();
    BridgeMod() : self_(*ll::mod::NativeMod::current()) {}
    [[nodiscard]] ll::mod::NativeMod& getSelf() const { return self_; }
    bool load();
    bool enable();
    bool disable();
private:
    ll::mod::NativeMod& self_;
    BridgeTransport transport_;
    ll::event::ListenerPtr tick_;
    ll::event::ListenerPtr join_;
    ll::event::ListenerPtr leave_;
    ll::event::ListenerPtr break_;
};
}
