"""Tests fuer Versionsvergleich, Update-Abfrage und Dateiauswahl."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from pdfblack.core import updater


class _FakeResponse:
    """Minimaler Ersatz fuer urlopen()."""

    def __init__(self, data: bytes) -> None:
        self._stream = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False


def test_versionsvergleich():
    assert updater.parse_version("v1.0.1") == (1, 0, 1)
    assert updater.parse_version("1.10.0-beta") == (1, 10, 0)
    assert updater.parse_version("quatsch") == ()
    assert updater.is_newer("1.0.0", "1.0.1")
    assert updater.is_newer("1.0.0", "v1.1")
    assert updater.is_newer("1.9.0", "1.10.0")
    assert not updater.is_newer("1.0.1", "1.0.1")
    assert not updater.is_newer("1.2.0", "1.1.9")
    assert not updater.is_newer("1.0.0", "unbekannt")


def test_dateiauswahl_fuer_betriebssystem():
    release = updater.Release(
        version="1.0.1",
        tag="v1.0.1",
        assets={
            "PDFblack-1.0.1-Setup.exe": "https://example.org/setup",
            "PDFblack_1.0.1_amd64.deb": "https://example.org/deb",
            "PDFblack-1.0.1-linux-x86_64.tar.gz": "https://example.org/tar",
        },
    )
    assert updater.asset_for(release, "win32") == (
        "PDFblack-1.0.1-Setup.exe",
        "https://example.org/setup",
    )
    assert updater.asset_for(release, "linux") == (
        "PDFblack-1.0.1-linux-x86_64.tar.gz",
        "https://example.org/tar",
    )
    assert updater.asset_for(release, "darwin") is None


def test_abfrage_liest_release(monkeypatch):
    payload = {
        "tag_name": "v1.0.1",
        "body": "Fehler behoben",
        "html_url": "https://github.com/soendi/PDFblack/releases/tag/v1.0.1",
        "assets": [
            {"name": "PDFblack-1.0.1-Setup.exe", "browser_download_url": "https://e.x/a"},
            {"name": "kaputt"},
        ],
    }
    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(json.dumps(payload).encode()),
    )
    release = updater.fetch_latest(timeout=1)
    assert release is not None
    assert release.version == "1.0.1"
    assert release.notes == "Fehler behoben"
    assert release.assets == {"PDFblack-1.0.1-Setup.exe": "https://e.x/a"}


def test_abfrage_ohne_netz_und_ohne_tag(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.URLError("kein Netz")

    monkeypatch.setattr(updater.urllib.request, "urlopen", boom)
    assert updater.fetch_latest(timeout=1) is None

    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b'{"assets": []}'),
    )
    assert updater.fetch_latest(timeout=1) is None

    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"kein json"),
    )
    assert updater.fetch_latest(timeout=1) is None


_FEED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
    "<id>tag:github.com,2008:Repository/1/v1.2.0</id>"
    '<link rel="alternate" type="text/html" '
    'href="https://github.com/soendi/PDFblack/releases/tag/v1.2.0"/>'
    "<title>PDFblack 1.2.0</title>"
    '<content type="html">Notizen</content></entry></feed>'
)


def test_feed_als_ausweichweg(monkeypatch):
    """Ist das API-Kontingent erschoepft, wird der Release-Feed gelesen."""

    def fake(request, timeout=None):
        url = getattr(request, "full_url", str(request))
        if "api.github.com" in url:
            raise urllib.error.HTTPError(url, 403, "rate limit", None, None)
        return _FakeResponse(_FEED.encode())

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake)
    release = updater.fetch_latest(timeout=1)
    assert release is not None
    assert release.version == "1.2.0"
    assert release.tag == "v1.2.0"
    assert release.page.endswith("/releases/tag/v1.2.0")
    assert updater.asset_for(release, "win32")[0] == "PDFblack-1.2.0-Setup.exe"
    assert (
        updater.asset_for(release, "linux")[0]
        == "PDFblack-1.2.0-linux-x86_64.tar.gz"
    )


def test_download_schreibt_datei(monkeypatch, tmp_path):
    inhalt = b"x" * 5000
    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(inhalt),
    )
    gesehen: list[tuple[int, int]] = []
    ziel = updater.download(
        "https://e.x/a", tmp_path / "paket.tar.gz", progress=lambda d, t: gesehen.append((d, t))
    )
    assert ziel.read_bytes() == inhalt
    assert gesehen[-1] == (5000, 5000)


def test_archiv_ersetzt_programmverzeichnis(tmp_path):
    """Das Hilfsskript tauscht den Inhalt aus und startet die App neu."""
    import os
    import subprocess
    import tarfile

    if not updater.sys.platform.startswith("linux"):
        pytest.skip("plattformspezifisch")

    app = tmp_path / "PDFblack"
    app.mkdir()
    starter = app / "PDFblack"
    starter.write_text('#!/bin/sh\ntouch "$(dirname "$0")/gestartet"\n', encoding="utf-8")
    starter.chmod(0o755)
    (app / "alt.txt").write_text("alt", encoding="utf-8")

    quelle = tmp_path / "quelle" / "PDFblack"
    quelle.mkdir(parents=True)
    (quelle / "neu.txt").write_text("neu", encoding="utf-8")
    download = tmp_path / "download"
    download.mkdir()
    archiv = download / "PDFblack-1.0.1-linux-x86_64.tar.gz"
    with tarfile.open(archiv, "w:gz") as tar:
        tar.add(quelle, arcname="PDFblack")

    # PID eines sicher beendeten Prozesses: das Skript wartet nicht.
    skript = updater._swap_script(archiv, app, pid=999_999)
    subprocess.run(["/bin/sh", str(skript)], timeout=120, check=True)

    assert (app / "neu.txt").read_text(encoding="utf-8") == "neu"
    assert (app / "alt.txt").exists()
    assert (app / "gestartet").exists()
    assert not archiv.exists()
    assert os.access(app / "PDFblack", os.X_OK)


def test_einbau_ausserhalb_einer_installation(tmp_path):
    if not updater.sys.platform.startswith("linux"):
        pytest.skip("plattformspezifisch")
    assert updater.installation_dir() is None
    assert not updater.can_install()
    paket = tmp_path / "PDFblack_1.0.1_amd64.deb"
    paket.write_bytes(b"deb")
    result = updater.install(paket)
    assert not result.ok
    assert "apt" in result.message
