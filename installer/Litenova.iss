#define MyAppName "Litenova"
#define MyAppVersion "3.0.3"
#define MyAppPublisher "Litenova Project"
#define MyAppExeName "Litenova.exe"

[Setup]
AppId={{D56B54DC-193D-4D5D-A6AB-94FA60E43A3E}

AppName={#MyAppName}

AppVersion={#MyAppVersion}

AppVerName={#MyAppName} {#MyAppVersion}

AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\Litenova

DefaultGroupName=Litenova

DisableProgramGroupPage=yes

DisableWelcomePage=no

PrivilegesRequired=lowest

WizardStyle=modern

SetupIconFile=..\resources\icons\litenova.ico

UninstallDisplayIcon={app}\Litenova.exe

OutputDir=..\installer_output

OutputBaseFilename=Litenova-Setup-{#MyAppVersion}

Compression=lzma2

SolidCompression=yes

ArchitecturesAllowed=x64compatible

CloseApplications=yes
ChangesAssociations=yes

RestartApplications=no

UsePreviousAppDir=yes

Uninstallable=yes

VersionInfoVersion={#MyAppVersion}

VersionInfoCompany={#MyAppPublisher}

VersionInfoDescription=Litenova Installer

VersionInfoProductName={#MyAppName}

VersionInfoProductVersion={#MyAppVersion}


[Languages]

Name: "english"; MessagesFile: "compiler:Default.isl"


[Tasks]

Name: "desktopicon"; \
    Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; \
    Flags: unchecked


[Files]

Source: "..\release\Litenova.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion


[Registry]
Root: HKCU; Subkey: "Software\Classes\.epub\OpenWithProgids"; ValueType: string; ValueName: "Litenova.EPUB"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.cbz\OpenWithProgids"; ValueType: string; ValueName: "Litenova.CBZ"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Litenova.EPUB"; ValueType: string; ValueData: "Litenova EPUB eBook"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Litenova.EPUB\DefaultIcon"; ValueType: string; ValueData: """{app}\Litenova.exe"",0"
Root: HKCU; Subkey: "Software\Classes\Litenova.EPUB\shell\open\command"; ValueType: string; ValueData: """{app}\Litenova.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Litenova.CBZ"; ValueType: string; ValueData: "Litenova CBZ Comic Archive"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Litenova.CBZ\DefaultIcon"; ValueType: string; ValueData: """{app}\Litenova.exe"",0"
Root: HKCU; Subkey: "Software\Classes\Litenova.CBZ\shell\open\command"; ValueType: string; ValueData: """{app}\Litenova.exe"" ""%1"""


[UninstallDelete]
Type: files; Name: "{app}\Litenova.exe"
Type: dirifempty; Name: "{app}"


[Icons]

Name: "{autoprograms}\Litenova"; \
    Filename: "{app}\Litenova.exe"; \
    WorkingDir: "{app}"

Name: "{autodesktop}\Litenova"; \
    Filename: "{app}\Litenova.exe"; \
    WorkingDir: "{app}"; \
    Tasks: desktopicon


[Run]

Filename: "{app}\Litenova.exe"; \
    Description: "Launch Litenova"; \
    Flags: nowait postinstall skipifsilent
