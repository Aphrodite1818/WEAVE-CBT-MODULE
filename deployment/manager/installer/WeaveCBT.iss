#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef BuildChannel
  #define BuildChannel "production"
#endif
#ifndef ManagerDist
  #error ManagerDist must point to the Nuitka standalone directory
#endif
#ifndef RuntimeRootfs
  #error RuntimeRootfs must point to weave-runtime-rootfs.tar
#endif
#ifndef OutputDir
  #define OutputDir ".\output"
#endif

#define ProductionAppId "{{B30C8A22-8724-4CFD-A2E8-7F84B6449676}"
#define StagingAppId "{{B9C74F4B-552B-421E-A0D7-26BC7A395296}"

#if BuildChannel == "staging"
  #define EffectiveAppId StagingAppId
  #define ProductName "WEAVE CBT (Staging)"
  #define OutputName "WeaveCBT-Setup-Staging-x64"
#else
  #define EffectiveAppId ProductionAppId
  #define ProductName "WEAVE CBT"
  #define OutputName "WeaveCBT-Setup-Windows-x64"
#endif

[Setup]
AppId={#EffectiveAppId}
AppName={#ProductName}
AppVersion={#AppVersion}
AppPublisher=WEAVE
DefaultDirName={autopf}\WEAVE CBT
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19041
SetupIconFile=..\resources\weave.ico
UninstallDisplayIcon={app}\manager\WeaveCBT-Manager.exe
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#ProductName}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#ManagerDist}\*"; DestDir: "{app}\manager"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RuntimeRootfs}"; DestDir: "{app}\assets"; DestName: "weave-runtime-rootfs.tar"; Flags: ignoreversion
Source: "..\..\compose.yaml"; DestDir: "{app}\assets"; DestName: "compose.yaml"; Flags: ignoreversion
Source: "..\..\nginx\nginx.conf"; DestDir: "{app}\assets"; DestName: "nginx.conf"; Flags: ignoreversion

[Icons]
Name: "{group}\WEAVE CBT Manager"; Filename: "{app}\manager\WeaveCBT-Manager.exe"
Name: "{autodesktop}\WEAVE CBT Manager"; Filename: "{app}\manager\WeaveCBT-Manager.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\manager\WeaveCBT-Manager.exe"; Parameters: "--first-run"; Description: "Open WEAVE CBT Manager"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\manager\WeaveCBT-Manager.exe"; Parameters: "--uninstall-keep-data"; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
function InitializeSetup(): Boolean;
var
  State: AnsiString;
  OtherChannel: String;
begin
  Result := True;
#if BuildChannel == "staging"
  OtherChannel := 'production';
#else
  OtherChannel := 'staging';
#endif
  if LoadStringFromFile(ExpandConstant('{commonappdata}\WeaveCBT\manager-state.json'), State) then
  begin
    if Pos('"channel": "' + OtherChannel + '"', String(State)) > 0 then
    begin
      MsgBox('This computer already contains a ' + OtherChannel + ' Weave server. Use its matching installer. Production and staging require separate computers.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
