package net.minecraft.client;

/** Tiny JavaBridge tick facade, NOT a real Minecraft Java client. */
public final class MinecraftClient {
    private static final MinecraftClient INSTANCE = new MinecraftClient();
    private int bridgeTicks;
    private MinecraftClient() {}
    public static MinecraftClient getInstance() { return INSTANCE; }
    public int bridgeTickCount() { return bridgeTicks; }
    public void bridgeAdvanceTick() { bridgeTicks++; }
}
