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
INCLUDE="$("${PYTHON}" -c 'import sysconfig; print(sysconfig.get_path("include"))')"
SITE="$("${PYTHON}" -c 'import sysconfig; print(sysconfig.get_path("platlib"))')"
FRAMEWORK_PREFIX="$("${PYTHON}" -c 'import sysconfig; print(sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX") or "")')"
if [[ -z "${FRAMEWORK_PREFIX}" ]]; then
  FRAMEWORK_PREFIX="/opt/homebrew/opt/python@3.14/Frameworks"
fi
PYTHON_CONFIG="${ROOT}/.venv/bin/python-config"
if [[ ! -x "${PYTHON_CONFIG}" ]]; then
  PYTHON_CONFIG="$(command -v python3-config)"
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

if [[ -d "${ROOT}/macos/AppIcon.iconset" ]]; then
  iconutil -c icns "${ROOT}/macos/AppIcon.iconset" -o "${RESOURCES}/AppIcon.icns"
fi

codesign --force --deep --sign - "${APP_DIR}" >/dev/null
xattr -cr "${APP_DIR}" 2>/dev/null || true

printf '%s\n' "installed ${APP_DIR}"
printf '%s\n' "Grant Accessibility and Screen Recording to AI Translate, then open that one app."
