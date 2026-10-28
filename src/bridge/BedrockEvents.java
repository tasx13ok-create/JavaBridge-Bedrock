package bridge;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/** Experimental event API, NOT Java Edition Minecraft or Fabric API. */
public final class BedrockEvents {
    private static final List<Runnable> TICKS = new CopyOnWriteArrayList<>();
    private static final List<Runnable> JOINS = new CopyOnWriteArrayList<>();
    private static final List<Runnable> LEAVES = new CopyOnWriteArrayList<>();
    private static final List<BlockBreakHandler> BLOCK_BREAKS = new CopyOnWriteArrayList<>();
    public record BlockBreakEvent(int x, int y, int z) {}
    @FunctionalInterface public interface BlockBreakHandler {
        void onBlockBreak(BlockBreakEvent event);
    }
    private BedrockEvents() {}
    public static void onTick(Runnable handler) { TICKS.add(handler); }
    public static void onJoin(Runnable handler) { JOINS.add(handler); }
    public static void onLeave(Runnable handler) { LEAVES.add(handler); }
    public static void onBlockBreak(BlockBreakHandler handler) { BLOCK_BREAKS.add(handler); }
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
    static int dispatchBlockBreak(int x, int y, int z) {
        int count = 0;
        BlockBreakEvent event = new BlockBreakEvent(x, y, z);
        for (BlockBreakHandler listener : BLOCK_BREAKS) {
            try { listener.onBlockBreak(event); count++; }
            catch (Throwable ex) { System.err.println("BREAK_HANDLER_ERROR " + ex); }
        }
        return count;
    }
    static int tickHandlerCount() { return TICKS.size(); }
}
