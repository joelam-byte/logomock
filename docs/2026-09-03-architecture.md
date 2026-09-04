# logo 工作台 —— 系统架构与任务分解

版本：v0.3（合并 software-architect-2 与 -3 两版精华，主理人审定并实测复核）
日期：2026-09-03
架构师：高见远（software-architect-2 + software-architect-3）
审定：齐活林（team-lead）

> **本版本变更**：v0.3 在 v0.2 基础上，合并了 software-architect-2（因限流中断但已发回关键内容）的两条实测硬结论 + 三条同源性机制保证 + 能力探测双模式。所有新增技术结论均已由主理人复跑 Inkscape 实测复核通过。

> **前置文档**
> - `2026-09-02-logo-mockup-design.md` —— 设计文档 v0.2（需求、决策、数据流、错误处理 12 条、测试 T1～T6）
> - `2026-09-03-inkscape-probe.md` —— 引擎实测报告（本文档所有技术参数的唯一来源）
>
> 本文件不复述需求，只写实现方案。三份文档冲突时以本文档为准。

---

## 0. 相对主理人初始稿的两处改动

| # | 改动 | 来源 | 说明 |
|---|------|------|------|
| 1 | `input/ output/ project.json` 从项目根平铺改为 **`projects/<订单>/` 子目录** | 架构师 | 平铺会导致第二个订单覆盖第一个；设计文档 3.2 已定「一个订单 = 一个文件夹」 |
| 2 | 纠正 B3 验收中的格式清单 | 主理人 | 架构师原文写「`.ai/.eps/.cdr` 可转换」，与实测冲突。**EPS 实测导入报 parser error，`.cdr` 亦不支持**，已改为 `.ai/.pdf/.svg` |

---

## 1. 技术栈（已锁定）

| 层 | 选型 | 说明 |
|----|------|------|
| 后端 | Python 3.13 + FastAPI | venv：`C:\Users\ljhmo\.workbuddy\binaries\python\envs\logomock` |
| 前端 | 原生 HTML/CSS/JS | **无构建链**，强制分层（见 3.2） |
| 矢量引擎 | Inkscape CLI 1.4.4 | `D:\Program Files\Inkscape\bin\inkscape.exe`，**不在 PATH** |
| 图像合成 | Pillow 12.3.0 | **仅用于选款图导出**，不用于预览 |
| 存储 | JSON + 原子写入 | 封装在 `routers/project.py`，可迁移（见 3.3） |

已装：fastapi 0.141.1 / uvicorn 0.52.4 / pillow 12.3.0 / python-multipart 0.32

---

## 2. 目录结构

```
logomock/
  run.bat                          双击启动：激活 venv → uvicorn → 自动开浏览器
  requirements.txt                 依赖清单（与已装版本对齐）
  assets/
    icon.ico                       窗口图标（可选）

  app/
    main.py                        FastAPI 入口，挂载路由 + 挂载 web/ 静态目录
    config.py                      路径常量、端口、Inkscape 路径解析（配置 → 注册表 → 默认）
    models.py                      Pydantic 模型，与 project.json schema 一一对应
    routers/
      project.py                   项目文件夹新建/加载/保存（**唯一数据访问入口**）
      upload.py                    接收包图与 logo 源文件，落 input/
      convert.py                   logo 源文件 → logo.svg + logo_preview.png
      export.py                    三份交付物导出编排（**只读 mm，零换算**）
      health.py                    /api/health，返回 Inkscape 可用性与版本
    services/
      spec_svg.py                  工艺尺寸图 SVG 文本生成（logo 矢量 + 尺寸链）
      placement_svg.py             定位图 SVG 文本生成（包正视图 + logo 位置尺寸链）
      selection_png.py             选款图拼版（**全项目唯一使用 Pillow 合成处**，仅导出调用）
      dimension.py                 尺寸链几何：标注线/箭头/文字坐标计算，纯数值无 IO
      errors.py                    AppError + 12 条错误的码、级别、文案模板
    engine/
      base.py                      矢量引擎抽象接口（上层唯一依赖此文件）
      inkscape.py                  Inkscape CLI 实现：路径发现、命令拼装、stderr 捕获
      registry.py                  Windows 注册表读取（HKLM\SOFTWARE\Inkscape\Inkscape）

  web/
    index.html                     单页骨架：顶部步骤条 + 三栏 + 底部方案条
    css/
      layout.css                   三栏栅格、步骤条、方案条布局
      widgets.css                  表单/按钮/**黄色提示条**/方案卡片/阻断弹窗样式
    js/
      state.js                     **单一数据源**：calibration/frames/schemes/current；变更广播
      api.js                       后端 fetch 封装，按错误级别渲染提示条或阻断弹窗
      canvas.js                    **唯一 Canvas 层**：只绘制与交互，零业务状态，通过回调上报
      sidebar.js                   右侧参数面板，订阅 state 重绘
      schemes.js                   底部方案条：方案增删/切换/复制
      steps/
        upload.js                  步骤1 上传包图与 logo
        calib_product.js           步骤2A 产品框定比例尺（高度提示 + px_per_mm 区间提示）
        calib_logo.js              步骤2B logo 框定基准（框超出产品框提示）
        place.js                   步骤3 摆放（夹在框内、锁比缩放、**写入 scheme 的 mm 值**）
        export.js                  步骤4 导出，展示三份结果文件路径与错误
      main.js                      启动装配：初始化 state、挂载步骤、订阅渲染

  projects/
    <日期>_<客户>_<包型>/
      project.json                 全部参数，可复现可回退
      input/                       bag.jpg / logo.<源> / logo.svg / logo_preview.png
      output/                      selection.png / spec.pdf / spec.svg / placement.pdf / placement.svg
```

---

## 3. 关键设计

### 3.1 ★ 引擎适配层（`app/engine/`）

**整套架构唯一为将来留的口子。** Inkscape 被关在这三个文件里，上层完全不知道它存在。

```python
# app/engine/base.py —— 上层唯一依赖
class VectorEngine(Protocol):
    def available(self) -> bool: ...                    # 引擎是否可用
    def version(self) -> str: ...                       # 版本串，用于 health 与错误提示
    def to_svg(self, src: Path, svg: Path) -> None: ... # 任意源格式 → SVG
    def svg_to_pdf(self, svg: Path, pdf: Path, *, text_to_path: bool = True) -> None: ...

# 唯一抛出类型
class EngineError(AppError):
    code: str
    stderr: str
```

**铁律**：
- `app/services/*` 与 `app/routers/*` **只 import `base.py`**
- 这两处禁止出现 `subprocess` 与 "inkscape" 字面量
- 命令拼装、路径发现、stderr 捕获全部封在 `inkscape.py`
- 将来换 Cairo / AI COM 只需新增一个实现类 + 改 `config.py` 工厂，上层零改动

**路径发现顺序**（`inkscape.py` + `registry.py`）：
1. 配置文件指定路径
2. 注册表 `HKLM\SOFTWARE\Inkscape\Inkscape` → `D:\Program Files\Inkscape`
3. 常见安装路径扫描（含 `bin/inkscape.exe`）
4. 全部失败 → `available=False`，**启动不阻断**，调用时给明确提示 + 下载链接

**能力边界（2026-09-03 实测，必须体现在实现中）**

| 能力 | 状态 | 说明 |
|------|------|------|
| 导入 `.ai`（PDF 兼容） | ✅ | 走 PDF 导入路径，矢量完整保留 |
| 导入 `.pdf` / `.svg` | ✅ | |
| 导入 `.eps` | ❌ | **报 parser error**，Inkscape 1.4 把 EPS 当 SVG 解析 |
| 导入 `.cdr` | ❌ | 从未支持 |
| 导出 `.pdf` / `.svg` / `.png` | ✅ | |
| 导出 `.ai` | ❌ | **Inkscape 1.4.4 不支持**，允许值列表中无此项 |

**转曲参数**：`--export-text-to-path`
**无效参数（严禁使用）**：`--pdf-page=1`（1.4.4 无此参数）、`--export-ps-level=3`（对 EPS 导入无效）

**★ 两条实测硬结论（software-architect-2 发现，主理人已复核，引擎层必须遵守）**

| # | 结论 | 实测证据 | 架构含义 |
|---|------|---------|---------|
| 1 | **Inkscape 失败时退出码恒为 0** | EPS 导入失败→exit 0 且无产物；`--export-type=ai` 失败→exit 0 且无产物；PDF 成功→exit 0 | **引擎层禁止用 returncode 判成败**。唯一可靠信号是「输出文件存在且非空」。失败原因从 stderr 关键字反推，归一化成结构化码（`INPUT_UNREADABLE` / `UNKNOWN_EXPORT_TYPE` / `MULTIPAGE_FIRST_PAGE_ONLY` 等） |
| 2 | **`--help` 格式列表 ≠ 实际允许值** | help 写 8 项 `[svg,png,ps,eps,pdf,emf,wmf,xaml]`，报错信息里才是 23 项真实列表 | **能力探测禁止解析 `--help`**，只能靠真实转换实测 |

**能力探测双模式**（因单次转换冷启动约 2.1s，深探测 5 种格式约 10s，不能放启动路径）：
- **浅探测**（启动路径）：只查版本 + 可执行文件存在，<0.5s
- **深探测**（按需触发）：真实跑转换，产出完整能力表。提供 `scripts/probe_engine.py --deep` 供不启 UI 验证

**关键常量**：Inkscape 输出 SVG 使用 96dpi 用户单位。`PX96_PER_MM = 3.7795275591`（= 96/25.4）。实测 `from_ai.svg` 中 100mm → 377.95276 用户单位。

### 3.2 ★ 前端强制分层

| 文件 | 职责 | 禁止 |
|------|------|------|
| `state.js` | 单一数据源。框坐标、px_per_mm、方案数值只存此处 | 不得触碰 DOM 与 Canvas API |
| `canvas.js` | 唯一 Canvas 层，只绘制与交互，通过回调上报 | **不得出现 `state.xxx = ` 形式的业务状态赋值** |
| `api.js` | 后端通信，按错误级别渲染提示条或阻断弹窗 | — |
| `steps/*.js` | 各步骤事件编排，把用户操作翻译成 state 变更 | 不得绕过 state 直接改 canvas |

**动机**：界面主体是 Canvas 而非 DOM，React/Vue 的 diff 机制对画布内容无效。分层的真正目的是**可迁移性**——将来若要上框架，只需把 `state.js` 换成 `useReducer`，`canvas.js` 几乎不用改。

**预览必须走前端 Canvas**：实测 Pillow 叠加 15.7ms 但 PNG 编码 133ms，后端实时预览只有 7.5fps。Pillow **只在导出选款图时使用**。

**mm 值写入时机**：在 `place.js` 交互结束那一刻算完并存入 state。**导出阶段只读不算。**

### 3.3 存储：JSON + 原子写入 + 可迁移封装

**决策：v1 用 JSON，不用 SQLite。**

理由（针对本项目实际）：
- 单机、单人、一个订单 3～5 个方案，数据量极小，SQLite 优势无从发挥
- JSON **人可读可编辑**：设计师能直接查看、手动修正、整个文件夹复制备份——对单机工具这是核心价值
- 架构师提出的"全量重写可能写坏"用**原子写入**解决：写临时文件 → `os.replace()` 原子重命名

**但架构师的顾虑必须兜住**：所有数据访问封装在 `routers/project.py`，对外只暴露：

```python
load(project_dir) -> Project
save(project) -> None                # 内部原子写入
get_scheme(id) / add_scheme() / update_scheme() / delete_scheme()
```

存储格式因此可迁移：将来需换 SQLite 时只改这一个文件，上层零改动。

### 3.4 数据模型（沿用设计文档 5.2）

```json
{
  "calibration": {
    "product_frame": {"x": 120, "y": 60, "w": 900, "h": 1200},
    "width_mm": 300.0,
    "height_mm": null,
    "px_per_mm": 3.0
  },
  "frames": [
    {"id": "f1", "name": "翻盖可印区", "x": 200, "y": 300, "w": 600, "h": 400}
  ],
  "schemes": [
    {
      "id": "A",
      "frame_id": "f1",
      "logo_px": {"x": 320, "y": 380, "w": 226, "h": 90},
      "size_mm": {"w": 75.3, "h": 30.0},
      "offset_mm": {"left": 40.0, "bottom": 20.0},
      "color": null
    }
  ]
}
```

**★ 像素与毫米双存** —— 三份交付物一律读已算好的 mm 值，导出阶段不得有任何二次计算。这是"三份同源"的机制保证，也是 T2 测试的核心断言。

**★ 同源性的三条机制保证（software-architect-2 提出，不是靠小心）**

1. `size_mm` / `offset_mm` 在步骤 3 落库时就 `round(x, 2)` 定型，之后全链路读同一个值
2. 毫米文字一律经 `services/dimension.py` 的 `fmt_mm()` 统一格式化，**禁止任何一处自行 format**
3. **`app/services/` 内所有导出相关文件（spec_svg / placement_svg / selection_png / dimension）与 `app/routers/export.py` 内，禁止出现 `px_per_mm` 标识符、禁止做任何 px↔mm 换算** —— 由 `test_no_recompute.py` 用源码 grep 强制断言

第 3 条能成立是因为已验证过：定位图用图片像素作 SVG 内部坐标（像素值直接写，物理尺寸只通过根节点 width/height 声明一次），工艺尺寸图直接用 mm 作用户单位，选款图用 `logo_px` 贴图 + `fmt_mm(size_mm)` 写小字。**导出阶段确实一次换算都不需要。**

**几何权威性（与 B5～B7 已落地实现对齐）**：
- 前端 `place.js` 在交互结束（mouseup）那一刻算 `size_mm` / `offset_mm`（round2）存入 scheme —— 这就是权威值
- 后端导出（B8～B10）**只读** scheme 里的 mm 值，尺寸链几何计算放 `services/dimension.py`，一律不重算 px→mm
- 注：架构 v0.2 曾设想「前端手感层 + 后端 geometry 权威层纠正」的双层结构，B5～B7 实际实现简化为「前端一次算定、后端只读」，本 v0.3 以此为准

**T2 测试的强化断言**：只比字符串不够，加一层几何自洽——用 `offset_mm` 反推 logo 像素位置，与 `logo_px` 比对误差 < 0.5px，验证"定位图上的位置"和"尺寸链上的数字"自洽。

### 3.5 SVG 模板单位策略（实测验证，必须沿用）

```
viewBox 数值 = mm 数值，即 1 user unit = 1 mm
width / height 属性写 "115.30mm"
```

实测：页面 115.30 × 95.00 mm → PDF MediaBox 326.83 × 269.29 pt → **偏差 0.000003 mm**。
换算关系：**1 mm = 2.8346 pt**。
`--export-dpi` 对 mm 单位 SVG **无影响**（default/96/300 尺寸均正确），无需设置。

---

## 4. 任务列表

| 批次 | 内容 | 涉及文件 | 依赖 | 验收标准 |
|------|------|---------|------|---------|
| **B0** | 骨架与启动 | `run.bat`、`app/main.py`、`app/config.py`、`web/index.html`、`css/layout.css`、`js/main.js` | — | 双击 run.bat 打开三栏空壳，步骤条 4 步可点击（内容为空不报错） |
| **B1** | 数据模型与持久化 | `app/models.py`、`app/routers/project.py` | B0 | 新建项目生成 `projects/<名>/project.json`；存取往返字段完全一致；**保存为原子写入** |
| **B2** | 引擎适配层 | `engine/base.py`、`engine/inkscape.py`、`engine/registry.py`、`routers/health.py` | B0 | Inkscape 不在 PATH 时仍能经注册表定位；`/api/health` 返回版本号；路径填错时返回可读错误（错误条 #8） |
| **B3** | 上传与 logo 转换 | `routers/upload.py`、`routers/convert.py`、`js/api.js`、`js/steps/upload.js` | B1、B2 | **`.ai` / `.pdf` / `.svg` 三种源能转成 logo.svg**（注意：EPS 不支持）；浏览器显示包图；转换失败显示 stderr 原文并保留中间 SVG（错误条 #9） |
| **B4** | 前端分层骨架 | `js/state.js`、`js/canvas.js`、`js/sidebar.js`、`js/schemes.js`、`css/widgets.css` | B3 | 包图渲染到 Canvas；state 变更 → Canvas 与侧边栏同步刷新；**人工审查 canvas.js 全文无业务状态赋值** |
| **B5** | 步骤 2A 产品框定标 | `js/steps/calib_product.js`、`js/canvas.js` 矩形拖拽工具 | B4 | 拖框 → 填宽度 → px_per_mm 写入 state；宽度为空或零面积**阻断**无法进 2B（#1、#2）；高度偏差 >2% 黄色提示不阻断（#3）；px_per_mm 超区间提示单位填错（#4） |
| **B6** | 步骤 2B logo 框定基准 | `js/steps/calib_logo.js` | B5 | 可建多个命名框；框超出产品框时黄色提示、允许继续（#5）；数据写入 frames |
| **B7** | 步骤 3 摆放 | `js/steps/place.js`、`js/canvas.js` 拖动与四角控制点 | B6 | logo **物理夹在框内**越界不动（#6）；四角缩放锁长宽比、有最小尺寸、不会为 0 或负（#7）；交互结束把 `size_mm` 与 `offset_mm{left,bottom}` 存进 scheme；色号留空不阻断；方案切换后数值各自独立 |
| **B8** | 尺寸图与定位图 SVG | `services/dimension.py`、`services/spec_svg.py`、`services/placement_svg.py` | B1 | 产出 spec.svg / placement.svg；viewBox 数值 == mm 数值、width/height 带 mm 单位；转 PDF 后 1:1 偏差 < 0.001mm；**源码中所有 mm 数字直接取自 scheme，无乘除换算** |
| **B9** | 选款图 PNG | `services/selection_png.py` | B1 | 3～5 方案拼一张，每格标注方案号与 mm 尺寸；**纯程序化 alpha 平铺叠加**，无变形、无叠底、无光影，未调用任何生成式 AI |
| **B10** | 导出编排与错误收口 | `routers/export.py`、`services/errors.py`、`js/steps/export.js` | B2、B8、B9 | 一次产出 5 个文件；三类阻断错误文案正确（#8、#9、#10）；转曲失败出**警告**非阻断（#11）；已用 `--export-text-to-path`，未出现两个已知无效参数 |
| **B11** | 联调验收 | 仅调参与修 bug | B10 | **T1a 毫米文本串一致（必过）+ T1b 字节差异仅时间戳**；**T2 选款图 mm == 工艺图 mm == 定位图 mm（核心）**；T3 px_per_mm 误差 <1%；T6 俯拍图能触发黄色提示 |

**实现节奏（Joe + 主理人共同决定）**

第一批先做 **B0～B4**，人工验收后再做 B5～B11。

理由：B0～B4 覆盖全部高风险部分（引擎适配、格式转换、坐标换算、分层骨架），且能让 Joe 最快摸到真实界面。

**并行机会**：B1 与 B2 可并行；B5/B6/B7（前端）与 B8/B9（后端）可并行——B8/B9 只依赖 B1 的数据模型，按 schema 写即可，无需等界面。

---

## 5. 关键技术参数（实测，实现直接引用）

| 项 | 值 |
|----|-----|
| Inkscape 路径 | `D:\Program Files\Inkscape\bin\inkscape.exe`（**不在 PATH**） |
| 转曲参数 | `--export-text-to-path` |
| 单位换算 | 1 mm = 2.8346 pt |
| **PX96_PER_MM** | **3.7795275591**（= 96/25.4，Inkscape SVG 用户单位） |
| Inkscape 单次转换冷启动 | 约 2.1s（深探测 5 格式约 10s） |
| Pillow 叠加耗时 | 15.7 ms（3000×4000 底图） |
| PNG 编码耗时 | 133 ms → **预览绝不可走后端** |
| 中文路径 | 已验证：读写、Inkscape 调用、中文文件名上传均正常 |
| venv | `C:\Users\ljhmo\.workbuddy\binaries\python\envs\logomock`（**位于同步盘之外**） |

**依赖包**（运行时仅 4 个，办公机依赖越少越好）：fastapi 0.115.6 / uvicorn 0.34.0 / python-multipart 0.0.20 / pillow 11.1.0
> 注：上表版本号为架构师建议值；当前 venv 实际已装 fastapi 0.141.1 / uvicorn 0.52.4 / pillow 12.3.0，均向后兼容，实现时以 `requirements.txt` 锁实际版本。
**明确拒绝的依赖**：`uvicorn[standard]`（拉 uvloop/httptools/watchfiles 编译依赖）、任何矢量库、numpy/opencv、Ghostscript。

---

## 6. 共享知识（跨文件约定）

1. **坐标单位**：前端 Canvas 一律用**图片原始像素坐标**（非显示缩放坐标）。显示缩放只在 `canvas.js` 绘制时应用，state 中存的永远是原始像素。
2. **错误响应格式**：后端统一 `{"ok": bool, "data": ..., "error": {"code", "message"}}`。阻断级前端弹窗，提示级前端黄色信息条。
3. **错误处理清单**：设计文档第 7 节 12 条**必须全部落地，不得遗漏**，编号与本文件任务表引用一致。
4. **SVG 模板占位符**：统一 `{{PLACEHOLDER}}` 双大括号。
5. **命名**：Python 模块与函数 snake_case；JS 变量 camelCase；DOM id 用 kebab-case。
6. **路径处理**：全程 `pathlib.Path`，禁止字符串拼接路径。
7. **禁止项**：`canvas.js` 中不得出现业务状态；导出阶段不得做任何毫米换算。
8. **★ `canvas.js` 拖拽瞬时变量例外**（不写清这条工程师会不敢动手）：拖拽过程中的临时变量（`dragStartX`、`currentScale` 等）**不算业务状态，允许存在**，但必须在 `mouseup` 时一次性通过 `state.update()` 提交，不得残留。判据：**只要不是"这个值要存下来跨步骤用"，就不算业务状态。**
9. **★ logo 上传一律先过一次 `to_svg()` 规范化**，哪怕源文件本来就是 SVG。这样下游永远拿到带 `width`/`height`/`viewBox` 的干净 SVG，规避用户 SVG 缺属性的坑。
10. **降级链核心**：SVG 是我们自己拼文本的，不依赖引擎。所以即使 Inkscape 完全挂掉，选款图（Pillow）+ 工艺尺寸图 SVG + 定位图 SVG 照出，只是 PDF 标记跳过；唯有"logo 源文件是 AI/PDF"会真阻断（无法转 SVG）。

### 6.1 错误处理补充（architect-2 在 12 条基础上补 4 条）

| # | 场景 | 级别 | 处理 |
|---|------|------|------|
| 13 | logo 源为 EPS | 阻断 | 三段引导：① 说明 EPS 不支持 ② 请客户改存 AI 或 PDF ③ 说明这是 Inkscape 引擎限制 |
| 14 | 多页 PDF / AI | 提示 | 取第一页，标注「已取第 1 页，共 N 页」 |
| 15 | logo SVG 缺 viewBox | 提示 | 规范化阶段自动补，提示已修复 |
| 16 | 包图含 EXIF 旋转 | 提示 | 按 EXIF Orientation 自动纠正，提示已纠正 |

---

## 7. 三条红线（违反即项目失败）

1. **S1 禁用生成式 AI** —— 效果图只能程序化 alpha 平铺叠加，不变形、不做正片叠底、不加光影。原因：生成式模型会微调 logo 比例/颜色/位置，导致无法反推毫米数，下游全断链。
2. **三份交付物同源** —— 一律读已算好的 mm 值，导出阶段零换算。
3. **项目隔离** —— 与"包装刀版引擎"（另一个项目）完全无关，禁止类比参考。两个项目文件名都含 mockup/packaging，勿误判为同一体系。

---

## 8. 待明确事项（动工前需 Joe 拍板）

### 8.1 需立即拍板（已全部拍板 ✅）

| # | 问题 | 结论 | 拍板依据 |
|---|------|------|---------|
| **Q1** | T1「字节级一致」 | **拆成 T1a + T1b** | Inkscape 写 `/CreationDate` 时间戳，硬比字节永远误报。T1a 自动断言毫米文本串一致（必过）；T1b 字节差异人工确认仅为时间戳 |
| **Q2** | 导出范围 | **默认只出选定方案 + `include_unselected` 开关（默认关）** | 客户未选定时给工厂全套无意义 |
| **Q3** | 项目路径 | **F 盘**（`F:\BaiduSyncdisk\joeai\logomock`） | 实测确认，设计文档 §11 的 `e:` 为历史笔误，已纠正 |
| **Q4** | 输出格式默认值 | **`["pdf","svg"]`**（选款图固定 PNG） | 与「PDF 主 + SVG 备选，砍 EPS」决策一致 |

### 8.2 可边做边定（架构师已给默认值）

| # | 问题 | 默认值 |
|---|------|--------|
| Q5 | 高度偏差分母定义 | 以宽度定标时，高度提示用「填写的 height_mm vs 由宽度×像素比推算的高度」 |
| Q6 | px_per_mm 经验区间取值 | 0.5～20（超出提示单位填错） |
| Q7 | 标注字体 | Arial，尺寸链文字 4mm |
| Q8 | 底图相对路径 vs base64 | 相对路径（project.json 存 input/bag.jpg） |
| Q9 | 选款图拼版列数 | `ceil(sqrt(n))` 网格 + **方案编号徽章**（客户靠它圈选回编号，必须有） |
| Q10 | 选款图整图宽度 | 2400px，每格底部 `B 75.3 × 30.0 mm` 小字 |
| Q11 | 步骤4界面 | 左栏三张交付物卡片 + 中栏三 Tab 预览 + 右栏设置（格式多选按能力表置灰并显示原因） |
| Q12 | 方案条选中态 | 蓝色 → 导出后绿色带对勾 |
| Q13 | 转曲失败自动化检测 | 转曲后解析产物统计 `<text>` 元素数，>0 才警告 |
| Q14 | 测试基线 | `_probe/` 11 个产物在 B1.6 用作固件：EPS 必失败报 INPUT_UNREADABLE、`--export-type=ai` 必失败、转曲后 `<text>`=0、from_ai.svg path=2/image=0 |

### 8.3 遗留待验证

| # | 事项 | 状态 |
|---|------|------|
| V1 | AI 打开 roundtrip.pdf 验证路径可编辑 | **独立批次，不阻塞开发**。不通过的唯一后果是"不能给工厂 .ai"，届时改 config.json 的 spec_formats 即可，架构零改动 |
| V2 | 客户 logo 为非 PDF 兼容的老版 `.ai` | 待真实文件验证 |
| V3 | 贴片厂是否接受 PDF | Joe 已用 AI 实机验证，待贴片厂最终确认 |
