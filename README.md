# LogoMock · 内部印标工作台 V1

本机使用的产品图 + Logo 排版工具。当前不部署网站，不开放客户账号。

## 打开应用

双击 `run.bat`。发布包的 `LogoMock.exe` 已包含 Python，不需要另装 Python。
应用启动后会打开浏览器中的本地工作台，另有一个小控制窗口；关闭控制窗口即退出服务。
服务只监听 `127.0.0.1`，素材不上传到云端。

项目放在数据目录的 `projects/`，配置在 `config.json`。直接运行 EXE 时，数据目录默认是 EXE 所在文件夹；本项目的 `run.bat` 使用本项目目录，所以能打开已有订单。请把应用放在自己有写入权限的文件夹，不要放进 Program Files。

SVG / PDF / AI 分析和 PDF 导出需要单独安装 **Inkscape**，在工作台“设置”中选择 `bin/inkscape.exe`。当前开发机使用项目 `tools/inkscape/inkscape/` 中的便携版本；发布 EXE 不包含 Inkscape。换电脑需重新设置路径。

## 分享给其他人

不要直接把整个源码目录或 `projects/` 发给别人。请从 GitHub Release 下载 Windows 发布包，解压到有写入权限的文件夹（不要放在 Program Files），然后双击 `run.bat`。发布包中应有同目录的 `LogoMock.exe`、`run.bat` 和本说明；使用者不需要安装 Python。

首次使用 AI / SVG / PDF 素材或需要导出 PDF 时，使用者需安装 Inkscape，并在应用“设置”里选择它的 `bin/inkscape.exe`。如需预先配置，也可复制 `config.example.json` 为本机 `config.json`，再修改路径；`config.json` 不应提交到 GitHub。

产品图、Logo、项目数据和导出文件仅保存在使用者自己的 `projects/` 目录。不要把该目录上传到仓库或作为公开发布包的一部分。

## GitHub 维护与发布

仓库保存源码、测试、构建脚本和文档；`.gitignore` 会排除项目素材、本机配置、Inkscape、构建缓存和 EXE。每次可交付版本按 `v1.0.0` 这类标签创建 GitHub Release，并把 Windows 发布压缩包作为 Release 附件上传，而不是提交 `LogoMock.exe` 到 Git 历史。

## 制作流程

1. 新建项目，或从左侧打开/复制已有项目。
2. 导入产品 PNG/JPG/WebP、Logo SVG/PDF/AI/PNG/JPG/WebP。AI 必须以 PDF 兼容方式保存；PDF/AI 默认第一页。
3. 点击“分析与清理”，检查原图与透明 Logo。可恢复被排除对象、多选候选、框选对象或取消个别图形。
4. 画产品尺寸框，输入真实宽度，**单位为毫米**。画印标参照框。
5. 建立方案，拖动 Logo 或手柄；右侧可输入宽高、距左/距底，尺寸锁定原比例。滚轮缩放、空格/中键平移、撤销/重做。
6. 保存状态稳定后导出。导出也会主动等待保存完成。

产品框、参照框和裁剪框都可重新选中、移动和拉动角点。改产品比例尺时保持 Logo 毫米尺寸不变，重新计算显示像素。

## 导出内容

- `mockup-*.png`：只有产品图和 Logo；不带编辑框、方案编号、尺寸条。裁剪框只影响此图及可选对比图。
- `artwork-*.svg/pdf`：无标注的 1:1 Logo 稿，打印请选 100% / 实际大小。
- `spec-*.svg/pdf`：1:1 Logo 加宽高标注。
- `placement-*.svg/pdf`：完整照片上的定位参考，带参照框和毫米偏移，页面是缩放参考，不是整张实物 1:1。
- `snapshot.json`：本次导出所用的项目修订。

每次导出独立目录，旧交付不会被新一次导出覆盖。SVG 自带图像资源，不依赖旁边的 input 文件。

## 自动处理的边界

自动清理是**可恢复的建议，不是语义识别保证**。标注与 Logo 相连、复杂照片背景、嵌套蒙版或特殊矢量结构，需要查看结果后确认。多个分離图形暂选最大候选，可手动合并。位图仅清理边缘连通的近似纯色背景，并保留图形内部白色；位图输出到 SVG/PDF 仍然是位图。

产品照片本身已经印上的文字/尺寸不会因隐藏编辑框而消失：可使用裁剪，或上传无标注产品原图。Logo 的原图不会被 AI 重画。

旧项目打开不会自动改写；重新分析或编辑后才保存 V1 数据。原始输入始终保留，新素材另存版本。更换产品图会清空旧标定、参照框和方案，请先复制项目再试不同产品。

## 开发 / 构建

Windows Python 3.13（当前验证版本），在本目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe launcher.py
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/editor.test.mjs
.\build.bat
```

构建结果 `dist/LogoMock.exe`。开发可用 `launcher.py --headless --port 8018 --data-dir <独立目录>`；也支持 `LOGOMOCK_DATA_DIR`、`LOGOMOCK_INKSCAPE` 环境变量。

`backups/source-before-internal-v1.zip` 保存改造前源码。`_qa/` 是独立验收数据，原来的 `projects/01`、`02`、`demo_sample` 不作为修改测试目标。
