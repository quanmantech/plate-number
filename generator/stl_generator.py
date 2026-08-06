"""STL 车牌钥匙扣模型生成器（支持多款式）。"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import threading

import cadquery as cq
from cadquery.occ_impl.shapes import Shape, Compound
from OCP.Font import Font_FontMgr
from OCP.StlAPI import StlAPI_Reader
from OCP.TCollection import TCollection_AsciiString
from OCP.TopoDS import TopoDS_Shape

import config

# CadQuery/OCCT 用 AsciiString 传 fontPath：路径含中文等非 ASCII 时 CheckFont 会失败，
# 随后静默回退到系统 Arial。按源字体路径缓存解析结果。
_font_lock = threading.Lock()
_resolved_fonts: dict[str, str] = {}
_font_tmpdir: str | None = None


class ModelGenerationError(Exception):
    """模型生成失败。"""


def _path_is_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _occt_can_load_font(path: str) -> bool:
    mgr = Font_FontMgr.GetInstance_s()
    return bool(mgr.CheckFont(TCollection_AsciiString(path).ToCString()))


def _resolve_font_path(font_path: str) -> str:
    """返回 OCCT 能加载的字体绝对路径；必要时复制到纯 ASCII 临时目录。"""
    global _font_tmpdir

    src = os.path.abspath(font_path)
    with _font_lock:
        cached = _resolved_fonts.get(src)
        if cached and os.path.isfile(cached):
            return cached

        if not os.path.isfile(src):
            raise ModelGenerationError(
                f"字体文件未找到: {src}\n"
                "请将 TTF/OTF 字体放到对应款式的 fonts 目录"
            )

        candidates = [src]
        if not _path_is_ascii(src):
            if _font_tmpdir is None:
                _font_tmpdir = tempfile.mkdtemp(prefix="plate_font_")
            ext = os.path.splitext(src)[1].lower() or ".ttf"
            # 用哈希避免多款式字体互相覆盖
            digest = abs(hash(src)) % (10**8)
            dst = os.path.join(_font_tmpdir, f"font_{digest}{ext}")
            shutil.copy2(src, dst)
            candidates.insert(0, dst)

        for path in candidates:
            if _path_is_ascii(path) and _occt_can_load_font(path):
                _resolved_fonts[src] = path
                return path

        raise ModelGenerationError(
            f"OpenCASCADE 无法加载字体: {src}\n"
            "请确认字体文件有效，且尽量放在纯英文路径中。"
        )


def _load_style(style_id: str | None) -> dict:
    try:
        return config.get_style(style_id)
    except ValueError as e:
        raise ModelGenerationError(str(e)) from e


def _validate_paths(style: dict) -> None:
    if not os.path.isfile(style["base_model_path"]):
        raise ModelGenerationError(
            f"[{style['label']}] 基础模型未找到: {style['base_model_path']}\n"
            f"请将不含文字的 STL 放到 {style['models_dir']}"
        )
    _resolve_font_path(style["font_path"])


def _load_base_stl(path: str) -> tuple[cq.Workplane, Shape]:
    """加载 STL 并返回 Workplane 与 Shape（兼容 CadQuery 2.8）。"""
    reader = StlAPI_Reader()
    topo = TopoDS_Shape()
    if not reader.Read(topo, path):
        raise ModelGenerationError(f"无法读取 STL 文件: {path}")

    solid = Shape(topo)
    wp = cq.Workplane("XY").newObject([solid])
    return wp, solid


def _text_z(style: dict, extrude_height: float, bb) -> float:
    if style.get("text_z_base") is not None:
        return style["text_z_base"]
    return bb.zmax - extrude_height


def _make_text(
    text: str, font_size: float, extrude_height: float, font_path: str
) -> cq.Workplane:
    return cq.Workplane("XY").text(
        text.upper(),
        fontsize=font_size,
        distance=extrude_height,
        fontPath=_resolve_font_path(font_path),
        halign="center",
        valign="center",
    )


def _place_text(wp: cq.Workplane, target_x: float, target_y: float, z: float) -> cq.Workplane:
    """按包围盒将文字精确对齐到目标中心点。"""
    tbb = wp.val().BoundingBox()
    return wp.translate((
        target_x - tbb.center.x,
        target_y - tbb.center.y,
        z - tbb.zmin,
    ))


def _place_text_by_left(
    wp: cq.Workplane, left_x: float, target_y: float, z: float
) -> cq.Workplane:
    """按包围盒左边缘对齐，保证距牌面左边的距离固定。"""
    tbb = wp.val().BoundingBox()
    return wp.translate((
        left_x - tbb.xmin,
        target_y - tbb.center.y,
        z - tbb.zmin,
    ))


def _wp_bbox(wp: cq.Workplane):
    return wp.val().BoundingBox()


def _main_text_bounds(
    style: dict, bb, side_wp: cq.Workplane | None = None
) -> tuple[float, float]:
    """计算主文字可用区域的水平范围 (left, right)。"""
    cfg = style["main_text"]
    margin = cfg.get("horizontal_margin", 4.0)
    right = bb.xmax - cfg.get("right_reserved", 0.0) - margin / 2

    if side_wp is not None:
        side_right = _wp_bbox(side_wp).xmax
        left = side_right + cfg.get("gap_after_side", 3.0)
    else:
        left = bb.xmin + cfg.get("left_reserved", 0.0) + margin / 2

    return left, right


def _main_text_center(
    style: dict, bb, side_wp: cq.Workplane | None = None
) -> tuple[float, float]:
    left, right = _main_text_bounds(style, bb, side_wp)
    return (left + right) / 2, bb.center.y


def _compute_main_font_size(
    style: dict, text: str, bb, side_wp: cq.Workplane | None = None
) -> float:
    cfg = style["main_text"]
    font_size = cfg["font_size"]
    font_path = style["font_path"]

    if cfg.get("auto_fit", True):
        target_h = bb.ylen * cfg.get("height_fill_ratio", 0.80)
        left, right = _main_text_bounds(style, bb, side_wp)
        avail_w = right - left

        # 用探针实测当前字体宽高比（换字体后硬编码 ratio 会算错字号）
        probe = _make_text(text, 10.0, cfg["extrude_height"], font_path)
        probe_bb = probe.val().BoundingBox()
        probe_w = probe_bb.xlen
        probe_h = probe_bb.ylen
        height_ratio = (
            probe_h / 10.0
            if probe_h > 0
            else cfg.get("font_height_ratio", 0.7)
        )
        by_height = target_h / height_ratio
        by_width = avail_w * 10.0 / probe_w if probe_w > 0 else by_height

        font_size = min(font_size, by_height, by_width)

    if not style.get("auto_scale", True):
        return font_size

    max_len = cfg["max_length"]
    if len(text) <= max_len:
        return font_size

    scale = max_len / len(text)
    return max(style.get("auto_scale_min_font_size", 6.0), font_size * scale)


def _create_main_text(
    style: dict, text: str, bb, side_wp: cq.Workplane | None = None
) -> cq.Workplane:
    cfg = style["main_text"]
    font_size = _compute_main_font_size(style, text, bb, side_wp)
    target_x, target_y = _main_text_center(style, bb, side_wp)
    z = _text_z(style, cfg["extrude_height"], bb)

    wp = _make_text(text, font_size, cfg["extrude_height"], style["font_path"])
    return _place_text(wp, target_x, target_y, z)


def _side_char_spacing(style: dict, font_size: float, n: int, bb) -> float:
    """按字高与牌面高度计算竖排字距，避免换字体后粘连或溢出。"""
    cfg = style["side_text"]
    configured = cfg.get("char_spacing", font_size)
    if n <= 1:
        return configured

    probe = _make_text("H", font_size, cfg["extrude_height"], style["font_path"])
    char_h = probe.val().BoundingBox().ylen
    fill = cfg.get("height_fill_ratio", 0.78)
    avail = bb.ylen * fill
    # (n-1)*spacing + char_h <= avail
    max_spacing = (avail - char_h) / (n - 1) if avail > char_h else char_h
    min_spacing = char_h * cfg.get("min_gap_ratio", 1.15)
    # 在牌面内尽量拉开：取期望字距，夹在 [min_spacing, max_spacing]
    desired = max(configured, min_spacing)
    if max_spacing < min_spacing:
        return max(0.1, max_spacing)
    return min(desired, max_spacing)


def _create_side_text(style: dict, text: str, bb) -> cq.Workplane | None:
    if not text or not style.get("has_side_text") or not style.get("side_text"):
        return None

    cfg = style["side_text"]
    chars = [c for c in text.upper()[: cfg["max_length"]] if c != " "]
    if not chars:
        return None
    z = _text_z(style, cfg["extrude_height"], bb)
    font_size = cfg["font_size"]
    n = len(chars)
    spacing = _side_char_spacing(style, font_size, n, bb)

    result = None
    for i, char in enumerate(chars):
        y_local = (n - 1) / 2 * spacing - i * spacing
        char_wp = _make_text(char, font_size, cfg["extrude_height"], style["font_path"])
        char_wp = char_wp.translate((0, y_local, 0))
        result = char_wp if result is None else result.union(char_wp)

    left_x = bb.xmin + cfg.get("left_margin", 3.5)
    return _place_text_by_left(result, left_x, bb.center.y, z)


def _collect_shapes(*workplanes: cq.Workplane | None) -> list:
    shapes: list = []
    for wp in workplanes:
        if wp is None:
            continue
        val = wp.val()
        if val is None:
            continue
        solids = val.Solids()
        shapes.extend(solids if solids else [val])
    return shapes


def _merge_model(base: cq.Workplane, *parts: cq.Workplane | None) -> Compound:
    shapes = _collect_shapes(base, *parts)
    if not shapes:
        raise ModelGenerationError("模型合并失败：没有可导出的几何体")
    return Compound.makeCompound(shapes)


def generate_keychain(
    main_text: str,
    side_text: str = "",
    style_id: str | None = None,
) -> bytes:
    """
    生成车牌钥匙扣 STL 模型。

    Args:
        main_text: 主文字
        side_text: 侧边竖排小字（仅 classic 等支持侧字的款式）
        style_id: 款式 id（classic / slim），默认 classic
    """
    style = _load_style(style_id)
    _validate_paths(style)

    main_text = main_text.strip()
    side_text = side_text.strip() if style.get("has_side_text") else ""

    if not main_text:
        raise ModelGenerationError("主文字不能为空")

    max_main = style["main_text"]["max_length"]
    hard_max = style["main_text"].get("hard_max_length", max_main)
    if len(main_text) > hard_max:
        raise ModelGenerationError(f"主文字最多 {hard_max} 个字符")
    if len(main_text) > max_main and not style.get("auto_scale", True):
        raise ModelGenerationError(f"主文字最多 {max_main} 个字符")

    side_cfg = style.get("side_text")
    if side_cfg and len(side_text) > side_cfg["max_length"]:
        raise ModelGenerationError(
            f"侧边文字最多 {side_cfg['max_length']} 个字符"
        )

    base, solid = _load_base_stl(style["base_model_path"])
    bb = solid.BoundingBox()

    side = _create_side_text(style, side_text, bb)
    main = _create_main_text(style, main_text, bb, side)
    model = _merge_model(base, main, side)

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        Shape.exportStl(model, tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def generate_keychain_to_buffer(
    main_text: str,
    side_text: str = "",
    style_id: str | None = None,
) -> io.BytesIO:
    """生成 STL 并返回 BytesIO 缓冲区，便于 Flask 直接发送。"""
    buf = io.BytesIO(generate_keychain(main_text, side_text, style_id=style_id))
    buf.seek(0)
    return buf
