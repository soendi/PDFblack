# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Build fuer PDFblack (onedir inkl. Presidio, spaCy-Modell und Qt)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent  # .../packaging
SRC = ROOT / "src"

datas = []
binaries = []
hiddenimports = []

# Diese Pakete bringen Daten, Modelle oder Erweiterungen mit, die PyInstaller
# nicht selbst findet.
for package in (
    "spacy",
    "thinc",
    "srsly",
    "blis",
    "cymem",
    "preshed",
    "murmurhash",
    "weasel",
    "confection",
    "spacy_legacy",
    "presidio_analyzer",
    "presidio_anonymizer",
    "pymupdf",
    "de_core_news_md",
    "phonenumbers",
    "tldextract",
    "spellchecker",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # pragma: no cover - optionale Pakete
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Amtliche PLZ-/Ortschaftsliste und Berufsbezeichnungen
# (tools/build_plz_data.py, tools/build_berufe_data.py).
datas += [
    (str(SRC / "pdfblack" / "data" / "plz_ch.json"), "pdfblack/data"),
    (str(SRC / "pdfblack" / "data" / "berufe.json"), "pdfblack/data"),
]

hiddenimports += collect_submodules("presidio_analyzer.predefined_recognizers")
hiddenimports += ["spacy.lang.de", "spacy.lang.en", "yaml"]

icon_file = ROOT / "packaging" / "pdfblack.ico"

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pandas",
        "scipy",
        "IPython",
        "pytest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtDesigner",
        "PySide6.QtTest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFblack",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_file) if icon_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDFblack",
)
