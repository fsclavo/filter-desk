#!/usr/bin/env bash
# Build a self-contained Debian package from the PyInstaller onedir bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

VERSION="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n 1)}"
VERSION="${VERSION#v}"
ARCH="${2:-amd64}"
BUNDLE="${BUNDLE:-$ROOT/dist/FilterDesk}"
OUT="${OUT:-$ROOT/dist/FilterDesk-${VERSION}-${ARCH}.deb}"
STAGE="${STAGE:-$ROOT/build/deb/filterdesk_${VERSION}_${ARCH}}"

cleanup() {
  if [ "${KEEP_DEB_STAGE:-0}" != "1" ]; then
    rm -rf "$STAGE"
    rmdir "$(dirname "$STAGE")" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [ -z "$VERSION" ]; then
  echo "Could not determine version; pass it as the first argument." >&2
  exit 1
fi
if [ ! -x "$BUNDLE/FilterDesk" ]; then
  echo "Missing bundle launcher: $BUNDLE/FilterDesk" >&2
  echo "Build it first with packaging/filterdesk.spec." >&2
  exit 1
fi

rm -rf "$STAGE"
mkdir -p "$(dirname "$OUT")"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/opt/filterdesk" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/256x256/apps" \
  "$STAGE/usr/share/doc/filterdesk"

cp -a "$BUNDLE/." "$STAGE/opt/filterdesk/"
ln -s /opt/filterdesk/FilterDesk "$STAGE/usr/bin/filterdesk"

sed 's|^Exec=FilterDesk$|Exec=filterdesk|' \
  packaging/appimage/filterdesk.desktop \
  > "$STAGE/usr/share/applications/filterdesk.desktop"
cp packaging/appimage/filterdesk.png \
  "$STAGE/usr/share/icons/hicolor/256x256/apps/filterdesk.png"
cp LICENSE "$STAGE/usr/share/doc/filterdesk/copyright"
cp packaging/NOTICE-third-party.md "$STAGE/usr/share/doc/filterdesk/NOTICE-third-party.md"

INSTALLED_KIB="$(du -sk "$STAGE" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: filterdesk
Version: $VERSION
Architecture: $ARCH
Maintainer: FilterDesk contributors
Installed-Size: $INSTALLED_KIB
Depends: libc6 (>= 2.35), libgl1, libegl1, libxkbcommon-x11-0, libdbus-1-3, libxcb-cursor0
Section: science
Priority: optional
Homepage: https://github.com/fsclavo/filter-desk
Description: Passive lumped-element RF filter synthesis and analysis
 FilterDesk synthesizes, analyzes, optimizes and documents passive RF filters
 and matching networks, with Touchstone import/export, BOM generation and
 distributed microstrip tools.
EOF

find "$STAGE" -type d -exec chmod 0755 {} +
chmod 0644 \
  "$STAGE/DEBIAN/control" \
  "$STAGE/usr/share/applications/filterdesk.desktop" \
  "$STAGE/usr/share/icons/hicolor/256x256/apps/filterdesk.png" \
  "$STAGE/usr/share/doc/filterdesk/copyright" \
  "$STAGE/usr/share/doc/filterdesk/NOTICE-third-party.md"
chmod 0755 "$STAGE/DEBIAN"

dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "Wrote $OUT"
if [ "${KEEP_DEB_STAGE:-0}" = "1" ]; then
  echo "Kept staging directory: $STAGE" >&2
fi
