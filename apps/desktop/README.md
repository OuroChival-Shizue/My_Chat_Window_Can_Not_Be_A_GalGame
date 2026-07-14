# GalGame Chat Studio

Tauri v2 refactor desktop app for `My_Chat_Window_Can_Not_Be_A_GalGame`. The goal is to replace the old PyQt editor and Python listener engine with a modern Windows-first desktop app that can still read the existing assets and YAML files.

## Current Status

Done:

- React + TypeScript + Vite frontend
- Tauri v2 desktop shell
- Fluent-style three-pane workbench UI
- Konva editor canvas for portrait/name/text/crop layout editing
- Inspector controls for active portrait/background, text styling, crop, and layout numbers
- Rust commands for reading and saving legacy `global_config.yaml`
- Rust commands for scanning and reading legacy `assets/characters/*/config.yaml`
- Character creation, asset import/delete, and opening character folders
- Native Windows file picker for portrait/background/font/dialog-box imports
- Legacy-compatible YAML saving
- Native Rust render preview for background, portrait, dialog box, text, and crop
- Legacy-compatible advanced multi-layer name rendering
- Native Rust cache builder for `assets/cache/<character>/p_<portrait>__b_<background>.*`
- Engine runtime state commands: status, start, stop, pause/resume, active portrait, and render-current-text output
- Windows clipboard output for the latest engine render using `CF_DIB` plus optional `PNG` format
- Windows `Ctrl+V` paste automation command for future hotkey callbacks
- Global shortcut registration using Tauri global-shortcut and `global_config.yaml` trigger hotkey
- Hotkey callback pipeline: capture active input text with `Ctrl+A`/`Ctrl+X`, render, copy image, and paste with `Ctrl+V`
- Auxiliary engine hotkeys: `Alt+1~9` expression switching, `Ctrl+F12` pause/resume, and `Ctrl+F5` config reload
- Top command bar engine controls wired to the Rust runtime state
- Live engine status polling for hotkey hits, last action, captured text length, and errors
- Windows NSIS installer packaging configuration

Not done yet:

- Code signing, release hosting, and automatic updater activation

## Compatibility Contract

The first Tauri version must directly read the existing project-root files and folders:

- `global_config.yaml`
- `assets/characters/<id>/config.yaml`
- `assets/characters/<id>/portrait/`
- `assets/characters/<id>/background/`
- `assets/characters/<id>/fonts/`
- `assets/characters/<id>/textbox_bg.png`

The Rust backend discovers the legacy project root by walking upward from `CARGO_MANIFEST_DIR` until it finds `global_config.yaml` and `assets/characters`, so development does not require copying legacy assets into `apps/desktop`.

## Packaging

See `PACKAGING.md` for release build commands, installer output paths, and the updater readiness checklist.
