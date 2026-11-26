; Установщик SpriteAnim Studio 0.2 (настольное окно).
; Inno Setup 6:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\SpriteAnimStudio.iss
;
; Ставится в профиль пользователя (%LOCALAPPDATA%\Programs\SpriteAnimStudio),
; поэтому не требует прав администратора и может писать .cache/output/voice рядом.

#define AppName "SpriteAnim Studio"
#define AppVersion "0.4.10"
#define AppExe "SpriteAnimStudio.exe"

[Setup]
AppId={{7E2C5A54-4B7E-4C2F-9E51-9A7D3B1C6F20}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=MaxKeks88
AppPublisherURL=https://github.com/MaxKeks88/spriteanim-studio
AppSupportURL=https://github.com/MaxKeks88/spriteanim-studio/issues
AppUpdatesURL=https://github.com/MaxKeks88/spriteanim-studio/releases
LicenseFile=EULA.txt
DefaultDirName={localappdata}\Programs\SpriteAnimStudio
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=SpriteAnimStudio-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\SpriteAnimStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".profile\*, .cache\*, output\*"
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD-PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "EULA.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall

[InstallDelete]
; Старый скилл удалён в 0.4.7 — чистим его при обновлении существующей установки.
Type: filesandordirs; Name: "{app}\_internal\skills\qwen-image-2-1-director-prompt"

[UninstallDelete]
; Профиль WebView2 и лог можно удалять. .cache с настройками, output с результатами
; и voice с моделями не трогаем.
Type: filesandordirs; Name: "{app}\.profile"
Type: files; Name: "{app}\.cache\studio.log"
Type: files; Name: "{app}\.cache\studio.log.1"
