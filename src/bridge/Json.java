package bridge;

import java.util.*;

/** Small strict JSON reader so this proof-of-concept has no Maven dependencies. */
final class Json {
    private final String s;
    private int p;
    private Json(String s) { this.s = s; }
    static Object parse(String json) {
        Json parser = new Json(json);
        Object value = parser.value();
        parser.ws();
        if (parser.p != parser.s.length()) throw new IllegalArgumentException("Trailing JSON content");
        return value;
    }
    private void ws() { while (p < s.length() && Character.isWhitespace(s.charAt(p))) p++; }
    private char next() { if (p >= s.length()) throw new IllegalArgumentException("Unexpected EOF"); return s.charAt(p++); }
    private char peek() { ws(); if (p >= s.length()) throw new IllegalArgumentException("Unexpected EOF"); return s.charAt(p); }
    private void expect(char c) { ws(); if (next() != c) throw new IllegalArgumentException("Expected '" + c + "'"); }
    private Object value() {
        char c = peek();
        if (c == '{') return object();
        if (c == '[') return array();
        if (c == '"') return string();
        if (c == 't' || c == 'f' || c == 'n') return literal();
        if (c == '-' || Character.isDigit(c)) return number();
        throw new IllegalArgumentException("Invalid JSON at " + p);
    }
    private Object object() {
        Map<String, Object> obj = new LinkedHashMap<>(); expect('{');
        if (peek() == '}') { p++; return obj; }
        while (true) {
            if (peek() != '"') throw new IllegalArgumentException("Expected JSON object key");
            String k = string(); expect(':'); obj.put(k, value());
            char c = nextAfterSpace();
            if (c == '}') return obj;
            if (c != ',') throw new IllegalArgumentException("Expected ',' or '}'");
        }
    }
    private Object array() {
        List<Object> array = new ArrayList<>(); expect('[');
        if (peek() == ']') { p++; return array; }
        while (true) {
            array.add(value()); char c = nextAfterSpace();
            if (c == ']') return array;
            if (c != ',') throw new IllegalArgumentException("Expected ',' or ']'");
        }
    }
    private char nextAfterSpace() { ws(); return next(); }
    private String string() {
        expect('"'); StringBuilder out = new StringBuilder();
        while (true) {
            char c = next();
            if (c == '"') return out.toString();
            if (c == '\\') {
                char escaped = next();
                switch (escaped) {
                    case '"' -> out.append('"'); case '\\' -> out.append('\\');
                    case '/' -> out.append('/'); case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f'); case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r'); case 't' -> out.append('\t');
                    case 'u' -> { if (p + 4 > s.length()) throw new IllegalArgumentException("Bad unicode escape");
                        out.append((char)Integer.parseInt(s.substring(p, p + 4), 16)); p += 4; }
                    default -> throw new IllegalArgumentException("Invalid escape");
                }
            } else {
                if (c < 0x20) throw new IllegalArgumentException("Unescaped control character");
                out.append(c);
            }
        }
    }
    private Object literal() {
        for (String token : new String[]{"true", "false", "null"}) {
            if (s.startsWith(token, p)) { p += token.length(); return switch (token) {
                case "true" -> Boolean.TRUE; case "false" -> Boolean.FALSE; default -> null; }; }
        }
        throw new IllegalArgumentException("Invalid literal");
    }
    private Number number() {
        int start = p;
        if (s.charAt(p) == '-') p++;
        if (p >= s.length()) throw new IllegalArgumentException("Invalid number");
        if (s.charAt(p) == '0') p++;
        else {
            if (!Character.isDigit(s.charAt(p))) throw new IllegalArgumentException("Invalid number");
            while (p < s.length() && Character.isDigit(s.charAt(p))) p++;
        }
        if (p < s.length() && s.charAt(p) == '.') {
            p++; if (p >= s.length() || !Character.isDigit(s.charAt(p))) throw new IllegalArgumentException("Invalid decimal");
            while (p < s.length() && Character.isDigit(s.charAt(p))) p++;
        }
        if (p < s.length() && (s.charAt(p) == 'e' || s.charAt(p) == 'E')) {
            p++; if (p < s.length() && (s.charAt(p) == '+' || s.charAt(p) == '-')) p++;
            if (p >= s.length() || !Character.isDigit(s.charAt(p))) throw new IllegalArgumentException("Invalid exponent");
            while (p < s.length() && Character.isDigit(s.charAt(p))) p++;
        }
        return Double.parseDouble(s.substring(start, p));
    }
}
