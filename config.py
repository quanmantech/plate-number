"""车牌钥匙扣生成器配置 — 根据你的基础模型尺寸调整以下参数。"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(BASE_DIR, "assets", "models")
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")


def _find_asset(directory: str, extensions: tuple[str, ...]) -> str | None:
    """在目录中自动查找第一个匹配的资源文件。"""
    if not os.path.isdir(directory):
        return None
    for name in sorted(os.listdir(directory)):
        if name.startswith("."):
            continue
        if name.lower().endswith(extensions):
            return os.path.join(directory, name)
    return None


# ── 文件路径（自动识别目录中的 .stl / .ttf 文件）──────────
BASE_MODEL_PATH = _find_asset(MODELS_DIR, (".stl",)) or os.path.join(
    MODELS_DIR, "base_keychain.stl"
)
FONT_PATH = _find_asset(FONTS_DIR, (".ttf", ".otf")) or os.path.join(
    FONTS_DIR, "plate_font.ttf"
)

# ── 基础模型尺寸（mm）────────────────────────────────────
MODEL = {
    "length": 79.5,
    "width": 25.0,
    "height": 3.0,
}

TEXT_Z_BASE = None

# ── 主文字（右侧区域居中，如 YOUR / FRYTON）──────────────
MAIN_TEXT = {
    "font_size": 30.0,
    "extrude_height": 1.0,
    "max_length": 8,
    "auto_fit": True,
    "height_fill_ratio": 0.80,
    "font_height_ratio": 0.684,
    "right_reserved": 6.0,      # 右侧挂环区域预留 (mm)
    "horizontal_margin": 4.0,   # 主文字区水平边距 (mm)
    "gap_after_side": 3.0,      # 左侧文字与主文字之间的间距 (mm)
}

# ── 侧边文字（左侧竖排小字，如 A / C / T）────────────────
SIDE_TEXT = {
    "font_size": 5.5,
    "extrude_height": 1.0,
    "left_margin": 3.5,       # 文字左边缘距牌面左边缘的固定距离 (mm)
    "char_spacing": 5.5,        # 字符竖向间距 (mm)
    "max_length": 3,
}

# ── 超长文字自动缩小 ──────────────────────────────────────
AUTO_SCALE = True
AUTO_SCALE_MIN_FONT_SIZE = 9.0

# ── 批量生成 ──────────────────────────────────────────────
BATCH = {
    "max_workers": None,  # 并行进程数，None = CPU 核心数
}
