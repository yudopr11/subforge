#!/usr/bin/env sh
# SubForge Linux & macOS Complete Uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.sh | sh

set -e

APP_NAME="subforge"
INSTALL_DIR="${HOME}/.local/bin"
TARGET_BIN="${INSTALL_DIR}/${APP_NAME}"
DATA_DIR="${HOME}/.local/share/subforge"
PROJECTS_DIR="${DATA_DIR}/projects"
CONFIG_DIR="${HOME}/.config/subforge"
DOT_SUBFORGE_DIR="${HOME}/.subforge"
CUSTOM_SUBFORGE_DIR="${SUBFORGE_HOME}"

KEEP_PROJECTS=false

for arg in "$@"; do
  case "$arg" in
    --keep-projects)
      KEEP_PROJECTS=true
      ;;
  esac
done

printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
printf "\033[1;37m  SubForge — Complete Uninstaller\033[0m\n"
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"

# 1. Remove binary
if [ -f "${TARGET_BIN}" ]; then
  printf "\033[33m▸ Removing binary %s...\033[0m\n" "${TARGET_BIN}"
  rm -f "${TARGET_BIN}"
  printf "\033[32m✓ Removed executable.\033[0m\n"
fi

# 2. Check uv tool / pipx
if command -v uv >/dev/null 2>&1; then
  if uv tool list 2>/dev/null | grep -q "${APP_NAME}"; then
    printf "\033[33m▸ Uninstalling SubForge from uv tools...\033[0m\n"
    uv tool uninstall "${APP_NAME}" >/dev/null 2>&1 || true
    printf "\033[32m✓ Uninstalled from uv.\033[0m\n"
  fi
fi

if command -v pipx >/dev/null 2>&1; then
  if pipx list 2>/dev/null | grep -q "package ${APP_NAME}"; then
    printf "\033[33m▸ Uninstalling SubForge from pipx...\033[0m\n"
    pipx uninstall "${APP_NAME}" >/dev/null 2>&1 || true
    printf "\033[32m✓ Uninstalled from pipx.\033[0m\n"
  fi
fi

# 3. Clean temporary files & audio previews
printf "\033[33m▸ Cleaning temporary preview files...\033[0m\n"
rm -f /tmp/subforge* /tmp/subforge_preview_*.wav 2>/dev/null || true
printf "\033[32m✓ Cleaned temporary files.\033[0m\n"

# 4. Clean application data, models, binaries, configuration
if [ -d "${DATA_DIR}" ]; then
  if [ "${KEEP_PROJECTS}" = true ] && [ -d "${PROJECTS_DIR}" ]; then
    printf "\033[33m▸ Cleaning models and managed binaries (keeping projects)...\033[0m\n"
    find "${DATA_DIR}" -mindepth 1 -maxdepth 1 ! -name "projects" -exec rm -rf {} +
    printf "\033[32m✓ Cleaned models and binaries (projects preserved).\033[0m\n"
  else
    printf "\033[33m▸ Removing application data and models (%s)...\033[0m\n" "${DATA_DIR}"
    rm -rf "${DATA_DIR}"
    printf "\033[32m✓ Removed %s.\033[0m\n" "${DATA_DIR}"
  fi
fi

if [ -d "${CONFIG_DIR}" ]; then
  printf "\033[33m▸ Removing configuration directory (%s)...\033[0m\n" "${CONFIG_DIR}"
  rm -rf "${CONFIG_DIR}"
  printf "\033[32m✓ Removed %s.\033[0m\n" "${CONFIG_DIR}"
fi

# Clean ~/.subforge or $SUBFORGE_HOME if used
for EXTRA_DIR in "${DOT_SUBFORGE_DIR}" "${CUSTOM_SUBFORGE_DIR}"; do
  if [ -n "${EXTRA_DIR}" ] && [ -d "${EXTRA_DIR}" ]; then
    if [ "${KEEP_PROJECTS}" = true ] && [ -d "${EXTRA_DIR}/projects" ]; then
      printf "\033[33m▸ Cleaning models and managed binaries in %s (keeping projects)...\033[0m\n" "${EXTRA_DIR}"
      find "${EXTRA_DIR}" -mindepth 1 -maxdepth 1 ! -name "projects" -exec rm -rf {} +
      printf "\033[32m✓ Cleaned %s (projects preserved).\033[0m\n" "${EXTRA_DIR}"
    else
      printf "\033[33m▸ Removing %s...\033[0m\n" "${EXTRA_DIR}"
      rm -rf "${EXTRA_DIR}"
      printf "\033[32m✓ Removed %s.\033[0m\n" "${EXTRA_DIR}"
    fi
  fi
done

# 5. Shell profile PATH note/cleanup
for PROFILE in "${HOME}/.zshrc" "${HOME}/.bashrc" "${HOME}/.profile"; do
  if [ -f "${PROFILE}" ]; then
    if grep -q "export PATH=\"${INSTALL_DIR}:\$PATH\"" "${PROFILE}" 2>/dev/null; then
      printf "\033[33m▸ Note: '%s' in %s can be removed if no longer used by other tools.\033[0m\n" "${INSTALL_DIR}" "${PROFILE}"
    fi
  fi
done

printf "\n\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
printf "\033[32m✓ SubForge, its dependencies, models, and paths are fully uninstalled!\033[0m\n"
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"
