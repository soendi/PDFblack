#!/usr/bin/env bash
# Baut PDFblack fuer macOS als .app und ZIP-Archiv.
# Hinweis: dieser Weg ist nicht auf einem Mac verifiziert worden.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0, "src"); from pdfblack import APP_VERSION; print(APP_VERSION)')"

"$PYTHON" "$ROOT/packaging/make_icon.py"
"$PYTHON" -m PyInstaller \
    --noconfirm --clean \
    --windowed \
    --name PDFblack \
    --osx-bundle-identifier de.pdfblack.app \
    --icon "$ROOT/packaging/pdfblack.ico" \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build" \
    "$ROOT/src/pdfblack/__main__.py"

ditto -c -k --sequesterRsrc --keepParent \
    "$ROOT/dist/PDFblack.app" \
    "$ROOT/dist/PDFblack-${VERSION}-macOS.zip"

echo "Fertig: dist/PDFblack-${VERSION}-macOS.zip"
