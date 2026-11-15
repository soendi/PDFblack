# Baut PDFblack fuer Windows: Programmordner + Setup-EXE (Inno Setup).
# Aufruf in PowerShell:  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Push-Location $root
try {
    Write-Host "== Abhaengigkeiten installieren =="
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt pyinstaller

    Write-Host "== Deutsches Sprachmodell (spaCy) =="
    & $python -m spacy download de_core_news_md

    $version = & $python -c "import sys; sys.path.insert(0, 'src'); from pdfblack import APP_VERSION; print(APP_VERSION)"
    Write-Host "== PDFblack $version bauen =="

    Write-Host "== Symbol erzeugen =="
    & $python packaging\make_icon.py

    & $python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\pdfblack.spec

    Write-Host "== Selbsttest der gebauten Anwendung =="
    # GUI-Anwendung: nicht einfach aufrufen, sondern auf das Prozessende warten.
    $tested = Start-Process -FilePath "dist\PDFblack\PDFblack.exe" `
        -ArgumentList "--self-test" -Wait -PassThru -NoNewWindow
    if ($tested.ExitCode -ne 0) {
        throw "Selbsttest fehlgeschlagen (Exit-Code $($tested.ExitCode))"
    }

    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (Test-Path $iscc) {
        Write-Host "== Installer erstellen =="
        & $iscc "/DAppVersion=$version" "packaging\installer.iss"
        Write-Host "Fertig: dist\PDFblack-$version-Setup.exe"
    }
    else {
        Write-Warning "Inno Setup 6 nicht gefunden. Programmordner liegt in dist\PDFblack."
        Write-Warning "Installer: ISCC.exe installieren (https://jrsoftware.org/isdl.php) und Skript erneut ausfuehren."
    }
}
finally {
    Pop-Location
}
