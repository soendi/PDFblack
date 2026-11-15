#!/usr/bin/env bash
# Baut PDFblack fuer Linux: eigenstaendiges Programmverzeichnis, .deb und .tar.gz.
# Voraussetzung: virtuelle Umgebung mit Abhaengigkeiten (siehe README).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Interpreter bestimmen: explizit gesetzt (PYTHON=...), sonst die virtuelle
# Umgebung im Projekt, sonst der Python aus dem PATH (z. B. auf CI-Runnern).
if [ -z "${PYTHON:-}" ]; then
    if [ -x "$ROOT/.venv/bin/python" ]; then
        PYTHON="$ROOT/.venv/bin/python"
    else
        PYTHON="$(command -v python3 || command -v python || true)"
    fi
fi

if [ -z "${PYTHON:-}" ] || [ ! -x "$PYTHON" ]; then
    echo "Kein Python-Interpreter gefunden. Bitte virtuelle Umgebung anlegen" >&2
    echo "(siehe README) oder PYTHON=/pfad/zu/python setzen." >&2
    exit 1
fi

VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0, "src"); from pdfblack import APP_VERSION; print(APP_VERSION)')"
echo "== PDFblack $VERSION =="

echo "== Symbol erzeugen =="
"$PYTHON" "$ROOT/packaging/make_icon.py"

echo "== PyInstaller =="
"$PYTHON" -m PyInstaller \
    --noconfirm --clean \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build" \
    "$ROOT/packaging/pdfblack.spec"

echo "== Selbsttest der gebauten Anwendung =="
"$ROOT/dist/PDFblack/PDFblack" --self-test

echo "== Debian-Paket bauen =="
PKGROOT="$ROOT/build/deb"
rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/DEBIAN" \
         "$PKGROOT/opt/pdfblack" \
         "$PKGROOT/usr/bin" \
         "$PKGROOT/usr/share/applications" \
         "$PKGROOT/usr/share/icons/hicolor/256x256/apps"

cp -a "$ROOT/dist/PDFblack/." "$PKGROOT/opt/pdfblack/"
chmod +x "$PKGROOT/opt/pdfblack/PDFblack"
ln -sf /opt/pdfblack/PDFblack "$PKGROOT/usr/bin/pdfblack"
cp "$ROOT/packaging/pdfblack.png" "$PKGROOT/usr/share/icons/hicolor/256x256/apps/pdfblack.png"

cat > "$PKGROOT/usr/share/applications/pdfblack.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=PDFblack
Comment=Vertrauliche Daten in PDF-Dateien automatisch schwaerzen
Exec=pdfblack %f
Icon=pdfblack
Terminal=false
Categories=Office;Utility;
MimeType=application/pdf;
Keywords=PDF;Schwaerzen;Redaktion;Anonymisierung;
DESKTOP

INSTALLED_SIZE="$(du -sk "$PKGROOT/opt" | cut -f1)"
cat > "$PKGROOT/DEBIAN/control" <<CONTROL
Package: pdfblack
Version: $VERSION
Section: office
Priority: optional
Architecture: amd64
Installed-Size: $INSTALLED_SIZE
Maintainer: PDFblack
Depends: libc6, libgl1, libegl1, libxkbcommon0, libfontconfig1, libfreetype6, libpng16-16, libdbus-1-3
Description: Automatische Schwaerzung personenbezogener Daten in PDFs
 PDFblack findet Namen, Adressen, PLZ/Ort, Nummern, E-Mail, Telefon und IBAN
 in PDF-Dateien, zeigt alle Fundstellen als farbige Vorschau und entfernt
 die Daten beim Speichern physisch aus dem Dokument.
CONTROL

dpkg-deb --build --root-owner-group "$PKGROOT" "$ROOT/dist/PDFblack_${VERSION}_amd64.deb"

echo "== Archiv fuer manuelle Installation =="
tar -C "$ROOT/dist" -czf "$ROOT/dist/PDFblack-${VERSION}-linux-x86_64.tar.gz" PDFblack

echo
echo "Fertig:"
ls -lh "$ROOT/dist"/*.deb "$ROOT/dist"/*.tar.gz
