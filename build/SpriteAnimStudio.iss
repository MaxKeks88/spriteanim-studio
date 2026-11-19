; Установщик SpriteAnim Studio (Inno Setup 6).
; Ставится в профиль пользователя (%LOCALAPPDATA%\Programs\SpriteAnimStudio),
; поэтому не требует прав администратора и может писать .cache/output/voice рядом.

#define AppName "SpriteAnim Studio"
#define AppVersion "0.1"
#define AppExe "SpriteAnimStudio.exe"

[Setup]
AppId={{7E2C5A54-4B7E-4C2F-9E51-9A7D3B1C6F20}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\SpriteAnimStudio
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SpriteAnimStudio-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\SpriteAnimStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Кэш браузера и служебные логи — их можно смело удалять.
; .cache с настройками, output и voice (скачанные модели) не трогаем.
Type: filesandordirs; Name: "{app}\.profile"
Type: files; Name: "{app}\.cache\studio.log"
