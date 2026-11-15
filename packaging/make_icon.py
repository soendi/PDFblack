"""Erzeugt PDFblack-Logodateien (PNG + ICO) fuer Installer und Desktop-Eintraege."""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from pdfblack.ui.branding import _pixmap  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(size: int) -> bytes:
    pixmap = _pixmap(size)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def write_ico(path: Path) -> None:
    images = [(size, png_bytes(size)) for size in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    offset = 6 + 16 * len(images)
    payload = b""
    for size, data in images:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        payload += data
        offset += len(data)
    path.write_bytes(header + entries + payload)


def main() -> int:
    QGuiApplication([])
    out_dir = HERE
    png_path = out_dir / "pdfblack.png"
    _pixmap(256).save(str(png_path), "PNG")
    write_ico(out_dir / "pdfblack.ico")
    print(f"{png_path}")
    print(f"{out_dir / 'pdfblack.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
