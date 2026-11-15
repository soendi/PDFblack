"""Erzeugt Screenshots der Oberflaeche ohne Bildschirm (z. B. fuer Doku/Pruefung).

Aufruf:  python tools/ui_preview.py [--pdf samples/beispiel.pdf] [--out bild.png]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from pdfblack.app import _configure_logging  # noqa: E402
from pdfblack.core.detect import run_detection  # noqa: E402
from pdfblack.ui.branding import app_icon  # noqa: E402
from pdfblack.ui.main_window import MainWindow  # noqa: E402
from pdfblack.ui.theme import apply_theme  # noqa: E402


def _silence_dialogs() -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []

    def make(kind: str):
        def inner(parent, title, text, *args, **kwargs):
            seen.append((kind, f"{title}: {text}"))
            return QMessageBox.Ok

        return staticmethod(inner)

    QMessageBox.warning = make("warning")
    QMessageBox.information = make("info")
    QMessageBox.critical = make("critical")
    QMessageBox.about = make("about")
    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default=str(ROOT / "samples" / "beispiel.pdf"))
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "vorschau.png"))
    parser.add_argument("--page", type=int, default=1, help="Seite, die gezeigt wird")
    args = parser.parse_args()

    messages = _silence_dialogs()
    _configure_logging()
    app = QApplication([])
    app.setWindowIcon(app_icon())
    apply_theme(app)

    window = MainWindow()
    window.resize(1440, 940)
    window.show()
    app.processEvents()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(out.with_name(out.stem + "_1_leer.png")))

    window.load_pdf(args.pdf)
    app.processEvents()
    window.grab().save(str(out.with_name(out.stem + "_2_geladen.png")))

    options = window.controls.read_options()
    result = run_detection(window._path, options)
    window._on_detection_done(result)
    app.processEvents()
    if args.page > 1 and args.page <= window.canvas.page_count:
        window.scroll.verticalScrollBar().setValue(
            int(window.canvas._page_pos[args.page - 1].y())
        )
        app.processEvents()
    window.grab().save(str(out))

    if window._findings:
        window._select_finding(window._findings[0].uid)
        window._toggle_finding(window._findings[0].uid)
        app.processEvents()
        window.grab().save(str(out.with_name(out.stem + "_3_abgewaehlt.png")))

    # Speichern-Weg der Oberflaeche testen (Dateidialog wird ersetzt)
    target = Path(args.out).with_name("ui_gespeichert.pdf")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(target), "PDF"))
    window._save_as()
    if target.exists():
        import pymupdf

        check = pymupdf.open(str(target))
        remaining = "".join(page.get_text() for page in check)
        check.close()
        leaked = [
            token
            for token in ("4711-2233", "80331", "maximiliane.schmidt@example.de", "DE89 3704")
            if token in remaining
        ]
        print(f"Gespeichert: {target.name}, Resttext-Treffer: {leaked or 'keine'}")
    else:
        print("FEHLER: Speichern hat keine Datei erzeugt")

    print(f"Treffer: {len(result.findings)}  Warnungen: {result.warnings}")
    print(f"Status: {window.statusBar().currentMessage()}")
    for kind, text in messages:
        print(f"[{kind}] {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
