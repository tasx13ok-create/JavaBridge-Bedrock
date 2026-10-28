package demo;

import net.fabricmc.api.ModInitializer;
import bridge.BedrockEvents;
import bridge.BedrockActions;

/** Demo only: not a third-party CurseForge mod. */
public final class HelloFabric implements ModInitializer {
    private int ticks = 0;
    @Override public void onInitialize() {
        System.out.println("HELLO_FABRIC_INIT direct Java bytecode executed");
        BedrockEvents.onTick(() -> {
            ticks++;
            System.out.println("HELLO_FABRIC_TICK " + ticks);
        });
        BedrockEvents.onJoin(() -> { System.out.println("HELLO_FABRIC_JOIN"); BedrockActions.log("Hello from Java JAR"); });
        BedrockEvents.onLeave(() -> System.out.println("HELLO_FABRIC_LEAVE"));
    }
}
