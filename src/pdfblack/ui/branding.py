"""Programmatisch gezeichnetes App-Symbol (keine Bilddateien noetig)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap


def _pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    s = float(size)
    gradient = QLinearGradient(0.0, 0.0, s, s)
    gradient.setColorAt(0.0, QColor("#f2555a"))
    gradient.setColorAt(1.0, QColor("#8f1d21"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)

    page = QRectF(s * 0.23, s * 0.15, s * 0.54, s * 0.70)
    painter.setBrush(QColor("#f6f7f9"))
    painter.drawRoundedRect(page, s * 0.05, s * 0.05)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#c8ccd4"))
    line_h = s * 0.052
    for index, y in enumerate((0.27, 0.38, 0.49, 0.60, 0.71)):
        width = s * 0.36 if index % 2 == 0 else s * 0.28
        painter.drawRoundedRect(
            QRectF(s * 0.31, s * y, width, line_h), line_h / 2, line_h / 2
        )

    painter.setBrush(QColor("#13151a"))
    painter.drawRoundedRect(
        QRectF(s * 0.29, s * 0.470, s * 0.42, s * 0.078), s * 0.012, s * 0.012
    )
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_pixmap(size))
    return icon


def logo_pixmap(size: int = 34) -> QPixmap:
    return _pixmap(size)
