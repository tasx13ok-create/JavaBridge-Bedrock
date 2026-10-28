package net.fabricmc.fabric.api.event;

/** Experimental binary-compatible subset of Fabric API's Event<T> registration API. */
public abstract class Event<T> {
    protected volatile T invoker;
    public abstract void register(T listener);
    public final T invoker() { return invoker; }
}
