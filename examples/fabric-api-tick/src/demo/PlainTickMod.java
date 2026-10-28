package demo;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.Event;
import net.fabricmc.fabric.api.event.EventFactory;

/**
 * This demo JAR imports ordinary Fabric API namespaces, not bridge.* symbols.
 * It demonstrates one compatible callback ABI, NOT a real Java server.
 */
public final class PlainTickMod implements ModInitializer {
    @FunctionalInterface public interface Echo { void say(String text); }
    private static final Event<Echo> ECHO = EventFactory.createArrayBacked(
        Echo.class, callbacks -> value -> {
            for (Echo callback : callbacks) callback.say(value);
        });

    @Override public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(server ->
            System.out.println("FABRIC_API_TICK " + server.getTickCount())
        );
        System.out.println("FABRIC_API_LISTENER_REGISTERED");
        ECHO.register(text -> System.out.println("FABRIC_FACTORY_EVENT=" + text));
        ECHO.invoker().say("ok");
        System.out.println("FABRIC_LOADER_SELF=" + FabricLoader.getInstance().isModLoaded("fabric_api_tick_direct"));
        System.out.println("FABRIC_LOADER_WORKSPACE=" + FabricLoader.getInstance().getGameDir().getFileName());
    }
}
