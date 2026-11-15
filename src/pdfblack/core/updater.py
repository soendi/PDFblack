"""Selbstaktualisierung ueber die GitHub-Releases von PDFblack.

Die Pruefung und der Download laufen ohne Zusatzbibliothek ueber urllib. Der
Einbau ist plattformabhaengig:

* Windows: das Setup-Programm wird still gestartet (Inno Setup schliesst die
  laufende Anwendung und startet sie nach dem Update neu).
* Linux: ein Archiv (.tar.gz) ersetzt das Programmverzeichnis, sobald PDFblack
  beendet ist, und startet die Anwendung neu. Liegt die Installation unter
  /usr (Debian-Paket) und ist damit nicht beschreibbar, wird nichts veraendert;
  dann bleibt der Weg ueber die Paketverwaltung.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

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
    """Dateinamen, die der Release-Workflow erzeugt."""
    base = f"https://github.com/{repository()}/releases/download/{tag}"
    names = (
        f"PDFblack-{version}-Setup.exe",
        f"PDFblack_{version}_amd64.deb",
        f"PDFblack-{version}-linux-x86_64.tar.gz",
    )
    return {name: f"{base}/{name}" for name in names}


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
    """Ausweichweg: Release-Feed ohne API-Kontingent (Dateinamen nach Schema)."""
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
    """Passende Datei fuer dieses Betriebssystem: (Dateiname, Adresse)."""
    system = (system or sys.platform).lower()
    names = sorted(release.assets)

    def pick(suffix: str) -> tuple[str, str] | None:
        for name in names:
            if name.lower().endswith(suffix):
                return name, release.assets[name]
        return None

    if system.startswith("win"):
        return pick("-setup.exe") or pick(".exe")
    if system.startswith("linux"):
        return pick(".tar.gz") or pick(".deb")
    return None


# ---------------------------------------------------------------------------
# Einbau
# ---------------------------------------------------------------------------


def installation_dir() -> Path | None:
    """Programmverzeichnis einer gepackten Installation, sonst None."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def can_install() -> bool:
    """Kann diese Installation sich selbst ersetzen?"""
    if sys.platform.startswith("win"):
        return getattr(sys, "frozen", False)
    directory = installation_dir()
    return directory is not None and os.access(directory, os.W_OK)


def _swap_script(archive: Path, app_dir: Path, pid: int | None = None) -> Path:
    """Hilfsskript: wartet auf das Ende von PDFblack, ersetzt, startet neu."""
    stage = Path(tempfile.mkdtemp(prefix="pdfblack-stage-"))
    script = stage / "update.sh"
    script.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        f"APP={shlex.quote(str(app_dir))}\n"
        f"ARCHIVE={shlex.quote(str(archive))}\n"
        f"STAGE={shlex.quote(str(stage))}/entpackt\n"
        f"while kill -0 {os.getpid() if pid is None else pid} 2>/dev/null; do sleep 0.5; done\n"
        'mkdir -p "$STAGE"\n'
        'tar -xzf "$ARCHIVE" -C "$STAGE"\n'
        'SRC="$STAGE/PDFblack"\n'
        '[ -d "$SRC" ] || SRC="$(find "$STAGE" -mindepth 1 -maxdepth 1 -type d | head -n 1)"\n'
        '[ -d "$SRC" ] || exit 1\n'
        'cp -a "$SRC/." "$APP/"\n'
        f'rm -rf {shlex.quote(str(stage))} {shlex.quote(str(archive.parent))}\n'
        'exec "$APP/PDFblack"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def install(archive: Path) -> InstallResult:
    """Heruntergeladene Datei einspielen."""
    if not archive.exists():
        return InstallResult(False, "Die heruntergeladene Datei fehlt.")
    if sys.platform.startswith("win"):
        return _install_windows(archive)
    return _install_linux(archive)


def _install_windows(archive: Path) -> InstallResult:
    if not archive.name.lower().endswith(".exe"):
        return InstallResult(False, "Fuer Windows wird das Setup-Programm benoetigt.")
    flags = ["/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
    try:
        subprocess.Popen(  # noqa: S603 - feste Argumentliste, eigene Datei
            [str(archive), *flags],
            close_fds=True,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
    except OSError as exc:
        return InstallResult(False, f"Der Installer liess sich nicht starten: {exc}")
    return InstallResult(
        True,
        "Das Update wird im Hintergrund eingespielt, PDFblack startet dabei neu.",
    )


def _install_linux(archive: Path) -> InstallResult:
    app_dir = installation_dir()
    if not archive.name.endswith(".tar.gz"):
        return InstallResult(
            False,
            "Diese Datei muss von Hand installiert werden "
            f"(z. B. sudo apt install ./{archive.name}).",
        )
    if app_dir is None or not os.access(app_dir, os.W_OK):
        return InstallResult(
            False,
            "Dieses PDFblack liegt in einem geschuetzten Verzeichnis und kann sich "
            "nicht selbst ersetzen. Bitte die neue Version ueber die "
            "Paketverwaltung oder von der Release-Seite installieren.",
        )
    try:
        script = _swap_script(archive, app_dir)
        subprocess.Popen(  # noqa: S603 - eigenes Skript mit festen Argumenten
            ["/bin/sh", str(script)],
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        return InstallResult(False, f"Das Update liess sich nicht starten: {exc}")
    return InstallResult(
        True, "PDFblack wird ersetzt und gleich neu gestartet."
    )
