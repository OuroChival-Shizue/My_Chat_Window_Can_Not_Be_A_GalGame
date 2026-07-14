# Packaging

This app targets Windows-first distribution through Tauri v2 and the NSIS installer bundle.

## Release Build

From `apps/desktop`:

```powershell
npm run tauri -- build
```

The expected Windows artifacts are created under:

```text
src-tauri/target/release/
src-tauri/target/release/bundle/nsis/
```

Use this for a local executable-only smoke build:

```powershell
npm run tauri -- build --no-bundle
```

## Current Installer Policy

- Bundle target: `nsis`
- Install mode: current user
- WebView2 policy: download the Microsoft bootstrapper silently during installation
- Installer languages: Simplified Chinese and English
- Start menu folder: `GalGame Chat Studio`

## Verified Local Output

The bundle build has been verified locally with:

```powershell
npm run tauri -- build
```

Latest verified installer:

```text
src-tauri/target/release/bundle/nsis/GalGame Chat Studio_0.1.0_x64-setup.exe
```

## Smoke QA

Verified locally:

- `npm run tauri -- build` completed and produced the NSIS installer
- `cargo test` passed all 16 Rust tests
- `src-tauri/target/release/galgame-chat-desktop.exe` stayed alive for a 5-second launch smoke test

## Signing And Updater

Automatic updates should be enabled only after the project has:

- A code-signing certificate and timestamp server policy
- A Tauri updater signing key
- A stable HTTPS release endpoint that serves version metadata and artifacts
- CI release jobs that build, sign, upload, and verify the installer

Until those exist, `createUpdaterArtifacts` remains disabled so local release builds stay reproducible and do not emit unusable updater artifacts.
