#!/usr/bin/env bash
# Gera um AppImage do Osteon Viewer a partir de dist/Osteon/ (saída do PyInstaller onedir).
# Uso (Linux):  bash packaging/build-appimage.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d dist/Osteon ] || { echo "Rode primeiro: pyinstaller packaging/osteon.spec"; exit 1; }

APPDIR=dist/Osteon.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/512x512/apps"

cp -r dist/Osteon/* "$APPDIR/usr/bin/"
cp packaging/icon.png "$APPDIR/usr/share/icons/hicolor/512x512/apps/osteon.png"
cp packaging/icon.png "$APPDIR/osteon.png"

cat > "$APPDIR/osteon.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Osteon Viewer
Exec=Osteon
Icon=osteon
Categories=Science;MedicalSoftware;
Terminal=false
DESK
cp "$APPDIR/osteon.desktop" "$APPDIR/usr/share/applications/osteon.desktop"

cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Osteon" "$@"
RUN
chmod +x "$APPDIR/AppRun"

# baixa o appimagetool se necessário
TOOL=dist/appimagetool-x86_64.AppImage
if [ ! -f "$TOOL" ]; then
  curl -L -o "$TOOL" \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi

ARCH=x86_64 "$TOOL" "$APPDIR" "dist/OsteonViewer-1.0.0-x86_64.AppImage"
echo "AppImage gerado em dist/OsteonViewer-1.0.0-x86_64.AppImage"
