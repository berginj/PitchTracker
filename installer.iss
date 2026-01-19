; PitchTracker Installer Script
; Requires Inno Setup 6.0 or later (https://jrsoftware.org/isinfo.php)

#define AppName "PitchTracker"
#define AppVersion "1.3.0"
#define AppPublisher "PitchTracker Development Team"
#define AppURL "https://github.com/berginj/PitchTracker"
#define AppExeName "PitchTracker.exe"

[Setup]
; App identification
AppId={{A3B2C1D4-5E6F-7A8B-9C0D-1E2F3A4B5C6D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=PitchTracker-Setup-v{#AppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Privileges
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Visual settings
DisableProgramGroupPage=yes
LicenseFile=LICENSE
; InfoBeforeFile=README_INSTALL.md
DisableWelcomePage=no

; Architecture
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Windows version
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Application files
Source: "dist\PitchTracker\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PitchTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Config and assets
Source: "configs\*.yaml"; DestDir: "{app}\configs"; Flags: ignoreversion confirmoverwrite
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Attribs: readonly

; Documentation
Source: "README_LAUNCHER.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\calibration"
Type: filesandordirs; Name: "{app}\rois"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);

  // Check Windows 10 or later
  if Version.Major < 10 then
  begin
    MsgBox('PitchTracker requires Windows 10 or later.' + #13#13 +
           'Your system: Windows ' + IntToStr(Version.Major) + '.' + IntToStr(Version.Minor),
           mbError, MB_OK);
    Result := False;
    Exit;
  end;

  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create directories for user data
    CreateDir(ExpandConstant('{app}\data'));
    CreateDir(ExpandConstant('{app}\data\sessions'));
    CreateDir(ExpandConstant('{app}\logs'));
    CreateDir(ExpandConstant('{app}\calibration'));
    CreateDir(ExpandConstant('{app}\rois'));
  end;
end;
