#!/usr/bin/env bash
set -e

echo ""
echo -e "\033[0;36m=========================================\033[0m"
echo -e "\033[0;36m      Rasputin Installer (macOS/Linux)   \033[0m"
echo -e "\033[0;36m=========================================\033[0m"
echo ""

TARGET_DIR="$PWD/Rasputin"

if [ -d "$TARGET_DIR" ]; then
    echo -e "\033[0;33mDirectory '$TARGET_DIR' already exists!\033[0m"
    read -p "Do you want to overwrite it? (y/N) " choice
    case "$choice" in 
      y|Y ) rm -rf "$TARGET_DIR";;
      * ) echo -e "\033[0;31mInstallation aborted.\033[0m"; exit 1;;
    esac
fi

echo -e "\033[0;36mDownloading Rasputin...\033[0m"
ZIP_URL="https://github.com/Shingenn5/Rasputin/archive/refs/heads/main.zip"
ZIP_PATH="$PWD/rasputin-main.zip"

curl -L -o "$ZIP_PATH" "$ZIP_URL"

echo -e "\033[0;36mExtracting...\033[0m"
unzip -q "$ZIP_PATH" -d "$PWD"
rm "$ZIP_PATH"

mv "$PWD/Rasputin-main" "$TARGET_DIR"

echo ""
echo -e "\033[0;32mInstallation complete! Rasputin is now in '$TARGET_DIR'\033[0m"
echo ""

cd "$TARGET_DIR"
chmod +x rasputin.sh
echo -e "\033[0;36mStarting Rasputin setup...\033[0m"
./rasputin.sh start
