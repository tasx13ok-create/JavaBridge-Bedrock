package demo;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;

public final class ClientTickDemo implements ClientModInitializer {
    public void onInitializeClient() {
        ClientTickEvents.START_CLIENT_TICK.register(client ->
            System.out.println("CLIENT_START " + client.bridgeTickCount()));
        ClientTickEvents.END_CLIENT_TICK.register(client ->
            System.out.println("CLIENT_END " + client.bridgeTickCount()));
    }
}
