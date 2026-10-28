package net.fabricmc.loader.api;

import java.nio.file.Path;
import java.util.Collections;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import net.fabricmc.api.EnvType;

/**
 * Experimental subset of Fabric Loader's public API, NOT Fabric Loader.
 * Its paths refer to the Java sidecar workspace, never an actual Bedrock world.
 */
public interface FabricLoader {
    FabricLoader INSTANCE = new BridgeInstance();
    static FabricLoader getInstance() { return INSTANCE; }

    Path getGameDir();
    Path getConfigDir();
    boolean isModLoaded(String id);
    boolean isDevelopmentEnvironment();
    EnvType getEnvironmentType();
    String getRawGameVersion();

    /** Internal support for JavaBridge's loader simulation, NOT a Fabric API method. */
    static void bridgeConfigure(Path modsDir) {
        ((BridgeInstance) INSTANCE).configure(modsDir);
    }
    static void bridgeRegister(String id) {
        ((BridgeInstance) INSTANCE).loaded.add(id);
    }
    static void bridgeForget(String id) {
        ((BridgeInstance) INSTANCE).loaded.remove(id);
    }

    final class BridgeInstance implements FabricLoader {
        private volatile Path gameDir = Path.of(".").toAbsolutePath().normalize();
        private final Set<String> loaded = Collections.newSetFromMap(new ConcurrentHashMap<>());
        private void configure(Path mods) {
            Path root = mods.toAbsolutePath().normalize().getParent();
            gameDir = root == null ? Path.of(".").toAbsolutePath().normalize() : root;
            loaded.clear();
        }
        @Override public Path getGameDir() { return gameDir; }
        @Override public Path getConfigDir() { return gameDir.resolve("config"); }
        @Override public boolean isModLoaded(String id) { return loaded.contains(id); }
        @Override public boolean isDevelopmentEnvironment() { return true; }
        @Override public EnvType getEnvironmentType() { return EnvType.CLIENT; }
        @Override public String getRawGameVersion() { return "bedrock-java-bridge-experimental"; }
    }
}
