#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "当前只支持 macOS 13+。" >&2
  exit 1
fi

python_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null
}

find_python() {
  local cmd path
  for cmd in python3 python3.12 python3.13 python3.14 python3.15; do
    path="$(command -v "${cmd}" || true)"
    if [[ -n "${path}" ]] && python_ok "${path}"; then
      printf '%s\n' "${path}"
      return 0
    fi
  done
  return 1
}

if pgrep -x AITranslate >/dev/null 2>&1; then
  echo "请先点菜单栏「译 → 退出」，再重新安装。" >&2
  exit 1
fi

VENV_PYTHON="${ROOT}/.venv/bin/python"
if [[ -x "${VENV_PYTHON}" ]] && python_ok "${VENV_PYTHON}"; then
  PYTHON="${VENV_PYTHON}"
else
  BASE="$(find_python)" || {
    echo "需要 Python 3.12 或更新版本。可用 python.org 或 Homebrew 安装后再执行本脚本。" >&2
    exit 1
  }
  echo "正在用 ${BASE} 创建 .venv …"
  "${BASE}" -m venv "${ROOT}/.venv"
  PYTHON="${VENV_PYTHON}"
fi

echo "正在安装依赖…"
"${PYTHON}" -m pip install -e "${ROOT}"

"${ROOT}/scripts/build-macos-app.sh"

APP="${HOME}/Applications/AI Translate.app"
echo "下一步：给 AI Translate 打开辅助功能和屏幕录制。翻译默认使用 Google（内置），可在「设置…」更换。"
open "${APP}"
