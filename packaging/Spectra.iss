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
#define SpectraExeName SpectraArtifactName + ".exe"
#define SpectraDistDir "..\dist\" + SpectraArtifactName

[Setup]
AppId={#SpectraAppId}
AppName={#SpectraName}
AppVersion={#SpectraVersion}
AppVerName={#SpectraName} {#SpectraVersion}
AppPublisher={#SpectraPublisher}
DefaultDirName={localappdata}\Programs\{#SpectraName}
DefaultGroupName={#SpectraName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#SpectraArtifactName}-Setup
SetupIconFile=..\Spectra.ico
UninstallDisplayIcon={app}\{#SpectraExeName}
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "{#SpectraDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#SpectraName}"; Filename: "{app}\{#SpectraExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#SpectraName}"; Filename: "{app}\{#SpectraExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#SpectraExeName}"; Description: "{cm:LaunchProgram,{#SpectraName}}"; Flags: nowait postinstall skipifsilent
