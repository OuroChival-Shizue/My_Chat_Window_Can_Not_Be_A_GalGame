use ab_glyph::{FontArc, PxScale};
use image::{imageops, DynamicImage, ImageFormat, Rgba, RgbaImage};
use imageproc::drawing::draw_text_mut;
use serde::{Deserialize, Serialize};
use serde_yaml::{Mapping, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use thiserror::Error;
#[cfg(target_os = "windows")]
use windows_sys::Win32::Foundation::{HANDLE, HGLOBAL};
#[cfg(target_os = "windows")]
use windows_sys::Win32::System::DataExchange::{
    CloseClipboard, EmptyClipboard, GetClipboardData, IsClipboardFormatAvailable, OpenClipboard,
    RegisterClipboardFormatW, SetClipboardData,
};
#[cfg(target_os = "windows")]
use windows_sys::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};
#[cfg(target_os = "windows")]
use windows_sys::Win32::UI::Controls::Dialogs::{
    GetOpenFileNameW, OFN_EXPLORER, OFN_FILEMUSTEXIST, OFN_HIDEREADONLY, OFN_NOCHANGEDIR,
    OFN_PATHMUSTEXIST, OPENFILENAMEW,
};
#[cfg(target_os = "windows")]
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, VIRTUAL_KEY, VK_A,
    VK_CONTROL, VK_V, VK_X,
};

#[derive(Debug, Error)]
enum AppError {
    #[error("无法定位项目根目录")]
    ProjectRootNotFound,
    #[error("文件系统错误: {0}")]
    Io(#[from] std::io::Error),
    #[error("YAML 解析错误: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("JSON 解析错误: {0}")]
    Json(#[from] serde_json::Error),
    #[error("角色不存在: {0}")]
    CharacterNotFound(String),
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    #[error("Asset not found: {0}")]
    AssetNotFound(String),
    #[error("Image error: {0}")]
    Image(#[from] image::ImageError),
    #[error("Clipboard error: {0}")]
    Clipboard(String),
    #[error("Hotkey error: {0}")]
    Hotkey(String),
}

impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::ser::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

#[derive(Debug, Clone, Serialize)]
struct EngineStatus {
    running: bool,
    paused: bool,
    character_id: Option<String>,
    current_portrait: Option<String>,
    trigger_hotkey: String,
    last_output_path: Option<String>,
    last_error: Option<String>,
    registered_hotkey: Option<String>,
    registered_aux_hotkeys: Vec<String>,
    shortcut_hits: u64,
    expression_count: usize,
    last_captured_text: Option<String>,
    last_action: Option<String>,
}

#[derive(Debug, Clone)]
struct EngineState {
    running: bool,
    paused: bool,
    character_id: Option<String>,
    current_portrait: Option<String>,
    trigger_hotkey: String,
    last_output_path: Option<String>,
    last_error: Option<String>,
    registered_hotkey: Option<String>,
    registered_aux_hotkeys: Vec<String>,
    shortcut_hits: u64,
    current_config: Option<CharacterConfig>,
    portrait_assets: Vec<String>,
    last_captured_text: Option<String>,
    last_action: Option<String>,
}

impl Default for EngineState {
    fn default() -> Self {
        Self {
            running: false,
            paused: false,
            character_id: None,
            current_portrait: None,
            trigger_hotkey: "ctrl+enter".to_string(),
            last_output_path: None,
            last_error: None,
            registered_hotkey: None,
            registered_aux_hotkeys: Vec::new(),
            shortcut_hits: 0,
            current_config: None,
            portrait_assets: Vec::new(),
            last_captured_text: None,
            last_action: None,
        }
    }
}

impl EngineState {
    fn status(&self) -> EngineStatus {
        EngineStatus {
            running: self.running,
            paused: self.paused,
            character_id: self.character_id.clone(),
            current_portrait: self.current_portrait.clone(),
            trigger_hotkey: self.trigger_hotkey.clone(),
            last_output_path: self.last_output_path.clone(),
            last_error: self.last_error.clone(),
            registered_hotkey: self.registered_hotkey.clone(),
            registered_aux_hotkeys: self.registered_aux_hotkeys.clone(),
            shortcut_hits: self.shortcut_hits,
            expression_count: self.portrait_assets.len(),
            last_captured_text: self.last_captured_text.clone(),
            last_action: self.last_action.clone(),
        }
    }
}

fn normalize_hotkey(raw: &str) -> String {
    raw.split('+')
        .filter_map(|part| {
            let key = part.trim();
            if key.is_empty() {
                return None;
            }
            let normalized = match key.to_ascii_lowercase().as_str() {
                "ctrl" | "control" => "Ctrl".to_string(),
                "shift" => "Shift".to_string(),
                "alt" | "option" => "Alt".to_string(),
                "cmd" | "command" | "meta" | "super" => "Super".to_string(),
                "enter" | "return" => "Enter".to_string(),
                "esc" | "escape" => "Escape".to_string(),
                "space" => "Space".to_string(),
                other if other.len() == 1 => other.to_ascii_uppercase(),
                other => {
                    let mut chars = other.chars();
                    match chars.next() {
                        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
                        None => String::new(),
                    }
                }
            };
            Some(normalized)
        })
        .collect::<Vec<_>>()
        .join("+")
}

fn expression_hotkey(index: usize) -> String {
    format!("Alt+{index}")
}

fn engine_aux_hotkeys() -> Vec<String> {
    let mut hotkeys = (1..=9).map(expression_hotkey).collect::<Vec<_>>();
    hotkeys.push("Ctrl+F12".to_string());
    hotkeys.push("Ctrl+F5".to_string());
    hotkeys
}

fn unique_shortcuts(shortcuts: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut seen = BTreeSet::new();
    let mut out = Vec::new();
    for shortcut in shortcuts {
        if !shortcut.is_empty() && seen.insert(shortcut.clone()) {
            out.push(shortcut);
        }
    }
    out
}

fn register_engine_hotkeys(
    app: &tauri::AppHandle,
    desired_trigger: &str,
    previous_trigger: Option<String>,
    previous_aux: Vec<String>,
) -> Result<(Option<String>, Vec<String>), AppError> {
    let trigger = Some(normalize_hotkey(desired_trigger)).filter(|value| !value.is_empty());
    let aux = engine_aux_hotkeys();
    let previous = unique_shortcuts(previous_trigger.into_iter().chain(previous_aux));
    let desired = unique_shortcuts(trigger.clone().into_iter().chain(aux.clone()));

    for shortcut in previous
        .iter()
        .filter(|shortcut| !desired.contains(shortcut))
    {
        let _ = app.global_shortcut().unregister(shortcut.as_str());
    }
    for shortcut in &desired {
        if !app.global_shortcut().is_registered(shortcut.as_str()) {
            app.global_shortcut()
                .register(shortcut.as_str())
                .map_err(|error| AppError::Hotkey(error.to_string()))?;
        }
    }
    Ok((trigger, aux))
}

fn unregister_engine_hotkeys(app: &tauri::AppHandle, trigger: Option<String>, aux: Vec<String>) {
    for shortcut in unique_shortcuts(trigger.into_iter().chain(aux)) {
        let _ = app.global_shortcut().unregister(shortcut.as_str());
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EngineShortcutAction {
    Trigger,
    Expression(usize),
    TogglePause,
    ReloadConfig,
    Ignore,
}

fn classify_engine_shortcut(engine: &EngineState, shortcut: &str) -> EngineShortcutAction {
    let shortcut = normalize_hotkey(shortcut);
    if engine.registered_hotkey.as_deref() == Some(shortcut.as_str()) {
        return EngineShortcutAction::Trigger;
    }
    if shortcut == "Ctrl+F12" && engine.registered_aux_hotkeys.contains(&shortcut) {
        return EngineShortcutAction::TogglePause;
    }
    if shortcut == "Ctrl+F5" && engine.registered_aux_hotkeys.contains(&shortcut) {
        return EngineShortcutAction::ReloadConfig;
    }
    for index in 1..=9 {
        if shortcut == expression_hotkey(index) && engine.registered_aux_hotkeys.contains(&shortcut)
        {
            return EngineShortcutAction::Expression(index);
        }
    }
    EngineShortcutAction::Ignore
}

fn lock_engine_state<'a>(
    state: &'a tauri::State<'_, Mutex<EngineState>>,
) -> Result<std::sync::MutexGuard<'a, EngineState>, AppError> {
    state
        .lock()
        .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RenderConfig {
    cache_format: String,
    jpeg_quality: u8,
    use_memory_canvas_cache: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct GlobalConfig {
    current_character: String,
    trigger_hotkey: String,
    global_hotkeys: BTreeMap<String, String>,
    render: RenderConfig,
}

impl Default for GlobalConfig {
    fn default() -> Self {
        Self {
            current_character: "yuraa".to_string(),
            trigger_hotkey: "enter".to_string(),
            global_hotkeys: BTreeMap::from([
                ("copy_to_clipboard".to_string(), "ctrl+shift+c".to_string()),
                ("show_character".to_string(), "ctrl+shift+v".to_string()),
            ]),
            render: RenderConfig {
                cache_format: "jpeg".to_string(),
                jpeg_quality: 90,
                use_memory_canvas_cache: true,
            },
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TextWrapper {
    #[serde(rename = "type")]
    wrapper_type: String,
    preset: String,
    prefix: String,
    suffix: String,
}

impl Default for TextWrapper {
    fn default() -> Self {
        Self {
            wrapper_type: "none".to_string(),
            preset: "corner_single".to_string(),
            prefix: String::new(),
            suffix: String::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BasicStyle {
    font_size: u32,
    text_color: [u8; 3],
    name_font_size: u32,
    name_color: [u8; 3],
}

impl Default for BasicStyle {
    fn default() -> Self {
        Self {
            font_size: 40,
            text_color: [255, 255, 255],
            name_font_size: 32,
            name_color: [255, 85, 255],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct NameLayer {
    text: String,
    position: [i32; 2],
    font_color: [u8; 3],
    font_size: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    font_file: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct AdvancedStyle {
    name_layers: BTreeMap<String, Vec<NameLayer>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StyleConfig {
    mode: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    font_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    name_font_file: Option<String>,
    text_wrapper: TextWrapper,
    basic: BasicStyle,
    advanced: AdvancedStyle,
}

impl Default for StyleConfig {
    fn default() -> Self {
        Self {
            mode: "basic".to_string(),
            font_file: None,
            name_font_file: None,
            text_wrapper: TextWrapper::default(),
            basic: BasicStyle::default(),
            advanced: AdvancedStyle::default(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct MetaConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<String>,
}

impl Default for MetaConfig {
    fn default() -> Self {
        Self {
            id: None,
            name: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LayoutConfig {
    #[serde(rename = "_canvas_size")]
    canvas_size: [u32; 2],
    stand_pos: [i32; 2],
    stand_scale: f32,
    stand_on_top: bool,
    current_portrait: String,
    current_background: String,
    box_pos: [i32; 2],
    text_area: [i32; 4],
    name_pos: [i32; 2],
    enable_crop: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    crop_area: Option<[i32; 4]>,
}

impl Default for LayoutConfig {
    fn default() -> Self {
        Self {
            canvas_size: [1280, 720],
            stand_pos: [0, 0],
            stand_scale: 1.0,
            stand_on_top: false,
            current_portrait: String::new(),
            current_background: String::new(),
            box_pos: [0, 0],
            text_area: [100, 432, 1180, 680],
            name_pos: [100, 380],
            enable_crop: false,
            crop_area: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AssetsConfig {
    dialog_box: String,
}

impl Default for AssetsConfig {
    fn default() -> Self {
        Self {
            dialog_box: "textbox_bg.png".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CharacterConfig {
    meta: MetaConfig,
    style: StyleConfig,
    layout: LayoutConfig,
    assets: AssetsConfig,
}

impl Default for CharacterConfig {
    fn default() -> Self {
        Self {
            meta: MetaConfig::default(),
            style: StyleConfig::default(),
            layout: LayoutConfig::default(),
            assets: AssetsConfig::default(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct CharacterSummary {
    id: String,
    name: String,
    portrait_count: usize,
    background_count: usize,
}

#[derive(Debug, Clone, Serialize)]
struct CharacterBundle {
    id: String,
    config: CharacterConfig,
    portraits: Vec<String>,
    backgrounds: Vec<String>,
    fonts: Vec<String>,
    dialog_box_exists: bool,
}

#[derive(Debug, Clone, Serialize)]
struct RenderPreviewResult {
    path: String,
    width: u32,
    height: u32,
}

#[derive(Debug, Clone, Serialize)]
struct ClipboardResult {
    path: String,
    width: u32,
    height: u32,
    formats: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
struct BuildCacheResult {
    cache_dir: String,
    generated: usize,
    format: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
enum AssetKind {
    Portrait,
    Background,
    Font,
    DialogBox,
}

fn wide_nul(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

fn wide_double_nul(parts: &[&str]) -> Vec<u16> {
    let mut out = Vec::new();
    for part in parts {
        out.extend(part.encode_utf16());
        out.push(0);
    }
    out.push(0);
    out
}

fn asset_dialog_filter(kind: &AssetKind) -> Vec<u16> {
    match kind {
        AssetKind::Portrait | AssetKind::Background | AssetKind::DialogBox => wide_double_nul(&[
            "Image files (*.png;*.jpg;*.jpeg)",
            "*.png;*.jpg;*.jpeg",
            "All files (*.*)",
            "*.*",
        ]),
        AssetKind::Font => wide_double_nul(&[
            "Font files (*.ttf;*.otf)",
            "*.ttf;*.otf",
            "All files (*.*)",
            "*.*",
        ]),
    }
}

#[cfg(target_os = "windows")]
fn pick_file_with_windows_dialog(kind: &AssetKind) -> Result<Option<String>, AppError> {
    let filter = asset_dialog_filter(kind);
    let title = wide_nul(match kind {
        AssetKind::Portrait => "Import portrait image",
        AssetKind::Background => "Import background image",
        AssetKind::Font => "Import font file",
        AssetKind::DialogBox => "Import dialog box image",
    });
    let mut filename = vec![0u16; 32768];
    let mut dialog = OPENFILENAMEW {
        lStructSize: std::mem::size_of::<OPENFILENAMEW>() as u32,
        hwndOwner: std::ptr::null_mut(),
        hInstance: std::ptr::null_mut(),
        lpstrFilter: filter.as_ptr(),
        lpstrCustomFilter: std::ptr::null_mut(),
        nMaxCustFilter: 0,
        nFilterIndex: 1,
        lpstrFile: filename.as_mut_ptr(),
        nMaxFile: filename.len() as u32,
        lpstrFileTitle: std::ptr::null_mut(),
        nMaxFileTitle: 0,
        lpstrInitialDir: std::ptr::null(),
        lpstrTitle: title.as_ptr(),
        Flags: OFN_EXPLORER
            | OFN_FILEMUSTEXIST
            | OFN_PATHMUSTEXIST
            | OFN_HIDEREADONLY
            | OFN_NOCHANGEDIR,
        nFileOffset: 0,
        nFileExtension: 0,
        lpstrDefExt: std::ptr::null(),
        lCustData: 0,
        lpfnHook: None,
        lpTemplateName: std::ptr::null(),
        pvReserved: std::ptr::null_mut(),
        dwReserved: 0,
        FlagsEx: 0,
    };

    let picked = unsafe { GetOpenFileNameW(&mut dialog) };
    if picked == 0 {
        return Ok(None);
    }
    let len = filename
        .iter()
        .position(|ch| *ch == 0)
        .unwrap_or(filename.len());
    if len == 0 {
        return Ok(None);
    }
    Ok(Some(String::from_utf16_lossy(&filename[..len])))
}

#[cfg(not(target_os = "windows"))]
fn pick_file_with_windows_dialog(_kind: &AssetKind) -> Result<Option<String>, AppError> {
    Err(AppError::InvalidInput(
        "Native file picker is currently implemented for Windows only".to_string(),
    ))
}

fn project_root() -> Result<PathBuf, AppError> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for ancestor in manifest_dir.ancestors() {
        if ancestor.join("assets").join("characters").is_dir()
            && ancestor.join("global_config.yaml").is_file()
        {
            return Ok(ancestor.to_path_buf());
        }
    }
    std::env::current_dir()?
        .ancestors()
        .find(|path| path.join("assets").join("characters").is_dir())
        .map(Path::to_path_buf)
        .ok_or(AppError::ProjectRootNotFound)
}

fn read_yaml<T: for<'de> Deserialize<'de> + Default>(path: &Path) -> Result<T, AppError> {
    if !path.exists() {
        return Ok(T::default());
    }
    let raw = fs::read_to_string(path)?;
    Ok(serde_yaml::from_str(&raw)?)
}

fn write_yaml<T: Serialize>(path: &Path, value: &T) -> Result<(), AppError> {
    let raw = serde_yaml::to_string(value)?;
    fs::write(path, raw)?;
    Ok(())
}

fn sanitize_character_id(id: &str) -> Result<String, AppError> {
    let trimmed = id.trim();
    if trimmed.is_empty() {
        return Err(AppError::InvalidInput(
            "Character ID cannot be empty".to_string(),
        ));
    }
    if !trimmed
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
    {
        return Err(AppError::InvalidInput(
            "Character ID may only contain letters, numbers, underscores, and hyphens".to_string(),
        ));
    }
    Ok(trimmed.to_string())
}

fn character_root(root: &Path, id: &str) -> PathBuf {
    root.join("assets").join("characters").join(id)
}

fn asset_folder(char_root: &Path, kind: &AssetKind) -> PathBuf {
    match kind {
        AssetKind::Portrait => char_root.join("portrait"),
        AssetKind::Background => char_root.join("background"),
        AssetKind::Font => char_root.join("fonts"),
        AssetKind::DialogBox => char_root.to_path_buf(),
    }
}

fn allowed_asset_extension(kind: &AssetKind, ext: &str) -> bool {
    let ext = ext.to_ascii_lowercase();
    match kind {
        AssetKind::Portrait | AssetKind::Background | AssetKind::DialogBox => {
            matches!(ext.as_str(), "png" | "jpg" | "jpeg")
        }
        AssetKind::Font => matches!(ext.as_str(), "ttf" | "otf"),
    }
}

fn unique_asset_name(folder: &Path, original: &str) -> String {
    let path = Path::new(original);
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("asset");
    let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("");
    let mut candidate = if ext.is_empty() {
        stem.to_string()
    } else {
        format!("{stem}.{ext}")
    };
    let mut index = 1;
    while folder.join(&candidate).exists() {
        candidate = if ext.is_empty() {
            format!("{stem}_{index}")
        } else {
            format!("{stem}_{index}.{ext}")
        };
        index += 1;
    }
    candidate
}

fn image_files(path: &Path) -> Vec<String> {
    let Ok(entries) = fs::read_dir(path) else {
        return Vec::new();
    };
    let mut files = entries
        .flatten()
        .filter_map(|entry| {
            let path = entry.path();
            let ext = path.extension()?.to_string_lossy().to_lowercase();
            matches!(ext.as_str(), "png" | "jpg" | "jpeg")
                .then(|| entry.file_name().to_string_lossy().to_string())
        })
        .collect::<Vec<_>>();
    files.sort_by(|a, b| natord::compare(a, b));
    files
}

fn font_files(path: &Path) -> Vec<String> {
    let Ok(entries) = fs::read_dir(path) else {
        return Vec::new();
    };
    let mut files = entries
        .flatten()
        .filter_map(|entry| {
            let path = entry.path();
            let ext = path.extension()?.to_string_lossy().to_lowercase();
            matches!(ext.as_str(), "ttf" | "otf")
                .then(|| entry.file_name().to_string_lossy().to_string())
        })
        .collect::<Vec<_>>();
    files.sort();
    files
}

fn load_character_config(path: &Path) -> Result<CharacterConfig, AppError> {
    let yaml_path = path.join("config.yaml");
    let json_path = path.join("config.json");
    if yaml_path.exists() {
        let raw = fs::read_to_string(yaml_path)?;
        let mut value: Value = serde_yaml::from_str(&raw)?;
        normalize_character_value(&mut value);
        Ok(serde_yaml::from_value(value)?)
    } else if json_path.exists() {
        let raw = fs::read_to_string(json_path)?;
        let json_value = serde_json::from_str::<serde_json::Value>(&raw)?;
        let mut value: Value = serde_yaml::to_value(json_value)?;
        normalize_character_value(&mut value);
        Ok(serde_yaml::from_value(value)?)
    } else {
        Ok(CharacterConfig::default())
    }
}

fn normalize_character_value(value: &mut Value) {
    let Value::Mapping(root) = value else {
        *value = Value::Mapping(Mapping::new());
        let Value::Mapping(root) = value else { return };
        ensure_character_sections(root);
        return;
    };
    ensure_character_sections(root);
}

fn ensure_character_sections(root: &mut Mapping) {
    let meta_key = Value::String("meta".to_string());
    let style_key = Value::String("style".to_string());
    let layout_key = Value::String("layout".to_string());
    let assets_key = Value::String("assets".to_string());

    root.entry(meta_key)
        .or_insert_with(|| serde_yaml::to_value(MetaConfig::default()).unwrap());
    root.entry(style_key.clone())
        .or_insert_with(|| serde_yaml::to_value(StyleConfig::default()).unwrap());
    root.entry(layout_key.clone())
        .or_insert_with(|| serde_yaml::to_value(LayoutConfig::default()).unwrap());
    root.entry(assets_key)
        .or_insert_with(|| serde_yaml::to_value(AssetsConfig::default()).unwrap());

    if let Some(Value::Mapping(style)) = root.get_mut(&style_key) {
        style
            .entry(Value::String("mode".to_string()))
            .or_insert(Value::String("basic".to_string()));
        style
            .entry(Value::String("text_wrapper".to_string()))
            .or_insert_with(|| serde_yaml::to_value(TextWrapper::default()).unwrap());
        style
            .entry(Value::String("basic".to_string()))
            .or_insert_with(|| serde_yaml::to_value(BasicStyle::default()).unwrap());
        style
            .entry(Value::String("advanced".to_string()))
            .or_insert_with(|| serde_yaml::to_value(AdvancedStyle::default()).unwrap());
    }

    if let Some(Value::Mapping(layout)) = root.get_mut(&layout_key) {
        let default = serde_yaml::to_value(LayoutConfig::default()).unwrap();
        let Value::Mapping(default_layout) = default else {
            return;
        };
        for (key, fallback) in default_layout {
            layout.entry(key).or_insert(fallback);
        }
    }
}

fn resolve_first_file(folder: &Path, allowed: &[&str]) -> Option<PathBuf> {
    let mut files = fs::read_dir(folder)
        .ok()?
        .flatten()
        .filter_map(|entry| {
            let path = entry.path();
            let ext = path.extension()?.to_string_lossy().to_lowercase();
            allowed.contains(&ext.as_str()).then_some(path)
        })
        .collect::<Vec<_>>();
    files.sort_by(|a, b| a.file_name().cmp(&b.file_name()));
    files.into_iter().next()
}

fn resolve_background_path(
    root: &Path,
    char_id: &str,
    config: &CharacterConfig,
) -> Option<PathBuf> {
    let char_root = character_root(root, char_id);
    let current = config.layout.current_background.trim();
    let canvas = config.layout.canvas_size;
    if !current.is_empty() {
        let current_path = Path::new(current);
        let stem = current_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(current);
        let ext = current_path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("png");
        let scaled = root
            .join("assets")
            .join("pre_scaled")
            .join("characters")
            .join(char_id)
            .join("background")
            .join(format!("{stem}@{}x{}.{}", canvas[0], canvas[1], ext));
        if scaled.is_file() {
            return Some(scaled);
        }
        let char_bg = char_root.join("background").join(current);
        if char_bg.is_file() {
            return Some(char_bg);
        }
        let common_bg = root
            .join("assets")
            .join("common")
            .join("background")
            .join(current);
        if common_bg.is_file() {
            return Some(common_bg);
        }
    }
    resolve_first_file(&char_root.join("background"), &["png", "jpg", "jpeg"]).or_else(|| {
        resolve_first_file(
            &root.join("assets").join("common").join("background"),
            &["png", "jpg", "jpeg"],
        )
    })
}

fn resolve_portrait_path(root: &Path, char_id: &str, config: &CharacterConfig) -> Option<PathBuf> {
    let folder = character_root(root, char_id).join("portrait");
    let current = config.layout.current_portrait.trim();
    if !current.is_empty() {
        let path = folder.join(current);
        if path.is_file() {
            return Some(path);
        }
    }
    resolve_first_file(&folder, &["png", "jpg", "jpeg"])
}

fn resolve_font_path(
    root: &Path,
    _char_id: &str,
    char_root: &Path,
    font_file: Option<&str>,
) -> Option<PathBuf> {
    if let Some(font_file) = font_file.filter(|s| !s.trim().is_empty()) {
        let raw = Path::new(font_file);
        if raw.is_absolute() && raw.is_file() {
            return Some(raw.to_path_buf());
        }
        let in_char = char_root.join(font_file);
        if in_char.is_file() {
            return Some(in_char);
        }
        let in_common = root
            .join("assets")
            .join("common")
            .join("fonts")
            .join(font_file);
        if in_common.is_file() {
            return Some(in_common);
        }
    }
    resolve_first_file(&char_root.join("fonts"), &["ttf", "otf"])
        .or_else(|| {
            Some(
                root.join("assets")
                    .join("common")
                    .join("fonts")
                    .join("LXGWWenKai-Medium.ttf"),
            )
            .filter(|p| p.is_file())
        })
        .or_else(|| {
            resolve_first_file(
                &root.join("assets").join("common").join("fonts"),
                &["ttf", "otf"],
            )
        })
}

fn load_rgba(path: &Path) -> Result<RgbaImage, AppError> {
    Ok(image::open(path)?.to_rgba8())
}

fn resize_rgba(img: &RgbaImage, width: u32, height: u32) -> RgbaImage {
    DynamicImage::ImageRgba8(img.clone())
        .resize_exact(width, height, imageops::FilterType::Lanczos3)
        .to_rgba8()
}

fn overlay_rgba(canvas: &mut RgbaImage, image: &RgbaImage, x: i32, y: i32) {
    imageops::overlay(canvas, image, i64::from(x), i64::from(y));
}

fn rgba(color: [u8; 3]) -> Rgba<u8> {
    Rgba([color[0], color[1], color[2], 255])
}

fn clamp_rect(rect: [i32; 4], width: u32, height: u32) -> [u32; 4] {
    let max_x = width as i32;
    let max_y = height as i32;
    let x1 = rect[0].clamp(0, max_x.saturating_sub(1)) as u32;
    let y1 = rect[1].clamp(0, max_y.saturating_sub(1)) as u32;
    let x2 = rect[2].clamp((x1 + 1) as i32, max_x) as u32;
    let y2 = rect[3].clamp((y1 + 1) as i32, max_y) as u32;
    [x1, y1, x2, y2]
}

fn wrap_text(text: &str, font_size: u32, max_width: u32) -> Vec<String> {
    let mut lines = Vec::new();
    let char_width = (font_size as f32 * 0.9).max(1.0);
    let max_chars = ((max_width as f32 / char_width).floor() as usize).max(1);
    for paragraph in text.split('\n') {
        let mut line = String::new();
        for ch in paragraph.chars() {
            if line.chars().count() >= max_chars {
                lines.push(line);
                line = String::new();
            }
            line.push(ch);
        }
        lines.push(line);
    }
    lines
}

fn apply_text_wrapper(text: &str, wrapper: &TextWrapper) -> String {
    if wrapper.wrapper_type == "none" || (wrapper.prefix.is_empty() && wrapper.suffix.is_empty()) {
        return text.to_string();
    }
    format!("{}{}{}", wrapper.prefix, text, wrapper.suffix)
}

fn load_font_arc(path: &Path) -> Result<FontArc, AppError> {
    FontArc::try_from_vec(fs::read(path)?)
        .map_err(|_| AppError::InvalidInput(format!("Failed to load font: {}", path.display())))
}

fn draw_basic_name(canvas: &mut RgbaImage, font: &FontArc, config: &CharacterConfig, name: &str) {
    if name.is_empty() {
        return;
    }
    let basic = &config.style.basic;
    draw_text_mut(
        canvas,
        rgba(basic.name_color),
        config.layout.name_pos[0],
        config.layout.name_pos[1],
        PxScale::from(basic.name_font_size as f32),
        font,
        name,
    );
}

fn draw_advanced_name(
    canvas: &mut RgbaImage,
    root: &Path,
    char_id: &str,
    char_root: &Path,
    fallback_font: &FontArc,
    config: &CharacterConfig,
    name: &str,
) -> Result<bool, AppError> {
    if !config.style.mode.eq_ignore_ascii_case("advanced") {
        return Ok(false);
    }
    let layers = config
        .style
        .advanced
        .name_layers
        .get(name)
        .or_else(|| config.style.advanced.name_layers.get("default"));
    let Some(layers) = layers else {
        return Ok(false);
    };
    if layers.is_empty() {
        return Ok(false);
    }

    let base_x = config.layout.name_pos[0];
    let base_y = config.layout.name_pos[1];
    let mut rendered = false;
    for layer in layers {
        let text = layer.text.replace("{name}", name);
        if text.is_empty() {
            continue;
        }
        let font = if let Some(font_path) =
            resolve_font_path(root, char_id, char_root, layer.font_file.as_deref())
        {
            load_font_arc(&font_path).unwrap_or_else(|_| fallback_font.clone())
        } else {
            fallback_font.clone()
        };
        draw_text_mut(
            canvas,
            rgba(layer.font_color),
            base_x + layer.position[0],
            base_y + layer.position[1],
            PxScale::from(layer.font_size as f32),
            &font,
            &text,
        );
        rendered = true;
    }
    Ok(rendered)
}

fn draw_dialogue_text(
    canvas: &mut RgbaImage,
    font: &FontArc,
    config: &CharacterConfig,
    text: &str,
) {
    let basic = &config.style.basic;
    let text_area = clamp_rect(
        config.layout.text_area,
        config.layout.canvas_size[0],
        config.layout.canvas_size[1],
    );
    let wrapped = apply_text_wrapper(text, &config.style.text_wrapper);
    let max_width = text_area[2].saturating_sub(text_area[0]);
    let line_height = basic.font_size as i32 + 6;
    for (idx, line) in wrap_text(&wrapped, basic.font_size, max_width)
        .iter()
        .enumerate()
    {
        let y = text_area[1] as i32 + idx as i32 * line_height;
        if y + line_height > text_area[3] as i32 {
            break;
        }
        draw_text_mut(
            canvas,
            rgba(basic.text_color),
            text_area[0] as i32,
            y,
            PxScale::from(basic.font_size as f32),
            font,
            line,
        );
    }
}

fn draw_text_layers(
    canvas: &mut RgbaImage,
    root: &Path,
    char_id: &str,
    char_root: &Path,
    config: &CharacterConfig,
    text: &str,
) -> Result<(), AppError> {
    let text_font_path =
        resolve_font_path(root, char_id, char_root, config.style.font_file.as_deref())
            .ok_or_else(|| AppError::AssetNotFound("No usable font was found".to_string()))?;
    let text_font = load_font_arc(&text_font_path)?;
    let name_font = if let Some(name_font_path) = resolve_font_path(
        root,
        char_id,
        char_root,
        config.style.name_font_file.as_deref(),
    ) {
        load_font_arc(&name_font_path).unwrap_or_else(|_| text_font.clone())
    } else {
        text_font.clone()
    };
    let name = config.meta.name.as_deref().unwrap_or("Character");
    let advanced_drawn =
        draw_advanced_name(canvas, root, char_id, char_root, &name_font, config, name)?;
    if !advanced_drawn {
        draw_basic_name(canvas, &name_font, config, name);
    }
    draw_dialogue_text(canvas, &text_font, config, text);
    Ok(())
}

fn render_engine_output(
    id: &str,
    mut config: CharacterConfig,
    selected_portrait: Option<String>,
    text: &str,
) -> Result<RenderPreviewResult, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id.to_string()));
    }
    if let Some(portrait) = selected_portrait.filter(|value| !value.trim().is_empty()) {
        config.layout.current_portrait = portrait;
    }
    let rendered = render_preview_image(&root, id, &config, text)?;
    let output_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("engine");
    fs::create_dir_all(&output_dir)?;
    let path = output_dir.join(format!("{}_last.png", sanitize_character_id(id)?));
    let width = rendered.width();
    let height = rendered.height();
    rendered.save(&path)?;
    Ok(RenderPreviewResult {
        path: path.to_string_lossy().to_string(),
        width,
        height,
    })
}

fn write_u16_le(out: &mut Vec<u8>, value: u16) {
    out.extend_from_slice(&value.to_le_bytes());
}

fn write_u32_le(out: &mut Vec<u8>, value: u32) {
    out.extend_from_slice(&value.to_le_bytes());
}

fn write_i32_le(out: &mut Vec<u8>, value: i32) {
    out.extend_from_slice(&value.to_le_bytes());
}

fn encode_png_bytes(img: &RgbaImage) -> Result<Vec<u8>, AppError> {
    let mut cursor = Cursor::new(Vec::new());
    DynamicImage::ImageRgba8(img.clone()).write_to(&mut cursor, ImageFormat::Png)?;
    Ok(cursor.into_inner())
}

fn rgba_to_cf_dib_bytes(img: &RgbaImage) -> Result<Vec<u8>, AppError> {
    let width = i32::try_from(img.width())
        .map_err(|_| AppError::Clipboard("Image width is too large for a DIB".to_string()))?;
    let height = i32::try_from(img.height())
        .map_err(|_| AppError::Clipboard("Image height is too large for a DIB".to_string()))?;
    let pixel_bytes = u64::from(img.width())
        .checked_mul(u64::from(img.height()))
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or_else(|| {
            AppError::Clipboard("Image is too large for clipboard memory".to_string())
        })?;
    let pixel_bytes_u32 = u32::try_from(pixel_bytes)
        .map_err(|_| AppError::Clipboard("Image is too large for a DIB".to_string()))?;
    let capacity = 40usize.checked_add(pixel_bytes as usize).ok_or_else(|| {
        AppError::Clipboard("Image is too large for clipboard memory".to_string())
    })?;

    let mut out = Vec::with_capacity(capacity);
    write_u32_le(&mut out, 40);
    write_i32_le(&mut out, width);
    write_i32_le(&mut out, -height);
    write_u16_le(&mut out, 1);
    write_u16_le(&mut out, 32);
    write_u32_le(&mut out, 0);
    write_u32_le(&mut out, pixel_bytes_u32);
    write_i32_le(&mut out, 0);
    write_i32_le(&mut out, 0);
    write_u32_le(&mut out, 0);
    write_u32_le(&mut out, 0);

    for rgba in img.as_raw().chunks_exact(4) {
        out.extend_from_slice(&[rgba[2], rgba[1], rgba[0], rgba[3]]);
    }
    Ok(out)
}

#[cfg(target_os = "windows")]
struct ClipboardGuard;

#[cfg(target_os = "windows")]
impl Drop for ClipboardGuard {
    fn drop(&mut self) {
        unsafe {
            CloseClipboard();
        }
    }
}

#[cfg(target_os = "windows")]
unsafe fn alloc_global_bytes(bytes: &[u8]) -> Result<HGLOBAL, AppError> {
    let handle = GlobalAlloc(GMEM_MOVEABLE, bytes.len());
    if handle.is_null() {
        return Err(AppError::Clipboard("GlobalAlloc failed".to_string()));
    }
    let target = GlobalLock(handle);
    if target.is_null() {
        return Err(AppError::Clipboard("GlobalLock failed".to_string()));
    }
    std::ptr::copy_nonoverlapping(bytes.as_ptr(), target.cast::<u8>(), bytes.len());
    GlobalUnlock(handle);
    Ok(handle)
}

fn utf16le_clipboard_bytes(text: &str) -> Vec<u8> {
    text.encode_utf16()
        .chain(std::iter::once(0))
        .flat_map(u16::to_le_bytes)
        .collect()
}

#[cfg(target_os = "windows")]
fn get_clipboard_text() -> Result<String, AppError> {
    const CF_UNICODETEXT: u32 = 13;
    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return Err(AppError::Clipboard("OpenClipboard failed".to_string()));
        }
        let _guard = ClipboardGuard;
        if IsClipboardFormatAvailable(CF_UNICODETEXT) == 0 {
            return Ok(String::new());
        }
        let handle = GetClipboardData(CF_UNICODETEXT);
        if handle.is_null() {
            return Ok(String::new());
        }
        let ptr = GlobalLock(handle.cast());
        if ptr.is_null() {
            return Err(AppError::Clipboard(
                "GlobalLock clipboard text failed".to_string(),
            ));
        }
        let text_ptr = ptr.cast::<u16>();
        let mut len = 0usize;
        while *text_ptr.add(len) != 0 {
            len += 1;
        }
        let slice = std::slice::from_raw_parts(text_ptr, len);
        let text = String::from_utf16_lossy(slice);
        GlobalUnlock(handle.cast());
        Ok(text)
    }
}

#[cfg(not(target_os = "windows"))]
fn get_clipboard_text() -> Result<String, AppError> {
    Err(AppError::Clipboard(
        "Text clipboard input is currently implemented for Windows only".to_string(),
    ))
}

#[cfg(target_os = "windows")]
fn set_clipboard_text(text: &str) -> Result<(), AppError> {
    const CF_UNICODETEXT: u32 = 13;
    let bytes = utf16le_clipboard_bytes(text);
    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return Err(AppError::Clipboard("OpenClipboard failed".to_string()));
        }
        let _guard = ClipboardGuard;
        if EmptyClipboard() == 0 {
            return Err(AppError::Clipboard("EmptyClipboard failed".to_string()));
        }
        let handle = alloc_global_bytes(&bytes)?;
        if SetClipboardData(CF_UNICODETEXT, handle as HANDLE).is_null() {
            return Err(AppError::Clipboard(
                "SetClipboardData(CF_UNICODETEXT) failed".to_string(),
            ));
        }
        Ok(())
    }
}

#[cfg(not(target_os = "windows"))]
fn set_clipboard_text(_text: &str) -> Result<(), AppError> {
    Err(AppError::Clipboard(
        "Text clipboard output is currently implemented for Windows only".to_string(),
    ))
}

#[cfg(target_os = "windows")]
fn copy_image_to_clipboard(img: &RgbaImage) -> Result<Vec<String>, AppError> {
    const CF_DIB: u32 = 8;
    let dib = rgba_to_cf_dib_bytes(img)?;
    let png = encode_png_bytes(img)?;
    let mut formats = Vec::new();

    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return Err(AppError::Clipboard("OpenClipboard failed".to_string()));
        }
        let _guard = ClipboardGuard;
        if EmptyClipboard() == 0 {
            return Err(AppError::Clipboard("EmptyClipboard failed".to_string()));
        }

        let dib_handle = alloc_global_bytes(&dib)?;
        if SetClipboardData(CF_DIB, dib_handle as HANDLE).is_null() {
            return Err(AppError::Clipboard(
                "SetClipboardData(CF_DIB) failed".to_string(),
            ));
        }
        formats.push("CF_DIB".to_string());

        let png_name: Vec<u16> = "PNG".encode_utf16().chain(std::iter::once(0)).collect();
        let png_format = RegisterClipboardFormatW(png_name.as_ptr());
        if png_format != 0 {
            let png_handle = alloc_global_bytes(&png)?;
            if !SetClipboardData(png_format, png_handle as HANDLE).is_null() {
                formats.push("PNG".to_string());
            }
        }
    }

    Ok(formats)
}

#[cfg(not(target_os = "windows"))]
fn copy_image_to_clipboard(_img: &RgbaImage) -> Result<Vec<String>, AppError> {
    Err(AppError::Clipboard(
        "Image clipboard output is currently implemented for Windows only".to_string(),
    ))
}

fn render_base_image(
    root: &Path,
    char_id: &str,
    config: &CharacterConfig,
) -> Result<RgbaImage, AppError> {
    let char_root = character_root(root, char_id);
    let canvas_w = config.layout.canvas_size[0];
    let canvas_h = config.layout.canvas_size[1];
    let mut canvas = if let Some(bg_path) = resolve_background_path(root, char_id, config) {
        resize_rgba(&load_rgba(&bg_path)?, canvas_w, canvas_h)
    } else {
        RgbaImage::from_pixel(canvas_w, canvas_h, Rgba([24, 32, 42, 255]))
    };

    let dialog = char_root.join(&config.assets.dialog_box);
    let dialog_img = if dialog.is_file() {
        let box_img = load_rgba(&dialog)?;
        let new_h = ((box_img.height() as f32) * (canvas_w as f32 / box_img.width().max(1) as f32))
            .round()
            .max(1.0) as u32;
        Some(resize_rgba(&box_img, canvas_w, new_h))
    } else {
        None
    };

    let portrait_img = if let Some(portrait_path) = resolve_portrait_path(root, char_id, config) {
        let portrait = load_rgba(&portrait_path)?;
        let w = ((portrait.width() as f32) * config.layout.stand_scale)
            .round()
            .max(1.0) as u32;
        let h = ((portrait.height() as f32) * config.layout.stand_scale)
            .round()
            .max(1.0) as u32;
        Some(resize_rgba(&portrait, w, h))
    } else {
        None
    };

    if !config.layout.stand_on_top {
        if let Some(portrait) = &portrait_img {
            overlay_rgba(
                &mut canvas,
                portrait,
                config.layout.stand_pos[0],
                config.layout.stand_pos[1],
            );
        }
        if let Some(dialog) = &dialog_img {
            overlay_rgba(
                &mut canvas,
                dialog,
                0,
                canvas_h as i32 - dialog.height() as i32,
            );
        }
    } else {
        if let Some(dialog) = &dialog_img {
            overlay_rgba(
                &mut canvas,
                dialog,
                0,
                canvas_h as i32 - dialog.height() as i32,
            );
        }
        if let Some(portrait) = &portrait_img {
            overlay_rgba(
                &mut canvas,
                portrait,
                config.layout.stand_pos[0],
                config.layout.stand_pos[1],
            );
        }
    }

    Ok(canvas)
}

fn render_preview_image(
    root: &Path,
    char_id: &str,
    config: &CharacterConfig,
    text: &str,
) -> Result<RgbaImage, AppError> {
    let char_root = character_root(root, char_id);
    let canvas_w = config.layout.canvas_size[0];
    let canvas_h = config.layout.canvas_size[1];
    let mut canvas = if let Some(bg_path) = resolve_background_path(root, char_id, config) {
        resize_rgba(&load_rgba(&bg_path)?, canvas_w, canvas_h)
    } else {
        RgbaImage::from_pixel(canvas_w, canvas_h, Rgba([24, 32, 42, 255]))
    };

    let dialog = char_root.join(&config.assets.dialog_box);
    let dialog_img = if dialog.is_file() {
        let box_img = load_rgba(&dialog)?;
        let new_h = ((box_img.height() as f32) * (canvas_w as f32 / box_img.width().max(1) as f32))
            .round()
            .max(1.0) as u32;
        Some(resize_rgba(&box_img, canvas_w, new_h))
    } else {
        None
    };

    let portrait_img = if let Some(portrait_path) = resolve_portrait_path(root, char_id, config) {
        let portrait = load_rgba(&portrait_path)?;
        let w = ((portrait.width() as f32) * config.layout.stand_scale)
            .round()
            .max(1.0) as u32;
        let h = ((portrait.height() as f32) * config.layout.stand_scale)
            .round()
            .max(1.0) as u32;
        Some(resize_rgba(&portrait, w, h))
    } else {
        None
    };

    if !config.layout.stand_on_top {
        if let Some(portrait) = &portrait_img {
            overlay_rgba(
                &mut canvas,
                portrait,
                config.layout.stand_pos[0],
                config.layout.stand_pos[1],
            );
        }
        if let Some(dialog) = &dialog_img {
            overlay_rgba(
                &mut canvas,
                dialog,
                0,
                canvas_h as i32 - dialog.height() as i32,
            );
        }
    } else {
        if let Some(dialog) = &dialog_img {
            overlay_rgba(
                &mut canvas,
                dialog,
                0,
                canvas_h as i32 - dialog.height() as i32,
            );
        }
        if let Some(portrait) = &portrait_img {
            overlay_rgba(
                &mut canvas,
                portrait,
                config.layout.stand_pos[0],
                config.layout.stand_pos[1],
            );
        }
    }

    draw_text_layers(&mut canvas, root, char_id, &char_root, config, text)?;

    if config.layout.enable_crop {
        if let Some(crop) = config.layout.crop_area {
            let [x1, y1, x2, y2] = clamp_rect(crop, canvas.width(), canvas.height());
            canvas = imageops::crop_imm(&canvas, x1, y1, x2 - x1, y2 - y1).to_image();
        }
    }

    Ok(canvas)
}

#[tauri::command]
fn engine_status(state: tauri::State<'_, Mutex<EngineState>>) -> Result<EngineStatus, AppError> {
    Ok(lock_engine_state(&state)?.status())
}

#[tauri::command]
fn start_engine(
    app: tauri::AppHandle,
    id: String,
    config: CharacterConfig,
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<EngineStatus, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let global = load_global_config()?;
    let portraits = image_files(&char_root.join("portrait"));
    let (previous_hotkey, previous_aux) = {
        let engine = lock_engine_state(&state)?;
        (
            engine.registered_hotkey.clone(),
            engine.registered_aux_hotkeys.clone(),
        )
    };
    let (registered_hotkey, registered_aux_hotkeys) =
        register_engine_hotkeys(&app, &global.trigger_hotkey, previous_hotkey, previous_aux)?;
    let mut engine = lock_engine_state(&state)?;
    engine.running = true;
    engine.paused = false;
    engine.character_id = Some(id);
    engine.current_portrait = (!config.layout.current_portrait.trim().is_empty())
        .then(|| config.layout.current_portrait.clone())
        .or_else(|| portraits.first().cloned());
    if let Some(portrait) = engine.current_portrait.clone() {
        let mut runtime_config = config;
        runtime_config.layout.current_portrait = portrait;
        engine.current_config = Some(runtime_config);
    } else {
        engine.current_config = Some(config);
    }
    engine.portrait_assets = portraits;
    engine.trigger_hotkey = global.trigger_hotkey;
    engine.registered_hotkey = registered_hotkey;
    engine.registered_aux_hotkeys = registered_aux_hotkeys;
    engine.last_action = Some("engine_started".to_string());
    engine.last_error = None;
    Ok(engine.status())
}

#[tauri::command]
fn stop_engine(
    app: tauri::AppHandle,
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<EngineStatus, AppError> {
    let (previous_hotkey, previous_aux) = {
        let engine = lock_engine_state(&state)?;
        (
            engine.registered_hotkey.clone(),
            engine.registered_aux_hotkeys.clone(),
        )
    };
    unregister_engine_hotkeys(&app, previous_hotkey, previous_aux);
    let mut engine = lock_engine_state(&state)?;
    engine.running = false;
    engine.paused = false;
    engine.registered_hotkey = None;
    engine.registered_aux_hotkeys.clear();
    engine.last_action = Some("engine_stopped".to_string());
    engine.last_error = None;
    Ok(engine.status())
}

#[tauri::command]
fn toggle_engine_pause(
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<EngineStatus, AppError> {
    toggle_engine_pause_state(state.inner())?;
    Ok(lock_engine_state(&state)?.status())
}

#[tauri::command]
fn refresh_engine_hotkey(
    app: tauri::AppHandle,
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<EngineStatus, AppError> {
    reload_engine_config_and_hotkeys(&app, state.inner())?;
    Ok(lock_engine_state(&state)?.status())
}

#[tauri::command]
fn set_engine_portrait(
    filename: String,
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<EngineStatus, AppError> {
    let safe_name = Path::new(&filename)
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| AppError::InvalidInput("Invalid portrait filename".to_string()))?;
    let mut engine = lock_engine_state(&state)?;
    engine.current_portrait = Some(safe_name.to_string());
    if let Some(config) = engine.current_config.as_mut() {
        config.layout.current_portrait = safe_name.to_string();
    }
    engine.last_action = Some(format!("expression_set:{safe_name}"));
    Ok(engine.status())
}

#[tauri::command]
fn render_engine_text(
    id: String,
    config: CharacterConfig,
    text: String,
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<RenderPreviewResult, AppError> {
    let selected_portrait = {
        let engine = lock_engine_state(&state)?;
        if engine.running && engine.character_id.as_deref() == Some(id.as_str()) {
            engine.current_portrait.clone()
        } else {
            None
        }
    };

    let result = render_engine_output(&id, config.clone(), selected_portrait, &text);

    let mut engine = lock_engine_state(&state)?;
    match &result {
        Ok(rendered) => {
            engine.running = true;
            engine.paused = false;
            engine.character_id = Some(id);
            engine.current_config = Some(config);
            engine.last_output_path = Some(rendered.path.clone());
            engine.last_captured_text = Some(text);
            engine.last_action = Some("manual_render".to_string());
            engine.last_error = None;
        }
        Err(error) => {
            engine.last_error = Some(error.to_string());
        }
    }
    result
}

#[cfg(target_os = "windows")]
fn keyboard_input(vk: VIRTUAL_KEY, flags: u32) -> INPUT {
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: vk,
                wScan: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    }
}

#[cfg(target_os = "windows")]
fn send_ctrl_combo(vk: VIRTUAL_KEY) -> Result<(), AppError> {
    let mut inputs = [
        keyboard_input(VK_CONTROL, 0),
        keyboard_input(vk, 0),
        keyboard_input(vk, KEYEVENTF_KEYUP),
        keyboard_input(VK_CONTROL, KEYEVENTF_KEYUP),
    ];
    let sent = unsafe {
        SendInput(
            inputs.len() as u32,
            inputs.as_mut_ptr(),
            std::mem::size_of::<INPUT>() as i32,
        )
    };
    if sent != inputs.len() as u32 {
        return Err(AppError::Clipboard(format!(
            "SendInput sent {sent}/{} keyboard events",
            inputs.len()
        )));
    }
    Ok(())
}

#[cfg(not(target_os = "windows"))]
fn send_ctrl_combo(_vk: u16) -> Result<(), AppError> {
    Err(AppError::Clipboard(
        "Keyboard automation is currently implemented for Windows only".to_string(),
    ))
}

#[cfg(target_os = "windows")]
fn send_ctrl_a() -> Result<(), AppError> {
    send_ctrl_combo(VK_A)
}

#[cfg(not(target_os = "windows"))]
fn send_ctrl_a() -> Result<(), AppError> {
    send_ctrl_combo(0)
}

#[cfg(target_os = "windows")]
fn send_ctrl_x() -> Result<(), AppError> {
    send_ctrl_combo(VK_X)
}

#[cfg(not(target_os = "windows"))]
fn send_ctrl_x() -> Result<(), AppError> {
    send_ctrl_combo(0)
}

#[cfg(target_os = "windows")]
fn send_ctrl_v() -> Result<(), AppError> {
    send_ctrl_combo(VK_V)
}

#[cfg(not(target_os = "windows"))]
fn send_ctrl_v() -> Result<(), AppError> {
    Err(AppError::Clipboard(
        "Paste automation is currently implemented for Windows only".to_string(),
    ))
}

fn switch_engine_expression(state: &Mutex<EngineState>, index: usize) -> Result<(), AppError> {
    let mut engine = state
        .lock()
        .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
    if !engine.running {
        return Err(AppError::InvalidInput("Engine is not running".to_string()));
    }
    let Some(portrait) = index
        .checked_sub(1)
        .and_then(|idx| engine.portrait_assets.get(idx).cloned())
    else {
        engine.last_action = Some(format!("expression_out_of_range:{index}"));
        engine.last_error = None;
        return Ok(());
    };
    engine.current_portrait = Some(portrait.clone());
    if let Some(config) = engine.current_config.as_mut() {
        config.layout.current_portrait = portrait.clone();
    }
    engine.last_action = Some(format!("expression_switched:{index}:{portrait}"));
    engine.last_error = None;
    Ok(())
}

fn toggle_engine_pause_state(state: &Mutex<EngineState>) -> Result<(), AppError> {
    let mut engine = state
        .lock()
        .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
    if engine.running {
        engine.paused = !engine.paused;
        engine.last_action = Some(
            if engine.paused {
                "engine_paused"
            } else {
                "engine_resumed"
            }
            .to_string(),
        );
        engine.last_error = None;
    }
    Ok(())
}

fn reload_engine_config_and_hotkeys(
    app: &tauri::AppHandle,
    state: &Mutex<EngineState>,
) -> Result<(), AppError> {
    let global = load_global_config()?;
    let (id, previous_hotkey, previous_aux, selected_portrait) = {
        let engine = state
            .lock()
            .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
        (
            engine.character_id.clone(),
            engine.registered_hotkey.clone(),
            engine.registered_aux_hotkeys.clone(),
            engine.current_portrait.clone(),
        )
    };
    let (registered_hotkey, registered_aux_hotkeys) =
        register_engine_hotkeys(app, &global.trigger_hotkey, previous_hotkey, previous_aux)?;

    let mut loaded_config = None;
    let mut portraits = Vec::new();
    if let Some(id) = id.as_deref() {
        let root = project_root()?;
        let char_root = character_root(&root, id);
        if char_root.is_dir() {
            let mut config = load_character_config(&char_root)?;
            portraits = image_files(&char_root.join("portrait"));
            let portrait = selected_portrait
                .filter(|portrait| portraits.contains(portrait))
                .or_else(|| {
                    (!config.layout.current_portrait.trim().is_empty())
                        .then(|| config.layout.current_portrait.clone())
                })
                .or_else(|| portraits.first().cloned());
            if let Some(portrait) = portrait {
                config.layout.current_portrait = portrait;
            }
            loaded_config = Some(config);
        }
    }

    let mut engine = state
        .lock()
        .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
    engine.trigger_hotkey = global.trigger_hotkey;
    engine.registered_hotkey = registered_hotkey;
    engine.registered_aux_hotkeys = registered_aux_hotkeys;
    if let Some(config) = loaded_config {
        engine.current_portrait = (!config.layout.current_portrait.trim().is_empty())
            .then(|| config.layout.current_portrait.clone());
        engine.current_config = Some(config);
        engine.portrait_assets = portraits;
    }
    engine.last_action = Some("config_reloaded".to_string());
    engine.last_error = None;
    Ok(())
}

fn handle_engine_shortcut(
    app: tauri::AppHandle,
    shortcut: String,
    state: &Mutex<EngineState>,
) -> Result<(), AppError> {
    let action = {
        let mut engine = state
            .lock()
            .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
        engine.shortcut_hits = engine.shortcut_hits.saturating_add(1);
        classify_engine_shortcut(&engine, &shortcut)
    };

    match action {
        EngineShortcutAction::Trigger => {
            run_engine_hotkey_pipeline(state)?;
        }
        EngineShortcutAction::Expression(index) => {
            switch_engine_expression(state, index)?;
        }
        EngineShortcutAction::TogglePause => {
            toggle_engine_pause_state(state)?;
        }
        EngineShortcutAction::ReloadConfig => {
            reload_engine_config_and_hotkeys(&app, state)?;
        }
        EngineShortcutAction::Ignore => {
            let mut engine = state
                .lock()
                .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
            engine.last_action = Some(format!("shortcut_ignored:{shortcut}"));
        }
    }
    Ok(())
}

fn capture_active_input_text() -> Result<Option<String>, AppError> {
    send_ctrl_a()?;
    thread::sleep(Duration::from_millis(50));
    send_ctrl_x()?;
    thread::sleep(Duration::from_millis(100));
    let text = get_clipboard_text()?.trim().to_string();
    if text.is_empty() {
        let _ = send_ctrl_v();
        return Ok(None);
    }
    Ok(Some(text))
}

fn run_engine_hotkey_pipeline(state: &Mutex<EngineState>) -> Result<RenderPreviewResult, AppError> {
    let (id, config, selected_portrait) = {
        let engine = state
            .lock()
            .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
        if !engine.running {
            return Err(AppError::InvalidInput("Engine is not running".to_string()));
        }
        if engine.paused {
            return Err(AppError::InvalidInput("Engine is paused".to_string()));
        }
        let id = engine
            .character_id
            .clone()
            .ok_or_else(|| AppError::InvalidInput("Engine has no active character".to_string()))?;
        let config = engine.current_config.clone().ok_or_else(|| {
            AppError::InvalidInput("Engine has no active character config".to_string())
        })?;
        (id, config, engine.current_portrait.clone())
    };

    let Some(text) = capture_active_input_text()? else {
        let mut engine = state
            .lock()
            .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
        engine.last_action = Some("capture_empty_restored".to_string());
        engine.last_error = None;
        return Err(AppError::InvalidInput(
            "No text was captured from the active input".to_string(),
        ));
    };

    let result = match render_engine_output(&id, config, selected_portrait, &text) {
        Ok(result) => result,
        Err(error) => {
            let _ = set_clipboard_text(&text).and_then(|_| send_ctrl_v());
            let mut engine = state
                .lock()
                .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
            engine.last_captured_text = Some(text);
            engine.last_action = Some("render_failed_text_restored".to_string());
            engine.last_error = Some(error.to_string());
            return Err(error);
        }
    };

    let image = load_rgba(&PathBuf::from(&result.path))?;
    copy_image_to_clipboard(&image)?;
    thread::sleep(Duration::from_millis(100));
    send_ctrl_v()?;

    let mut engine = state
        .lock()
        .map_err(|_| AppError::InvalidInput("Engine state lock failed".to_string()))?;
    engine.last_output_path = Some(result.path.clone());
    engine.last_captured_text = Some(text);
    engine.last_action = Some("captured_rendered_copied_pasted".to_string());
    engine.last_error = None;
    Ok(result)
}

#[tauri::command]
fn run_engine_once(
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<RenderPreviewResult, AppError> {
    run_engine_hotkey_pipeline(state.inner())
}

#[tauri::command]
fn copy_engine_output_to_clipboard(
    state: tauri::State<'_, Mutex<EngineState>>,
) -> Result<ClipboardResult, AppError> {
    let path = {
        let engine = lock_engine_state(&state)?;
        engine.last_output_path.clone().ok_or_else(|| {
            AppError::Clipboard("No engine output has been rendered yet".to_string())
        })?
    };
    let img = load_rgba(&PathBuf::from(&path))?;
    let formats = copy_image_to_clipboard(&img)?;
    Ok(ClipboardResult {
        path,
        width: img.width(),
        height: img.height(),
        formats,
    })
}

#[tauri::command]
fn paste_clipboard_to_active_window() -> Result<(), AppError> {
    send_ctrl_v()
}

#[tauri::command]
fn load_global_config() -> Result<GlobalConfig, AppError> {
    let root = project_root()?;
    read_yaml(&root.join("global_config.yaml"))
}

#[tauri::command]
fn save_global_config(config: GlobalConfig) -> Result<(), AppError> {
    let root = project_root()?;
    write_yaml(&root.join("global_config.yaml"), &config)
}

#[tauri::command]
fn list_characters() -> Result<Vec<CharacterSummary>, AppError> {
    let root = project_root()?;
    let chars_root = root.join("assets").join("characters");
    let mut items = Vec::new();
    for entry in fs::read_dir(chars_root)?.flatten() {
        if !entry.path().is_dir() {
            continue;
        }
        let id = entry.file_name().to_string_lossy().to_string();
        let config = load_character_config(&entry.path()).unwrap_or_default();
        let name = config.meta.name.unwrap_or_else(|| id.clone());
        items.push(CharacterSummary {
            id,
            name,
            portrait_count: image_files(&entry.path().join("portrait")).len(),
            background_count: image_files(&entry.path().join("background")).len(),
        });
    }
    items.sort_by(|a, b| a.id.cmp(&b.id));
    Ok(items)
}

#[tauri::command]
fn load_character(id: String) -> Result<CharacterBundle, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let config = load_character_config(&char_root)?;
    let dialog_box_exists = char_root.join(&config.assets.dialog_box).exists();
    Ok(CharacterBundle {
        id,
        config,
        portraits: image_files(&char_root.join("portrait")),
        backgrounds: image_files(&char_root.join("background")),
        fonts: font_files(&char_root.join("fonts")),
        dialog_box_exists,
    })
}

#[tauri::command]
fn save_character(id: String, config: CharacterConfig) -> Result<(), AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    write_yaml(&char_root.join("config.yaml"), &config)
}

#[tauri::command]
fn create_character(id: String, display_name: String) -> Result<CharacterBundle, AppError> {
    let root = project_root()?;
    let id = sanitize_character_id(&id)?;
    let char_root = character_root(&root, &id);
    if char_root.exists() {
        return Err(AppError::InvalidInput(format!(
            "Character already exists: {id}"
        )));
    }
    fs::create_dir_all(char_root.join("portrait"))?;
    fs::create_dir_all(char_root.join("background"))?;
    fs::create_dir_all(char_root.join("fonts"))?;

    let mut config = CharacterConfig::default();
    config.meta.id = Some(id.clone());
    config.meta.name = Some(if display_name.trim().is_empty() {
        id.clone()
    } else {
        display_name.trim().to_string()
    });
    write_yaml(&char_root.join("config.yaml"), &config)?;
    load_character(id)
}

#[tauri::command]
fn pick_asset_file(kind: AssetKind) -> Result<Option<String>, AppError> {
    pick_file_with_windows_dialog(&kind)
}

#[tauri::command]
fn import_asset(
    id: String,
    kind: AssetKind,
    source_path: String,
) -> Result<CharacterBundle, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let source = PathBuf::from(source_path.trim().trim_matches('"'));
    if !source.is_file() {
        return Err(AppError::AssetNotFound(source.display().to_string()));
    }
    let filename = source
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| AppError::InvalidInput("Cannot read asset filename".to_string()))?;
    let ext = source
        .extension()
        .and_then(|ext| ext.to_str())
        .ok_or_else(|| AppError::InvalidInput("Asset file is missing an extension".to_string()))?;
    if !allowed_asset_extension(&kind, ext) {
        return Err(AppError::InvalidInput(format!(
            "Unsupported asset extension: .{ext}"
        )));
    }

    let folder = asset_folder(&char_root, &kind);
    fs::create_dir_all(&folder)?;
    let target_name = match kind {
        AssetKind::DialogBox => "textbox_bg.png".to_string(),
        _ => unique_asset_name(&folder, filename),
    };
    fs::copy(&source, folder.join(&target_name))?;

    let mut config = load_character_config(&char_root)?;
    match kind {
        AssetKind::Portrait if config.layout.current_portrait.is_empty() => {
            config.layout.current_portrait = target_name;
        }
        AssetKind::Background if config.layout.current_background.is_empty() => {
            config.layout.current_background = target_name;
        }
        AssetKind::Font => {
            config.style.font_file = Some(format!("fonts/{target_name}"));
        }
        AssetKind::DialogBox => {
            config.assets.dialog_box = target_name;
        }
        _ => {}
    }
    write_yaml(&char_root.join("config.yaml"), &config)?;
    load_character(id)
}

#[tauri::command]
fn delete_asset(
    id: String,
    kind: AssetKind,
    filename: String,
) -> Result<CharacterBundle, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let safe_name = Path::new(&filename)
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| AppError::InvalidInput("Invalid asset filename".to_string()))?;
    let target = asset_folder(&char_root, &kind).join(safe_name);
    if !target.is_file() {
        return Err(AppError::AssetNotFound(target.display().to_string()));
    }
    fs::remove_file(&target)?;

    let mut config = load_character_config(&char_root)?;
    match kind {
        AssetKind::Portrait if config.layout.current_portrait == safe_name => {
            config.layout.current_portrait = image_files(&char_root.join("portrait"))
                .first()
                .cloned()
                .unwrap_or_default();
        }
        AssetKind::Background if config.layout.current_background == safe_name => {
            config.layout.current_background = image_files(&char_root.join("background"))
                .first()
                .cloned()
                .unwrap_or_default();
        }
        AssetKind::Font
            if config.style.font_file.as_deref() == Some(&format!("fonts/{safe_name}")) =>
        {
            config.style.font_file = None;
        }
        AssetKind::DialogBox if config.assets.dialog_box == safe_name => {
            config.assets.dialog_box = "textbox_bg.png".to_string();
        }
        _ => {}
    }
    write_yaml(&char_root.join("config.yaml"), &config)?;
    load_character(id)
}

fn cache_format(config: &GlobalConfig) -> (&'static str, &'static str, ImageFormat) {
    if config.render.cache_format.eq_ignore_ascii_case("png") {
        ("png", ".png", ImageFormat::Png)
    } else {
        ("jpeg", ".jpg", ImageFormat::Jpeg)
    }
}

fn save_cache_image(path: &Path, img: &RgbaImage, format: ImageFormat) -> Result<(), AppError> {
    match format {
        ImageFormat::Jpeg => DynamicImage::ImageRgba8(img.clone())
            .to_rgb8()
            .save_with_format(path, ImageFormat::Jpeg)?,
        ImageFormat::Png => {
            DynamicImage::ImageRgba8(img.clone()).save_with_format(path, ImageFormat::Png)?
        }
        other => DynamicImage::ImageRgba8(img.clone()).save_with_format(path, other)?,
    }
    Ok(())
}

fn file_stem_string(filename: &str) -> String {
    Path::new(filename)
        .file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or(filename)
        .to_string()
}

#[tauri::command]
fn build_cache(id: String, config: CharacterConfig) -> Result<BuildCacheResult, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let global = load_global_config()?;
    let (format_name, ext, image_format) = cache_format(&global);
    let portraits = image_files(&char_root.join("portrait"));
    let backgrounds = image_files(&char_root.join("background"));
    if portraits.is_empty() {
        return Err(AppError::AssetNotFound(
            "No portrait assets found".to_string(),
        ));
    }
    if backgrounds.is_empty() {
        return Err(AppError::AssetNotFound(
            "No background assets found".to_string(),
        ));
    }

    let cache_dir = root.join("assets").join("cache").join(&id);
    fs::create_dir_all(&cache_dir)?;
    let mut generated = 0usize;
    for portrait in portraits {
        for background in &backgrounds {
            let mut combo = config.clone();
            combo.layout.current_portrait = portrait.clone();
            combo.layout.current_background = background.clone();
            combo.layout.enable_crop = false;
            let img = render_base_image(&root, &id, &combo)?;
            let filename = format!(
                "p_{}__b_{}{}",
                file_stem_string(&portrait),
                file_stem_string(background),
                ext
            );
            save_cache_image(&cache_dir.join(filename), &img, image_format)?;
            generated += 1;
        }
    }

    Ok(BuildCacheResult {
        cache_dir: cache_dir.to_string_lossy().to_string(),
        generated,
        format: format_name.to_string(),
    })
}

#[tauri::command]
fn render_preview(
    id: String,
    config: CharacterConfig,
    text: String,
) -> Result<RenderPreviewResult, AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }
    let preview = render_preview_image(&root, &id, &config, &text)?;
    let preview_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("preview");
    fs::create_dir_all(&preview_dir)?;
    let path = preview_dir.join(format!("{}_preview.png", sanitize_character_id(&id)?));
    let width = preview.width();
    let height = preview.height();
    preview.save(&path)?;
    Ok(RenderPreviewResult {
        path: path.to_string_lossy().to_string(),
        width,
        height,
    })
}

#[tauri::command]
fn open_character_folder(id: String) -> Result<(), AppError> {
    let root = project_root()?;
    let char_root = character_root(&root, &id);
    if !char_root.is_dir() {
        return Err(AppError::CharacterNotFound(id));
    }

    #[cfg(target_os = "windows")]
    {
        Command::new("explorer").arg(&char_root).spawn()?;
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open").arg(&char_root).spawn()?;
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Command::new("xdg-open").arg(&char_root).spawn()?;
    }

    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(Mutex::new(EngineState::default()))
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        let app = app.clone();
                        let shortcut = shortcut.into_string();
                        thread::spawn(move || {
                            let state = app.state::<Mutex<EngineState>>();
                            if let Err(error) =
                                handle_engine_shortcut(app.clone(), shortcut, state.inner())
                            {
                                if let Ok(mut engine) = state.lock() {
                                    if engine.last_error.is_none() {
                                        engine.last_error = Some(error.to_string());
                                    }
                                }
                            }
                        });
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            load_global_config,
            save_global_config,
            list_characters,
            load_character,
            save_character,
            create_character,
            pick_asset_file,
            import_asset,
            delete_asset,
            build_cache,
            render_preview,
            open_character_folder,
            engine_status,
            start_engine,
            stop_engine,
            toggle_engine_pause,
            refresh_engine_hotkey,
            set_engine_portrait,
            render_engine_text,
            run_engine_once,
            copy_engine_output_to_clipboard,
            paste_clipboard_to_active_window
        ])
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

mod natord {
    use std::cmp::Ordering;

    pub fn compare(a: &str, b: &str) -> Ordering {
        a.to_lowercase().cmp(&b.to_lowercase())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn yuraa_advanced_name_layers_are_available() {
        let root = project_root().expect("project root should be discoverable");
        let char_root = character_root(&root, "yuraa");
        let config = load_character_config(&char_root).expect("yuraa config should load");
        let name = config
            .meta
            .name
            .as_deref()
            .expect("yuraa should have a display name");
        let layers = config
            .style
            .advanced
            .name_layers
            .get(name)
            .expect("yuraa should define character-specific name layers");
        assert!(layers.len() >= 4);
        assert_eq!(layers[0].position, [-25, -15]);
    }

    #[test]
    fn advanced_default_name_layer_draws_pixels() {
        let root = project_root().expect("project root should be discoverable");
        let char_root = character_root(&root, "yuraa");
        let font_path = resolve_font_path(&root, "yuraa", &char_root, Some("fonts/lolita.ttf"))
            .expect("test font should resolve");
        let fallback_font = load_font_arc(&font_path).expect("test font should load");
        let mut config = CharacterConfig::default();
        config.meta.name = Some("Layer Test".to_string());
        config.style.mode = "advanced".to_string();
        config.layout.name_pos = [8, 8];
        config.style.advanced.name_layers.insert(
            "default".to_string(),
            vec![NameLayer {
                text: "{name}".to_string(),
                position: [0, 0],
                font_color: [255, 0, 0],
                font_size: 24,
                font_file: Some("fonts/lolita.ttf".to_string()),
            }],
        );
        let mut canvas = RgbaImage::from_pixel(240, 80, Rgba([0, 0, 0, 0]));
        let rendered = draw_advanced_name(
            &mut canvas,
            &root,
            "yuraa",
            &char_root,
            &fallback_font,
            &config,
            "Layer Test",
        )
        .expect("advanced name drawing should not fail");
        assert!(rendered);
        assert!(canvas.pixels().any(|pixel| pixel[3] > 0));
    }

    #[test]
    fn builds_double_nul_dialog_filter() {
        let filter = asset_dialog_filter(&AssetKind::Font);
        assert_eq!(filter.last().copied(), Some(0));
        assert!(filter.len() >= 2 && filter[filter.len() - 2] == 0);
        let zero_count = filter.iter().filter(|value| **value == 0).count();
        assert!(zero_count >= 5);
    }

    #[test]
    fn auxiliary_hotkeys_parse_and_classify() {
        for shortcut in engine_aux_hotkeys() {
            assert!(
                shortcut
                    .parse::<tauri_plugin_global_shortcut::Shortcut>()
                    .is_ok(),
                "{shortcut} should parse"
            );
        }
        let mut engine = EngineState::default();
        engine.registered_hotkey = Some("Ctrl+Enter".to_string());
        engine.registered_aux_hotkeys = engine_aux_hotkeys();
        assert_eq!(
            classify_engine_shortcut(&engine, "Ctrl+Enter"),
            EngineShortcutAction::Trigger
        );
        assert_eq!(
            classify_engine_shortcut(&engine, "Alt+3"),
            EngineShortcutAction::Expression(3)
        );
        assert_eq!(
            classify_engine_shortcut(&engine, "Ctrl+F12"),
            EngineShortcutAction::TogglePause
        );
        assert_eq!(
            classify_engine_shortcut(&engine, "Ctrl+F5"),
            EngineShortcutAction::ReloadConfig
        );
    }

    #[test]
    fn switches_expression_by_one_based_index() {
        let state = Mutex::new(EngineState {
            running: true,
            portrait_assets: vec!["1.png".to_string(), "2.png".to_string()],
            current_config: Some(CharacterConfig::default()),
            ..EngineState::default()
        });
        switch_engine_expression(&state, 2).expect("expression switch should work");
        let engine = state.lock().unwrap();
        assert_eq!(engine.current_portrait.as_deref(), Some("2.png"));
        assert_eq!(
            engine
                .current_config
                .as_ref()
                .unwrap()
                .layout
                .current_portrait,
            "2.png"
        );
    }

    #[test]
    fn normalized_hotkey_is_parseable_by_tauri_plugin() {
        let shortcut = normalize_hotkey("ctrl+enter");
        let parsed = shortcut.parse::<tauri_plugin_global_shortcut::Shortcut>();
        assert!(
            parsed.is_ok(),
            "{shortcut} should parse as a global shortcut"
        );
    }

    #[test]
    fn encodes_clipboard_text_as_utf16le_nul_terminated() {
        assert_eq!(
            utf16le_clipboard_bytes("A\u{597d}"),
            vec![65, 0, 125, 89, 0, 0]
        );
    }

    #[test]
    fn normalizes_legacy_hotkey_strings() {
        assert_eq!(normalize_hotkey("ctrl+enter"), "Ctrl+Enter");
        assert_eq!(normalize_hotkey("CTRL + shift + v"), "Ctrl+Shift+V");
        assert_eq!(normalize_hotkey(""), "");
    }

    #[test]
    fn converts_rgba_to_top_down_cf_dib() {
        let mut img = RgbaImage::new(2, 1);
        img.put_pixel(0, 0, Rgba([10, 20, 30, 40]));
        img.put_pixel(1, 0, Rgba([50, 60, 70, 80]));
        let bytes = rgba_to_cf_dib_bytes(&img).expect("DIB conversion should work");
        assert_eq!(bytes.len(), 48);
        assert_eq!(&bytes[0..4], &40u32.to_le_bytes());
        assert_eq!(&bytes[4..8], &2i32.to_le_bytes());
        assert_eq!(&bytes[8..12], &(-1i32).to_le_bytes());
        assert_eq!(&bytes[14..16], &32u16.to_le_bytes());
        assert_eq!(&bytes[40..48], &[30, 20, 10, 40, 70, 60, 50, 80]);
    }

    #[test]
    fn default_engine_state_is_stopped() {
        let status = EngineState::default().status();
        assert!(!status.running);
        assert!(!status.paused);
        assert_eq!(status.trigger_hotkey, "ctrl+enter");
    }

    #[test]
    fn locates_legacy_project_root() {
        let root = project_root().expect("project root should be discoverable from src-tauri");
        assert!(root.join("global_config.yaml").is_file());
        assert!(root.join("assets").join("characters").is_dir());
    }

    #[test]
    fn loads_existing_yuraa_character() {
        let root = project_root().expect("project root should be discoverable");
        let char_root = character_root(&root, "yuraa");
        let config = load_character_config(&char_root).expect("yuraa config should load");
        assert_eq!(config.meta.name.as_deref(), Some("茅崎夕樱"));
        assert_eq!(config.layout.canvas_size, [1280, 720]);
        assert!(image_files(&char_root.join("portrait")).contains(&"1.png".to_string()));
    }

    #[test]
    fn validates_character_id_input() {
        assert_eq!(sanitize_character_id("alpha_01").unwrap(), "alpha_01");
        assert!(sanitize_character_id("").is_err());
        assert!(sanitize_character_id("bad/id").is_err());
    }

    #[test]
    fn generates_unique_asset_names() {
        let folder = project_root()
            .unwrap()
            .join("assets")
            .join("characters")
            .join("yuraa")
            .join("portrait");
        let generated = unique_asset_name(&folder, "1.png");
        assert_ne!(generated, "1.png");
        assert!(generated.ends_with(".png"));
    }

    #[test]
    fn renders_existing_yuraa_preview_image() {
        let root = project_root().expect("project root should be discoverable");
        let char_root = character_root(&root, "yuraa");
        let config = load_character_config(&char_root).expect("yuraa config should load");
        let rendered = render_preview_image(&root, "yuraa", &config, "Rust preview test")
            .expect("preview should render");
        if config.layout.enable_crop {
            let crop = config.layout.crop_area.expect("crop area should exist");
            assert_eq!(rendered.width(), (crop[2] - crop[0]) as u32);
            assert_eq!(rendered.height(), (crop[3] - crop[1]) as u32);
        } else {
            assert_eq!(rendered.width(), config.layout.canvas_size[0]);
            assert_eq!(rendered.height(), config.layout.canvas_size[1]);
        }
    }

    #[test]
    fn renders_existing_yuraa_base_cache_canvas() {
        let root = project_root().expect("project root should be discoverable");
        let char_root = character_root(&root, "yuraa");
        let config = load_character_config(&char_root).expect("yuraa config should load");
        let rendered =
            render_base_image(&root, "yuraa", &config).expect("base cache canvas should render");
        assert_eq!(rendered.width(), config.layout.canvas_size[0]);
        assert_eq!(rendered.height(), config.layout.canvas_size[1]);
    }
}
