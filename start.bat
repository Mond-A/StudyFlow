@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   StudyFlow - AI 学习管理平台
echo   -----------------------------------------
echo.

set "PYTHON_CMD="

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import flask" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=.venv\Scripts\python.exe"
)

if not defined PYTHON_CMD (
  py -3 -c "import flask" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  python -c "import flask" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [错误] 没有找到已安装 Flask 的 Python 环境。
  echo.
  echo 请先执行：
  echo    python -m venv .venv
  echo    .venv\Scripts\activate
  echo    pip install -r requirements.txt
  echo.
  echo 详细步骤见 README.md 的“快速开始”章节。
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [StudyFlow] 已根据 .env.example 创建 .env。
    echo [StudyFlow] 如需真实 AI，请在 .env 中填写 API Key 后重启。
    echo.
  )
)

echo [StudyFlow] 使用：%PYTHON_CMD%
echo [StudyFlow] 正在启动 http://127.0.0.1:5000 ...
echo [StudyFlow] 按 Ctrl+C 停止服务。
echo.
%PYTHON_CMD% run.py
if errorlevel 1 pause
endlocal
