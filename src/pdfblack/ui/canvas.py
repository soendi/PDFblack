"""PDF-Vorschau mit farbigen Markierungen und manueller Bereichsauswahl."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

import pymupdf

from ..core.extract import open_document
from ..core.models import Finding


class PdfCanvas(QWidget):
    """Zeichnet alle Seiten untereinander und markiert die Treffer."""

    findingActivated = Signal(int)  # uid
    regionDrawn = Signal(int, float, float, float, float)  # page, x0, y0, x1, y1
    wordActivated = Signal(int, str, float, float, float, float)  # Seite, Wort, Box
    zoomRequested = Signal(float)
    ensureRequested = Signal(QRect)

    MARGIN = 26
    GAP = 20
    MAX_PIXMAPS = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: pymupdf.Document | None = None
        self._zoom = 1.0
        self._findings: list[Finding] = []
        self._selected_uid = 0
        self._page_sizes: list[QSizeF] = []
        self._page_pos: list[QPointF] = []
        self._pixmaps: dict[int, tuple[float, QPixmap]] = {}
        self._drag_origin: QPointF | None = None
        self._drag_current: QPointF | None = None
        # Ein Klick auf einen Treffer wird kurz verzoegert, damit ein
        # Doppelklick (Wort schwaerzen) nicht vorher schon umschaltet.
        self._pending_click = 0
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(180)
        self._click_timer.timeout.connect(self._commit_click)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    # ------------------------------------------------------------------
    # Dokument
    # ------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        return self._doc.page_count if self._doc else 0

    @property
    def zoom(self) -> float:
        return self._zoom

    def page_width(self) -> float:
        if not self._doc:
            return 0.0
        return float(self._doc[0].rect.width)

    def load(self, path: str, password: str | None = None) -> None:
        # Erst das neue Dokument oeffnen: schlaegt das fehl, bleibt die bisher
        # angezeigte Datei unveraendert und benutzbar.
        doc = open_document(path, password)
        if self._doc is not None:
            self._doc.close()
        self._doc = doc
        self._findings = []
        self._selected_uid = 0
        self._pixmaps.clear()
        self._relayout(resize_height=True)
        self.update()

    def clear(self) -> None:
        if self._doc is not None:
            self._doc.close()
        self._doc = None
        self._findings = []
        self._page_sizes = []
        self._page_pos = []
        self._pixmaps.clear()
        self.setMinimumSize(QSize(1, 1))
        self.update()

    # ------------------------------------------------------------------
    # Treffer
    # ------------------------------------------------------------------

    def set_findings(self, findings: list[Finding]) -> None:
        self._findings = list(findings)
        self.update()

    def set_selected(self, uid: int) -> None:
        self._selected_uid = uid
        self.update()

    def scroll_to_finding(self, uid: int) -> None:
        for finding in self._findings:
            if finding.uid != uid or finding.page >= len(self._page_pos):
                continue
            origin = self._page_pos[finding.page]
            rects = [
                self._to_canvas(finding.page, rect) for rect in finding.rects
            ]
            if not rects:
                return
            box = rects[0]
            for other in rects[1:]:
                box = box.united(other)
            self._selected_uid = uid
            self.update()
            self.ensureRequested.emit(box.toAlignedRect().adjusted(-40, -80, 40, 80))
            return

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.25, min(4.0, zoom))
        if abs(zoom - self._zoom) < 1e-4:
            return
        self._zoom = zoom
        self._pixmaps.clear()
        self._relayout(resize_height=True)
        self.update()

    # ------------------------------------------------------------------
    # Layout und Zeichnen
    # ------------------------------------------------------------------

    def _relayout(self, resize_height: bool = False) -> None:
        if not self._doc:
            return
        self._page_sizes = [
            QSizeF(self._doc[i].rect.width * self._zoom, self._doc[i].rect.height * self._zoom)
            for i in range(self._doc.page_count)
        ]
        widest = max(size.width() for size in self._page_sizes)
        total_h = sum(size.height() for size in self._page_sizes) + self.GAP * (
            len(self._page_sizes) - 1
        )
        self.setMinimumSize(
            QSize(int(widest + 2 * self.MARGIN), int(total_h + 2 * self.MARGIN))
        )
        self._position_pages()

    def _position_pages(self) -> None:
        if not self._page_sizes:
            self._page_pos = []
            return
        available = max(self.width(), self.minimumWidth())
        positions: list[QPointF] = []
        y = float(self.MARGIN)
        for size in self._page_sizes:
            x = max(float(self.MARGIN), (available - size.width()) / 2.0)
            positions.append(QPointF(x, y))
            y += size.height() + self.GAP
        self._page_pos = positions

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_pages()

    def _pixmap_for(self, index: int) -> QPixmap | None:
        cached = self._pixmaps.get(index)
        if cached is not None and abs(cached[0] - self._zoom) < 1e-6:
            return cached[1]
        if not self._doc:
            return None
        page = self._doc[index]
        dpr = max(1.0, self.devicePixelRatioF())
        scale = self._zoom * dpr
        max_width = 4200.0
        if page.rect.width * scale > max_width:
            scale = max_width / page.rect.width
        data = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image = QImage(
            data.samples, data.width, data.height, data.stride, QImage.Format_RGB888
        ).copy()
        pixmap = QPixmap.fromImage(image)
        factor = scale / self._zoom if self._zoom else 1.0
        pixmap.setDevicePixelRatio(factor)
        if len(self._pixmaps) >= self.MAX_PIXMAPS:
            self._pixmaps.pop(next(iter(self._pixmaps)))
        self._pixmaps[index] = (self._zoom, pixmap)
        return pixmap

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0e1014"))
        if not self._doc:
            painter.end()
            return
        viewport = QRectF(event.rect())
        for index, position in enumerate(self._page_pos):
            box = QRectF(position, self._page_sizes[index])
            if not box.intersects(viewport):
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#1e222a"))
            painter.drawRoundedRect(box.adjusted(-1.0, -1.0, 1.0, 2.0), 3.0, 3.0)
            pixmap = self._pixmap_for(index)
            if pixmap is not None and not pixmap.isNull():
                painter.drawPixmap(box.topLeft(), pixmap)
            self._paint_overlays(painter, index)

        if self._drag_origin is not None and self._drag_current is not None:
            rubber = QRectF(self._drag_origin, self._drag_current).normalized()
            painter.setPen(QPen(QColor("#e5484d"), 1.4, Qt.DashLine))
            painter.setBrush(QColor(229, 72, 77, 58))
            painter.drawRect(rubber)
        painter.end()

    def _paint_overlays(self, painter: QPainter, page: int) -> None:
        for finding in self._findings:
            if finding.page != page:
                continue
            color = QColor(finding.category.color)
            selected = finding.uid == self._selected_uid
            for rect in finding.rects:
                box = self._to_canvas(page, rect)
                if finding.enabled:
                    fill = QColor(color)
                    fill.setAlpha(72 if not selected else 96)
                    painter.fillRect(box, fill)
                    pen = QPen(color)
                    pen.setWidthF(3.0 if selected else 1.6)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(box)
                else:
                    pen = QPen(QColor(126, 134, 148, 210))
                    pen.setWidthF(1.2)
                    pen.setStyle(Qt.DashLine)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(box)

    # ------------------------------------------------------------------
    # Koordinaten
    # ------------------------------------------------------------------

    def _to_canvas(self, page: int, rect: tuple[float, float, float, float]) -> QRectF:
        origin = self._page_pos[page]
        return QRectF(
            origin.x() + rect[0] * self._zoom,
            origin.y() + rect[1] * self._zoom,
            (rect[2] - rect[0]) * self._zoom,
            (rect[3] - rect[1]) * self._zoom,
        )

    def page_at_y(self, y: float) -> int:
        """Seitenindex zu einer Y-Position im Zeichenbereich."""
        for index, position in enumerate(self._page_pos):
            if y < position.y() + self._page_sizes[index].height():
                return index
        return max(0, len(self._page_pos) - 1)

    def _page_at(self, point: QPointF) -> int | None:
        for index, position in enumerate(self._page_pos):
            if QRectF(position, self._page_sizes[index]).contains(point):
                return index
        return None

    def _finding_at(self, point: QPointF) -> int:
        for finding in reversed(self._findings):
            for rect in finding.rects:
                if self._to_canvas(finding.page, rect).contains(point):
                    return finding.uid
        return 0

    def word_at(
        self, page: int, point: QPointF
    ) -> tuple[str, tuple[float, float, float, float]] | None:
        """Wort unter einer Canvas-Position (kleinste passende Wortbox)."""
        if self._doc is None or not (0 <= page < len(self._page_pos)):
            return None
        origin = self._page_pos[page]
        x = (point.x() - origin.x()) / self._zoom
        y = (point.y() - origin.y()) / self._zoom
        try:
            words = self._doc[page].get_text("words")
        except Exception:
            return None
        best: tuple[float, str, tuple[float, float, float, float]] | None = None
        for x0, y0, x1, y1, text, *_rest in words:
            if not text.strip():
                continue
            if x0 - 1.0 <= x <= x1 + 1.0 and y0 - 1.5 <= y <= y1 + 1.5:
                area = (x1 - x0) * (y1 - y0)
                if best is None or area < best[0]:
                    best = (area, text, (x0, y0, x1, y1))
        if best is None:
            return None
        return best[1], best[2]

    def _to_page_rect(self, page: int, rect: QRectF) -> tuple[float, float, float, float]:
        origin = self._page_pos[page]
        size = self._page_sizes[page]
        left = max(0.0, (rect.left() - origin.x()) / self._zoom)
        top = max(0.0, (rect.top() - origin.y()) / self._zoom)
        right = min(size.width() / self._zoom, (rect.right() - origin.x()) / self._zoom)
        bottom = min(size.height() / self._zoom, (rect.bottom() - origin.y()) / self._zoom)
        return (left, top, right, bottom)

    # ------------------------------------------------------------------
    # Maus und Rad
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or not self._doc:
            return
        self._drag_origin = event.position()
        self._drag_current = event.position()
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None:
            self._drag_current = event.position()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is None:
            return
        start = self._drag_origin
        end = event.position()
        self._drag_origin = None
        self._drag_current = None
        self.update()

        if (end - start).manhattanLength() < 8:
            uid = self._finding_at(end)
            if uid:
                self._pending_click = uid
                self._click_timer.start()
            return

        area = QRectF(start, end).normalized()
        page = self._page_at(area.center())
        if page is None:
            return
        box = self._to_page_rect(page, area)
        if box[2] - box[0] < 3 or box[3] - box[1] < 3:
            return
        self.regionDrawn.emit(page, *box)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or not self._doc:
            return
        # Ein Doppelklick schwaerzt das Wort; der Einzelklick davor
        # (Treffer umschalten) wird verworfen.
        self._click_timer.stop()
        self._pending_click = 0
        page = self._page_at(event.position())
        if page is None:
            return
        hit = self.word_at(page, event.position())
        if hit is None:
            return
        text, box = hit
        self.wordActivated.emit(page, text, *box)

    def _commit_click(self) -> None:
        uid = self._pending_click
        self._pending_click = 0
        if uid:
            self.findingActivated.emit(uid)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                factor = 1.12 if delta > 0 else 1 / 1.12
                self.zoomRequested.emit(self._zoom * factor)
            event.accept()
            return
        super().wheelEvent(event)
