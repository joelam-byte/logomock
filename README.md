# LogoMock · 内部印标工作台 V1

给业务员日常制作产品印标效果图的本地工具。它不会上传客户素材；产品图、Logo、任务草稿和版本都保存在使用者电脑上。

## 打开应用

发布包中双击 `run.bat`。`LogoMock.exe` 已包含 Python，使用者不需要另装 Python。应用会启动浏览器中的本地工作台；服务只监听 `127.0.0.1`。

请把整个发布包解压到有写入权限的文件夹，例如 `D:\LogoMock`，不要放在 `Program Files`，也不要在压缩包预览中直接运行。项目数据默认保存于同目录的 `projects/`，请定期备份。

## 日常制作流程

1. 新建任务，或从左侧打开一条已有任务。
2. 导入产品图，再导入客户 Logo。
3. 点击“分析 Logo”，在页面卡片中勾选需要使用的内容，右侧预览确认后使用。无需认识文件内部的图层或对象名称。
4. 按原有方式在产品图上画产品尺寸框，输入产品实际宽度（mm），再画印标区域。
5. 拖动 Logo 或八个控制点调整位置和大小；右侧可直接输入宽高（mm）、切换比例锁定、选原色/黑色/白色/深灰。
6. 点击“生成客户确认图”，选择保存位置。每次只生成一张 PNG：产品图、Logo 和数值 `宽 × 高 mm`；不会带编辑框、参考线、版本号或颜色说明。
7. 客户稍后反馈时，打开任务的“版本记录”，选中此前版本并点击“从此版本继续编辑”；调整后再次生成确认图，即形成下一版。

当前 V1 始终只保留一个正在编辑的 Logo 放置，不会在界面里出现多套方案或多份重复导出文件。

## Logo 文件兼容性与清理

- 产品图：PNG、JPG、JPEG、WebP。
- Logo：SVG、PDF、PDF 兼容的 AI，以及 PNG、JPG、JPEG、WebP。
- SVG / PDF / AI 的分析需要另装 Inkscape。AI 必须由 Illustrator 以“创建 PDF 兼容文件”方式保存；原生、非 PDF 兼容的 AI 无法可靠读取。
- PDF 或 PDF 兼容 AI 中能读取到的页面都会呈现为页面卡片，不只读取第一页。Logo 内已组合的字标会尽量作为一个候选整体；背景、尺寸标注和其他独立内容可不勾选。

自动清理是可撤销的初步分析，不是对 Logo 语义的保证。业务员应在右侧预览中确认：只勾选需要的 Logo，排除背景、尺寸标注和无关图形。复杂蒙版、标注与 Logo 连在一起、或照片式背景仍可能需要客户提供更干净的源文件。

## 客户确认图与版本

生成客户确认图会先保存当前草稿，再让你选择 PNG 保存位置。成功保存后，软件会自动建立一个内部版本；版本记录用于查看、恢复和管理历史。

- 删除版本只删除软件内部存档，不会删除已经发给客户的 PNG。
- 恢复版本会替换当前草稿，恢复后的内容仍可继续编辑。
- 日常编辑会自动保存；即使退出应用，未导出的任务也会保留在本机。

## Inkscape：推荐安装版

发布包不包含 Inkscape。对外分享时，推荐“LogoMock 绿色版 + 官方稳定版 Inkscape 64 位 MSI 安装版”，而不是把体积很大的便携 Inkscape 一并塞进发布包。

从 [Inkscape 官方下载页](https://inkscape.org/release/) 安装 Windows 64 位 **Windows Installer Package (MSI)**。首次使用后，在工作台“设置”中确认 Inkscape 已就绪；若未自动识别，选择 `C:\Program Files\Inkscape\bin\inkscape.exe`。便携版仅适用于无法安装软件、离线/U 盘使用或需并存多个版本的情形。

完整的分享、首次配置和故障排查见[绿色版使用说明](./docs/绿色版使用说明.md)。

## 分享给同事

从 GitHub Release 下载 Windows 发布压缩包，解压后把 `LogoMock.exe`、`run.bat` 和本说明放在同一文件夹。使用者不需要安装 Python，但要自行安装并配置 Inkscape，才能分析 SVG/PDF/AI Logo。

不要把客户项目目录、`config.json` 或客户素材提交到 GitHub。要交接某个任务时，单独复制相应的 `projects/<任务名称>/` 目录即可。

## 开发 / 构建

Windows Python 3.13（当前验证版本）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/editor.test.mjs tests/ui-state.test.mjs
.\build.bat
```

构建结果为 `dist/LogoMock.exe`。开发时可用 `launcher.py --headless --port 8018 --data-dir <独立目录>` 启动；也支持 `LOGOMOCK_DATA_DIR`、`LOGOMOCK_INKSCAPE` 环境变量。
