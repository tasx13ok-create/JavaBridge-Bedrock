package net.minecraft.server;

/**
 * Deliberately narrow facade for tick callback compatibility.
 * NOT the Minecraft Java Edition server. It has no world, players, or registries.
 */
public final class MinecraftServer {
    private int tickCount;
    public int getTickCount() { return tickCount; }
    public void bridgeAdvanceTick() { tickCount++; }
}
