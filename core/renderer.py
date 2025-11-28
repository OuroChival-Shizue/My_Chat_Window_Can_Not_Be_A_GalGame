import os
import json
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

try:
    from .utils import load_global_config, normalize_layout
except Exception:  # pragma: no cover - fallback for standalone runs
    def load_global_config() -> Dict[str, object]:
        return {}

    def normalize_layout(layout, canvas_size):
        return layout or {}

def _load_render_config() -> Tuple[Tuple[int, int], str, str, bool]:
    cfg = load_global_config() or {}
    render = cfg.get("render", {})
    canvas_size = tuple(render.get("canvas_size", (2560, 1440)))  # type: ignore[arg-type]
    cache_format = str(render.get("cache_format", "jpeg")).lower()
    if cache_format not in {"jpeg", "png"}:
        cache_format = "jpeg"
    cache_ext = ".jpg" if cache_format == "jpeg" else ".png"
    use_memory = bool(render.get("use_memory_canvas_cache", True))
    return canvas_size, cache_format, cache_ext, use_memory

CANVAS_SIZE, CACHE_FORMAT, CACHE_EXT, USE_MEMORY_CACHE = _load_render_config()


class CharacterRenderer:
    def __init__(self, char_id: str, base_path: str = "assets"):
        self.char_id = char_id
        self.base_path = base_path
        self.char_root = os.path.join(base_path, "characters", char_id)
        self.font_cache: Dict[Tuple[int, Optional[str]], ImageFont.ImageFont] = {}
        self.default_font_name = "LXGWWenKai-Medium.ttf"
        self.default_font_path: Optional[str] = os.path.join(
            self.base_path, "common", "fonts", self.default_font_name
        )

        self.canvas_size = CANVAS_SIZE
        self.cache_ext = CACHE_EXT
        self.use_memory_cache = USE_MEMORY_CACHE
        self._canvas_cache: Dict[Tuple[str, str], Image.Image] = {}
        self._scaled_suffix = f"{self.canvas_size[0]}x{self.canvas_size[1]}"

        print(f"--- 开始加载角色 {char_id} ---")

        config_path = os.path.join(self.char_root, "config.json")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"未找到角色配置 {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        layout_raw = self.config.setdefault("layout", {})
        self.layout = normalize_layout(layout_raw, self.canvas_size)
        self.layout["_canvas_size"] = [self.canvas_size[0], self.canvas_size[1]]
        self.config["layout"] = self.layout

        self.assets: Dict[str, object] = {
            "dialog_box": None,
            "portraits": {},
            "backgrounds": {},
            "font": None,
        }

        self._load_resources()
        print("--- 资源加载完成 ---\n")

    # -----------------------
    # 资源加载
    # -----------------------
    def _load_resources(self):
        # 立绘
        portrait_dir = os.path.join(self.char_root, "portrait")
        if os.path.exists(portrait_dir):
            count = 0
            for file in os.listdir(portrait_dir):
                if file.lower().endswith((".png", ".jpg", ".jpeg")):
                    key = os.path.splitext(file)[0]
                    full_path = os.path.join(portrait_dir, file)
                    portraits = self.assets.setdefault("portraits", {})
                    portraits[key] = Image.open(full_path).convert("RGBA")  # type: ignore[index]
                    count += 1
            print(f"✅ 已加载 {count} 张立绘")
        else:
            print(f"⚠️ 警告: 找不到立绘文件夹 {portrait_dir}")

        # 背景（优先使用预缩放目录，再回退到角色目录 / 公共目录）
        pre_scaled_bg_dir = os.path.join(
            self.base_path, "pre_scaled", "characters", self.char_id, "background"
        )
        char_bg_dir = os.path.join(self.char_root, "background")
        common_bg_dir = os.path.join(self.base_path, "common", "background")

        bg_dirs_to_try: List[str] = []
        if os.path.isdir(pre_scaled_bg_dir):
            bg_dirs_to_try.append(pre_scaled_bg_dir)
        if os.path.isdir(char_bg_dir):
            bg_dirs_to_try.append(char_bg_dir)
        if os.path.isdir(common_bg_dir):
            bg_dirs_to_try.append(common_bg_dir)

        count = 0
        self.assets["backgrounds"] = {}
        for bg_dir in bg_dirs_to_try:
            files = [
                f for f in os.listdir(bg_dir)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
            for file in files:
                base_name, ext = os.path.splitext(file)
                key = base_name
                if "@" in base_name:
                    prefix, tag = base_name.rsplit("@", 1)
                    if tag != self._scaled_suffix:
                        continue
                    key = prefix

                if key in self.assets["backgrounds"]:  # type: ignore[index]
                    continue
                full_path = os.path.join(bg_dir, file)
                img = Image.open(full_path).convert("RGBA")
                self.assets["backgrounds"][key] = self._resize_to_canvas(img)  # type: ignore[index]
                count += 1

        if count:
            print(f"✅ 已加载 {count} 张背景")
        else:
            print("⚠️ 警告: 找不到任何背景文件夹")

        # 对话框
        box_filename = self.config.get("assets", {}).get("dialog_box", "textbox_bg.png")
        box_path = os.path.join(self.char_root, box_filename)
        if os.path.exists(box_path):
            box_img = Image.open(box_path).convert("RGBA")
            self.assets["dialog_box"] = self._fit_dialog_box_to_canvas(box_img)
            print(f"✅ 对话框已加载: {box_filename}")
        else:
            print(f"⚠️ 警告: 找不到对话框图片 {box_path}")

        # 字体
        style = self.config.get("style", {})
        font_size = style.get("font_size", 40)
        text_font_file = style.get("font_file")
        self.assets["font"] = self._get_font(font_size, self._resolve_font_path(text_font_file))

    # -----------------------
    # 渲染主流程
    # -----------------------
    def render(
        self,
        text: str,
        portrait_key: Optional[str] = None,
        bg_key: Optional[str] = None,
        speaker_name: Optional[str] = None,
    ) -> Image.Image:
        portrait_key = portrait_key or self._first_key(self.assets["portraits"])  # type: ignore[arg-type]
        bg_key = bg_key or self._first_key(self.assets["backgrounds"])  # type: ignore[arg-type]

        canvas = self._get_base_canvas(portrait_key, bg_key)
        draw = ImageDraw.Draw(canvas)
        self._draw_text(draw, text, speaker_name)
        return canvas

    def _get_base_canvas(self, portrait_key: str, bg_key: str) -> Image.Image:
        cache_key = (portrait_key, bg_key)
        if self.use_memory_cache and cache_key in self._canvas_cache:
            return self._canvas_cache[cache_key]

        filename = f"p_{portrait_key}__b_{bg_key}{self.cache_ext}"
        cache_path = os.path.join(self.base_path, "cache", self.char_id, filename)

        if os.path.exists(cache_path):
            img = Image.open(cache_path).convert("RGBA")
            if self.use_memory_cache:
                self._canvas_cache[cache_key] = img
            return img

        # 兼容旧缓存扩展名
        legacy_path = cache_path[:-len(self.cache_ext)] + ".png"
        if not os.path.exists(cache_path) and os.path.exists(legacy_path):
            img = Image.open(legacy_path).convert("RGBA")
            if self.use_memory_cache:
                self._canvas_cache[cache_key] = img
            return img

        img = self._realtime_render(portrait_key, bg_key)
        if self.use_memory_cache:
            self._canvas_cache[cache_key] = img
        return img

    def _realtime_render(self, portrait_key: str, bg_key: str) -> Image.Image:
        canvas_w, canvas_h = self.canvas_size
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        # 背景
        bg = self.assets["backgrounds"].get(bg_key) or self._first_value(self.assets["backgrounds"])  # type: ignore
        if bg:
            bg_resized = bg.resize((canvas_w, canvas_h), Image.LANCZOS)
            canvas.paste(bg_resized, (0, 0))

        layout = self.layout

        # 立绘
        stand_pos = tuple(layout.get("stand_pos", (0, 0)))
        portrait = self.assets["portraits"].get(portrait_key) or self._first_value(self.assets["portraits"])  # type: ignore
        if portrait:
            stand_scale = layout.get("stand_scale", 1.0)
            if stand_scale != 1.0:
                new_w = int(portrait.width * stand_scale)
                new_h = int(portrait.height * stand_scale)
                portrait = portrait.resize((new_w, new_h), Image.LANCZOS)

        # 对话框：拉满宽度并贴底
        dialog_box = self.assets.get("dialog_box")
        if dialog_box:
            dialog_box, box_pos = self._fit_dialog_box_to_canvas(dialog_box)
        else:
            box_pos = (0, 0)

        stand_on_top = layout.get("stand_on_top", False)
        if not stand_on_top:
            if portrait:
                canvas.paste(portrait, stand_pos, portrait)
            if dialog_box:
                canvas.paste(dialog_box, box_pos, dialog_box)
        else:
            if dialog_box:
                canvas.paste(dialog_box, box_pos, dialog_box)
            if portrait:
                canvas.paste(portrait, stand_pos, portrait)

        return canvas

    def _resize_to_canvas(self, img: Image.Image) -> Image.Image:
        if img.size == self.canvas_size:
            return img
        return img.resize(self.canvas_size, Image.LANCZOS)

    def _fit_dialog_box_to_canvas(self, box_img: Image.Image) -> Tuple[Image.Image, Tuple[int, int]]:
        """Resize dialog box to canvas width and bottom align."""
        canvas_w, canvas_h = self.canvas_size
        if box_img.width != canvas_w:
            scale = canvas_w / box_img.width
            new_h = int(box_img.height * scale)
            box_img = box_img.resize((canvas_w, new_h), Image.LANCZOS)
        box_pos = (0, canvas_h - box_img.height)
        return box_img, box_pos

    # -----------------------
    # 文本绘制
    # -----------------------
    def _draw_text(self, draw: ImageDraw.ImageDraw, text: str, speaker_name: Optional[str]):
        style = self.config.get("style", {})
        text_color = tuple(style.get("text_color", (255, 255, 255)))
        name_color = tuple(style.get("name_color", (253, 145, 175)))
        text_size = style.get("font_size", 40)
        name_size = style.get("name_font_size", text_size)

        font_text_path = self._resolve_font_path(style.get("font_file"))
        font_name_path = self._resolve_font_path(style.get("name_font_file"))
        font_text: ImageFont.FreeTypeFont = self._get_font(text_size, font_text_path)  # type: ignore
        font_name: ImageFont.FreeTypeFont = self._get_font(name_size, font_name_path)  # type: ignore

        layout = self.layout
        text_area = layout.get("text_area", [100, 800, 1800, 1000])
        name_pos = layout.get("name_pos", [100, 100])

        if speaker_name is None:
            speaker_name = self.config.get("meta", {}).get("name", self.char_id)

        # 名字
        if speaker_name:
            draw.text(tuple(name_pos), speaker_name, font=font_name, fill=name_color)

        # 正文
        x1, y1, x2, y2 = text_area
        max_width = max(10, x2 - x1)
        lines = self._wrap_text(text, draw, font_text, max_width)
        line_height = self._line_height(font_text)

        for i, line in enumerate(lines):
            y = y1 + i * line_height
            if y > y2 - line_height:
                break
            draw.text((x1, y), line, font=font_text, fill=text_color)

    def _wrap_text(self, text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_width: int):
        lines = []
        paragraphs = text.split("\n") if text else [""]
        for para in paragraphs:
            if not para:
                lines.append("")
                continue
            current = ""
            for ch in para:
                if draw.textlength(current + ch, font=font) <= max_width:
                    current += ch
                else:
                    lines.append(current)
                    current = ch
            if current:
                lines.append(current)
        return lines

    def _line_height(self, font: ImageFont.ImageFont) -> int:
        bbox = font.getbbox("测试")
        return (bbox[3] - bbox[1]) + 4

    def _resolve_font_path(self, font_file: Optional[str]) -> Optional[str]:
        """Resolve a font path with fallbacks."""
        if font_file:
            if os.path.isabs(font_file) and os.path.exists(font_file):
                return font_file

            char_path = os.path.join(self.char_root, font_file)
            if os.path.exists(char_path):
                return char_path

            common_path = os.path.join(self.base_path, "common", "fonts", font_file)
            if os.path.exists(common_path):
                return common_path

        if self.default_font_path and os.path.exists(self.default_font_path):
            return self.default_font_path
        return None

    def _get_font(self, size: int, font_path: Optional[str]) -> ImageFont.ImageFont:
        """Load font with caching; fallback to default when missing."""
        cache_key = (size, font_path)
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]

        if font_path:
            try:
                font = ImageFont.truetype(font_path, size)
                self.font_cache[cache_key] = font
                return font
            except OSError:
                pass

        font = ImageFont.load_default()
        self.font_cache[cache_key] = font
        return font

    @staticmethod
    def _first_key(mapping: Dict[str, Image.Image]) -> Optional[str]:
        return next(iter(mapping.keys()), None)

    @staticmethod
    def _first_value(mapping: Dict[str, Image.Image]) -> Optional[Image.Image]:
        return next(iter(mapping.values()), None)


if __name__ == "__main__":
    renderer = CharacterRenderer("yuraa")
    img = renderer.render("这是一个渲染测试", "yuraa_portrait_1", "yuraa_bg_1")
    img.show()
