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
    # Die Software laeuft nur unter Windows.
    assert updater.asset_for(release, "linux") is None
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
    assert updater.asset_for(release, "linux") is None


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


def test_einbau_ausserhalb_von_windows(tmp_path):
    if updater.sys.platform.startswith("win"):
        pytest.skip("plattformspezifisch")
    assert not updater.can_install()
    paket = tmp_path / "PDFblack-1.0.1-Setup.exe"
    paket.write_bytes(b"exe")
    result = updater.install(paket)
    assert not result.ok
    assert "Windows" in result.message


def test_einbau_startet_das_setup_still(monkeypatch, tmp_path):
    archive = tmp_path / "PDFblack-1.0.6-Setup.exe"
    archive.write_bytes(b"MZ")
    aufrufe: list[list[str]] = []

    class _Popen:
        def __init__(self, args, **kwargs) -> None:
            aufrufe.append(list(args))

        def poll(self):
            return None

    monkeypatch.setattr(updater.subprocess, "Popen", _Popen)
    monkeypatch.setattr(updater.sys, "platform", "win32")

    result = updater.install(archive)

    assert result.ok
    assert "selbst wieder" in result.message
    assert aufrufe == [[str(archive), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"]]


def test_installer_startet_das_programm_nach_dem_einbau():
    skript = Path(__file__).resolve().parents[1] / "packaging" / "installer.iss"
    zeilen = [
        zeile
        for zeile in skript.read_text(encoding="utf-8").splitlines()
        if zeile.startswith("Filename: ")
    ]
    assert len(zeilen) == 1, zeilen
    eintrag = zeilen[0]
    text = skript.read_text(encoding="utf-8")
    assert '#define AppExe "PDFblack.exe"' in text
    assert "{app}\\{#AppExe}" in eintrag
    # nowait: PDFblack laeuft weiter, waehrend das Setup endet.
    assert "nowait" in eintrag
    # skipifsilent wuerde beim stillen Update genau den Neustart verhindern.
    assert "skipifsilent" not in eintrag


def test_abgebrochenes_setup_bleibt_offen(monkeypatch, tmp_path):
    archive = tmp_path / "PDFblack-1.0.7-Setup.exe"
    archive.write_bytes(b"MZ")

    class _Popen:
        def __init__(self, args, **kwargs) -> None:
            pass

        def poll(self):
            return 5

    monkeypatch.setattr(updater.subprocess, "Popen", _Popen)
    monkeypatch.setattr(updater.sys, "platform", "win32")

    result = updater.install(archive)

    assert result.ok is False
    assert "Code 5" in result.message
    assert updater.release_page() in result.message
