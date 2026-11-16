"""Startpunkt der Anwendung."""

from __future__ import annotations

from pathlib import Path

import logging
import os
import sys

from . import APP_NAME, APP_VERSION


def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    for name in ("presidio-analyzer", "presidio_analyzer", "presidio-anonymizer"):
        logging.getLogger(name).setLevel(logging.ERROR)
    logging.getLogger("spacy").setLevel(logging.ERROR)


def _self_test() -> int:
    """Kurztest ohne Oberflaeche - prueft Presidio, Muster und Schwaerzung."""
    import tempfile
    from pathlib import Path

    import pymupdf

    from .core.detect import DetectionOptions, run_detection
    from .core.redact import apply_redactions

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 120), "Maximiliane Schmidt-Lorenz", fontsize=11, fontname="helv")
        page.insert_text((60, 140), "Königsallee 42 a", fontsize=11, fontname="helv")
        page.insert_text((60, 160), "80331 München", fontsize=11, fontname="helv")
        page.insert_text((60, 180), "Personalnummer: 4711-2233", fontsize=11, fontname="helv")
        doc.save(str(source))
        doc.close()

        result = run_detection(
            str(source),
            DetectionOptions(
                use_ai=True,
                ai_entities=("PERSON", "LOCATION"),
                rule_groups=("address", "id"),
            ),
        )
        texts = [finding.text for finding in result.findings]
        assert any("Schmidt-Lorenz" in text for text in texts), texts
        assert any("Königsallee" in text for text in texts), texts
        assert any("4711-2233" in text for text in texts), texts

        target = Path(tmp) / "out.pdf"
        count = apply_redactions(str(source), str(target), result.findings)
        assert count > 0

        check = pymupdf.open(str(target))
        remaining = check[0].get_text()
        check.close()
        assert "4711-2233" not in remaining
        assert "Königsallee" not in remaining
        assert "Schmidt-Lorenz" not in remaining

        warnings = "; ".join(result.warnings)
        print(f"SELFTEST OK - {count} Schwaerzungen, {len(result.findings)} Treffer")
        if warnings:
            print(f"Hinweise: {warnings}")
    return 0


def _apply_update(argv: list[str]) -> int:
    """Wartet auf das Ende des alten Fensters und startet dann das Setup.

    Der Installer darf erst laufen, wenn PDFblack wirklich beendet ist - sonst
    kann Windows die Programmdateien nicht ersetzen. Dieser Helfer laeuft als
    eigener, abgekoppelter Prozess weiter, waehrend sich das Fenster schliesst.
    """
    from .core.updater import launch_installer, wait_for_exit

    index = argv.index("--apply-update")
    if index + 1 >= len(argv):
        return 2
    archive = Path(argv[index + 1])
    pid = 0
    if "--wait-pid" in argv:
        try:
            pid = int(argv[argv.index("--wait-pid") + 1])
        except (IndexError, ValueError):
            pid = 0
    if pid:
        wait_for_exit(pid)
    if not launch_installer(archive):
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _configure_logging()

    if "--version" in argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--self-test" in argv:
        return _self_test()
    if "--apply-update" in argv:
        return _apply_update(argv)

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PySide6.QtWidgets import QApplication

    from .ui.branding import app_icon
    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())
    apply_theme(app)

    window = MainWindow()
    window.show()

    for argument in argv[1:]:
        if argument.lower().endswith(".pdf") and os.path.exists(argument):
            window.open_path(argument)
            break

    # Stilles Update beim Start; abschaltbar fuer Tests und abweichende Builds.
    if "--no-update" not in argv and os.environ.get("PDFBLACK_NO_UPDATE") != "1":
        window.start_auto_update()

    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
