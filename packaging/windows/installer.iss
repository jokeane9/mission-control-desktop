; Inno Setup script for Orrery (built by packaging/build_windows.ps1)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7C1FBE0D-3E1A-4A6B-9B1B-6C2C6A2C9D01}
AppName=Orrery
AppVersion={#AppVersion}
AppPublisher=John O'Keane
AppPublisherURL=https://github.com/jokeane9
DefaultDirName={autopf}\Orrery
DefaultGroupName=Orrery
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=Orrery-{#AppVersion}-setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Orrery.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\Orrery\*"; DestDir: "{app}"; Flags: recursesubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: WebView2Missing

[Icons]
Name: "{autoprograms}\Orrery"; Filename: "{app}\Orrery.exe"
Name: "{autodesktop}\Orrery"; Filename: "{app}\Orrery.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; Flags: unchecked

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft Edge WebView2 runtime…"; Check: WebView2Missing
Filename: "{app}\Orrery.exe"; Description: "Launch Orrery"; \
  Flags: nowait postinstall skipifsilent

[Code]
function WebView2Missing: Boolean;
var v: string;
begin
  { Evergreen runtime writes pv under this clients key (per-machine or per-user) }
  Result := not (RegQueryStringValue(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v)
    or RegQueryStringValue(HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v));
end;
