package net.fabricmc.fabric.api.event.lifecycle.v1;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import net.fabricmc.fabric.api.event.Event;
import net.minecraft.server.MinecraftServer;

/**
 * Minimal Fabric API binary surface, not Fabric API itself.
 * End/start callbacks are dispatched by JavaBridge on native TICK events.
 */
public final class ServerTickEvents {
    @FunctionalInterface public interface StartTick { void onStartTick(MinecraftServer server); }
    @FunctionalInterface public interface EndTick { void onEndTick(MinecraftServer server); }
    private static final List<StartTick> START_LISTENERS = new CopyOnWriteArrayList<>();
    private static final List<EndTick> END_LISTENERS = new CopyOnWriteArrayList<>();
    private static final MinecraftServer FACADE = new MinecraftServer();

    public static final Event<StartTick> START_SERVER_TICK = new Event<>() {
        @Override public void register(StartTick listener) {
            if (listener == null) throw new IllegalArgumentException("null listener");
            START_LISTENERS.add(listener);
            invoker = server -> START_LISTENERS.forEach(l -> l.onStartTick(server));
        }
    };
    public static final Event<EndTick> END_SERVER_TICK = new Event<>() {
        @Override public void register(EndTick listener) {
            if (listener == null) throw new IllegalArgumentException("null listener");
            END_LISTENERS.add(listener);
            invoker = server -> END_LISTENERS.forEach(l -> l.onEndTick(server));
        }
    };

    private ServerTickEvents() {}
    /** Called exactly once per TICK received over the experimental IPC protocol. */
    public static int fire() {
        int invoked = 0;
        for (StartTick listener : START_LISTENERS) {
            try { listener.onStartTick(FACADE); invoked++; }
            catch (Throwable error) { System.err.println("FABRIC_START_TICK_ERROR " + error); }
        }
        FACADE.bridgeAdvanceTick();
        for (EndTick listener : END_LISTENERS) {
            try { listener.onEndTick(FACADE); invoked++; }
            catch (Throwable error) { System.err.println("FABRIC_END_TICK_ERROR " + error); }
        }
        return invoked;
    }
    public static int listenerCount() { return START_LISTENERS.size() + END_LISTENERS.size(); }
}
