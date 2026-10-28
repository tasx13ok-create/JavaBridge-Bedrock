# v0.2 initial GitHub publication (2026-10-27)

- Imported original experimental Java .jar host and Fabric-style example.
- Added read-only CurseForge/JAR metadata inspector.
- Published C++20 native event transport and source-only LeviLamina Windows client plugin.
- Added local session token launcher and cross-language tests.
- Added GitHub Actions build-and-test workflow.

**Status:** Standalone native-to-Java demo validated previously; GitHub CI will independently verify the checked-in code. No Bedrock Windows DLL build or third-party CurseForge mod compatibility proven.

## v0.3 development milestones (2026-10-27)

- Added Fabric tick callback, limited Fabric Loader API, and dependency-aware direct-JAR initialization.
- Added a strictly bounded Java -> native LOG action channel, with Windows + Linux round-trip tests.
- Added offline mod scanner flags and reproducible sidecar-runtime ZIP packaging.
- The full LeviLamina Bedrock client DLL remains unverified; SDK builds are being debugged separately.
