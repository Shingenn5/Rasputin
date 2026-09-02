#!/usr/bin/env bash
set -Eeuo pipefail

cat >&2 <<'EOF'
Rasputin Desktop currently supports Windows x64 only.

Download the Windows installer from:
https://github.com/Shingenn5/Rasputin/releases

macOS and Linux packages are not available yet. Docker-era install instructions
are retired and do not represent the current product.
EOF
exit 1
