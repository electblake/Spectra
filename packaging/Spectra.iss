#define SpectraName "Spectra"
#define SpectraPublisher "electblake"
#define SpectraAppId "electblake.Spectra"

#ifndef SpectraVersion
  #error SpectraVersion must be supplied by the build task
#endif
#ifndef SpectraPlatform
  #error SpectraPlatform must be supplied by the build task
#endif
#ifndef SpectraArchitecture
  #error SpectraArchitecture must be supplied by the build task
#endif

#define SpectraArtifactName SpectraName + "-" + SpectraVersion + "-" + SpectraPlatform + "-" + SpectraArchitecture

[Setup]
AppId={#SpectraAppId}
AppName={#SpectraName}
AppVersion={#SpectraVersion}
AppVerName={#SpectraName} {#SpectraVersion}
AppPublisher={#SpectraPublisher}
DefaultDirName={localappdata}\Programs\{#SpectraName}
DefaultGroupName={#SpectraName}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputDir=..\dist
OutputBaseFilename={#SpectraArtifactName}-Setup
SetupIconFile=..\Spectra.ico
UninstallDisplayIcon={app}\app\Spectra.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
SetupLogging=yes

[Files]
Source: "..\build\bootstrap\uv\uv.exe"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "..\build\bootstrap\LICENSE-*"; DestDir: "{app}\tools\licenses"; Flags: ignoreversion
Source: "..\app\*.py"; DestDir: "{app}\app\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\Spectra.ico"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "install-runtime.cmd"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\Spectra-*-windows-amd64.exe"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#SpectraName}"; Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}"; IconFilename: "{app}\app\Spectra.ico"
Name: "{autodesktop}\{#SpectraName}"; Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}"; IconFilename: "{app}\app\Spectra.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Spectra"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\app\Spectra.ico"""; Flags: dontcreatekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Spectra\command"; ValueType: string; ValueData: """{app}\runtime\venv\Scripts\pythonw.exe"" -I -m app ""%1"""; Flags: dontcreatekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Spectra"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\app\Spectra.ico"""; Flags: dontcreatekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Spectra\command"; ValueType: string; ValueData: """{app}\runtime\venv\Scripts\pythonw.exe"" -I -m app ""%V"""; Flags: dontcreatekey
Root: HKCU; Subkey: "Software\Classes\Drive\shell\Spectra"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\app\Spectra.ico"""; Flags: dontcreatekey
Root: HKCU; Subkey: "Software\Classes\Drive\shell\Spectra\command"; ValueType: string; ValueData: """{app}\runtime\venv\Scripts\pythonw.exe"" -I -m app ""%1"""; Flags: dontcreatekey

[Run]
Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#SpectraName}}"; Flags: nowait postinstall skipifsilent; Check: DependenciesInstalled

[UninstallDelete]
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\app\spectra.egg-info"
Type: filesandordirs; Name: "{app}\app\build"
Type: files; Name: "{app}\app\uv.lock"

[Code]
var
  DependencyExitCode: Integer;
  DependencyLog: TNewMemo;

procedure InitializeWizard;
begin
  DependencyLog := TNewMemo.Create(WizardForm);
  DependencyLog.Parent := WizardForm.InstallingPage;
  DependencyLog.SetBounds(0, ScaleY(100), WizardForm.InstallingPage.Width,
    WizardForm.InstallingPage.Height - ScaleY(100));
  DependencyLog.ReadOnly := True;
  DependencyLog.ScrollBars := ssVertical;
end;

procedure DependencyOutput(const S: String; const Error, FirstLine: Boolean);
begin
  Log(S);
  DependencyLog.Lines.Add(S);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    WizardForm.StatusLabel.Caption := 'Downloading and installing Python and Spectra dependencies...';
    ExecAndLogOutput(ExpandConstant('{cmd}'),
      '/D /C ""' + ExpandConstant('{app}\install-runtime.cmd') + '""',
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, DependencyExitCode, @DependencyOutput);
    Log('Dependency setup exit code: ' + IntToStr(DependencyExitCode));
  end;
end;

function DependenciesInstalled: Boolean;
begin
  Result := DependencyExitCode = 0;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := DependencyExitCode;
end;
