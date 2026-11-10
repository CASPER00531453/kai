; Kai installer. Installs fresh, or updates an existing Kai in place.
; Settings, memory and reminders live in %APPDATA%\Kai and are never touched.
; build.ps1 passes the version: ISCC /DMyAppVersion=2.0.0 installer\Kai.iss

#define MyAppName "Kai"
#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif
#define MyAppExeName "Kai.exe"
#define MyAppId "{8F3C1A2E-6B47-4D91-9C2E-1A0B7E5D4F21}"

[Setup]
AppId={{8F3C1A2E-6B47-4D91-9C2E-1A0B7E5D4F21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Casper Technology
AppPublisherURL=https://casper-technology.vercel.app/
AppSupportURL=https://casper-technology.vercel.app/
AppCopyright=Copyright (c) 2026 Casper Technology
; New installs show the license and need "I accept"; silent updates skip the page.
LicenseFile=..\NOTICE
DefaultDirName={localappdata}\Kai
DefaultGroupName=Kai
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\build
OutputBaseFilename=Kai-Setup-{#MyAppVersion}
SetupIconFile=..\kai.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
UsePreviousAppDir=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName=Kai
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany=Casper Technology
VersionInfoDescription=Kai kurulumu - Windows için yapay zekâ asistanı
VersionInfoCopyright=Copyright (c) 2026 Casper Technology
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol koy"; GroupDescription: "Ek:"; Flags: unchecked

[InstallDelete]
; Kai is a folder since 2.0.8: start every update from a clean copy of its libraries.
Type: filesandordirs; Name: "{app}\_internal"
; Test Merkezi was removed in 2.0; take it off machines that had it.
Type: files; Name: "{app}\TestMerkezi.exe"
Type: files; Name: "{group}\Test Merkezi.lnk"

[Files]
Source: "..\dist\Kai\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Kai's MIT license (with Coucou's notice) and the bundled libraries' licenses.
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; DestName: "NOTICE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Kai"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Kai"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Kai'yi başlat"; Flags: nowait postinstall skipifsilent
; An update started from inside Kai runs silently; bring Kai back afterwards.
; Through Explorer, so Kai starts with a fresh environment: started directly it
; inherited the old Kai's PyInstaller variables and ran the old unpacked files.
Filename: "{win}\explorer.exe"; Parameters: """{app}\{#MyAppExeName}"""; Flags: nowait skipifnotsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "StopKai"

[Code]
var
  PreviousVersion: String;

function InstalledVersion(): String;
var
  Key, Value: String;
begin
  Result := '';
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1';
  if RegQueryStringValue(HKCU, Key, 'DisplayVersion', Value) then
    Result := Value
  else if RegQueryStringValue(HKLM, Key, 'DisplayVersion', Value) then
    Result := Value;
end;

function InitializeSetup(): Boolean;
begin
  PreviousVersion := InstalledVersion();
  Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // Kai already here: say so, and call the button what it does.
  if (PreviousVersion <> '') and (CurPageID = wpReady) then
  begin
    WizardForm.NextButton.Caption := 'Güncelle';
    WizardForm.ReadyLabel.Caption :=
      'Kai ' + PreviousVersion + ' yüklü, {#MyAppVersion} sürümüne güncellenecek. Ayarların ve hafızan korunur.';
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Kai.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(600);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Existing: String;
begin
  if CurStep = ssPostInstall then
  begin
    // "Start with Windows" keeps pointing at the right exe after a move.
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Kai', Existing) then
      RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Kai', '"' + ExpandConstant('{app}\Kai.exe') + '"');
  end;
end;
