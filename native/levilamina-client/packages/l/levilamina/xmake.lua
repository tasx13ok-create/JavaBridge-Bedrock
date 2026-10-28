-- Temporary, version-pinned upstream LeviLamina build workaround for 26.51.9.
-- This package recipe is local to JavaBridge, not part of the official SDK.
package("levilamina")
    add_urls("https://github.com/LiteLDev/LeviLamina.git")
    add_versions("26.51.9", "310bf95e173df01bc08a490dbdcb2e8dd0ae1de2")
    add_defines("ENTT_PACKED_PAGE=128", "ENTT_SPARSE_PAGE=4096", "ENTT_NO_MIXIN")
    add_configs("target_type", {default = "client", values = {"server", "client"}})

    on_load(function(package)
        local deps_common = {
            "entt v4.0.0",
            "expected-lite v0.8.0",
            "fmt 11.2.0",
            "gsl v4.2.0",
            "glm 1.0.1",
            "leveldb 1.23",
            "magic_enum v0.9.7",
            "nlohmann_json v3.12.0",
            "rapidjson 2025.02.05",
            "type_safe v0.2.4",
            "pcg_cpp v1.0.0",
            "pfr 2.1.1",
            "symbolprovider v1.3.0",
            "parallel-hashmap v1.3.12",
            "concurrentqueue v1.0.4",
            "stb 2025.03.14"
        }
        for _, dep in ipairs(deps_common) do package:add("deps", dep) end
        if package:config("target_type") == "server" then
            package:add("deps", "bedrockdata v26.51.1-server.12")
            package:add("defines", "LL_PLAT_S")
        else
            package:add("deps", "bedrockdata v26.51.1-client.12")
            package:add("defines", "LL_PLAT_C")
        end
    end)

    on_install(function(package)
        local source = "src/ll/api/event/command/ExecuteCommandEvent.cpp"
        if not os.isfile(source) then source = path.join("levilamina", source) end
        if not os.isfile(source) then
            raise("LeviLamina 26.51.9 expected ExecuteCommandEvent.cpp but it was not found")
        end

        local original = io.readfile(source)
        local anchor = '#include "ll/api/event/command/ExecuteCommandEvent.h"'
        assert(original:find(anchor, 1, true), "Expected LeviLamina source layout changed; refuse patch")

        -- Avoid instantiation of unique_ptr<T> destructors with T incomplete.
        -- Applied to downloaded dependency source in the XMake cache only.
        local extra = [[
#include "mc/server/commands/Command.h"
#include "mc/server/commands/CommandOutputSender.h"
#include "mc/server/commands/CommandRegistry.h"
#include "mc/server/commands/DeferredCommandBase.h"
]]
        local patched = original:gsub(anchor, anchor .. "\n" .. extra, 1)
        io.writefile(source, patched)

        -- Upstream generated BedrockSpawner has an inline destructor, but
        -- its unique_ptr member targets are only forward-declared.
        -- Include definitions in the generated header for this tagged build.
        local spawner = "src/mc/world/level/BedrockSpawner.h"
        if not os.isfile(spawner) then spawner = path.join("levilamina", spawner) end
        assert(os.isfile(spawner), "Expected BedrockSpawner.h missing")
        local header = io.readfile(spawner)
        local include_anchor = '#include "mc/world/level/Spawner.h"'
        assert(header:find(include_anchor, 1, true), "BedrockSpawner include layout changed")
        local includes = [[
#include "mc/world/actor/ActorSpawnRuleGroup.h"
#include "mc/world/actor/registry/SpawnGroupRegistry.h"
#include "mc/world/level/chunk/EntityTypeCache.h"
]]
        io.writefile(spawner, header:gsub(include_anchor, include_anchor .. "\n" .. includes, 1))
        cprint("${bright yellow}Applying JavaBridge temporary upstream compile workaround (26.51.9)${clear}")
        import("package.tools.xmake").install(package, {"--target_type=" .. package:config("target_type")})
    end)
