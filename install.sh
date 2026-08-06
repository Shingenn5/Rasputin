#!/usr/bin/env bash
set -Eeuo pipefail

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

require_command curl
require_command unzip
require_command docker
if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is required. Install Docker Desktop or Docker Engine with the Compose plugin." >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "The Docker engine is not running or is not accessible. Start it and retry." >&2
    exit 1
fi

echo ""
echo -e "\033[0;36m=========================================\033[0m"
echo -e "\033[0;36m      Rasputin Installer (macOS/Linux)   \033[0m"
echo -e "\033[0;36m=========================================\033[0m"
echo ""

TARGET_DIR="${RASPUTIN_INSTALL_DIR:-$PWD/Rasputin}"
REF="${RASPUTIN_REF:-main}"

if [ -d "$TARGET_DIR" ]; then
    echo -e "\033[0;33mDirectory '$TARGET_DIR' already exists!\033[0m"
    read -p "Do you want to overwrite it? (y/N) " choice
    case "$choice" in 
      y|Y ) rm -rf "$TARGET_DIR";;
      * ) echo -e "\033[0;31mInstallation aborted.\033[0m"; exit 1;;
    esac
fi

echo -e "\033[0;36mDownloading Rasputin...\033[0m"
ZIP_URL="https://github.com/Shingenn5/Rasputin/archive/refs/heads/$REF.zip"
ZIP_PATH="$PWD/rasputin-$REF.zip"

curl -L -o "$ZIP_PATH" "$ZIP_URL"

echo -e "\033[0;36mExtracting...\033[0m"
unzip -q "$ZIP_PATH" -d "$PWD"
rm "$ZIP_PATH"

mv "$PWD/Rasputin-$REF" "$TARGET_DIR"

echo ""
echo -e "\033[0;32mInstallation complete! Rasputin is now in '$TARGET_DIR'\033[0m"
echo ""

cd "$TARGET_DIR"
chmod +x rasputin.sh
echo -e "\033[0;36mStarting Rasputin setup...\033[0m"
./rasputin.sh start
