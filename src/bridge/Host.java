package bridge;

import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;

/** Direct-JAR JVM experiment. Mod bytecode is not sandboxed; use only trusted JARs. */
public final class Host {
    private record Mod(String id, List<String> mainEntries, Set<String> required) {}
    private record Candidate(Path file, Mod mod) {}
    private static final Set<String> BUILTIN_DEPENDENCIES = Set.of(
        "java", "minecraft", "fabricloader", "fabric-lifecycle-events-v1",
        "fabric-api", "fabric-api-base"
    );
    private static final int MAX_METADATA_BYTES = 1024 * 1024;
    private static final List<String> LOADED = new ArrayList<>();
    private static final List<String> SKIPPED = new ArrayList<>();
    private static URLClassLoader runtimeLoader;
    private static final List<Path> extractedJars = new ArrayList<>();
    private static Path nestedDir;
    private static long totalNestedBytes;

    public static void main(String[] args) throws Exception {
        if (args.length != 4 && args.length != 5) {
            System.err.println("usage: java bridge.Host <mods-folder> <port> <local-token> <max-events> [approved-hashes.tsv]");
            System.exit(2);
        }
        Path modsDir = Paths.get(args[0]);
        int port = Integer.parseInt(args[1]);
        String token = args[2];
        int maxEvents = Integer.parseInt(args[3]);
        if (token.length() < 16) throw new IllegalArgumentException("Token must be at least 16 characters");
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Invalid port");
        if (maxEvents < 1 || maxEvents > 1_000_000) throw new IllegalArgumentException("Invalid max events");
        if (args.length == 4) {
            System.err.println("WARNING: no approval file; run only known demo JARs");
        }
        loadMods(modsDir, args.length == 5 ? Paths.get(args[4]) : null);
        try (ServerSocket server = new ServerSocket()) {
            server.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), port));
            server.setSoTimeout(600000);
            System.out.println("READY port=" + server.getLocalPort() + " loaded=" + LOADED.size() + " skipped=" + SKIPPED.size());
            System.out.flush();
            try (Socket socket = server.accept()) {
                socket.setSoTimeout(600000);
                BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                PrintWriter out = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8), true);
                String hello = readBoundedLine(in, 512);
                if (hello == null || !hello.equals("HELLO " + token)) { out.println("ERROR unauthorized"); return; }
                out.println("OK bridge-v0");
                int count = 0;
                String command;
                while ((command = readBoundedLine(in, 256)) != null) {
                    if (command.equals("STATUS")) out.println("STATUS loaded=" + LOADED.size() + " skipped=" + SKIPPED.size() + " handlers=" + BedrockEvents.tickHandlerCount());
                    else if (command.equals("JOIN")) dispatch(out, "JOIN", BedrockEvents.dispatchJoin());
                    else if (command.equals("LEAVE")) dispatch(out, "LEAVE", BedrockEvents.dispatchLeave());
                    else if (command.equals("TICK")) {
                        if (++count > maxEvents) { out.println("ERROR event-limit"); break; }
                        dispatch(out, "TICK", BedrockEvents.dispatchTick() + ServerTickEvents.fire());
                    } else if (command.equals("STOP")) { out.println("BYE"); break; }
                    else out.println("ERROR unsupported-command");
                }
            }
        } finally {
            try { if (runtimeLoader != null) runtimeLoader.close(); }
            finally {
                for (Path file : extractedJars) Files.deleteIfExists(file);
                if (nestedDir != null) Files.deleteIfExists(nestedDir);
            }
        }
    }

    /** Refuse unbounded text from the local client before allocating large strings. */
    private static String readBoundedLine(BufferedReader input, int limit) throws IOException {
        StringBuilder line = new StringBuilder(Math.min(limit, 128));
        int value;
        while ((value = input.read()) >= 0) {
            if (value == '\n') return line.toString();
            if (value == '\r') continue;
            if (line.length() >= limit) throw new IOException("IPC command line exceeds limit");
            if (value < 32) throw new IOException("Unexpected control character in IPC");
            line.append((char) value);
        }
        return line.isEmpty() ? null : line.toString();
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
            Set<String> required = new LinkedHashSet<>();
            Object deps = map.get("depends");
            if (deps instanceof Map<?, ?> d) {
                for (Object key : d.keySet()) {
                    String name = String.valueOf(key);
                    if (!BUILTIN_DEPENDENCIES.contains(name)) required.add(name);
                }
            } else if (deps != null) {
                throw new UnsupportedOperationException("Non-object dependency metadata");
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
            return new Mod(id, names, required);
        }
    }

    private static void skip(Path file, String reason) {
        String description = file.getFileName() + " " + reason;
        SKIPPED.add(description);
        System.err.println("SKIP " + description);
    }

    /**
     * Resolve declared Java mod dependencies before any initializer executes.
     * This only checks IDs; it does not implement Fabric version-range resolution.
     */
    /**
     * Include Fabric's explicitly declared Jar-in-Jar dependencies on the JVM
     * classpath, using arbitrary temp filenames rather than untrusted ZIP paths.
     */
    private static void includeNested(Path jar, List<URL> urls) throws Exception {
        try (ZipFile archive = new ZipFile(jar.toFile())) {
            ZipEntry entry = archive.getEntry("fabric.mod.json");
            if (entry == null || entry.getSize() > MAX_METADATA_BYTES) return;
            byte[] bytes;
            try (InputStream in = archive.getInputStream(entry)) { bytes = in.readNBytes(MAX_METADATA_BYTES + 1); }
            if (bytes.length > MAX_METADATA_BYTES) return;
            Object obj = Json.parse(new String(bytes, StandardCharsets.UTF_8));
            if (!(obj instanceof Map<?, ?> map) || !(map.get("jars") instanceof List<?> nested)) return;
            for (Object declaration : nested) {
                if (!(declaration instanceof Map<?, ?> d) || !(d.get("file") instanceof String name))
                    throw new IOException("Invalid Fabric nested JAR declaration");
                final String prefix = "META-INF/jars/";
                if (!name.startsWith(prefix) || !name.endsWith(".jar")
                    || name.substring(prefix.length()).contains("/") || name.contains("..")
                    || name.contains("\\"))
                    throw new IOException("Unsafe nested JAR entry name");
                if (extractedJars.size() >= 32) throw new IOException("Too many nested JARs");
                ZipEntry dependency = archive.getEntry(name);
                if (dependency == null || dependency.isDirectory() || dependency.getSize() > 16 * 1024 * 1024)
                    throw new IOException("Nested JAR missing or oversized: " + name);
                byte[] data;
                try (InputStream in = archive.getInputStream(dependency)) {
                    data = in.readNBytes(16 * 1024 * 1024 + 1);
                }
                if (data.length > 16 * 1024 * 1024 || totalNestedBytes + data.length > 32L * 1024 * 1024)
                    throw new IOException("Nested JAR extraction size exceeded");
                if (nestedDir == null) nestedDir = Files.createTempDirectory("java-bridge-jij-");
                Path destination = nestedDir.resolve("nested-" + extractedJars.size() + ".jar");
                Files.write(destination, data, StandardOpenOption.CREATE_NEW);
                extractedJars.add(destination);
                totalNestedBytes += data.length;
                urls.add(destination.toUri().toURL());
                System.out.println("NESTED_JAR " + jar.getFileName() + " " + name);
            }
        }
    }

    /** Approve only exact downloaded bytes, before they reach the JVM classpath. */
    private static List<Path> verifiedJars(List<Path> jars, Path trustFile) throws Exception {
        if (!Files.isRegularFile(trustFile)) throw new IOException("Approval file missing: " + trustFile);
        Map<String, String> approved = new LinkedHashMap<>();
        List<String> lines = Files.readAllLines(trustFile, StandardCharsets.UTF_8);
        if (lines.size() > 1000) throw new IOException("Approval file too large");
        for (String line : lines) {
            if (line.isBlank() || line.startsWith("#")) continue;
            String[] pair = line.split("\\t", -1);
            if (pair.length != 2 || !pair[0].matches("[0-9a-f]{64}")
                    || pair[1].isBlank() || pair[1].contains("/") || pair[1].contains("\\\\")
                    || pair[1].contains("..")) {
                throw new IOException("Invalid mod approval entry");
            }
            if (approved.putIfAbsent(pair[1], pair[0]) != null)
                throw new IOException("Duplicate approval entry");
        }
        List<Path> result = new ArrayList<>();
        for (Path jar : jars) {
            String name = jar.getFileName().toString();
            String expected = approved.get(name);
            if (expected == null) {
                skip(jar, "not approved for execution");
                continue;
            }
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            try (InputStream in = Files.newInputStream(jar)) {
                byte[] block = new byte[64 * 1024];
                for (int size; (size = in.read(block)) >= 0;) {
                    if (size > 0) sha.update(block, 0, size);
                }
            }
            StringBuilder actual = new StringBuilder(64);
            for (byte b : sha.digest()) actual.append(String.format("%02x", b & 0xff));
            if (!actual.toString().equals(expected)) {
                skip(jar, "SHA-256 approval mismatch");
                continue;
            }
            result.add(jar);
        }
        return result;
    }

    private static void loadMods(Path modsDir, Path trustFile) throws Exception {
        if (!Files.isDirectory(modsDir)) throw new IllegalArgumentException("Missing mods folder: " + modsDir);
        FabricLoader.bridgeConfigure(modsDir);
        List<Path> jars;
        try (var paths = Files.list(modsDir)) {
            jars = paths.filter(path -> path.getFileName().toString().endsWith(".jar")).sorted().limit(101).toList();
        }
        if (jars.size() > 100) throw new IllegalArgumentException("Limit is 100 JARs in this proof-of-concept");
        if (trustFile != null) jars = verifiedJars(jars, trustFile);
        List<URL> urls = new ArrayList<>();
        for (Path jar : jars) {
            urls.add(jar.toUri().toURL());
            try { includeNested(jar, urls); }
            catch (Exception error) {
                System.err.println("NESTED_JAR_WARNING " + jar.getFileName() + ": " + error.getMessage());
            }
        }
        runtimeLoader = new URLClassLoader(urls.toArray(URL[]::new), Host.class.getClassLoader());
        URLClassLoader loader = runtimeLoader;

        Map<String, Candidate> pending = new LinkedHashMap<>();
        for (Path jar : jars) {
            try {
                Mod mod = metadata(jar);
                if (mod == null) {
                    skip(jar, "non-fabric-jar");
                } else if (!mod.id.matches("[a-z][a-z0-9_.-]{0,63}")) {
                    skip(jar, "invalid mod ID: " + mod.id);
                } else if (pending.containsKey(mod.id)) {
                    skip(jar, "duplicate mod ID: " + mod.id);
                } else {
                    pending.put(mod.id, new Candidate(jar, mod));
                }
            } catch (Throwable err) {
                skip(jar, err.getClass().getSimpleName() + ": " + err.getMessage());
            }
        }
        Set<String> initialized = new HashSet<>();
        while (!pending.isEmpty()) {
            boolean progressed = false;
            Iterator<Map.Entry<String, Candidate>> it = pending.entrySet().iterator();
            while (it.hasNext()) {
                Candidate candidate = it.next().getValue();
                Mod mod = candidate.mod;
                String missing = null;
                boolean waiting = false;
                for (String dependency : mod.required) {
                    if (initialized.contains(dependency)) continue;
                    if (pending.containsKey(dependency)) waiting = true;
                    else { missing = dependency; break; }
                }
                if (missing != null) {
                    skip(candidate.file, "unsatisfied dependency: " + missing);
                    it.remove();
                    progressed = true;
                } else if (!waiting) {
                    // Register the mod while its initializer runs, then undo on failure.
                    FabricLoader.bridgeRegister(mod.id);
                    try {
                        for (String entry : mod.mainEntries) {
                            Class<?> cls = Class.forName(entry, true, loader);
                            Object instance = cls.getDeclaredConstructor().newInstance();
                            if (!(instance instanceof ModInitializer init)) {
                                throw new UnsupportedOperationException("Not a ModInitializer: " + entry);
                            }
                            init.onInitialize();
                        }
                        initialized.add(mod.id);
                        LOADED.add(mod.id);
                        System.out.println("INIT " + mod.id);
                    } catch (Throwable err) {
                        FabricLoader.bridgeForget(mod.id);
                        skip(candidate.file, "initializer failed: " + err.getClass().getSimpleName() + ": " + err.getMessage());
                    }
                    it.remove();
                    progressed = true;
                }
            }
            if (!progressed) {
                // All remaining candidates have a dependency cycle.
                for (Candidate candidate : pending.values()) {
                    skip(candidate.file, "cyclic dependencies: " + candidate.mod.required);
                }
                pending.clear();
            }
        }
    }
}
