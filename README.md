# 车牌钥匙扣 STL 生成器

根据用户输入的文字，在固定的钥匙扣基础模型上生成 3D 凸起文字，输出可 3D 打印的 STL 文件。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> CadQuery 依赖 OpenCASCADE，首次安装可能需要几分钟。Windows 用户建议使用 Python 3.10–3.12。

### 2. 放置基础模型

将你的**不含文字**的钥匙扣模型放到：

```
assets/models/base_keychain.stl
```

**模型格式要求：**

| 项目 | 要求 |
|------|------|
| 格式 | **STL**（二进制或 ASCII 均可） |
| 内容 | 仅包含牌面、边框、挂环等固定结构，**不含任何文字** |
| 坐标系 | 文字生成在 XY 平面，Z 轴向上挤出；**牌面几何中心位于原点 (0, 0, 0)** |
| 单位 | **毫米 (mm)** |
| 尺寸 | 当前按 **79.5 × 25 × 3 mm**（长 × 宽 × 高）校准 |
| 朝向 | 牌面朝上，文字从凹槽底面（默认 z=2）向 +Z 挤出 1mm |

### 3. 放置字体文件

将 TTF 或 OTF 字体放到：

```
assets/fonts/plate_font.ttf
```

文件名须为 `plate_font.ttf`（若为 OTF，可改 `config.py` 中的 `FONT_PATH`）。

### 4. 调整文字位置（重要）

打开 `config.py`，根据你的基础模型尺寸调整文字位置和大小（已按 79.5×25×3mm 预设）：

```python
MODEL = {
    "length": 79.5,
    "width": 25.0,
    "height": 3.0,
}

TEXT_Z_BASE = 2.0   # 文字贴合面 Z 坐标（底板 2mm + 凸起 1mm）

MAIN_TEXT = {
    "font_size": 13.0,
    "extrude_height": 1.0,
    "x": 2.0,       # 略向右偏，补偿左侧州名区
    "y": 0.0,
}

SIDE_TEXT = {
    "font_size": 4.5,
    "x": -33.0,     # 左侧边距区
    "char_spacing": 5.0,
}
```

建议流程：先用默认参数生成一次，在切片软件中查看文字位置，再微调 `config.py` 中的数值。

### 5. 启动应用

```bash
python app.py
```

浏览器访问 http://127.0.0.1:5000

> **注意（Windows）：** 若页面显示 500 错误，请先按 `Ctrl+C` 停止旧的服务进程，再重新运行 `python app.py`。代码已关闭 Flask 自动重载（与 CadQuery 冲突）。若 5000 端口被占用，可执行 `$env:PORT=8765; python app.py` 换端口启动。

## API 接口

```
POST /api/generate
Content-Type: application/json

{
  "main_text": "FRYTON",
  "side_text": "WA"
}
```

返回 STL 文件下载。

### 批量生成

```
POST /api/batch-generate          # 上传 Excel，返回 { "job_id": "..." }
GET  /api/batch-progress/<job_id> # 查询进度 { status, current, total, percent, message }
GET  /api/batch-download/<job_id> # 下载 ZIP（完成后）
```

**Excel 必要列：**

| 列名 | 说明 |
|------|------|
| 订单号 | 唯一订单标识 |
| 订单数量 | 该订单模型份数 |
| 文本-定制文字标题 | 键：`Custom Text` 或 `State` |
| 文本-定制文字内容 | 值：右侧主文字 / 左侧文字 |
| 选项-标题 | 键：`Text and Border Color` 或 `Plate Color` |
| 选项-选择项输出文本 | 颜色选项值，组合为文件夹名 |

同一订单可占多行，按订单号聚合。`State` 可留空。导出文件名为 `订单号-序号.stl`，按颜色编码分文件夹存放。

## 项目结构

```
plate-number/
├── app.py                  # Flask 入口
├── config.py               # 文字位置与路径配置
├── generator/
│   ├── stl_generator.py    # STL 生成核心逻辑
│   └── batch_processor.py  # Excel 批量解析与 ZIP 打包
├── templates/
│   └── index.html          # Web 界面（单个 / 批量 Tab）
├── assets/
│   ├── models/
│   │   └── base_keychain.stl   ← 你提供的基础模型
│   └── fonts/
│       └── plate_font.ttf      ← 你提供的字体文件
└── requirements.txt
```

## 效果说明

- **主文字**：右侧区域居中大字
- **侧边文字**：左侧竖排小字（最多 3 个字符，可留空）
- 文字超过 8 个字符时自动缩小字号（可在 `config.py` 关闭）
