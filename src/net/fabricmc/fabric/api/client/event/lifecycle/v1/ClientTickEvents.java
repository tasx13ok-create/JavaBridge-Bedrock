package net.fabricmc.fabric.api.client.event.lifecycle.v1;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import net.fabricmc.fabric.api.event.Event;
import net.minecraft.client.MinecraftClient;

/** Fabric event binary-name subset only; no real Minecraft Java client. */
public final class ClientTickEvents {
    @FunctionalInterface public interface StartTick { void onStartTick(MinecraftClient client); }
    @FunctionalInterface public interface EndTick { void onEndTick(MinecraftClient client); }
    private static final List<StartTick> START = new CopyOnWriteArrayList<>();
    private static final List<EndTick> END = new CopyOnWriteArrayList<>();
    public static final Event<StartTick> START_CLIENT_TICK = new Event<>() {
        @Override public void register(StartTick listener) {
            if (listener == null) throw new IllegalArgumentException("null listener");
            START.add(listener);
            invoker = client -> START.forEach(l -> l.onStartTick(client));
        }
    };
    public static final Event<EndTick> END_CLIENT_TICK = new Event<>() {
        @Override public void register(EndTick listener) {
            if (listener == null) throw new IllegalArgumentException("null listener");
            END.add(listener);
            invoker = client -> END.forEach(l -> l.onEndTick(client));
        }
    };
    private ClientTickEvents() {}
    public static int fire() {
        MinecraftClient client = MinecraftClient.getInstance();
        int count = 0;
        for (StartTick listener : START) {
            try { listener.onStartTick(client); count++; }
            catch (Throwable e) { System.err.println("CLIENT_START_TICK_ERROR " + e); }
        }
        client.bridgeAdvanceTick();
        for (EndTick listener : END) {
            try { listener.onEndTick(client); count++; }
            catch (Throwable e) { System.err.println("CLIENT_END_TICK_ERROR " + e); }
        }
        return count;
    }
}
