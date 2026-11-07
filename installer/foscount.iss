; Inno Setup script for the Foscount Windows installer.
; Build the folder version first:  python tools/build_desktop.py --folder
; Then:  iscc /DMyAppVersion=0.1.0 installer\foscount.iss
; Output: dist\Foscount-Setup-<version>.exe

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{6F1C2E4A-8B7D-4C2B-9A51-F05C0C0A1E77}
AppName=Foscount
AppVersion={#MyAppVersion}
AppPublisher=Foscount
AppPublisherURL=https://github.com/Baboe/burkercell
DefaultDirName={autopf}\Foscount
DefaultGroupName=Foscount
UninstallDisplayIcon={app}\Foscount.exe
OutputDir=..\dist
OutputBaseFilename=Foscount-Setup-{#MyAppVersion}
SetupIconFile=..\build\foscount.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; per-user install by default, so no administrator rights are needed
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Foscount\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion

[Icons]
Name: "{group}\Foscount"; Filename: "{app}\Foscount.exe"
Name: "{group}\Example images"; Filename: "{app}\examples"
Name: "{group}\Uninstall Foscount"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Foscount"; Filename: "{app}\Foscount.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Foscount.exe"; Description: "{cm:LaunchProgram,Foscount}"; Flags: nowait postinstall skipifsilent
