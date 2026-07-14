import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import type { AssetKind, BuildCacheResult, CharacterBundle, CharacterSummary, ClipboardResult, EngineStatus, GlobalConfig, RenderPreviewResult } from "./types";

const demoConfig: GlobalConfig = {
  current_character: "yuraa",
  trigger_hotkey: "ctrl+enter",
  global_hotkeys: {
    copy_to_clipboard: "ctrl+shift+c",
    show_character: "ctrl+shift+v",
  },
  render: {
    cache_format: "jpeg",
    jpeg_quality: 90,
    use_memory_canvas_cache: true,
  },
};

const demoCharacter: CharacterBundle = {
  id: "yuraa",
  portraits: ["1.png"],
  backgrounds: ["1.png"],
  fonts: ["lolita.ttf"],
  dialog_box_exists: true,
  config: {
    meta: { name: "茅崎夕樱" },
    style: {
      mode: "advanced",
      font_file: "fonts/lolita.ttf",
      text_wrapper: {
        type: "preset",
        preset: "corner_double",
        prefix: "『",
        suffix: "』",
      },
      basic: {
        font_size: 39,
        text_color: [255, 255, 255],
        name_font_size: 29,
        name_color: [255, 0, 255],
      },
      advanced: { name_layers: {} },
    },
    layout: {
      _canvas_size: [1280, 720],
      stand_pos: [454, 114],
      stand_scale: 0.764,
      stand_on_top: false,
      current_portrait: "1.png",
      current_background: "1.png",
      box_pos: [0, 0],
      text_area: [239, 591, 1079, 716],
      name_pos: [344, 544],
      enable_crop: true,
      crop_area: [3, 513, 1280, 717],
    },
    assets: { dialog_box: "textbox_bg.png" },
  },
};


let demoEngineStatus: EngineStatus = {
  running: false,
  paused: false,
  trigger_hotkey: demoConfig.trigger_hotkey,
  registered_aux_hotkeys: [],
  shortcut_hits: 0,
  expression_count: demoCharacter.portraits.length,
  last_action: undefined,
  last_captured_text: undefined,
};

const canInvoke = "__TAURI_INTERNALS__" in window;

export async function loadGlobalConfig(): Promise<GlobalConfig> {
  if (!canInvoke) return demoConfig;
  return invoke<GlobalConfig>("load_global_config");
}

export async function listCharacters(): Promise<CharacterSummary[]> {
  if (!canInvoke) {
    return [{ id: "yuraa", name: "茅崎夕樱", portrait_count: 1, background_count: 1 }];
  }
  return invoke<CharacterSummary[]>("list_characters");
}

export async function loadCharacter(id: string): Promise<CharacterBundle> {
  if (!canInvoke) return demoCharacter;
  return invoke<CharacterBundle>("load_character", { id });
}

export async function saveGlobalConfig(config: GlobalConfig): Promise<void> {
  if (!canInvoke) {
    Object.assign(demoConfig, config);
    return;
  }
  return invoke("save_global_config", { config });
}

export async function saveCharacter(id: string, config: CharacterBundle["config"]): Promise<void> {
  if (!canInvoke) return;
  return invoke("save_character", { id, config });
}

export async function createCharacter(id: string, displayName: string): Promise<CharacterBundle> {
  if (!canInvoke) {
    return { ...demoCharacter, id, config: { ...demoCharacter.config, meta: { id, name: displayName || id } } };
  }
  return invoke<CharacterBundle>("create_character", { id, displayName });
}


export async function pickAssetFile(kind: AssetKind): Promise<string | null> {
  if (!canInvoke) return window.prompt("请输入本地文件完整路径");
  return invoke<string | null>("pick_asset_file", { kind });
}

export async function importAsset(id: string, kind: AssetKind, sourcePath: string): Promise<CharacterBundle> {
  if (!canInvoke) return demoCharacter;
  return invoke<CharacterBundle>("import_asset", { id, kind, sourcePath });
}

export async function deleteAsset(id: string, kind: AssetKind, filename: string): Promise<CharacterBundle> {
  if (!canInvoke) return demoCharacter;
  return invoke<CharacterBundle>("delete_asset", { id, kind, filename });
}

export async function openCharacterFolder(id: string): Promise<void> {
  if (!canInvoke) return;
  return invoke("open_character_folder", { id });
}

export async function renderPreview(id: string, config: CharacterBundle["config"], text: string): Promise<RenderPreviewResult> {
  if (!canInvoke) {
    return { path: "", width: config.layout._canvas_size[0], height: config.layout._canvas_size[1], url: "" };
  }
  const result = await invoke<Omit<RenderPreviewResult, "url">>("render_preview", { id, config, text });
  return { ...result, url: convertFileSrc(result.path) };
}

export async function buildCache(id: string, config: CharacterBundle["config"]): Promise<BuildCacheResult> {
  if (!canInvoke) {
    return { cache_dir: "", generated: 1, format: "jpeg" };
  }
  return invoke<BuildCacheResult>("build_cache", { id, config });
}

export async function loadEngineStatus(): Promise<EngineStatus> {
  if (!canInvoke) return demoEngineStatus;
  return invoke<EngineStatus>("engine_status");
}

export async function startEngine(id: string, config: CharacterBundle["config"]): Promise<EngineStatus> {
  if (!canInvoke) {
    demoEngineStatus = {
      running: true,
      paused: false,
      character_id: id,
      current_portrait: config.layout.current_portrait || undefined,
      trigger_hotkey: demoConfig.trigger_hotkey,
      registered_hotkey: demoConfig.trigger_hotkey,
      registered_aux_hotkeys: ["Alt+1", "Ctrl+F12", "Ctrl+F5"],
      shortcut_hits: demoEngineStatus.shortcut_hits,
      expression_count: demoCharacter.portraits.length,
    };
    return demoEngineStatus;
  }
  return invoke<EngineStatus>("start_engine", { id, config });
}

export async function stopEngine(): Promise<EngineStatus> {
  if (!canInvoke) {
    demoEngineStatus = { ...demoEngineStatus, running: false, paused: false };
    return demoEngineStatus;
  }
  return invoke<EngineStatus>("stop_engine");
}

export async function toggleEnginePause(): Promise<EngineStatus> {
  if (!canInvoke) {
    demoEngineStatus = demoEngineStatus.running ? { ...demoEngineStatus, paused: !demoEngineStatus.paused } : demoEngineStatus;
    return demoEngineStatus;
  }
  return invoke<EngineStatus>("toggle_engine_pause");
}

export async function setEnginePortrait(filename: string): Promise<EngineStatus> {
  if (!canInvoke) {
    demoEngineStatus = { ...demoEngineStatus, current_portrait: filename };
    return demoEngineStatus;
  }
  return invoke<EngineStatus>("set_engine_portrait", { filename });
}

export async function renderEngineText(id: string, config: CharacterBundle["config"], text: string): Promise<RenderPreviewResult> {
  if (!canInvoke) {
    demoEngineStatus = {
      ...demoEngineStatus,
      running: true,
      paused: false,
      character_id: id,
      current_portrait: config.layout.current_portrait || demoEngineStatus.current_portrait,
      last_output_path: "",
    };
    return { path: "", width: config.layout._canvas_size[0], height: config.layout._canvas_size[1], url: "" };
  }
  const result = await invoke<Omit<RenderPreviewResult, "url">>("render_engine_text", { id, config, text });
  return { ...result, url: convertFileSrc(result.path) };
}

export async function copyEngineOutputToClipboard(): Promise<ClipboardResult> {
  if (!canInvoke) {
    return {
      path: demoEngineStatus.last_output_path ?? "",
      width: demoCharacter.config.layout._canvas_size[0],
      height: demoCharacter.config.layout._canvas_size[1],
      formats: ["demo"],
    };
  }
  return invoke<ClipboardResult>("copy_engine_output_to_clipboard");
}

export async function pasteClipboardToActiveWindow(): Promise<void> {
  if (!canInvoke) return;
  return invoke("paste_clipboard_to_active_window");
}

export async function refreshEngineHotkey(): Promise<EngineStatus> {
  if (!canInvoke) {
    demoEngineStatus = { ...demoEngineStatus, registered_hotkey: demoConfig.trigger_hotkey, registered_aux_hotkeys: ["Alt+1", "Ctrl+F12", "Ctrl+F5"] };
    return demoEngineStatus;
  }
  return invoke<EngineStatus>("refresh_engine_hotkey");
}

export async function runEngineOnce(): Promise<RenderPreviewResult> {
  if (!canInvoke) {
    demoEngineStatus = { ...demoEngineStatus, shortcut_hits: demoEngineStatus.shortcut_hits + 1, last_action: "demo_run" };
    return { path: "", width: demoCharacter.config.layout._canvas_size[0], height: demoCharacter.config.layout._canvas_size[1], url: "" };
  }
  const result = await invoke<Omit<RenderPreviewResult, "url">>("run_engine_once");
  return { ...result, url: convertFileSrc(result.path) };
}
