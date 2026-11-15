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


def test_einbau_wartet_und_startet_neu(tmp_path):
    archive = tmp_path / "PDFblack-1.0.5-Setup.exe"
    exe = "C:\\Program Files\\PDFblack\\PDFblack.exe"
    command = updater.install_command(archive, [exe])

    # Setup still, ohne Inno-eigenen Neustart ...
    assert "/SILENT" in command and "/CLOSEAPPLICATIONS" in command
    assert "/RESTARTAPPLICATIONS" not in command
    # ... auf dessen Ende warten und danach PDFblack wieder starten.
    assert "/wait" in command
    assert f'"{archive}"' in command
    assert command.index(f'"{archive}"') < command.index("&&") < command.index(f'"{exe}"')
    assert command.rstrip().endswith(f'"{exe}"')


def test_neustart_nutzt_das_eigene_programm(monkeypatch):
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater.sys, "executable", "C:\\Apps\\PDFblack.exe")
    assert updater.relaunch_target() == ["C:\\Apps\\PDFblack.exe"]

    monkeypatch.setattr(updater.sys, "frozen", False, raising=False)
    monkeypatch.setattr(updater.sys, "executable", "C:\\Python\\python.exe")
    assert updater.relaunch_target()[-2:] == ["-m", "pdfblack"]
