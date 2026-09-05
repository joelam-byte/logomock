@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先按 README 创建开发环境。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" tools\prepare_tk_runtime.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm LogoMock.spec
if errorlevel 1 exit /b 1
echo 已生成 dist\LogoMock.exe。Inkscape 需单独安装或配置。
