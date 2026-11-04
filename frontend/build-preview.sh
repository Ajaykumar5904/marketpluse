#!/bin/sh
set -eu
rm -rf frontend/dist
mkdir -p frontend/dist
cp -R frontend/src/. frontend/dist/
cat > frontend/dist/config.js <<'EOF'
window.MARKETPULSE_API = '';
window.MARKETPULSE_PREVIEW_ONLY = true;
EOF
