# Changelog

## 0.2.0

PR7-LN runs on Linux (PR7-OS):
- **Programs come from the menu entries** Plasma's own launcher lists (.desktop files; your own override the system's;
  hidden, other desktops' and uninstalled ones left out), started from their Exec line; terminal programs open in a
  terminal.
- **Every action in Linux's terms**: files and links with their default app, folders in PR7-E (else the default file
  manager), `>` commands in a terminal that stays open (Ctrl+Enter through sudo), and Lock / Sleep / Restart / Shut down /
  Sign out / Empty Trash / Settings with Linux's own commands (each still asks first).
- Files come from PR7-IS's index (PR7-IS 0.4.0 runs on Linux), else your recent files (recently-used.xbel).
- **Alt+Space is a Plasma shortcut** on PR7-OS (System Settings > Keyboard > Shortcuts); start at sign-in is an autostart
  entry. The Paragon family items find the apps PR7-OS has.
Nothing changes on Windows.

## 0.1.1

- The family list (`family.py`) knows the three newest Paragon apps: PR7-HW (hardware information), PR7-BK
  (backups) and PR7-TM (terminal), so links between the apps and the PR7-U offer find them.

## 0.1.0

- First release: a launcher, the way Flow Launcher opens things, from Alt+Space.
- Programs from both Start menus, ranked by match and by how often you pick them.
- Files through PR7-IS's index service (else your recent files), a calculator, web searches, shell commands, the
  Paragon family, system commands (asking first), PR7-CB's clipboard history (off at first).
- Ctrl+Enter for a file's folder, Shift+Enter for more actions (family apps by file type), Alt+1..9.
- Settings, start with Windows, OBSIDIAN and AURORA finishes, Check for Updates.
