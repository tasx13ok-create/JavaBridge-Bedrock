package bridge;

import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;

/**
 * Experimental Java -> Bedrock command channel. The only supported operation is
 * logging a bounded UTF-8 message; world mutations are deliberately NOT implemented.
 * Runs in the separate Java process. Not a Fabric API replacement.
 */
public final class BedrockActions {
    private static final int MAX_PENDING = 128;
    private static final int MAX_BYTES = 240;
    private static final int MAX_PER_EVENT = 16;
    private static final ArrayDeque<String> PENDING = new ArrayDeque<>();
    private static long dropped;
    private BedrockActions() {}

    /** Request a message to be logged from the Bedrock client event thread. */
    public static synchronized boolean log(String message) {
        if (message == null) return false;
        byte[] bytes = message.getBytes(StandardCharsets.UTF_8);
        if (bytes.length == 0 || bytes.length > MAX_BYTES || PENDING.size() >= MAX_PENDING) {
            dropped++;
            return false;
        }
        StringBuilder hex = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            int b = Byte.toUnsignedInt(value);
            hex.append(Character.forDigit(b >> 4, 16));
            hex.append(Character.forDigit(b & 15, 16));
        }
        PENDING.addLast("ACTION LOG " + hex);
        return true;
    }

    static synchronized List<String> drain() {
        List<String> batch = new ArrayList<>();
        while (batch.size() < MAX_PER_EVENT && !PENDING.isEmpty()) {
            batch.add(PENDING.removeFirst());
        }
        return batch;
    }

    public static synchronized long droppedCount() {
        return dropped;
    }
}
