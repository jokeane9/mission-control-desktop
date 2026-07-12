; Inno Setup script for Mission Control (built by packaging/build_windows.ps1)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7C1FBE0D-3E1A-4A6B-9B1B-6C2C6A2C9D01}
AppName=Mission Control
AppVersion={#AppVersion}
AppPublisher=John O'Keane
AppPublisherURL=https://github.com/jokeane9
DefaultDirName={autopf}\Mission Control
DefaultGroupName=Mission Control
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=MissionControl-{#AppVersion}-setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Mission Control.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\Mission Control\*"; DestDir: "{app}"; Flags: recursesubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: WebView2Missing

[Icons]
Name: "{autoprograms}\Mission Control"; Filename: "{app}\Mission Control.exe"
Name: "{autodesktop}\Mission Control"; Filename: "{app}\Mission Control.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; Flags: unchecked

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft Edge WebView2 runtime…"; Check: WebView2Missing
Filename: "{app}\Mission Control.exe"; Description: "Launch Mission Control"; \
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
