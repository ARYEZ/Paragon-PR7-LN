# Paragon PR7-LN: notes for Claude

**Paragon PR7-LN** is the owner's personal launcher: Python (**PySide6**) that **works the way Flow Launcher works**, in
the Paragon family look (PR7-Z ... PR7-DB, PR7-UN `ARYEZ/Paragon-PR7-UN`). Windows 10/11 x64 is the target; it runs on
Linux for tests. The owner writes Python; explain the why.

## How it's built

- `pr7ln/match.py` (no Qt): `score(query, name)`: exact 100, prefix ~90, word start 80, initials 70, inside 60, all
  words 55, letters in order < 40, else None. `pr7ln/calc.py` (no Qt): sums through Python's syntax tree (never eval;
  powers capped), `looks_like_math` answers without `=`.
- `pr7ln/plugins.py` (no Qt): `Result(title, subtitle, icon, score, plugin, key, action, path)`; an action is a plain
  dict. Plugins: Programs (both Start menus' .lnk via `lnk.py`, uninstallers out), Files (**PR7-IS's service**:
  service.json's port + token, a JSON line `{"op": "search", ...}`; PR7IS_ADDRESS in tests; else Recent's .lnk),
  Calculator, Web (`ENGINES`), Shell (`>`), Family (`pr7`, `family.find`), System (confirm on the undoable ones),
  Clipboard (PR7-CB's clips.db read only, `mode=ro`; PR7CB_DATA in tests; off by default). `file_actions(path, find)`:
  Shift+Enter's list, family apps by extension (`FAMILY`) only when installed.
- `pr7ln/engine.py` (no Qt): `Engine.split` (a keyword first; `=` / `>` need no space), plugins with `default` answer
  without one, `History` (pick counts in <data>/history.json, boost 12*log2(1+n)), LIMIT rows, the web search last.
  A plugin that raises is skipped. <data> = %APPDATA%\Paragon\PR7-LN, **PR7LN_DATA** in tests.
- `pr7ln/actions.py` (no Qt): `plan(action, admin, find)` -> what will run (start / ShellExecute verb / Windows call /
  copy); `run(plan)` runs it. Tests only ever check plans.
- `pr7ln/launcher.py`: the frameless painted launcher (QLineEdit + painted rows), Flow Launcher's keys, hides on
  deactivation (`keep_open` in tests), `sync` skips the debounce, `run` replaced in tests; `_ask` / `answers` / `_say`.
- `pr7ln/tray.py`: `TrayApp` (tray menu, Alt+Space via `hotkeys.py` (PR7-CB's), `options()` / `DEFAULTS`,
  `make_engine`, `start_with_windows` = HKCU Run "Paragon PR7-LN" --tray), `SettingsDialog` (the mock-up's).
- `pr7ln/app.py`: one per user (QLocalSocket hand-off, PR7-R's Windows fix); command-line modes never let an error
  escape; `--selftest OUT.json` (a made-up Start menu through the real launcher, plans not run; the real Start menu
  counted; CI runs it on the installed exe), `--startup on|off`, `--unregister`.
- Installer `installer/pr7ln.iss` (per user, AppId {CF87A58B-036E-4398-BC81-BCECF5A010A7} permanent; tasks startup
  (ticked), desktopicon); CI installs it, `tools/verify_install.py installed|uninstalled`. Spec: file details, no UPX,
  PyInstaller's bootloader built in CI, Defender scan.
- Updates: `pr7ln/updates.py` / `update_ui.py` (the family's files, keep them in step); `family.py`: the family's AppIds
  (PR7-LN included). `pr7ln/finish.py`: the family's finish, the same file in every app.

## The look (family rules)

- Theme is PR7-UN's (OBSIDIAN + AURORA). Colours: the family's only (answers orange, the band the family gradient);
  Inter; labels UPPER CASE; names and paths keep their case.
- The PR7-LN mark: PR7 `Logo.cpp` geometry plus L and N (`widgets.L_OUTER` / `N_OUTER`); icon "7LN" by
  `tools/make_icon.py`, wizard art by `tools/make_installer_art.py`. Mock-up: `tools/mockup.py`. Check visuals with
  `QT_SCALE_FACTOR=2 python tools/screenshots.py OUT` (the made-up PC of `tools/sample_pc.py`).

## Rules

- Behaviour questions: do what Flow Launcher does (keys, ranking, action keywords, the context menu).
- Tests: `python -m pytest` (offscreen) on the made-up PC; nothing is ever started (plans are checked). Never the real
  settings, data folder, PR7-IS or PR7-CB (conftest), or, outside CI, the registry or global keys.
- Releases: bump `__version__` in `pr7ln/__init__.py` and add a `## x.y.z` section to CHANGELOG.md, then push: CI
  publishes that version by itself once every check has passed.
