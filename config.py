"""车牌钥匙扣生成器配置 — 支持多种款式。"""

from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 兼容旧路径（款式一未迁移到 styles/classic 时仍可用）
LEGACY_MODELS_DIR = os.path.join(BASE_DIR, "assets", "models")
LEGACY_FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")

STYLES_ROOT = os.path.join(BASE_DIR, "assets", "styles")

DEFAULT_STYLE = "classic"


def _find_asset(
    directory: str,
    extensions: tuple[str, ...],
    preferred: tuple[str, ...] = (),
) -> str | None:
    """在目录中查找资源；优先匹配 preferred 文件名。"""
    if not os.path.isdir(directory):
        return None
    names = [
        name
        for name in sorted(os.listdir(directory))
        if not name.startswith(".") and name.lower().endswith(extensions)
    ]
    if not names:
        return None
    preferred_lower = {p.lower() for p in preferred}
    for name in names:
        if name.lower() in preferred_lower:
            return os.path.join(directory, name)
    return os.path.join(directory, names[0])


def _has_asset(directory: str, extensions: tuple[str, ...]) -> bool:
    return _find_asset(directory, extensions) is not None


def _style_asset_dirs(style_id: str) -> tuple[str, str]:
    """返回 (models_dir, fonts_dir)。classic 可回退到旧版 assets/{models,fonts}。"""
    root = os.path.join(STYLES_ROOT, style_id)
    models_dir = os.path.join(root, "models")
    fonts_dir = os.path.join(root, "fonts")

    if style_id == "classic":
        if not _has_asset(models_dir, (".stl",)) and _has_asset(
            LEGACY_MODELS_DIR, (".stl",)
        ):
            models_dir = LEGACY_MODELS_DIR
        if not _has_asset(fonts_dir, (".ttf", ".otf")) and _has_asset(
            LEGACY_FONTS_DIR, (".ttf", ".otf")
        ):
            fonts_dir = LEGACY_FONTS_DIR

    return models_dir, fonts_dir


# ── 款式定义 ─────────────────────────────────────────────
# classic: 双色车牌，约 79.5×25×3，右侧挂环，可选左侧竖排州名
# slim:    窄版车牌，约 70×17×3，左侧挂孔，单行横排文字（挤出后总高约 4mm）
STYLES: dict[str, dict] = {
    "classic": {
        "id": "classic",
        "label": "双色车牌",
        "description": "79.5×25mm，右侧挂环，可选左侧竖排",
        "zip_prefix": "双色车牌",
        "has_side_text": True,
        "model": {
            "length": 79.5,
            "width": 25.0,
            "height": 3.0,
        },
        "text_z_base": None,
        "main_text": {
            "font_size": 30.0,
            "extrude_height": 1.0,
            "max_length": 8,           # 标准长度；超出后自动缩小字号
            "hard_max_length": 16,     # 硬上限（含空格）
            "auto_fit": True,
            "height_fill_ratio": 0.72,  # 上下留边，避免换字体后顶出牌面
            "font_height_ratio": 0.7,   # 仅作探针失败时的兜底；实际按字体实测
            "left_reserved": 0.0,
            "right_reserved": 6.0,
            "horizontal_margin": 4.0,
            "gap_after_side": 3.0,
        },
        "side_text": {
            "font_size": 5.0,
            "extrude_height": 1.0,
            "left_margin": 3.5,
            "char_spacing": 8.0,        # 竖排中心距上限；实际会按牌面高度夹紧
            "height_fill_ratio": 0.78,
            "min_gap_ratio": 1.20,      # 字距至少为字高的 1.2 倍，避免粘连
            "max_length": 3,
        },
        "auto_scale": True,
        "auto_scale_min_font_size": 9.0,
        "preferred_font": (
            "LICENSE PLATE USA.ttf",
            "UKNumberPlate.ttf",
            "plate_font.ttf",
        ),
        "preferred_model": (),
        "preview_placeholder": "YOUR",
    },
    "slim": {
        "id": "slim",
        "label": "窄版车牌",
        "description": "70×17×3mm，左侧挂孔，单行横排（文字高 +1mm）",
        "zip_prefix": "窄版车牌",
        "has_side_text": False,
        "model": {
            "length": 70.0,
            "width": 17.0,
            "height": 3.0,
        },
        "text_z_base": None,
        "main_text": {
            "font_size": 18.0,
            "extrude_height": 1.0,  # 底板 3mm + 文字 1mm ≈ 4mm
            "max_length": 10,
            "hard_max_length": 16,
            "auto_fit": True,
            "height_fill_ratio": 0.78,
            "font_height_ratio": 0.684,
            "left_reserved": 11.0,  # 左侧挂孔预留
            "right_reserved": 3.0,
            "horizontal_margin": 2.0,
            "gap_after_side": 0.0,
        },
        "side_text": None,
        "auto_scale": True,
        "auto_scale_min_font_size": 6.0,
        "preferred_font": ("slim_font.ttf", "plate_font.ttf", "UKNumberPlate.ttf"),
        "preferred_model": (),
        "preview_placeholder": "HAII LBH",
    },
}


def list_styles() -> list[dict]:
    """供前端展示的款式列表。"""
    result = []
    for style in STYLES.values():
        models_dir, fonts_dir = _style_asset_dirs(style["id"])
        result.append(
            {
                "id": style["id"],
                "label": style["label"],
                "description": style["description"],
                "has_side_text": style["has_side_text"],
                "max_main_length": style["main_text"].get(
                    "hard_max_length", style["main_text"]["max_length"]
                ),
                "design_main_length": style["main_text"]["max_length"],
                "max_side_length": (
                    style["side_text"]["max_length"] if style.get("side_text") else 0
                ),
                "preview_placeholder": style.get("preview_placeholder", "TEXT"),
                "model_ready": _has_asset(models_dir, (".stl",)),
                "font_ready": _has_asset(fonts_dir, (".ttf", ".otf")),
            }
        )
    return result


def get_style(style_id: str | None = None) -> dict:
    """获取款式配置；非法 id 抛出 ValueError。"""
    sid = (style_id or DEFAULT_STYLE).strip().lower()
    if sid not in STYLES:
        known = ", ".join(STYLES)
        raise ValueError(f"未知款式: {style_id!r}，可选: {known}")

    style = dict(STYLES[sid])
    models_dir, fonts_dir = _style_asset_dirs(sid)
    style["models_dir"] = models_dir
    style["fonts_dir"] = fonts_dir
    style["base_model_path"] = _find_asset(
        models_dir, (".stl",), preferred=tuple(style.get("preferred_model") or ())
    ) or os.path.join(models_dir, "base_keychain.stl")
    style["font_path"] = _find_asset(
        fonts_dir,
        (".ttf", ".otf"),
        preferred=tuple(style.get("preferred_font") or ()),
    ) or os.path.join(fonts_dir, "plate_font.ttf")
    return style


# ── 批量生成 ──────────────────────────────────────────────
BATCH = {
    "max_workers": None,  # 并行进程数，None = CPU 核心数
}

# ── 向后兼容：旧代码若仍引用顶层常量，默认指向 classic ──
_classic = get_style("classic")
BASE_MODEL_PATH = _classic["base_model_path"]
FONT_PATH = _classic["font_path"]
MODEL = _classic["model"]
TEXT_Z_BASE = _classic["text_z_base"]
MAIN_TEXT = _classic["main_text"]
SIDE_TEXT = _classic["side_text"]
AUTO_SCALE = _classic["auto_scale"]
AUTO_SCALE_MIN_FONT_SIZE = _classic["auto_scale_min_font_size"]
MODELS_DIR = _classic["models_dir"]
FONTS_DIR = _classic["fonts_dir"]
