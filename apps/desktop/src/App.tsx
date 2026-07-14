import { type ReactNode, useEffect, useMemo, useState } from "react";
import { CircleAlert, ClipboardCopy, Database, FolderOpen, MessageSquareText, Pause, Play, Plus, RefreshCw, Save, Sparkles, Square, Trash2, Upload } from "lucide-react";
import { Layer, Rect, Stage, Text } from "react-konva";
import { buildCache, copyEngineOutputToClipboard, createCharacter, deleteAsset, importAsset, listCharacters, loadCharacter, loadEngineStatus, loadGlobalConfig, openCharacterFolder, pickAssetFile, refreshEngineHotkey, renderEngineText, renderPreview, saveCharacter, saveGlobalConfig, setEnginePortrait, startEngine, stopEngine, toggleEnginePause } from "./tauri";
import type { AssetKind, CharacterBundle, CharacterSummary, EngineStatus, GlobalConfig, RenderPreviewResult } from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";
type Rect4 = [number, number, number, number];
type Point2 = [number, number];

export function App() {
  const [globalConfig, setGlobalConfig] = useState<GlobalConfig | null>(null);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [activeId, setActiveId] = useState("");
  const [bundle, setBundle] = useState<CharacterBundle | null>(null);
  const [state, setState] = useState<LoadState>("idle");
  const [message, setMessage] = useState("Booting GalGame Chat Studio...");
  const [preview, setPreview] = useState<RenderPreviewResult | null>(null);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      setState("loading");
      try {
        const [global, items] = await Promise.all([loadGlobalConfig(), listCharacters()]);
        if (cancelled) return;
        setGlobalConfig(global);
        setCharacters(items);
        const preferred = items.find((item) => item.id === global.current_character)?.id ?? items[0]?.id ?? "";
        setActiveId(preferred);
      } catch (error) {
        if (cancelled) return;
        setState("error");
        setMessage(toMessage(error));
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    async function load() {
      setState("loading");
      try {
        const character = await loadCharacter(activeId);
        if (cancelled) return;
        setBundle(character);
        setState("ready");
        setMessage(`Loaded ${character.config.meta.name ?? character.id}`);
      } catch (error) {
        if (cancelled) return;
        setState("error");
        setMessage(toMessage(error));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    loadEngineStatus()
      .then(setEngineStatus)
      .catch((error) => setMessage(toMessage(error)));
  }, []);

  useEffect(() => {
    if (!engineStatus?.running) return;
    const timer = window.setInterval(() => {
      loadEngineStatus()
        .then(setEngineStatus)
        .catch((error) => setMessage(toMessage(error)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [engineStatus?.running]);

  const canvasSize = bundle?.config.layout._canvas_size ?? [1280, 720];
  const stageScale = useMemo(() => Math.min(1, 880 / canvasSize[0], 520 / canvasSize[1]), [canvasSize]);

  async function runTask(task: () => Promise<void>) {
    try {
      await task();
      setState("ready");
    } catch (error) {
      setState("error");
      setMessage(toMessage(error));
    }
  }

  async function refreshCharacterList(preferredId = activeId) {
    const items = await listCharacters();
    setCharacters(items);
    if (preferredId && items.some((item) => item.id === preferredId)) {
      setActiveId(preferredId);
    }
  }

  function handleSelectCharacter(id: string) {
    setActiveId(id);
    if (globalConfig) {
      const next = { ...globalConfig, current_character: id };
      setGlobalConfig(next);
      saveGlobalConfig(next).catch((error) => setMessage(toMessage(error)));
    }
  }

  async function handleReload() {
    await runTask(async () => {
      await refreshCharacterList(activeId);
      if (activeId) setBundle(await loadCharacter(activeId));
      setPreview(null);
      setMessage("Workspace refreshed.");
    });
  }

  async function handleSave() {
    if (!bundle) return;
    await runTask(async () => {
      await saveCharacter(bundle.id, bundle.config);
      if (globalConfig) await saveGlobalConfig(globalConfig);
      if (engineStatus?.running) {
        setEngineStatus(await refreshEngineHotkey());
      }
      await refreshCharacterList(bundle.id);
      setMessage("Config saved.");
    });
  }

  async function handleCreateCharacter() {
    const id = window.prompt("Character ID");
    if (!id) return;
    const displayName = window.prompt("Display name", id) ?? id;
    await runTask(async () => {
      const created = await createCharacter(id, displayName);
      await refreshCharacterList(created.id);
      setActiveId(created.id);
      setBundle(created);
      setMessage(`Created ${created.config.meta.name ?? created.id}.`);
    });
  }

  async function handleImportAsset(kind: AssetKind) {
    if (!bundle) return;
    await runTask(async () => {
      const sourcePath = await pickAssetFile(kind);
      if (!sourcePath) {
        setMessage("Import cancelled.");
        return;
      }
      const updated = await importAsset(bundle.id, kind, sourcePath);
      setBundle(updated);
      await refreshCharacterList(bundle.id);
      setMessage("Asset imported.");
    });
  }

  async function handleDeleteAsset(kind: AssetKind, filename: string) {
    if (!bundle) return;
    if (!window.confirm(`Delete ${filename}?`)) return;
    await runTask(async () => {
      const updated = await deleteAsset(bundle.id, kind, filename);
      setBundle(updated);
      await refreshCharacterList(bundle.id);
      setMessage("Asset deleted.");
    });
  }

  async function handleOpenFolder() {
    if (!bundle) return;
    await runTask(async () => {
      await openCharacterFolder(bundle.id);
      setMessage("Character folder opened.");
    });
  }

  async function handlePreview() {
    if (!bundle) return;
    await runTask(async () => {
      const result = await renderPreview(bundle.id, bundle.config, "Rust renderer preview text.");
      setPreview(result);
      setMessage(`Preview rendered: ${result.width} x ${result.height}`);
    });
  }

  async function handleBuildCache() {
    if (!bundle) return;
    await runTask(async () => {
      const result = await buildCache(bundle.id, bundle.config);
      setMessage(`Cache built: ${result.generated} ${result.format} images -> ${result.cache_dir}`);
    });
  }

  async function handleStartEngine() {
    if (!bundle) return;
    await runTask(async () => {
      const status = await startEngine(bundle.id, bundle.config);
      setEngineStatus(status);
      setMessage(`Engine running for ${bundle.config.meta.name ?? bundle.id} (${status.trigger_hotkey}).`);
    });
  }

  async function handleStopEngine() {
    await runTask(async () => {
      const status = await stopEngine();
      setEngineStatus(status);
      setMessage("Engine stopped.");
    });
  }

  async function handleTogglePause() {
    await runTask(async () => {
      const status = await toggleEnginePause();
      setEngineStatus(status);
      setMessage(status.paused ? "Engine paused." : "Engine resumed.");
    });
  }

  async function handleRenderEngineText() {
    if (!bundle) return;
    const text = window.prompt("Dialogue text", "Rust engine render text.");
    if (!text) return;
    await runTask(async () => {
      if (bundle.config.layout.current_portrait) {
        setEngineStatus(await setEnginePortrait(bundle.config.layout.current_portrait));
      }
      const result = await renderEngineText(bundle.id, bundle.config, text);
      setPreview(result);
      try {
        const copied = await copyEngineOutputToClipboard();
        setMessage(`Engine rendered and copied: ${copied.width} x ${copied.height} (${copied.formats.join(", ")})`);
      } catch (error) {
        setMessage(`Engine rendered, clipboard failed: ${toMessage(error)}`);
      }
      setEngineStatus(await loadEngineStatus());
    });
  }

  async function handleCopyEngineOutput() {
    await runTask(async () => {
      const copied = await copyEngineOutputToClipboard();
      setMessage(`Copied engine output: ${copied.width} x ${copied.height} (${copied.formats.join(", ")})`);
    });
  }

  return (
    <main className="flex h-screen min-w-[1024px] flex-col bg-background text-foreground">
      <CommandBar disabled={!bundle} engineStatus={engineStatus} onBuildCache={handleBuildCache} onCopyOutput={handleCopyEngineOutput} onCreate={handleCreateCharacter} onEngineText={handleRenderEngineText} onOpenFolder={handleOpenFolder} onPauseEngine={handleTogglePause} onPreview={handlePreview} onReload={handleReload} onSave={handleSave} onStartEngine={handleStartEngine} onStopEngine={handleStopEngine} />
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_360px] border-t border-border">
        <aside className="flex min-h-0 flex-col border-r border-border bg-muted/35">
          <SectionTitle title="Characters" />
          <div className="flex-1 overflow-auto p-2">
            {characters.map((character) => (
              <button
                key={character.id}
                className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${activeId === character.id ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"}`}
                onClick={() => handleSelectCharacter(character.id)}
              >
                <span className="min-w-0">
                  <strong className="block truncate font-medium">{character.name || character.id}</strong>
                  <span className="text-xs text-muted-foreground">{character.id}</span>
                </span>
                <span className="ml-3 text-xs text-muted-foreground">{character.portrait_count}/{character.background_count}</span>
              </button>
            ))}
          </div>
          <SectionTitle title="Assets" />
          <AssetList title="Portraits" kind="portrait" items={bundle?.portraits ?? []} onImport={handleImportAsset} onDelete={handleDeleteAsset} />
          <AssetList title="Backgrounds" kind="background" items={bundle?.backgrounds ?? []} onImport={handleImportAsset} onDelete={handleDeleteAsset} />
          <AssetList title="Fonts" kind="font" items={bundle?.fonts ?? []} onImport={handleImportAsset} onDelete={handleDeleteAsset} />
        </aside>

        <section className="flex min-h-0 flex-col bg-[#f4f6f8]">
          <div className="flex h-10 items-center justify-between border-b border-border bg-background px-4 text-sm">
            <span className="font-medium">Canvas</span>
            <span className="text-muted-foreground">{canvasSize[0]} x {canvasSize[1]} / {Math.round(stageScale * 100)}%</span>
          </div>
          <div className="flex flex-1 items-center justify-center overflow-auto p-6">
            {state === "error" ? <ErrorPanel message={message} /> : preview ? <PreviewPane preview={preview} onBack={() => setPreview(null)} /> : <CanvasEditor bundle={bundle} scale={stageScale} onChange={setBundle} />}
          </div>
        </section>

        <Inspector bundle={bundle} globalConfig={globalConfig} onChange={setBundle} onGlobalChange={setGlobalConfig} onImport={handleImportAsset} />
      </div>
      <footer className="flex h-8 items-center justify-between border-t border-border bg-background px-3 text-xs text-muted-foreground">
        <span className="truncate">{message}</span>
        <span>{state === "loading" ? "Loading" : "Ready"}</span>
      </footer>
    </main>
  );
}

function CommandBar({
  disabled,
  engineStatus,
  onBuildCache,
  onCopyOutput,
  onCreate,
  onEngineText,
  onOpenFolder,
  onPauseEngine,
  onPreview,
  onReload,
  onSave,
  onStartEngine,
  onStopEngine,
}: {
  disabled: boolean;
  engineStatus: EngineStatus | null;
  onBuildCache: () => void;
  onCopyOutput: () => void;
  onCreate: () => void;
  onEngineText: () => void;
  onOpenFolder: () => void;
  onPauseEngine: () => void;
  onPreview: () => void;
  onReload: () => void;
  onSave: () => void;
  onStartEngine: () => void;
  onStopEngine: () => void;
}) {
  const running = engineStatus?.running ?? false;
  const paused = engineStatus?.paused ?? false;
  const engineLabel = running ? (paused ? "Paused" : "Running") : "Stopped";
  const hasOutput = Boolean(engineStatus?.last_output_path);
  const hotkey = engineStatus?.registered_hotkey ?? engineStatus?.trigger_hotkey ?? "";
  const capturedLength = engineStatus?.last_captured_text?.length ?? 0;
  const statusDetail = engineStatus?.last_error ?? engineStatus?.last_action ?? "";
  const expressionInfo = engineStatus?.expression_count ? `${engineStatus.current_portrait ?? "auto"} / ${engineStatus.expression_count}` : "";
  const auxHotkeys = engineStatus?.registered_aux_hotkeys?.join(", ") ?? "";
  return (
    <header className="flex h-12 items-center justify-between bg-background px-3">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Sparkles size={17} />
        </div>
        <div>
          <h1 className="text-sm font-semibold">GalGame Chat Studio</h1>
          <p className="text-xs text-muted-foreground">Tauri migration workbench</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`rounded-md px-2 py-1 text-xs font-medium ${running ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"}`}>{engineLabel}</span>
        {hotkey ? <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground" title={auxHotkeys ? `Aux: ${auxHotkeys}` : undefined}>{hotkey} / {engineStatus?.shortcut_hits ?? 0}</span> : null}
        {expressionInfo ? <span className="max-w-[160px] truncate rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground" title={expressionInfo}>{expressionInfo}</span> : null}
        {statusDetail ? <span className="max-w-[220px] truncate rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground" title={statusDetail}>{statusDetail}{capturedLength ? ` / ${capturedLength} chars` : ""}</span> : null}
        <div className="flex items-center gap-1 border-r border-border pr-2">
          <ToolbarButton icon={<Play size={16} />} label="Start" disabled={disabled || running} onClick={onStartEngine} />
          <ToolbarButton icon={<Pause size={16} />} label={paused ? "Resume" : "Pause"} disabled={!running} onClick={onPauseEngine} />
          <ToolbarButton icon={<Square size={15} />} label="Stop" disabled={!running} onClick={onStopEngine} />
          <ToolbarButton icon={<MessageSquareText size={16} />} label="Text" disabled={disabled} onClick={onEngineText} />
          <ToolbarButton icon={<ClipboardCopy size={16} />} label="Copy" disabled={!hasOutput} onClick={onCopyOutput} />
        </div>
        <div className="flex items-center gap-1">
          <ToolbarButton icon={<Plus size={16} />} label="New" onClick={onCreate} />
          <ToolbarButton icon={<FolderOpen size={16} />} label="Folder" disabled={disabled} onClick={onOpenFolder} />
          <ToolbarButton icon={<RefreshCw size={16} />} label="Reload" onClick={onReload} />
          <ToolbarButton icon={<Play size={16} />} label="Preview" disabled={disabled} onClick={onPreview} />
          <ToolbarButton icon={<Save size={16} />} label="Save" disabled={disabled} onClick={onSave} />
          <ToolbarButton icon={<Database size={16} />} label="Cache" disabled={disabled} onClick={onBuildCache} />
        </div>
      </div>
    </header>
  );
}

function ToolbarButton({ icon, label, disabled, onClick }: { icon: ReactNode; label: string; disabled?: boolean; onClick?: () => void }) {
  return <button className="inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-45" disabled={disabled} onClick={onClick} title={label}>{icon}<span>{label}</span></button>;
}

function SectionTitle({ title }: { title: string }) {
  return <div className="border-y border-border px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">{title}</div>;
}

function AssetList({ title, kind, items, onImport, onDelete }: { title: string; kind: AssetKind; items: string[]; onImport: (kind: AssetKind) => void; onDelete: (kind: AssetKind, filename: string) => void }) {
  return (
    <div className="max-h-44 overflow-auto p-2">
      <div className="mb-2 flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span>{title}</span>
        <button className="rounded p-1 hover:bg-accent" onClick={() => onImport(kind)} title={`Import ${title}`}><Upload size={14} /></button>
      </div>
      {items.map((item) => (
        <div key={item} className="group mb-1 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent/60">
          <span className="min-w-0 flex-1 truncate">{item}</span>
          <button className="rounded p-1 opacity-0 hover:bg-background group-hover:opacity-100" onClick={() => onDelete(kind, item)} title="Delete asset"><Trash2 size={13} /></button>
        </div>
      ))}
      {!items.length && <div className="px-2 py-3 text-xs text-muted-foreground">No assets</div>}
    </div>
  );
}


function PreviewPane({ preview, onBack }: { preview: RenderPreviewResult; onBack: () => void }) {
  return (
    <div className="flex max-h-full max-w-full flex-col items-center gap-3">
      <div className="flex w-full items-center justify-between rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm">
        <span className="text-muted-foreground">Rust preview - {preview.width} x {preview.height}</span>
        <button className="rounded-md px-3 py-1.5 text-sm hover:bg-accent" onClick={onBack}>Back to editor</button>
      </div>
      {preview.url ? (
        <img className="max-h-[calc(100vh-180px)] max-w-full object-contain shadow-[0_18px_50px_rgba(15,23,42,0.18)]" src={preview.url} alt="Rendered preview" />
      ) : (
        <div className="rounded-md border border-border bg-background px-4 py-6 text-sm text-muted-foreground">Preview is available only inside Tauri.</div>
      )}
    </div>
  );
}

function CanvasEditor({ bundle, scale, onChange }: { bundle: CharacterBundle | null; scale: number; onChange: (bundle: CharacterBundle) => void }) {
  if (!bundle) return <div className="text-sm text-muted-foreground">Select a character to edit.</div>;
  const current = bundle;

  const layout = current.config.layout;
  const [width, height] = layout._canvas_size;
  const textArea = normalizeRect(layout.text_area, width, height);
  const crop = normalizeRect(layout.crop_area ?? [0, 0, width, height], width, height);
  const portraitW = Math.max(40, 280 * layout.stand_scale);
  const portraitH = Math.max(80, 520 * layout.stand_scale);

  function patchLayout(patch: Partial<CharacterBundle["config"]["layout"]>) {
    onChange({ ...current, config: { ...current.config, layout: { ...layout, ...patch } } });
  }

  function moveRect(rect: Rect4, x: number, y: number): Rect4 {
    const rectW = rect[2] - rect[0];
    const rectH = rect[3] - rect[1];
    const nextX = clamp(Math.round(x), 0, Math.max(0, width - rectW));
    const nextY = clamp(Math.round(y), 0, Math.max(0, height - rectH));
    return [nextX, nextY, nextX + rectW, nextY + rectH];
  }

  function resizeRect(rect: Rect4, x2: number, y2: number): Rect4 {
    return normalizeRect([rect[0], rect[1], Math.round(x2), Math.round(y2)], width, height);
  }

  return (
    <div className="shadow-[0_18px_50px_rgba(15,23,42,0.18)]">
      <Stage width={width * scale} height={height * scale} scaleX={scale} scaleY={scale}>
        <Layer>
          <Rect width={width} height={height} fill="#18202a" />
          <Rect x={0} y={height * 0.72} width={width} height={height * 0.28} fill="#111827" opacity={0.82} />
          <Rect
            x={layout.stand_pos[0]}
            y={layout.stand_pos[1]}
            width={portraitW}
            height={portraitH}
            fill="#7dd3fc"
            opacity={0.3}
            stroke="#0891b2"
            strokeWidth={2}
            cornerRadius={8}
            draggable
            onDragEnd={(event: any) => patchLayout({ stand_pos: [Math.round(event.target.x()), Math.round(event.target.y())] })}
            onWheel={(event: any) => {
              event.evt.preventDefault();
              const delta = event.evt.deltaY > 0 ? -0.04 : 0.04;
              patchLayout({ stand_scale: round(clamp(layout.stand_scale + delta, 0.1, 3), 3) });
            }}
          />
          <Text x={layout.stand_pos[0] + 12} y={layout.stand_pos[1] + 12} text="portrait" fontSize={18} fill="#0e7490" />
          <Text
            x={layout.name_pos[0]}
            y={layout.name_pos[1]}
            text={current.config.meta.name ?? current.id}
            fontSize={current.config.style.basic.name_font_size}
            fill="#ff4fd8"
            draggable
            onDragEnd={(event: any) => patchLayout({ name_pos: [Math.round(event.target.x()), Math.round(event.target.y())] })}
          />
          <Rect
            x={textArea[0]}
            y={textArea[1]}
            width={textArea[2] - textArea[0]}
            height={textArea[3] - textArea[1]}
            stroke="#60a5fa"
            strokeWidth={2}
            dash={[8, 5]}
            draggable
            onDragEnd={(event: any) => patchLayout({ text_area: moveRect(textArea, event.target.x(), event.target.y()) })}
          />
          <Rect
            x={textArea[2] - 10}
            y={textArea[3] - 10}
            width={20}
            height={20}
            fill="#60a5fa"
            opacity={0.9}
            draggable
            onDragEnd={(event: any) => patchLayout({ text_area: resizeRect(textArea, event.target.x() + 10, event.target.y() + 10) })}
          />
          <Text x={textArea[0] + 8} y={textArea[1] + 8} text="Preview dialogue text" fontSize={current.config.style.basic.font_size} fill="white" />
          {layout.enable_crop ? (
            <>
              <Rect
                x={crop[0]}
                y={crop[1]}
                width={crop[2] - crop[0]}
                height={crop[3] - crop[1]}
                stroke="#ef4444"
                strokeWidth={2}
                dash={[10, 6]}
                draggable
                onDragEnd={(event: any) => patchLayout({ crop_area: moveRect(crop, event.target.x(), event.target.y()) })}
              />
              <Rect
                x={crop[2] - 10}
                y={crop[3] - 10}
                width={20}
                height={20}
                fill="#ef4444"
                opacity={0.9}
                draggable
                onDragEnd={(event: any) => patchLayout({ crop_area: resizeRect(crop, event.target.x() + 10, event.target.y() + 10) })}
              />
            </>
          ) : null}
        </Layer>
      </Stage>
    </div>
  );
}

function Inspector({ bundle, globalConfig, onChange, onGlobalChange, onImport }: { bundle: CharacterBundle | null; globalConfig: GlobalConfig | null; onChange: (bundle: CharacterBundle) => void; onGlobalChange: (config: GlobalConfig) => void; onImport: (kind: AssetKind) => void }) {
  if (!bundle) return <aside className="border-l border-border bg-background p-4 text-sm text-muted-foreground">No character loaded.</aside>;
  const current = bundle;

  const config = current.config;
  const layout = config.layout;

  function patchConfig(patch: Partial<CharacterBundle["config"]>) {
    onChange({ ...current, config: { ...config, ...patch } });
  }

  function patchLayout(patch: Partial<CharacterBundle["config"]["layout"]>) {
    patchConfig({ layout: { ...layout, ...patch } });
  }

  return (
    <aside className="min-h-0 overflow-auto border-l border-border bg-background">
      <SectionTitle title="Inspector" />
      <div className="space-y-5 p-4">
        <Field label="Display name">
          <input className="input" value={config.meta.name ?? ""} onChange={(event) => patchConfig({ meta: { ...config.meta, name: event.target.value } })} />
        </Field>
        <Field label="Trigger hotkey">
          <input className="input" value={globalConfig?.trigger_hotkey ?? ""} onChange={(event) => globalConfig && onGlobalChange({ ...globalConfig, trigger_hotkey: event.target.value })} />
        </Field>
        <Field label="Text size">
          <NumberInput value={config.style.basic.font_size} min={1} onChange={(value) => patchConfig({ style: { ...config.style, basic: { ...config.style.basic, font_size: value } } })} />
        </Field>
        <Field label="Text wrapper">
          <select
            className="input"
            value={config.style.text_wrapper.preset}
            onChange={(event) => patchConfig({ style: { ...config.style, text_wrapper: wrapperForPreset(event.target.value) } })}
          >
            <option value="corner_single">corner single</option>
            <option value="corner_double">corner double</option>
          </select>
        </Field>
        <Field label="Current portrait">
          <select className="input" value={layout.current_portrait} onChange={(event) => patchLayout({ current_portrait: event.target.value })}>
            <option value="">Auto</option>
            {current.portraits.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Current background">
          <select className="input" value={layout.current_background} onChange={(event) => patchLayout({ current_background: event.target.value })}>
            <option value="">Auto</option>
            {current.backgrounds.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Portrait position">
          <PointInput value={layout.stand_pos} onChange={(value) => patchLayout({ stand_pos: value })} />
        </Field>
        <Field label="Portrait scale">
          <NumberInput value={layout.stand_scale} min={0.1} step={0.01} onChange={(value) => patchLayout({ stand_scale: value })} />
        </Field>
        <Field label="Name position">
          <PointInput value={layout.name_pos} onChange={(value) => patchLayout({ name_pos: value })} />
        </Field>
        <Field label="Text area">
          <RectInput value={layout.text_area} onChange={(value) => patchLayout({ text_area: value })} />
        </Field>
        <Field label="Crop">
          <label className="mb-2 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={layout.enable_crop} onChange={(event) => patchLayout({ enable_crop: event.target.checked, crop_area: layout.crop_area ?? [0, 0, layout._canvas_size[0], layout._canvas_size[1]] })} />
            Enabled
          </label>
          {layout.enable_crop ? <RectInput value={layout.crop_area ?? [0, 0, layout._canvas_size[0], layout._canvas_size[1]]} onChange={(value) => patchLayout({ crop_area: value })} /> : null}
        </Field>
        <Field label="Dialog box">
          <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <span className="min-w-0 truncate">{current.dialog_box_exists ? config.assets.dialog_box : "missing"}</span>
            <button className="rounded p-1 hover:bg-accent" onClick={() => onImport("dialog_box")} title="Import dialog box"><Upload size={14} /></button>
          </div>
        </Field>
      </div>
    </aside>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</span>{children}</label>;
}

function NumberInput({ value, onChange, min, step = 1 }: { value: number; onChange: (value: number) => void; min?: number; step?: number }) {
  return <input className="input" type="number" step={step} min={min} value={value} onChange={(event) => onChange(Number(event.target.value))} />;
}

function PointInput({ value, onChange }: { value: Point2; onChange: (value: Point2) => void }) {
  return <div className="grid grid-cols-2 gap-2"><NumberInput value={value[0]} onChange={(next) => onChange([next, value[1]])} /><NumberInput value={value[1]} onChange={(next) => onChange([value[0], next])} /></div>;
}

function RectInput({ value, onChange }: { value: Rect4; onChange: (value: Rect4) => void }) {
  return <div className="grid grid-cols-4 gap-2"><NumberInput value={value[0]} onChange={(next) => onChange([next, value[1], value[2], value[3]])} /><NumberInput value={value[1]} onChange={(next) => onChange([value[0], next, value[2], value[3]])} /><NumberInput value={value[2]} onChange={(next) => onChange([value[0], value[1], next, value[3]])} /><NumberInput value={value[3]} onChange={(next) => onChange([value[0], value[1], value[2], next])} /></div>;
}

function ErrorPanel({ message }: { message: string }) {
  return <div className="flex max-w-md items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900"><CircleAlert className="mt-0.5 shrink-0" size={18} /><div><strong className="block">Load failed</strong><span>{message}</span></div></div>;
}

function normalizeRect(rect: Rect4, width: number, height: number): Rect4 {
  const x1 = clamp(Math.round(rect[0]), 0, width - 10);
  const y1 = clamp(Math.round(rect[1]), 0, height - 10);
  const x2 = clamp(Math.round(rect[2]), x1 + 10, width);
  const y2 = clamp(Math.round(rect[3]), y1 + 10, height);
  return [x1, y1, x2, y2];
}

function wrapperForPreset(preset: string) {
  const double = preset === "corner_double";
  return { type: "preset" as const, preset, prefix: double ? "\u300e" : "\u300c", suffix: double ? "\u300f" : "\u300d" };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function round(value: number, places: number) {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

function toMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
