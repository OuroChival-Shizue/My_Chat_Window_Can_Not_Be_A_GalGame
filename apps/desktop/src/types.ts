export type AssetKind = "portrait" | "background" | "font" | "dialog_box";

export interface GlobalConfig {
  current_character: string;
  trigger_hotkey: string;
  global_hotkeys: Record<string, string>;
  render: {
    cache_format: "jpeg" | "png";
    jpeg_quality: number;
    use_memory_canvas_cache: boolean;
  };
}

export interface CharacterSummary {
  id: string;
  name: string;
  portrait_count: number;
  background_count: number;
}

export interface TextWrapper {
  type: "none" | "preset" | "custom";
  preset: string;
  prefix: string;
  suffix: string;
}

export interface NameLayer {
  text: string;
  position: [number, number];
  font_color: [number, number, number];
  font_size: number;
  font_file?: string;
}

export interface CharacterConfig {
  meta: {
    id?: string;
    name?: string;
  };
  style: {
    mode: "basic" | "advanced";
    font_file?: string;
    name_font_file?: string;
    text_wrapper: TextWrapper;
    basic: {
      font_size: number;
      text_color: [number, number, number];
      name_font_size: number;
      name_color: [number, number, number];
    };
    advanced: {
      name_layers: Record<string, NameLayer[]>;
    };
  };
  layout: {
    _canvas_size: [number, number];
    stand_pos: [number, number];
    stand_scale: number;
    stand_on_top: boolean;
    current_portrait: string;
    current_background: string;
    box_pos: [number, number];
    text_area: [number, number, number, number];
    name_pos: [number, number];
    enable_crop: boolean;
    crop_area?: [number, number, number, number];
  };
  assets: {
    dialog_box: string;
  };
}

export interface CharacterBundle {
  id: string;
  config: CharacterConfig;
  portraits: string[];
  backgrounds: string[];
  fonts: string[];
  dialog_box_exists: boolean;
}


export interface EngineStatus {
  running: boolean;
  paused: boolean;
  character_id?: string;
  current_portrait?: string;
  trigger_hotkey: string;
  last_output_path?: string;
  last_error?: string;
  registered_hotkey?: string;
  registered_aux_hotkeys: string[];
  shortcut_hits: number;
  expression_count: number;
  last_captured_text?: string;
  last_action?: string;
}


export interface ClipboardResult {
  path: string;
  width: number;
  height: number;
  formats: string[];
}

export interface RenderPreviewResult {
  path: string;
  width: number;
  height: number;
  url: string;
}

export interface BuildCacheResult {
  cache_dir: string;
  generated: number;
  format: string;
}
