#!/usr/bin/env bash
# Best-effort AppImage packaging from the PyInstaller onedir bundle.
#
# Prereqs: built bundle in dist/FilterDesk (see packaging/filterdesk.spec),
# plus curl. Produces FilterDesk-x86_64.AppImage in the repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r dist/FilterDesk/* "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/FilterDesk" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cp packaging/appimage/filterdesk.desktop "$APPDIR/filterdesk.desktop"
cp packaging/appimage/filterdesk.png "$APPDIR/filterdesk.png"

TOOL=/tmp/appimagetool-x86_64.AppImage
if [ ! -x "$TOOL" ]; then
  curl -L -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi

ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" FilterDesk-x86_64.AppImage
echo "Wrote FilterDesk-x86_64.AppImage"
