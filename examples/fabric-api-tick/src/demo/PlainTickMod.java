package demo;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;

/**
 * This demo JAR imports ordinary Fabric API namespaces, not bridge.* symbols.
 * It demonstrates one compatible callback ABI, NOT a real Java server.
 */
public final class PlainTickMod implements ModInitializer {
    @Override public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(server ->
            System.out.println("FABRIC_API_TICK " + server.getTickCount())
        );
        System.out.println("FABRIC_API_LISTENER_REGISTERED");
    }
}
