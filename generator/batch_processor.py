"""Excel 批量订单解析与 ZIP 打包。"""

from __future__ import annotations

import io
import os
import re
import zipfile
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

import openpyxl

import config
from generator.stl_generator import ModelGenerationError, generate_keychain
from generator.text_utils import normalize_custom_text
REQUIRED_COLUMNS = (
    "订单号",
    "订单数量",
    "文本-定制文字标题",
    "文本-定制文字内容",
    "选项-标题",
    "选项-选择项输出文本",
)

CUSTOM_TEXT_KEY = "Custom Text"
STATE_KEY = "State"
TEXT_BORDER_KEY = "Text and Border Color"
PLATE_COLOR_KEY = "Plate Color"

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class BatchOrder:
    order_id: str
    quantity: int
    main_text: str
    side_text: str
    folder_code: str


def _cell_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _safe_path_part(name: str) -> str:
    cleaned = INVALID_PATH_CHARS.sub("_", name).strip().strip(".")
    return cleaned or "unknown"


def _parse_quantity(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return max(1, int(float(value)))
    except (TypeError, ValueError):
        raise ModelGenerationError(f"订单数量无效: {value}") from None


def _canonical_text_key(key: str) -> str | None:
    if not key:
        return None
    normalized = key.strip().lower()
    if normalized == "custom text":
        return CUSTOM_TEXT_KEY
    if normalized == "state":
        return STATE_KEY
    return key.strip()


def _canonical_option_key(key: str) -> str | None:
    if not key:
        return None
    normalized = key.strip().lower()
    if normalized == "text and border color":
        return TEXT_BORDER_KEY
    if normalized == "plate color":
        return PLATE_COLOR_KEY
    return key.strip()


def _get_option_value(options: dict[str, str], canonical_key: str) -> str:
    if canonical_key in options:
        return options[canonical_key]
    target = canonical_key.strip().lower()
    for key, value in options.items():
        if key.strip().lower() == target:
            return value
    return ""


def _make_folder_code(text_border: str, plate_color: str) -> str:
    """文件夹名 = Text and Border Color - Plate Color（横线连接）。"""
    border = _safe_path_part(text_border) if text_border else ""
    plate = _safe_path_part(plate_color) if plate_color else ""
    if border and plate:
        return f"{border}-{plate}"
    if border:
        return border
    if plate:
        return plate
    return "default"


def parse_orders_from_excel(file_bytes: bytes) -> list[BatchOrder]:
    """解析 Excel，按订单号聚合多行键值对。"""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        raise ModelGenerationError(f"无法读取 Excel 文件: {e}") from e

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ModelGenerationError("Excel 文件为空")

    headers = [_cell_str(h) for h in rows[0]]
    missing = [col for col in REQUIRED_COLUMNS if col not in headers]
    if missing:
        raise ModelGenerationError(f"缺少必要列: {', '.join(missing)}")

    col = {name: headers.index(name) for name in REQUIRED_COLUMNS}
    groups: dict[str, dict] = defaultdict(
        lambda: {"quantity": 1, "custom_texts": {}, "options": {}}
    )
    last_order_id: str | None = None

    for row_no, row in enumerate(rows[1:], start=2):
        if not row or not any(cell is not None and str(cell).strip() for cell in row):
            continue

        order_id = _cell_str(row[col["订单号"]])
        if order_id:
            last_order_id = order_id
        elif last_order_id:
            # 续行：订单号为空时归入上一订单（常见于选项/State 分行填写）
            order_id = last_order_id
        else:
            continue

        qty = _parse_quantity(row[col["订单数量"]])
        if qty is not None:
            groups[order_id]["quantity"] = qty

        text_key = _canonical_text_key(_cell_str(row[col["文本-定制文字标题"]]))
        text_val = _cell_str(row[col["文本-定制文字内容"]])
        if text_key:
            groups[order_id]["custom_texts"][text_key] = text_val

        opt_key = _canonical_option_key(_cell_str(row[col["选项-标题"]]))
        opt_val = _cell_str(row[col["选项-选择项输出文本"]])
        if opt_key and opt_val:
            groups[order_id]["options"][opt_key] = opt_val

    if not groups:
        raise ModelGenerationError("Excel 中未找到有效订单数据")

    orders: list[BatchOrder] = []
    for order_id, data in groups.items():
        custom = data["custom_texts"]
        try:
            main_text = normalize_custom_text(custom.get(CUSTOM_TEXT_KEY, ""))
            side_text = normalize_custom_text(custom.get(STATE_KEY, ""), allow_empty=True)
        except ModelGenerationError as e:
            raise ModelGenerationError(f"订单 {order_id}: {e}") from e

        opts = data["options"]
        folder_code = _make_folder_code(
            _get_option_value(opts, TEXT_BORDER_KEY),
            _get_option_value(opts, PLATE_COLOR_KEY),
        )

        orders.append(
            BatchOrder(
                order_id=order_id,
                quantity=data["quantity"],
                main_text=main_text,
                side_text=side_text,
                folder_code=folder_code,
            )
        )

    return orders


@dataclass
class _StlFileItem:
    arcname: str
    main_text: str
    side_text: str


def _generate_stl_worker(main_text: str, side_text: str) -> bytes:
    """进程池工作函数（需在模块顶层定义，供 Windows 多进程 pickle）。"""
    return generate_keychain(main_text, side_text)


def _resolve_max_workers(task_count: int) -> int:
    configured = config.BATCH.get("max_workers")
    cpu = os.cpu_count() or 4
    limit = configured if configured else cpu
    return max(1, min(task_count, limit))


def _build_file_items(orders: list[BatchOrder]) -> list[_StlFileItem]:
    folder_counts: dict[str, int] = defaultdict(int)
    for order in orders:
        folder_counts[order.folder_code] += order.quantity

    items: list[_StlFileItem] = []
    for order in orders:
        count = folder_counts[order.folder_code]
        folder = _safe_path_part(f"{count}-{order.folder_code}")
        safe_order_id = _safe_path_part(order.order_id)
        for seq in range(1, order.quantity + 1):
            items.append(
                _StlFileItem(
                    arcname=f"{folder}/{safe_order_id}-{seq}.stl",
                    main_text=order.main_text,
                    side_text=order.side_text,
                )
            )
    return items


def _generate_models_parallel(
    items: list[_StlFileItem],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[tuple[str, str], bytes]:
    """并行生成唯一文字组合的 STL，返回缓存字典。"""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in items:
        key = (item.main_text, item.side_text)
        grouped[key].append(item.arcname)

    unique_keys = list(grouped.keys())
    total_files = len(items)
    completed_files = 0
    cache: dict[tuple[str, str], bytes] = {}
    workers = _resolve_max_workers(len(unique_keys))

    def report(message: str) -> None:
        if progress_callback:
            progress_callback(completed_files, total_files, message)

    report(f"并行生成中（{workers} 进程，{len(unique_keys)} 种模型）…")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_generate_stl_worker, key[0], key[1]): key
            for key in unique_keys
        }
        for future in as_completed(future_map):
            key = future_map[future]
            cache[key] = future.result()
            completed_files += len(grouped[key])
            sample_name = os.path.basename(grouped[key][0])
            report(f"已完成 {completed_files}/{total_files}（{sample_name}）")

    return cache


def generate_batch_zip(
    file_bytes: bytes,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[bytes, str]:
    """批量并行生成 STL 并打包为 ZIP，返回 (zip_bytes, zip_filename)。"""

    def report(current: int, total: int, message: str) -> None:
        if progress_callback:
            progress_callback(current, total, message)

    report(0, 1, "正在解析 Excel…")
    orders = parse_orders_from_excel(file_bytes)
    items = _build_file_items(orders)

    if not items:
        raise ModelGenerationError("没有需要生成的模型")

    total = len(items)
    cache = _generate_models_parallel(items, progress_callback)

    report(total, total, "正在打包 ZIP…")
    zip_buf = io.BytesIO()
    zip_name = f"双色车牌-{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            key = (item.main_text, item.side_text)
            zf.writestr(item.arcname, cache[key])

    zip_buf.seek(0)
    return zip_buf.getvalue(), zip_name
