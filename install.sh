#!/usr/bin/env sh
# SubForge Linux & macOS Installer / Uninstaller
# Usage:
#   Install:   curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/install.sh | sh
#   Uninstall: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/install.sh | sh -s -- --uninstall
#   Uninstall (keep data): ... | sh -s -- --uninstall --keep-data

set -e

APP_NAME="subforge"
REPO="yudopr11/subforge"
INSTALL_DIR="${HOME}/.local/bin"
TARGET_BIN="${INSTALL_DIR}/${APP_NAME}"
DATA_DIR="${HOME}/.local/share/subforge"
CONFIG_DIR="${HOME}/.config/subforge"

# ── Parse flags ───────────────────────────────────────────────────────────────
MODE="install"
KEEP_DATA=false

for arg in "$@"; do
  case "$arg" in
    --uninstall) MODE="uninstall" ;;
    --keep-data) KEEP_DATA=true ;;
  esac
done

# ── Banner ─────────────────────────────────────────────────────────────────────
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
if [ "$MODE" = "uninstall" ]; then
  printf "\033[1;37m  SubForge — Uninstaller\033[0m\n"
else
  printf "\033[1;37m  SubForge — Local-First Subtitle Generator (Go)\033[0m\n"
fi
printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"

# ══════════════════════════════════════════════════════════════════════════════
# INSTALL
# ══════════════════════════════════════════════════════════════════════════════
if [ "$MODE" = "install" ]; then

  mkdir -p "${INSTALL_DIR}"

  # Detect OS & Architecture
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"
  case "${ARCH}" in
    x86_64|amd64) ARCH="x64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *) ARCH="x64" ;;
  esac

  ASSET_NAME="subforge-${OS}-${ARCH}"
  DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}"

  printf "\033[33m▸ Fetching latest release for %s (%s)...\033[0m\n" "${OS}" "${ARCH}"

  TEMP_FILE="$(mktemp)"

  if curl -fsSL "${DOWNLOAD_URL}" -o "${TEMP_FILE}" 2>/dev/null; then
    mv "${TEMP_FILE}" "${TARGET_BIN}"
    chmod +x "${TARGET_BIN}"
    printf "\033[32m✓ Downloaded binary from GitHub Releases.\033[0m\n"
  else
    printf "\033[90mℹ Binary release not found. Falling back to go install...\033[0m\n"
    if command -v go >/dev/null 2>&1; then
      GOBIN="${INSTALL_DIR}" go install "github.com/${REPO}/cmd/subforge@latest"
      printf "\033[32m✓ SubForge installed via go install.\033[0m\n"
    else
      printf "\033[31m[ERROR] Could not download binary from %s and 'go' is not installed.\033[0m\n" "${DOWNLOAD_URL}"
      rm -f "${TEMP_FILE}"
      exit 1
    fi
  fi

  rm -f "${TEMP_FILE}"

  # Ensure ~/.local/bin is in PATH
  case ":${PATH}:" in
    *":${INSTALL_DIR}:"*) ;;
    *)
      printf "\033[33m▸ Adding %s to PATH...\033[0m\n" "${INSTALL_DIR}"
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
  printf "  Open a new terminal and type:\n"
  printf "    \033[1;36msubforge\033[0m\n\n"
fi

# ══════════════════════════════════════════════════════════════════════════════
# UNINSTALL
# ══════════════════════════════════════════════════════════════════════════════
if [ "$MODE" = "uninstall" ]; then

  # Remove binary
  if [ -f "${TARGET_BIN}" ]; then
    printf "\033[33m▸ Removing %s...\033[0m\n" "${TARGET_BIN}"
    rm -f "${TARGET_BIN}"
    printf "\033[32m✓ Removed binary.\033[0m\n"
  else
    printf "\033[90mℹ Binary not found at %s, skipping.\033[0m\n" "${TARGET_BIN}"
  fi

  # Clean temp files
  rm -f /tmp/subforge* /tmp/subforge_preview_*.wav 2>/dev/null || true
  printf "\033[32m✓ Cleaned temporary files.\033[0m\n"

  # Remove data (models, managed whisper-cli)
  if [ "$KEEP_DATA" = true ]; then
    printf "\033[90mℹ --keep-data set: skipping removal of %s and %s.\033[0m\n" "${DATA_DIR}" "${CONFIG_DIR}"
  else
    if [ -d "${DATA_DIR}" ]; then
      printf "\033[33m▸ Removing application data (%s)...\033[0m\n" "${DATA_DIR}"
      rm -rf "${DATA_DIR}"
      printf "\033[32m✓ Removed %s.\033[0m\n" "${DATA_DIR}"
    fi
    if [ -d "${CONFIG_DIR}" ]; then
      printf "\033[33m▸ Removing config (%s)...\033[0m\n" "${CONFIG_DIR}"
      rm -rf "${CONFIG_DIR}"
      printf "\033[32m✓ Removed %s.\033[0m\n" "${CONFIG_DIR}"
    fi
  fi

  # Remind about PATH
  for PROFILE in "${HOME}/.zshrc" "${HOME}/.bashrc" "${HOME}/.profile"; do
    if [ -f "${PROFILE}" ] && grep -q "export PATH=\"${INSTALL_DIR}:\$PATH\"" "${PROFILE}" 2>/dev/null; then
      printf "\033[33m▸ Note: '%s' entry in %s can be removed manually if no longer needed.\033[0m\n" "${INSTALL_DIR}" "${PROFILE}"
    fi
  done

  printf "\n\033[32m✓ SubForge fully uninstalled.\033[0m\n\n"
fi
