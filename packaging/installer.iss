; Inno-Setup-Skript fuer den Windows-Installer von PDFblack.
; Build: ISCC.exe /DAppVersion=1.2.2 packaging\installer.iss
; Erwartet das PyInstaller-Ergebnis in dist\PDFblack (siehe build_windows.ps1).

#ifndef AppVersion
  #define AppVersion "1.2.2"
#endif

#define AppName "PDFblack"
#define AppPublisher "PDFblack"
#define AppExe "PDFblack.exe"

[Setup]
AppId={{8E4C1F52-7B2A-4B4E-9E1D-3B6A5C0D9F21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PDFblack-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=pdfblack.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PDFblack\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\samples\beispiel.pdf"; DestDir: "{app}\beispiele"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Beispiel-PDF"; Filename: "{app}\beispiele\beispiel.pdf"
Name: "{group}\{#AppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Ohne skipifsilent: auch das stille Update oeffnet PDFblack nach dem Einbau wieder.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait
