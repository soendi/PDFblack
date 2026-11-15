"""Selbstaktualisierung ueber die GitHub-Releases von PDFblack.

Die Pruefung und der Download laufen ohne Zusatzbibliothek ueber urllib. Der
Einbau ist auf Windows beschraenkt: das Setup laeuft still, schliesst die
laufende Anwendung und startet sie ueber seinen [Run]-Eintrag wieder - dafuer
darf beim Setup kein skipifsilent stehen.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

INSTALL_FLAGS = ("/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS")
# So lange muss das gestartete Setup laufen, damit es als "laeuft" gilt.
SETUP_GRACE = 2.0

DEFAULT_REPO = "soendi/PDFblack"
USER_AGENT = "PDFblack-Updater"
_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")
_CHUNK = 128 * 1024


@dataclass(frozen=True)
class Release:
    """Eine veroeffentlichte Version samt Downloadadressen."""

    version: str
    tag: str
    notes: str = ""
    page: str = ""
    assets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InstallResult:
    ok: bool
    message: str


def repository() -> str:
    """Repository fuer die Updates (per Umgebungsvariable austauschbar)."""
    return os.environ.get("PDFBLACK_UPDATE_REPO", DEFAULT_REPO)


def api_url() -> str:
    return f"https://api.github.com/repos/{repository()}/releases/latest"


def feed_url() -> str:
    return f"https://github.com/{repository()}/releases.atom"


def _conventional_assets(tag: str, version: str) -> dict[str, str]:
    """Dateiname, den der Release-Workflow erzeugt."""
    base = f"https://github.com/{repository()}/releases/download/{tag}"
    name = f"PDFblack-{version}-Setup.exe"
    return {name: f"{base}/{name}"}


# ---------------------------------------------------------------------------
# Versionsvergleich
# ---------------------------------------------------------------------------


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.10' -> (1, 2, 10); unbrauchbare Angaben ergeben ()."""
    match = _VERSION_RE.match((text or "").strip().lstrip("vV"))
    if match is None:
        return ()
    return tuple(int(part or 0) for part in match.groups())


def is_newer(current: str, candidate: str) -> bool:
    """Ist candidate eine spaetere Version als current?"""
    left, right = parse_version(current), parse_version(candidate)
    if not right:
        return False
    if not left:
        return True
    length = max(len(left), len(right), 3)
    left = left + (0,) * (length - len(left))
    right = right + (0,) * (length - len(right))
    return right > left


# ---------------------------------------------------------------------------
# Abfrage und Download
# ---------------------------------------------------------------------------


def fetch_latest(timeout: float = 8.0, url: str | None = None) -> Release | None:
    """Neueste Veroeffentlichung holen; bei Fehlern None (nie eine Ausnahme)."""
    request = urllib.request.Request(
        url or api_url(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Haeufigster Fall: HTTP 429/403 wegen des Kontingents je Adresse.
        log.info("Update-Abfrage ueber die API fehlgeschlagen: %s", exc)
        return _fetch_feed(timeout)
    if not isinstance(payload, dict):
        return None
    tag = str(payload.get("tag_name") or "")
    version = tag.lstrip("vV")
    if not parse_version(version):
        return None
    assets: dict[str, str] = {}
    for asset in payload.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        link = str(asset.get("browser_download_url") or "")
        if name and link:
            assets[name] = link
    return Release(
        version=version,
        tag=tag or f"v{version}",
        notes=str(payload.get("body") or ""),
        page=str(payload.get("html_url") or ""),
        assets=assets,
    )


def _fetch_feed(timeout: float = 8.0) -> Release | None:
    """Ausweichweg: Release-Feed ohne API-Kontingent (Dateiname nach Schema)."""
    request = urllib.request.Request(feed_url(), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        root = ET.fromstring(raw)  # noqa: S314 - eigene, feste Adresse
    except (urllib.error.URLError, OSError, ET.ParseError) as exc:
        log.info("Update-Abfrage ueber den Feed fehlgeschlagen: %s", exc)
        return None
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        return None
    identifier = entry.findtext("atom:id", default="", namespaces=namespace)
    tag = identifier.rsplit("/", 1)[-1].strip()
    version = tag.lstrip("vV")
    if not parse_version(version):
        return None
    page = ""
    for link in entry.findall("atom:link", namespace):
        if link.get("rel") == "alternate":
            page = link.get("href") or ""
    return Release(
        version=version,
        tag=tag,
        notes=entry.findtext("atom:content", default="", namespaces=namespace),
        page=page,
        assets=_conventional_assets(tag, version),
    )


def download(
    url: str,
    target: Path,
    timeout: float = 120.0,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Datei herunterladen und als target ablegen."""
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        with open(target, "wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if progress is not None:
                    progress(received, total)
    return target


# ---------------------------------------------------------------------------
# Auswahl der passenden Datei
# ---------------------------------------------------------------------------


def asset_for(release: Release, system: str | None = None) -> tuple[str, str] | None:
    """Windows-Setup fuer diese Version: (Dateiname, Adresse)."""
    system = (system or sys.platform).lower()
    if not system.startswith("win"):
        return None
    for name in sorted(release.assets):
        if name.lower().endswith("-setup.exe"):
            return name, release.assets[name]
    for name in sorted(release.assets):
        if name.lower().endswith(".exe"):
            return name, release.assets[name]
    return None


# ---------------------------------------------------------------------------
# Einbau
# ---------------------------------------------------------------------------


def release_page() -> str:
    """Seite, unter der die Fassungen zum Herunterladen liegen."""
    return f"https://github.com/{repository()}/releases/latest"


def can_install() -> bool:
    """Kann diese Installation sich selbst ersetzen?"""
    return sys.platform.startswith("win") and bool(getattr(sys, "frozen", False))


def install(archive: Path) -> InstallResult:
    """Heruntergeladenes Setup-Programm still starten."""
    if not archive.exists():
        return InstallResult(False, "Die heruntergeladene Datei fehlt.")
    if not sys.platform.startswith("win"):
        return InstallResult(
            False,
            "Automatische Updates gibt es nur fuer die Windows-Fassung. "
            "Bitte die neue Version von der Release-Seite installieren.",
        )
    if not archive.name.lower().endswith(".exe"):
        return InstallResult(False, "Fuer das Update wird das Setup-Programm benoetigt.")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NO_WINDOW", 0
    )
    try:
        process = subprocess.Popen(  # noqa: S603 - feste Argumentliste, eigene Datei
            [str(archive), *INSTALL_FLAGS],
            close_fds=True,
            creationflags=flags,
        )
    except OSError as exc:
        return InstallResult(False, f"Der Installer liess sich nicht starten: {exc}")
    # Bricht das Setup sofort ab, bleibt die Anwendung offen und verweist auf
    # die Release-Seite - sonst waere nach dem Schliessen gar nichts passiert.
    deadline = time.monotonic() + SETUP_GRACE
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            if code != 0:
                return InstallResult(
                    False,
                    f"Das Setup wurde ohne Installation beendet (Code {code}). "
                    f"Bitte die neue Fassung von {release_page()} installieren.",
                )
            break
        time.sleep(0.1)
    return InstallResult(
        True,
        "Das Update wird im Hintergrund eingespielt, PDFblack oeffnet sich "
        "danach von selbst wieder.",
    )
