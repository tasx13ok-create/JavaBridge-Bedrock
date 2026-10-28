package net.minecraft.resources;

import java.util.Objects;

/**
 * Compatibility identifier value type. No Java Edition registry implementation
 * exists behind this class.
 */
public final class Identifier {
    private final String namespace;
    private final String path;

    private Identifier(String namespace, String path) {
        if (!namespace.matches("[a-z0-9_.-]+") || !path.matches("[a-z0-9_./-]+")) {
            throw new IllegalArgumentException("Invalid identifier");
        }
        this.namespace = namespace;
        this.path = path;
    }
    public static Identifier fromNamespaceAndPath(String namespace, String path) {
        return new Identifier(Objects.requireNonNull(namespace), Objects.requireNonNull(path));
    }
    public static Identifier parse(String input) {
        int separator = input.indexOf(':');
        return separator < 0 ? new Identifier("minecraft", input)
                             : new Identifier(input.substring(0, separator), input.substring(separator + 1));
    }
    public String getNamespace() { return namespace; }
    public String getPath() { return path; }
    @Override public String toString() { return namespace + ":" + path; }
    @Override public boolean equals(Object other) {
        return other instanceof Identifier id && namespace.equals(id.namespace) && path.equals(id.path);
    }
    @Override public int hashCode() { return Objects.hash(namespace, path); }
}
