package demo;
import net.fabricmc.api.ClientModInitializer;
import bridge.BedrockEvents;
public final class ClientOnlyMod implements ClientModInitializer {
    @Override public void onInitializeClient() {
        System.out.println("CLIENT_ONLY_INITIALIZED");
        BedrockEvents.onTick(() -> System.out.println("CLIENT_ONLY_TICK"));
    }
}
