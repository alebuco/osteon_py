; Inno Setup — gera o instalador .exe do Osteon Viewer (Windows).
; Pré-requisito: PyInstaller já gerou dist\Osteon\ (onedir).
; Compile com: iscc packaging\osteon.iss   (ou via Inno Setup IDE)

#define AppName "Osteon Viewer"
#define AppVersion "0.0.5"
#define AppPublisher "Osteon"
#define AppExe "Osteon.exe"

[Setup]
AppId={{B5B8A3C2-1E4D-4F9A-9C21-0A5E6F7A8B90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Osteon Viewer
DefaultGroupName=Osteon Viewer
OutputDir=..\dist\installer
OutputBaseFilename=OsteonViewer-Setup-{#AppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\Osteon\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Osteon Viewer"; Filename: "{app}\{#AppExe}"
Name: "{commondesktop}\Osteon Viewer"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o Osteon Viewer"; Flags: nowait postinstall skipifsilent
