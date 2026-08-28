#!/usr/bin/env sh
# SubForge Linux & macOS Uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.sh | sh
# Or with purge: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.sh | sh -s -- --purge

set -e

APP_NAME="subforge"
INSTALL_DIR="${HOME}/.local/bin"
TARGET_BIN="${INSTALL_DIR}/${APP_NAME}"
DATA_DIR="${HOME}/.local/share/subforge"
CONFIG_DIR="${HOME}/.config/subforge"

PURGE=false
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --purge|-p)
      PURGE=true
      ;;
    --force|-y|-f)
      FORCE=true
      ;;
  esac
done

printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
printf "\033[1;37m  SubForge — Uninstaller\033[0m\n"
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"

# 1. Remove binary
if [ -f "${TARGET_BIN}" ]; then
  printf "\033[33m▸ Removing binary %s...\033[0m\n" "${TARGET_BIN}"
  rm -f "${TARGET_BIN}"
  printf "\033[32m✓ Removed binary.\033[0m\n"
fi

# 2. Check uv tool / pipx
if command -v uv >/dev/null 2>&1; then
  if uv tool list 2>/dev/null | grep -q "${APP_NAME}"; then
    printf "\033[33m▸ Uninstalling SubForge from uv tools...\033[0m\n"
    uv tool uninstall "${APP_NAME}" >/dev/null 2>&1 || true
    printf "\033[32m✓ Removed uv tool.\033[0m\n"
  fi
fi

if command -v pipx >/dev/null 2>&1; then
  if pipx list 2>/dev/null | grep -q "package ${APP_NAME}"; then
    printf "\033[33m▸ Uninstalling SubForge from pipx...\033[0m\n"
    pipx uninstall "${APP_NAME}" >/dev/null 2>&1 || true
    printf "\033[32m✓ Removed pipx package.\033[0m\n"
  fi
fi

# 3. Clean shell profile PATH hint
for PROFILE in "${HOME}/.zshrc" "${HOME}/.bashrc" "${HOME}/.profile"; do
  if [ -f "${PROFILE}" ]; then
    if grep -q "export PATH=\"${INSTALL_DIR}:\$PATH\"" "${PROFILE}" 2>/dev/null; then
      printf "\033[33m▸ Note: '%s' is present in %s (you can remove it manually if no longer needed).\033[0m\n" "${INSTALL_DIR}" "${PROFILE}"
    fi
  fi
done

# 4. Optional purge of data & configuration
REMOVE_DATA=false
if [ "${PURGE}" = true ]; then
  REMOVE_DATA=true
elif [ "${FORCE}" = true ]; then
  REMOVE_DATA=false
else
  if [ -d "${DATA_DIR}" ] || [ -d "${CONFIG_DIR}" ]; then
    if [ -t 0 ]; then
      printf "Do you want to delete models, cache, and configuration in ~/.local/share/subforge and ~/.config/subforge? [y/N]: "
      read -r answer
      case "$answer" in
        [yY]|[yY][eE][sS])
          REMOVE_DATA=true
          ;;
        *)
          REMOVE_DATA=false
          ;;
      esac
    fi
  fi
fi

if [ "${REMOVE_DATA}" = true ]; then
  if [ -d "${DATA_DIR}" ]; then
    printf "\033[33m▸ Removing data directory %s...\033[0m\n" "${DATA_DIR}"
    rm -rf "${DATA_DIR}"
    printf "\033[32m✓ Removed data directory.\033[0m\n"
  fi
  if [ -d "${CONFIG_DIR}" ]; then
    printf "\033[33m▸ Removing config directory %s...\033[0m\n" "${CONFIG_DIR}"
    rm -rf "${CONFIG_DIR}"
    printf "\033[32m✓ Removed config directory.\033[0m\n"
  fi
fi

printf "\n\033[32m✓ SubForge has been successfully uninstalled.\033[0m\n\n"
