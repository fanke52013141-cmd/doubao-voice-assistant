#define MyAppName "语音输入助手"
#define MyAppVersion "2.0.1"
#define MyAppExeName "VoiceInputAssistant.exe"

[Setup]
AppId={{95D903CA-5DB1-47E2-8D24-3A45B3D71B5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=fanke52013141-cmd
AppPublisherURL=https://github.com/fanke52013141-cmd/doubao-voice-assistant
DefaultDirName={autopf}\VoiceInputAssistant
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=语音输入助手-{#MyAppVersion}-安装包
SetupIconFile=assets\app-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce
Name: "startupicon"; Description: "开机自动启动"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "dist\VoiceInputAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "使用指南.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""VoiceInputAssistant 56789"""; Flags: runhidden waituntilterminated; StatusMsg: "正在更新防火墙规则..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""VoiceInputAssistant 56789"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes profile=private,domain protocol=TCP localport=56789"; Flags: runhidden waituntilterminated; StatusMsg: "正在允许手机访问..."
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""VoiceInputAssistant 56789"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveVoiceAssistantFirewallRule"
