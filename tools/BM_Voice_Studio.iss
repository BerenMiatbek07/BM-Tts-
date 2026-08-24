#define MyAppName "BM Voice Studio Personal"
#define MyAppVersion "5.6.2"
#define MyAppPublisher "BM Official"
#define MyAppExeName "BM Voice Studio.exe"

[Setup]
AppId={{A719619D-4A76-4AFB-9500-E69EC34E0D46}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\BM Voice Studio
DefaultGroupName=BM Voice Studio
DisableProgramGroupPage=yes
OutputBaseFilename=BM_Voice_Studio_Personal_v5.6.2_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=5.6.2.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=BM Voice Studio installer
InfoBeforeFile=..\OMNIVOICE_PERSONAL_NOTICE.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "..\dist_windows\BM_Text_to_Voice.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "..\OMNIVOICE_PERSONAL_NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\BM Voice Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\BM Voice Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch BM Voice Studio"; Flags: nowait postinstall skipifsilent
