package net.fabricmc.fabric.api.event;

import net.minecraft.resources.Identifier;

/** Experimental binary-compatible subset of Fabric API's Event<T> registration API. */
public abstract class Event<T> {
    protected volatile T invoker;
    public static final Identifier DEFAULT_PHASE = Identifier.fromNamespaceAndPath("fabric", "default");
    public abstract void register(T listener);
    public void register(Identifier phase, T listener) {
        if (!DEFAULT_PHASE.equals(phase)) throw new UnsupportedOperationException("Event phase ordering is not implemented");
        register(listener);
    }
    public void addPhaseOrdering(Identifier first, Identifier second) {
        if (!first.equals(second)) throw new UnsupportedOperationException("Event phase ordering is not implemented");
    }
    public final T invoker() { return invoker; }
}
