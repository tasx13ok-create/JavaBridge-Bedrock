# JavaBridge-Bedrock (experimental v0.2)

**Goal:** Research how original Java Edition mod `.jar` bytecode might execute next to Minecraft Bedrock on Windows, eventually enabling select Java mods to work without converting them to add-ons.

**Present status:** JVM host and C++ event transport are tested on Linux **and Windows**. The Windows native relay-to-JVM integration test [passed in GitHub Actions](https://github.com/tasx13ok-create/JavaBridge-Bedrock/actions/runs/40600778888). The source-only LeviLamina Windows client plugin has **not** yet built or run in Minecraft Bedrock; the first full build failed while compiling the upstream LeviLamina package, before reaching JavaBridge code. This is **not** a functioning general-purpose CurseForge Java-mod loader yet.

## Verified capabilities

- Read downloaded CurseForge mod JAR metadata locally and without modifying files: Fabric, Forge, NeoForge, Quilt. Inspect CurseForge Java modpack `manifest.json` files without downloading mods or installing a modpack.
- Compile an original demonstration Fabric-style JAR, then execute its Java bytecode through a small local JVM host.
- Relay bounded `BREAK x y z` block-break coordinate events as well as simulated `JOIN`, `TICK`, and `LEAVE` messages from a native C++ worker to Java event handlers over authenticated loopback TCP.
- Support bounded Java-to-native `BedrockActions.log` and `BedrockActions.chat` actions. The C++ relay validates and queues these on its worker thread; the unverified Bedrock client plugin is designed to send announcements to connected players during integrated server ticks. Windows/Linux relay tests confirm protocol delivery, **not** in-game chat.
- Extracts Fabric-declared nested JAR library dependencies to a temporary classpath, with strict path validation and size limits; does not initialize nested mods automatically.
- Deterministic multi-JAR initializer order based on declared Fabric mod dependencies, with explicit diagnostics for missing dependencies, cycles, and duplicate IDs. Dependency version ranges are not implemented.
- Minimal **Fabric Loader environment/config-path API** shim: `FabricLoader.getInstance().isModLoaded`, `getGameDir`, `getConfigDir`, and `getEnvironmentType`. The paths point to the sidecar workspace rather than Minecraft game directories. This is not a full Fabric Loader implementation.
- Minimal **Fabric API tick event ABI** shims for `ServerTickEvents.START_SERVER_TICK` and `END_SERVER_TICK` with a deliberately tiny `MinecraftServer` facade. An independently built JAR using Fabric API import names runs unchanged in the JVM sidecar. This only demonstrates that specific binary interface, not Fabric API or Minecraft Java Edition compatibility.
- Unit and integration tests for the host, inspector, token rejection, and C++ worker.
- Source for a LeviLamina Windows Bedrock client plugin wired to client join/exit and server-level tick events (not yet validated in Bedrock).

## Run standalone tests (Minecraft not required)

Requires **JDK 21**, **Python 3.10+**, and on Linux `g++` with C++20 support.

```sh
python tools/build.py
python tools/inspect.py out/mods
python -m unittest discover -s tests -v
```

Or launch a manual demo in separate terminals:

```sh
java --limit-modules java.base -cp out/host bridge.Host out/mods 32651 dev-secret-token-0123456789 1000
# second terminal:
python tools/adapter_sim.py
```

The printed demo token is not for real sessions.

**JAR approval for real sidecar launcher:** Java mod bytecode executes with your local user's OS privileges. Download and inspect only mods you trust; before using `tools/start_client_bridge.py`, explicitly approve each exact JAR hash:

```sh
python tools/approve_mods.py --mods out/mods --yes
python tools/start_client_bridge.py --mods out/mods
```

`--yes` is an explicit attestation that you've reviewed the JARs. This approval is **not a malware scanner**. Changing any JAR invalidates its approval. Standalone `Host` debug mode without an allowlist remains available for CI fixtures only.

Build a reproducible runtime-only ZIP (including Java classes and demo JARs):

```sh
python tools/package_runtime.py
```

This ZIP deliberately contains **no native Bedrock DLL** and is not a one-click mod installer. GitHub Actions also publishes a runtime archive as a build artifact for source inspection and standalone tests.

## Bedrock Windows integration (UNVERIFIED)

This project includes `native/levilamina-client/` source that follows the [official LeviLamina mod template](https://github.com/LiteLDev/levilamina-mod-template). This requires the compatible LeviLamina client, supported Bedrock version, Visual Studio build tools, clang-cl and xmake.

For an isolated, backed-up **test** client:

1. Follow the [LeviLamina Bedrock client install guide](https://docs.levimc.org/LeviLamina/user_guides/install_on_client/).
2. From `native/levilamina-client/`, run `xmake f -y -p windows -a x64 -m release --target_type=client` then `xmake`.
3. Install the resulting native mod into the isolated LeviLauncher instance (package layout depends on LeviLamina version).
4. From repo root run `py tools/build.py` then `py tools/start_client_bridge.py --mods out/mods`.
5. Open a local world and inspect Java host output for `HELLO_FABRIC_JOIN` / `HELLO_FABRIC_TICK` / `HELLO_FABRIC_LEAVE`.

The DLL build and in-game behavior are **not** currently verified. Actual game events, API definitions and loader version compatibility may differ. Never install an untested DLL into your primary game profile.

## What this does NOT do

- It does not supply the full Java Edition `net.minecraft.*` classes, Fabric Loader/Fabric API, registries, Mixins, shaders, rendering or world mutation. The single tick-event shim's `MinecraftServer` object is a limited facade, not a real Java server.
- It does not yet make third-party CurseForge Java mods work in Bedrock; the JAR executed in tests is our intentionally simple demonstration mod.
- The native C++ relay accepts bounded Java **LOG** and **CHAT** actions, but cannot change blocks, entities, inventory, lighting, or other game state. Actual in-game chat is not yet tested.
- It does not copy the CurseForge client or download its mods. API integration would require approved keys/permissions.
- It is not a sandbox. **Java JARs execute arbitrary code with your local user's permissions. Only run JARs you trust.**

Independent open-source research, unaffiliated with CurseForge, Mojang/Microsoft, Fabric, or LeviLamina. The repository's original code is MIT licensed; upstream and downloaded mods retain their own licenses.

## Upcoming engineering gates

1. Verify a real Windows Bedrock client build and native-to-Java live event logs.
2. Define a minimal Java API-compatible action channel with main-thread-safe Bedrock operations.
3. Validate a third-party openly licensed, minimal Fabric mod under precise compatibility constraints.
4. Gradually support other APIs, dependencies and graphics as feasible.
