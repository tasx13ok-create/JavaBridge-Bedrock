package bridge;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import net.fabricmc.api.ModInitializer;

/** Direct-JAR JVM experiment. Mod bytecode is not sandboxed; use only trusted JARs. */
public final class Host {
    private record Mod(String id, List<String> mainEntries) {}
    private static final int MAX_METADATA_BYTES = 1024 * 1024;
    private static final List<String> LOADED = new ArrayList<>();
    private static final List<String> SKIPPED = new ArrayList<>();
    private static URLClassLoader runtimeLoader;

    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            System.err.println("usage: java bridge.Host <mods-folder> <port> <local-token> <max-events>");
            System.exit(2);
        }
        Path modsDir = Paths.get(args[0]);
        int port = Integer.parseInt(args[1]);
        String token = args[2];
        int maxEvents = Integer.parseInt(args[3]);
        if (token.length() < 16) throw new IllegalArgumentException("Token must be at least 16 characters");
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Invalid port");
        if (maxEvents < 1 || maxEvents > 1_000_000) throw new IllegalArgumentException("Invalid max events");
        loadMods(modsDir);
        try (ServerSocket server = new ServerSocket()) {
            server.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), port));
            server.setSoTimeout(600000);
            System.out.println("READY port=" + server.getLocalPort() + " loaded=" + LOADED.size() + " skipped=" + SKIPPED.size());
            System.out.flush();
            try (Socket socket = server.accept()) {
                socket.setSoTimeout(600000);
                BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                PrintWriter out = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8), true);
                String hello = in.readLine();
                if (hello == null || !hello.equals("HELLO " + token)) { out.println("ERROR unauthorized"); return; }
                out.println("OK bridge-v0");
                int count = 0;
                String command;
                while ((command = in.readLine()) != null) {
                    if (command.equals("STATUS")) out.println("STATUS loaded=" + LOADED.size() + " skipped=" + SKIPPED.size() + " handlers=" + BedrockEvents.tickHandlerCount());
                    else if (command.equals("JOIN")) dispatch(out, "JOIN", BedrockEvents.dispatchJoin());
                    else if (command.equals("LEAVE")) dispatch(out, "LEAVE", BedrockEvents.dispatchLeave());
                    else if (command.equals("TICK")) {
                        if (++count > maxEvents) { out.println("ERROR event-limit"); break; }
                        dispatch(out, "TICK", BedrockEvents.dispatchTick());
                    } else if (command.equals("STOP")) { out.println("BYE"); break; }
                    else out.println("ERROR unsupported-command");
                }
            }
        } finally {
            if (runtimeLoader != null) runtimeLoader.close();
        }
    }

    /** Emit bounded sidecar actions before the event acknowledgement (protocol v0). */
    private static void dispatch(PrintWriter out, String event, int handlers) {
        for (String action : BedrockActions.drain()) out.println(action);
        out.println(event + "_OK handlers=" + handlers);
    }

    @SuppressWarnings("unchecked")
    private static Mod metadata(Path jar) throws Exception {
        try (ZipFile zip = new ZipFile(jar.toFile())) {
            ZipEntry entry = zip.getEntry("fabric.mod.json");
            if (entry == null) return null;
            if (entry.getSize() > MAX_METADATA_BYTES) throw new IOException("Oversized fabric.mod.json");
            byte[] bytes;
            try (InputStream stream = zip.getInputStream(entry)) { bytes = stream.readNBytes(MAX_METADATA_BYTES + 1); }
            if (bytes.length > MAX_METADATA_BYTES) throw new IOException("Oversized fabric.mod.json");
            Object doc = Json.parse(new String(bytes, StandardCharsets.UTF_8));
            if (!(doc instanceof Map<?, ?> map)) throw new IOException("Metadata is not an object");
            String id = map.containsKey("id") ? String.valueOf(map.get("id")) : jar.getFileName().toString();
            Object mixins = map.get("mixins");
            if (mixins instanceof List<?> list && !list.isEmpty() || mixins instanceof String s && !s.isBlank()) {
                throw new UnsupportedOperationException("Mixins require Java Edition target classes");
            }
            if (mixins instanceof Map<?, ?> mapMixins && !mapMixins.isEmpty()) {
                throw new UnsupportedOperationException("Mixins require Java Edition target classes");
            }
            Object deps = map.get("depends");
            if (deps instanceof Map<?, ?> d) {
                for (Object k : d.keySet()) {
                    if (!Set.of("java", "minecraft", "fabricloader").contains(String.valueOf(k))) {
                        throw new UnsupportedOperationException("Unimplemented dependency: " + k);
                    }
                }
            }
            Object entries = map.get("entrypoints");
            if (!(entries instanceof Map<?, ?> ep)) throw new UnsupportedOperationException("No Fabric entrypoints");
            Object main = ep.get("main");
            if (!(main instanceof List<?> mainList) || mainList.isEmpty()) throw new UnsupportedOperationException("No main entrypoints");
            List<String> names = new ArrayList<>();
            for (Object item : mainList) {
                if (item instanceof String name) names.add(name);
                else if (item instanceof Map<?, ?> e && "default".equals(e.get("adapter")) && e.get("value") instanceof String name) names.add(name);
                else throw new UnsupportedOperationException("Unsupported language adapter or entrypoint");
            }
            return new Mod(id, names);
        }
    }

    private static void loadMods(Path modsDir) throws Exception {
        if (!Files.isDirectory(modsDir)) throw new IllegalArgumentException("Missing mods folder: " + modsDir);
        List<Path> jars;
        try (var paths = Files.list(modsDir)) {
            jars = paths.filter(path -> path.getFileName().toString().endsWith(".jar")).sorted().limit(101).toList();
        }
        if (jars.size() > 100) throw new IllegalArgumentException("Limit is 100 JARs in this proof-of-concept");
        URL[] urls = new URL[jars.size()];
        for (int i = 0; i < jars.size(); i++) urls[i] = jars.get(i).toUri().toURL();
        runtimeLoader = new URLClassLoader(urls, Host.class.getClassLoader());
        URLClassLoader loader = runtimeLoader;
        for (Path jar : jars) {
            try {
                Mod mod = metadata(jar);
                if (mod == null) { SKIPPED.add(jar.getFileName() + " non-fabric-jar"); continue; }
                for (String entry : mod.mainEntries) {
                    Class<?> cls = Class.forName(entry, true, loader);
                    Object instance = cls.getDeclaredConstructor().newInstance();
                    if (!(instance instanceof ModInitializer init)) throw new UnsupportedOperationException("Not a ModInitializer: " + entry);
                    init.onInitialize();
                }
                LOADED.add(mod.id);
                System.out.println("INIT " + mod.id);
            } catch (Throwable err) {
                SKIPPED.add(jar.getFileName() + " " + err.getClass().getSimpleName() + ": " + err.getMessage());
                System.err.println("SKIP " + SKIPPED.get(SKIPPED.size() - 1));
            }
        }
    }
}
