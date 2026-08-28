#!/usr/bin/env sh
# SubForge Linux & macOS One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/install.sh | sh

set -e

APP_NAME="subforge"
REPO="yudopr11/subforge"
INSTALL_DIR="${HOME}/.local/bin"
TARGET_BIN="${INSTALL_DIR}/${APP_NAME}"

printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
printf "\033[1;37m  SubForge — Local-First Subtitle Generator\033[0m\n"
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"

# 1. Ensure install directory exists
mkdir -p "${INSTALL_DIR}"

# 2. Detect OS & Architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "${ARCH}" in
  x86_64|amd64)
    ARCH="x64"
    ;;
  arm64|aarch64)
    ARCH="arm64"
    ;;
  *)
    ARCH="x64"
    ;;
esac

ASSET_NAME="subforge-${OS}-${ARCH}"

printf "\033[33m▸ Fetching latest release for %s (%s)...\033[0m\n" "${OS}" "${ARCH}"

DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}"

TEMP_FILE="$(mktemp)"

if curl -fsSL "${DOWNLOAD_URL}" -o "${TEMP_FILE}" 2>/dev/null; then
  mv "${TEMP_FILE}" "${TARGET_BIN}"
  chmod +x "${TARGET_BIN}"
else
  # Fallback to uv tool or pipx if binary release is not available
  printf "\033[90mℹ Standalone binary not found. Bootstrapping via uv tool/pipx...\033[0m\n"
  if command -v uv >/dev/null 2>&1; then
    uv tool install "git+https://github.com/${REPO}.git" --force
    printf "\033[32m✓ SubForge installed via uv tool.\033[0m\n"
    exit 0
  elif command -v pipx >/dev/null 2>&1; then
    pipx install "git+https://github.com/${REPO}.git" --force
    printf "\033[32m✓ SubForge installed via pipx.\033[0m\n"
    exit 0
  else
    printf "\033[31m[ERROR] Failed to download binary from %s\033[0m\n" "${DOWNLOAD_URL}"
    rm -f "${TEMP_FILE}"
    exit 1
  fi
fi

rm -f "${TEMP_FILE}"

# 3. Check if ~/.local/bin is in PATH
case ":${PATH}:" in
  *":${INSTALL_DIR}:"*)
    ;;
  *)
    printf "\033[33m▸ Adding %s to PATH in shell profile...\033[0m\n" "${INSTALL_DIR}"
    SHELL_NAME="$(basename "${SHELL:-sh}")"
    if [ "${SHELL_NAME}" = "zsh" ]; then
      PROFILE="${HOME}/.zshrc"
    elif [ "${SHELL_NAME}" = "bash" ]; then
      PROFILE="${HOME}/.bashrc"
    else
      PROFILE="${HOME}/.profile"
    fi
    printf '\nexport PATH="%s:$PATH"\n' "${INSTALL_DIR}" >> "${PROFILE}"
    printf "\033[90m  Added to %s\033[0m\n" "${PROFILE}"
    ;;
esac

printf "\n\033[32m✓ SubForge installed successfully!\033[0m\n\n"
printf "  To get started, open a new terminal and type:\n"
printf "    \033[1;36msubforge\033[0m\n\n"
