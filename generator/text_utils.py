"""定制文字规范化与校验。"""

import re

from generator.stl_generator import ModelGenerationError

# 禁止控制字符（换行、制表符等）
INVALID_TEXT_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_custom_text(text: str, *, allow_empty: bool = False) -> str:
    """
    规范化定制文字：去除首尾空格；仅含空白时视为空字符串。

    支持字母、数字、空格及其他可打印符号（如 - . & # 等）。
  """
    normalized = text.strip()
    if not normalized:
        if allow_empty:
            return ""
        raise ModelGenerationError("主文字不能为空")

    if INVALID_TEXT_CHARS.search(normalized):
        raise ModelGenerationError("文字包含非法控制字符")

    return normalized
