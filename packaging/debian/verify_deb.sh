#!/usr/bin/env bash
# Install, exercise and remove a FilterDesk .deb in a clean Ubuntu container.
set -euo pipefail

DEB="${1:?usage: verify_deb.sh <package.deb>}"
DEB="$(readlink -f "$DEB")"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for the clean-container check." >&2
  exit 1
fi

docker run --rm -v "$DEB:/tmp/filterdesk.deb:ro" ubuntu:22.04 bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y --no-install-recommends /tmp/filterdesk.deb

test -x /opt/filterdesk/FilterDesk
test -L /usr/bin/filterdesk
test -f /usr/share/applications/filterdesk.desktop
test -f /usr/share/icons/hicolor/256x256/apps/filterdesk.png
test -f /usr/share/doc/filterdesk/copyright
grep -q "^Exec=filterdesk$" /usr/share/applications/filterdesk.desktop

clean="$(mktemp -d)"
env HOME="$clean" \
  XDG_CONFIG_HOME="$clean/config" \
  XDG_CACHE_HOME="$clean/cache" \
  XDG_DATA_HOME="$clean/data" \
  QT_QPA_PLATFORM=offscreen \
  filterdesk --self-test

apt-get remove -y filterdesk
test ! -e /opt/filterdesk/FilterDesk
test ! -e /usr/bin/filterdesk
'
