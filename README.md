# 车牌钥匙扣 STL 生成器

根据用户输入的文字，在固定的钥匙扣基础模型上生成 3D 凸起文字，输出可 3D 打印的 STL 文件。

## 快速开始

### 1. 安装依赖

**运行环境要求：Python 3.11 或 3.12**（CadQuery 2.8 / cadquery-ocp 在此范围最稳定）。

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

> CadQuery 依赖 OpenCASCADE（`cadquery-ocp`），首次安装可能需要几分钟、体积较大。  
> 若出现 `ResolutionImpossible` / `cadquery-ocp` 冲突，请确认 Python 版本为 3.11/3.12，并升级 pip 后再装。

### 2. 放置基础模型与字体（按款式）

应用支持两种款式，资源和参数分开：

| 款式 | ID | 尺寸 | 布局 | 资源目录 |
|------|----|------|------|----------|
| 双色车牌 | `classic` | 约 79.5×25×3 mm | 右侧挂环，可选左侧竖排 | `assets/models/` + `assets/fonts/`（或 `assets/styles/classic/`） |
| 窄版车牌 | `slim` | 约 70×17×3 mm（文字挤出后总高约 4 mm） | 左侧挂孔，单行横排 | `assets/styles/slim/models/` + `assets/styles/slim/fonts/` |

**模型格式要求：**

| 项目 | 要求 |
|------|------|
| 格式 | **STL**（二进制或 ASCII 均可） |
| 内容 | 仅包含牌面、边框、挂孔等固定结构，**不含任何文字** |
| 单位 | **毫米 (mm)** |
| 朝向 | 牌面朝上，文字沿 +Z 挤出（默认 `extrude_height=1.0`） |

**窄版（slim）请将空白 STL 和字体分别放到：**

```
assets/styles/slim/models/   ← 空白模型（70×17×3）
assets/styles/slim/fonts/    ← TTF/OTF 字体（文件名任意）
```

### 3. 调整文字参数

打开 `config.py` 中的 `STYLES`，按款式微调字号、左右预留（挂孔/挂环）等。窄版左侧挂孔预留由 `left_reserved` 控制。

建议流程：放入资源后生成一次，在切片软件中查看，再微调对应款式参数。

### 4. 启动应用

**Windows：** 双击 `start.bat`

- 使用系统已安装的 Python（优先项目 `venv`）
- 未安装 Python 时会提示，并打开下载页：  
  https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe  
  （安装时勾选 Add python.exe to PATH）
- 首次运行会自动创建 venv 并用清华源安装依赖

或手动启动：

```bash
python app.py
```

浏览器访问 http://127.0.0.1:5001

### 5. 打包发布（Windows）

双击 `package.bat`，在 `dist/` 生成源码 ZIP（不含 Python / venv）。  
目标电脑需自行安装 Python 3.11/3.12，再运行 `start.bat`。

## API 接口

```
POST /api/generate
Content-Type: application/json

{
  "style": "classic",
  "main_text": "FRYTON",
  "side_text": "WA"
}
```

窄版示例：`"style": "slim", "main_text": "HAII LBH"`（无需 `side_text`）。

返回 STL 文件下载。

### 批量生成

```
POST /api/batch-generate          # form: file + style，返回 { "job_id": "..." }
GET  /api/batch-progress/<job_id> # 查询进度 { status, current, total, percent, message }
GET  /api/batch-download/<job_id> # 下载 ZIP（完成后）
```

**Excel 必要列：**

| 列名 | 说明 |
|------|------|
| 订单号 | 唯一订单标识 |
| 订单数量 | 该订单模型份数 |
| 文本-定制文字标题 | 键：`Custom Text` 或 `State` |
| 文本-定制文字内容 | 值：主文字 / 左侧文字（slim 忽略 State） |
| 选项-标题 | 键：`Text and Border Color` 或 `Plate Color` |
| 选项-选择项输出文本 | 颜色选项值，组合为文件夹名 |

同一订单可占多行，按订单号聚合。`State` 可留空。导出文件名为 `订单号-序号.stl`，按颜色编码分文件夹存放。

## 项目结构

```
plate-number/
├── app.py
├── config.py                 # STYLES 多款式配置
├── generator/
├── templates/index.html
├── assets/
│   ├── models/ + fonts/      # classic 兼容路径
│   └── styles/
│       ├── classic/{models,fonts}
│       └── slim/{models,fonts}   ← 窄版资源放这里
└── requirements.txt
```

## 效果说明

- **双色车牌 (classic)**：右侧主文字 + 可选左侧竖排
- **窄版车牌 (slim)**：单行横排（如 `HAII LBH`），左侧挂孔区自动预留
- 文字过长时按款式自动缩小字号