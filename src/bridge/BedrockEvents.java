package bridge;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/** Experimental event API, NOT Java Edition Minecraft or Fabric API. */
public final class BedrockEvents {
    private static final List<Runnable> TICKS = new CopyOnWriteArrayList<>();
    private static final List<Runnable> JOINS = new CopyOnWriteArrayList<>();
    private static final List<Runnable> LEAVES = new CopyOnWriteArrayList<>();
    private BedrockEvents() {}
    public static void onTick(Runnable handler) { TICKS.add(handler); }
    public static void onJoin(Runnable handler) { JOINS.add(handler); }
    public static void onLeave(Runnable handler) { LEAVES.add(handler); }
    private static int dispatch(List<Runnable> handlers) {
        int successes = 0;
        for (Runnable handler : handlers) {
            try { handler.run(); successes++; }
            catch (Throwable e) { System.err.println("EVENT_HANDLER_ERROR " + e); }
        }
        return successes;
    }
    static int dispatchTick() { return dispatch(TICKS); }
    static int dispatchJoin() { return dispatch(JOINS); }
    static int dispatchLeave() { return dispatch(LEAVES); }
    static int tickHandlerCount() { return TICKS.size(); }
}
