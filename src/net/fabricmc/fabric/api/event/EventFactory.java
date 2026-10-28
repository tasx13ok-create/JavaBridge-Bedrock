package net.fabricmc.fabric.api.event;

import java.lang.reflect.Array;
import java.util.Arrays;
import java.util.Objects;
import java.util.function.Function;

/**
 * Small original JavaBridge subset of Fabric's EventFactory binary API.
 * Phase ordering and event invalidation are not implemented.
 */
public final class EventFactory {
    private EventFactory() {}

    public static <T> Event<T> createArrayBacked(Class<? super T> type,
                                                 Function<T[], T> invokerFactory) {
        Objects.requireNonNull(type);
        Objects.requireNonNull(invokerFactory);
        return new Event<>() {
            @SuppressWarnings("unchecked")
            private final T[] empty = (T[]) Array.newInstance(type, 0);
            private volatile T[] listeners = empty;
            {
                invoker = invokerFactory.apply(empty);
            }
            @Override public synchronized void register(T listener) {
                Objects.requireNonNull(listener);
                T[] copy = Arrays.copyOf(listeners, listeners.length + 1);
                copy[listeners.length] = listener;
                T result = invokerFactory.apply(copy);
                listeners = copy;
                invoker = result;
            }
        };
    }

    public static <T> Event<T> createArrayBacked(Class<T> type, T emptyInvoker,
                                                 Function<T[], T> invokerFactory) {
        Objects.requireNonNull(emptyInvoker);
        return createArrayBacked(type, listeners -> {
            if (listeners.length == 0) return emptyInvoker;
            if (listeners.length == 1) return listeners[0];
            return invokerFactory.apply(listeners);
        });
    }

    public static String getHandlerName(Object handler) {
        return handler.getClass().getName();
    }

    public static boolean isProfilingEnabled() {
        return false;
    }
}
