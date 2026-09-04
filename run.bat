@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "LogoMock.exe" (
  start "" "LogoMock.exe" --data-dir "%~dp0."
  exit /b
)
if exist "dist\LogoMock.exe" (
  start "" "dist\LogoMock.exe" --data-dir "%~dp0."
  exit /b
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo 未找到应用或开发环境，请查看 README。
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "launcher.py" --data-dir "%~dp0."
