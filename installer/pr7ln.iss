; Paragon PR7-LN installer (Inno Setup 6): a launcher, the way Flow Launcher opens things.
;   iscc /DAppVersion=0.1.0 installer\pr7ln.iss      (after pyinstaller pr7ln.spec has made dist\PR7-LN)
;
; Per-user (no admin rights) into %LOCALAPPDATA%\Programs\PR7-LN, with a Start menu entry. Ticked by default, PR7-LN
; starts with Windows (an HKCU Run entry written by PR7-LN itself: --startup on|off, so installer and Options agree):
; Alt+Space only works while it runs. --unregister on uninstall takes the entry away.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId is permanent: it's how a new version finds and upgrades the installed one. Never change it.
AppId={{CF87A58B-036E-4398-BC81-BCECF5A010A7}
AppName=Paragon PR7-LN
AppVersion={#AppVersion}
AppVerName=Paragon PR7-LN {#AppVersion}
AppPublisher=Paragon
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\PR7-LN
DefaultGroupName=Paragon PR7-LN
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PR7-LN-Setup-{#AppVersion}
SetupIconFile=..\pr7ln\icons\app.ico
UninstallDisplayIcon={app}\PR7-LN.exe
UninstallDisplayName=Paragon PR7-LN
WizardStyle=modern
WizardImageFile=wizard-large-1x.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small-1x.bmp,wizard-small-2x.bmp
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start PR7-LN with Windows (Alt+Space opens the launcher)"; GroupDescription: "Windows:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PR7-LN\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Paragon PR7-LN"; Filename: "{app}\PR7-LN.exe"; Comment: "Launcher"
Name: "{autodesktop}\Paragon PR7-LN"; Filename: "{app}\PR7-LN.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PR7-LN.exe"; Parameters: "--startup on"; Flags: runhidden waituntilterminated; Tasks: startup
Filename: "{app}\PR7-LN.exe"; Parameters: "--startup off"; Flags: runhidden waituntilterminated; Tasks: not startup
Filename: "{app}\PR7-LN.exe"; Description: "{cm:LaunchProgram,Paragon PR7-LN}"; Flags: nowait postinstall skipifsilent
; Updates (Check for updates runs this installer with /SILENT /relaunch=1): start PR7-LN again when done.
Filename: "{app}\PR7-LN.exe"; Parameters: "--tray"; Flags: nowait runasoriginaluser; Check: Relaunch

[UninstallRun]
Filename: "{app}\PR7-LN.exe"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[Code]
// True only when the updater asked for it (/relaunch=1): normal and CI installs behave as before.
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
