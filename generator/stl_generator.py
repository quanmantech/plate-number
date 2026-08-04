"""STL 车牌钥匙扣模型生成器。"""

from __future__ import annotations

import io
import os
import tempfile

import cadquery as cq
from cadquery.occ_impl.shapes import Shape, Compound
from OCP.StlAPI import StlAPI_Reader
from OCP.TopoDS import TopoDS_Shape

import config


class ModelGenerationError(Exception):
    """模型生成失败。"""


def _validate_paths() -> None:
    if not os.path.isfile(config.BASE_MODEL_PATH):
        raise ModelGenerationError(
            f"基础模型未找到: {config.BASE_MODEL_PATH}\n"
            "请将不含文字的钥匙扣 STL 文件放到 assets/models/ 目录"
        )
    if not os.path.isfile(config.FONT_PATH):
        raise ModelGenerationError(
            f"字体文件未找到: {config.FONT_PATH}\n"
            "请将 TTF/OTF 字体文件放到 assets/fonts/ 目录"
        )


def _load_base_stl(path: str) -> tuple[cq.Workplane, Shape]:
    """加载 STL 并返回 Workplane 与 Shape（兼容 CadQuery 2.8）。"""
    reader = StlAPI_Reader()
    topo = TopoDS_Shape()
    if not reader.Read(topo, path):
        raise ModelGenerationError(f"无法读取 STL 文件: {path}")

    solid = Shape(topo)
    wp = cq.Workplane("XY").newObject([solid])
    return wp, solid


def _text_z(extrude_height: float, bb) -> float:
    if config.TEXT_Z_BASE is not None:
        return config.TEXT_Z_BASE
    return bb.zmax - extrude_height


def _make_text(text: str, font_size: float, extrude_height: float) -> cq.Workplane:
    return cq.Workplane("XY").text(
        text.upper(),
        fontsize=font_size,
        distance=extrude_height,
        fontPath=config.FONT_PATH,
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


def _main_text_bounds(bb, side_wp: cq.Workplane | None = None) -> tuple[float, float]:
    """计算主文字可用区域的水平范围 (left, right)。"""
    cfg = config.MAIN_TEXT
    margin = cfg.get("horizontal_margin", 4.0)
    right = bb.xmax - cfg.get("right_reserved", 6.0) - margin / 2

    if side_wp is not None:
        side_right = _wp_bbox(side_wp).xmax
        left = side_right + cfg.get("gap_after_side", 3.0)
    else:
        left = bb.xmin + margin / 2

    return left, right


def _main_text_center(bb, side_wp: cq.Workplane | None = None) -> tuple[float, float]:
    """主文字在剩余区域内水平、垂直居中。"""
    left, right = _main_text_bounds(bb, side_wp)
    return (left + right) / 2, bb.center.y


def _compute_main_font_size(
    text: str, bb, side_wp: cq.Workplane | None = None
) -> float:
    cfg = config.MAIN_TEXT
    font_size = cfg["font_size"]

    if cfg.get("auto_fit", True):
        target_h = bb.ylen * cfg.get("height_fill_ratio", 0.80)
        height_ratio = cfg.get("font_height_ratio", 0.684)
        by_height = target_h / height_ratio

        left, right = _main_text_bounds(bb, side_wp)
        avail_w = right - left
        probe = _make_text(text, 10.0, cfg["extrude_height"])
        probe_w = probe.val().BoundingBox().xlen
        by_width = avail_w * 10.0 / probe_w if probe_w > 0 else by_height

        font_size = min(font_size, by_height, by_width)

    if not config.AUTO_SCALE:
        return font_size

    max_len = cfg["max_length"]
    if len(text) <= max_len:
        return font_size

    scale = max_len / len(text)
    return max(config.AUTO_SCALE_MIN_FONT_SIZE, font_size * scale)


def _create_main_text(
    text: str, bb, side_wp: cq.Workplane | None = None
) -> cq.Workplane:
    cfg = config.MAIN_TEXT
    font_size = _compute_main_font_size(text, bb, side_wp)
    target_x, target_y = _main_text_center(bb, side_wp)
    z = _text_z(cfg["extrude_height"], bb)

    wp = _make_text(text, font_size, cfg["extrude_height"])
    return _place_text(wp, target_x, target_y, z)


def _create_side_text(text: str, bb) -> cq.Workplane | None:
    if not text:
        return None

    cfg = config.SIDE_TEXT
    # 竖排显示时跳过空格字符（空格仅用于输入格式，不参与渲染）
    chars = [c for c in text.upper()[: cfg["max_length"]] if c != " "]
    if not chars:
        return None
    z = _text_z(cfg["extrude_height"], bb)
    spacing = cfg["char_spacing"]
    n = len(chars)

    # 逐字生成后竖排组合，再按包围盒整体居中
    result = None
    for i, char in enumerate(chars):
        y_local = (n - 1) / 2 * spacing - i * spacing
        char_wp = _make_text(char, cfg["font_size"], cfg["extrude_height"])
        char_wp = char_wp.translate((0, y_local, 0))
        result = char_wp if result is None else result.union(char_wp)

    left_x = bb.xmin + cfg.get("left_margin", 3.5)
    return _place_text_by_left(result, left_x, bb.center.y, z)


def _collect_shapes(*workplanes: cq.Workplane | None) -> list:
    """从 Workplane 中提取所有 Shape 对象。"""
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
    """将底座 STL 网格与文字实体合并为一个 Compound（STL 网格无法做布尔 union）。"""
    shapes = _collect_shapes(base, *parts)
    if not shapes:
        raise ModelGenerationError("模型合并失败：没有可导出的几何体")
    return Compound.makeCompound(shapes)


def generate_keychain(main_text: str, side_text: str = "") -> bytes:
    """
    生成车牌钥匙扣 STL 模型。

    Args:
        main_text: 主文字（居中显示，如 FRYTON）
        side_text: 侧边竖排小字（如 WA），可选

    Returns:
        STL 文件二进制内容
    """
    _validate_paths()

    main_text = main_text.strip()
    side_text = side_text.strip()

    if not main_text:
        raise ModelGenerationError("主文字不能为空")
        raise ModelGenerationError(
            f"主文字最多 {config.MAIN_TEXT['max_length']} 个字符"
        )

    if len(side_text) > config.SIDE_TEXT["max_length"]:
        raise ModelGenerationError(
            f"侧边文字最多 {config.SIDE_TEXT['max_length']} 个字符"
        )

    base, solid = _load_base_stl(config.BASE_MODEL_PATH)
    bb = solid.BoundingBox()

    side = _create_side_text(side_text, bb)
    main = _create_main_text(main_text, bb, side)
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


def generate_keychain_to_buffer(main_text: str, side_text: str = "") -> io.BytesIO:
    """生成 STL 并返回 BytesIO 缓冲区，便于 Flask 直接发送。"""
    buf = io.BytesIO(generate_keychain(main_text, side_text))
    buf.seek(0)
    return buf
