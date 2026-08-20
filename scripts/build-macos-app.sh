#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="AI Translate"
INSTALL_DIR="${HOME}/Applications"
APP_DIR="${INSTALL_DIR}/${APP_NAME}.app"
CONTENTS="${APP_DIR}/Contents"
MACOS="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  echo "missing ${PYTHON}; run scripts/install.sh first" >&2
  exit 1
fi
INCLUDE="$("${PYTHON}" -c 'import sysconfig; print(sysconfig.get_path("include"))')"
SITE="$("${PYTHON}" -c 'import sysconfig; print(sysconfig.get_path("platlib"))')"
FRAMEWORK_PREFIX="$("${PYTHON}" -c '
import sys
import sysconfig
from pathlib import Path

prefix = sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX") or ""
if prefix:
    print(prefix)
    raise SystemExit(0)
path = Path(sys.base_prefix).resolve()
for candidate in [path, *path.parents]:
    if candidate.name == "Python.framework":
        print(candidate.parent)
        raise SystemExit(0)
    nested = candidate / "Python.framework"
    if nested.is_dir():
        print(candidate)
        raise SystemExit(0)
raise SystemExit(1)
')" || {
  echo "cannot find Python.framework for ${PYTHON}" >&2
  echo "Use a python.org or Homebrew framework build of Python 3.12+." >&2
  exit 1
}
PYTHON_CONFIG="${ROOT}/.venv/bin/python-config"
if [[ ! -x "${PYTHON_CONFIG}" ]]; then
  PYTHON_CONFIG="$("${PYTHON}" -c '
import shutil
import sys
print(shutil.which(f"python{sys.version_info.major}.{sys.version_info.minor}-config") or shutil.which("python3-config") or "")
')"
fi
if [[ -z "${PYTHON_CONFIG}" || ! -x "${PYTHON_CONFIG}" ]]; then
  echo "need python3-config to link the app launcher" >&2
  exit 1
fi
rm -rf "${APP_DIR}" "${ROOT}/dist/${APP_NAME}.app"
mkdir -p "${INSTALL_DIR}" "${MACOS}" "${RESOURCES}"

clang \
  -o "${MACOS}/AITranslate" \
  "${ROOT}/macos/launcher.c" \
  -I"${INCLUDE}" \
  $("${PYTHON_CONFIG}" --ldflags --embed) \
  -Wl,-rpath,"${FRAMEWORK_PREFIX}"

cp "${ROOT}/macos/Info.plist" "${CONTENTS}/Info.plist"
printf '%s\n' "${ROOT}" > "${RESOURCES}/project_root"
printf '%s\n' "${SITE}" > "${RESOURCES}/site_packages"

if [[ -f "${ROOT}/macos/AppIcon.icns" ]]; then
  cp "${ROOT}/macos/AppIcon.icns" "${RESOURCES}/AppIcon.icns"
elif [[ -d "${ROOT}/macos/AppIcon.iconset" ]]; then
  iconutil -c icns "${ROOT}/macos/AppIcon.iconset" -o "${RESOURCES}/AppIcon.icns"
fi

codesign --force --deep --sign - "${APP_DIR}" >/dev/null
xattr -cr "${APP_DIR}" 2>/dev/null || true

printf '%s\n' "installed ${APP_DIR}"
