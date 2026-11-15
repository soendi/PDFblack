"""Schwaerzen: Text wirklich entfernen und die Datei neu schreiben.

Wichtig: Es wird kein schwarzes Rechteck ueber den Text gelegt, sondern der
Text unter der Flaeche wird aus dem Dokument entfernt (PyMuPDF-Redaction) und
die Datei anschliessend vollstaendig neu geschrieben (garbage=4, clean=True),
damit keine Reste im PDF zurueckbleiben.
"""

from __future__ import annotations

import os

import pymupdf

from .extract import open_document
from .models import Finding

BLACK = (0.0, 0.0, 0.0)


def _drop_links_inside(page: pymupdf.Page, boxes: list[pymupdf.Rect]) -> None:
    """Links entfernen, die auf eine geschwaerzte Stelle zeigen."""
    for link in page.get_links():
        raw = link.get("from")
        if raw is None:
            continue
        link_rect = pymupdf.Rect(raw)
        if any(link_rect.intersects(box) for box in boxes):
            page.delete_link(link)


def _clear_widgets(page: pymupdf.Page, boxes: list[pymupdf.Rect]) -> None:
    """Formularfelder im Schwärzungsbereich leeren und entfernen.

    Feldwerte stehen in der Felderscheinung, nicht im Seitentext; ohne diesen
    Schritt bliebe der Wert im PDF erhalten, obwohl die Flaeche geschwaerzt ist.
    """
    try:
        widgets = list(page.widgets() or [])
    except Exception:  # noqa: BLE001 - defekte Formulare nicht abbrechen
        return
    for widget in widgets:
        try:
            rect = pymupdf.Rect(widget.rect)
        except Exception:  # noqa: BLE001
            continue
        if not any(rect.intersects(box) for box in boxes):
            continue
        try:
            widget.field_value = ""
            widget.update()
        except Exception:  # noqa: BLE001
            pass
        try:
            page.delete_widget(widget)
        except Exception:  # noqa: BLE001
            pass


def apply_redactions(
    src: str,
    dst: str,
    findings: list[Finding],
    password: str | None = None,
) -> int:
    """Alle aktiven Treffer schwaerzen und unter ``dst`` speichern.

    Rueckgabe: Anzahl der geschwaerzten Stellen.
    """
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError("Ziel- und Quelldatei sind identisch. Bitte einen anderen Dateinamen waehlen.")

    doc = open_document(src, password)
    count = 0
    try:
        per_page: dict[int, list[Finding]] = {}
        for finding in findings:
            if finding.enabled and finding.rects:
                per_page.setdefault(finding.page, []).append(finding)

        for page_index, page_findings in sorted(per_page.items()):
            if page_index < 0 or page_index >= doc.page_count:
                continue
            page = doc[page_index]
            page_rect = page.rect
            boxes: list[pymupdf.Rect] = []
            for finding in page_findings:
                for raw in finding.rects:
                    box = pymupdf.Rect(raw) & page_rect
                    if box.is_empty or box.width < 0.4 or box.height < 0.4:
                        continue
                    page.add_redact_annot(box, fill=BLACK, cross_out=False)
                    boxes.append(box)
                    count += 1
            if boxes:
                _drop_links_inside(page, boxes)
                _clear_widgets(page, boxes)
                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

        doc.save(
            dst,
            garbage=4,
            clean=True,
            deflate=True,
            deflate_fonts=True,
            deflate_images=True,
        )
    finally:
        doc.close()
    return count
