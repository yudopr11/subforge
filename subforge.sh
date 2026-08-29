#!/usr/bin/env sh
# SubForge Linux & macOS Installer / Uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/subforge.sh | sh

set -e

APP_NAME="subforge"
REPO="yudopr11/subforge"
INSTALL_DIR="${HOME}/.local/bin"
TARGET_BIN="${INSTALL_DIR}/${APP_NAME}"
DATA_DIR="${HOME}/.local/share/subforge"
CONFIG_DIR="${HOME}/.config/subforge"

# ── Helpers ────────────────────────────────────────────────────────────────────
print_banner() {
  printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n"
  printf "\033[1;37m  SubForge — Local-First Subtitle Generator (Go)\033[0m\n"
  printf "\033[36m════════════════════════════════════════════════════════════════\033[0m\n\n"
}

ask() {
  # ask <prompt> → returns 0 (yes) or 1 (no)
  printf "%s [y/N] " "$1"
  REPLY=""
  if [ -t 0 ]; then
    read -r REPLY
  elif [ -e /dev/tty ]; then
    read -r REPLY < /dev/tty 2>/dev/null || REPLY=""
  fi
  case "$REPLY" in
    [Yy]*) return 0 ;;
    *)     return 1 ;;
  esac
}

# ── Banner ─────────────────────────────────────────────────────────────────────
print_banner

# ── Main menu ──────────────────────────────────────────────────────────────────
printf "  What would you like to do?\n\n"
printf "    \033[1;36m1)\033[0m Install SubForge\n"
printf "    \033[1;36m2)\033[0m Uninstall SubForge\n\n"
printf "  Choice [1/2]: "
CHOICE=""
if [ -t 0 ]; then
  read -r CHOICE
elif [ -e /dev/tty ]; then
  read -r CHOICE < /dev/tty 2>/dev/null || CHOICE=""
fi

case "$CHOICE" in
  2) MODE="uninstall" ;;
  *) MODE="install" ;;
esac

printf "\n"

# ══════════════════════════════════════════════════════════════════════════════
# INSTALL
# ══════════════════════════════════════════════════════════════════════════════
if [ "$MODE" = "install" ]; then

  mkdir -p "${INSTALL_DIR}"

  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  case "${OS}" in
    darwin*) OS="darwin" ;;
    linux*)  OS="linux" ;;
    *)       OS="linux" ;;
  esac

  ARCH="$(uname -m)"
  case "${ARCH}" in
    x86_64|amd64)  ARCH="x64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *)             ARCH="x64" ;;
  esac

  # macOS Rosetta check: if running under Rosetta translation, use native arm64
  if [ "${OS}" = "darwin" ] && [ "${ARCH}" = "x64" ]; then
    if [ "$(sysctl -in sysctl.proc_translated 2>/dev/null)" = "1" ]; then
      ARCH="arm64"
    fi
  fi

  ASSET_NAME="subforge-${OS}-${ARCH}"
  DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}"

  printf "\033[33m▸ Fetching latest release for %s (%s)...\033[0m\n" "${OS}" "${ARCH}"

  TEMP_FILE="$(mktemp 2>/dev/null || mktemp -t subforge.XXXXXX 2>/dev/null || echo "/tmp/subforge-download.$$")"

  DOWNLOAD_SUCCESS=false
  if command -v curl >/dev/null 2>&1; then
    if curl -fsSL "${DOWNLOAD_URL}" -o "${TEMP_FILE}" 2>/dev/null; then
      DOWNLOAD_SUCCESS=true
    fi
  elif command -v wget >/dev/null 2>&1; then
    if wget -qO "${TEMP_FILE}" "${DOWNLOAD_URL}" 2>/dev/null; then
      DOWNLOAD_SUCCESS=true
    fi
  fi

  if [ "$DOWNLOAD_SUCCESS" = true ]; then
    mv "${TEMP_FILE}" "${TARGET_BIN}"
    chmod +x "${TARGET_BIN}"
    if [ "${OS}" = "darwin" ]; then
      xattr -dr com.apple.quarantine "${TARGET_BIN}" 2>/dev/null || true
    fi
    printf "\033[32m✓ Downloaded binary from GitHub Releases.\033[0m\n"
  else
    printf "\033[90mℹ Binary release not found. Falling back to go install...\033[0m\n"
    if command -v go >/dev/null 2>&1; then
      GOBIN="${INSTALL_DIR}" go install "github.com/${REPO}/cmd/subforge@latest"
      printf "\033[32m✓ SubForge installed via go install.\033[0m\n"
    else
      printf "\033[31m[ERROR] Could not download binary and 'go' is not installed.\033[0m\n"
      rm -f "${TEMP_FILE}"
      exit 1
    fi
  fi

  rm -f "${TEMP_FILE}"

  case ":${PATH}:" in
    *":${INSTALL_DIR}:"*) ;;
    *)
      printf "\033[33m▸ Adding %s to PATH...\033[0m\n" "${INSTALL_DIR}"
      SHELL_NAME="$(basename "${SHELL:-sh}")"
      if [ "${SHELL_NAME}" = "zsh" ]; then
        PROFILE="${HOME}/.zshrc"
      elif [ "${SHELL_NAME}" = "bash" ]; then
        if [ -f "${HOME}/.bash_profile" ]; then
          PROFILE="${HOME}/.bash_profile"
        else
          PROFILE="${HOME}/.bashrc"
        fi
      elif [ "${SHELL_NAME}" = "fish" ]; then
        mkdir -p "${HOME}/.config/fish"
        PROFILE="${HOME}/.config/fish/config.fish"
      else
        PROFILE="${HOME}/.profile"
      fi

      if [ "${SHELL_NAME}" = "fish" ]; then
        printf '\nset -gx PATH "%s" $PATH\n' "${INSTALL_DIR}" >> "${PROFILE}"
      else
        printf '\nexport PATH="%s:$PATH"\n' "${INSTALL_DIR}" >> "${PROFILE}"
      fi
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

  printf "\033[33m  Uninstall options:\033[0m\n\n"
  KEEP_DATA=false
  if ask "  Keep downloaded models and application data?"; then
    KEEP_DATA=true
    printf "\033[90m  ℹ Data and config will be preserved.\033[0m\n"
  else
    printf "\033[90m  ℹ Data and config will be removed.\033[0m\n"
  fi
  printf "\n"

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

  if [ "$KEEP_DATA" = false ]; then
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

  # Remind about PATH entry
  for PROFILE in "${HOME}/.zshrc" "${HOME}/.bashrc" "${HOME}/.profile"; do
    if [ -f "${PROFILE}" ] && grep -q "export PATH=\"${INSTALL_DIR}:\$PATH\"" "${PROFILE}" 2>/dev/null; then
      printf "\033[33m▸ Note: '%s' entry in %s can be removed manually if no longer needed.\033[0m\n" "${INSTALL_DIR}" "${PROFILE}"
    fi
  done

  printf "\n\033[32m✓ SubForge fully uninstalled.\033[0m\n\n"
fi
