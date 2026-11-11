#!/usr/bin/env bash
# StudyFlow quick launcher for macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "  StudyFlow - AI 学习管理平台"
echo "  -----------------------------------------"
echo ""

PYTHON=""
for candidate in ".venv/bin/python" "python3" "python"; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c "import flask" >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "[错误] 没有找到已安装 Flask 的 Python 环境。"
  echo "请先执行："
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp ".env.example" ".env"
  echo "[StudyFlow] 已根据 .env.example 创建 .env。"
fi

echo "[StudyFlow] 使用：$PYTHON"
echo "[StudyFlow] 正在启动 http://127.0.0.1:5000 ..."
echo "[StudyFlow] 按 Ctrl+C 停止服务。"
echo ""
exec "$PYTHON" run.py
