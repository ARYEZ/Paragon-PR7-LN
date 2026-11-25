"""PR7-LN in the notification area, as Flow Launcher lives: the key (Alt+Space), the launcher, Settings.

`options()` are the settings with their defaults; `make_engine` builds the plugins from them, so a change in Settings
takes effect on the next query. `answers` replaces dialogs in tests."""

from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout,
                               QHeaderView, QKeySequenceEdit, QLabel, QMenu, QMessageBox, QPushButton, QRadioButton,
                               QSystemTrayIcon, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import __version__, finish, hotkeys, plugins, settings, theme, widgets
from .engine import DEFAULT_OFF, Engine, History, default_plugins
from .launcher import Launcher, data_folder

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULTS = {"key_show": "Alt+Space", "hide_on_blur": True, "keep_query": False, "engine": "g",
            "disabled": sorted(DEFAULT_OFF)}


def option(key: str):
    d = DEFAULTS[key]
    if isinstance(d, bool):
        return settings.get_bool(key, d)
    if isinstance(d, list):
        v = settings.get(key, "")
        if not v:
            return list(d)
        try:
            got = json.loads(v)
            return got if isinstance(got, list) else list(d)
        except ValueError:
            return list(d)
    return settings.get(key, d) or d


def start_with_windows(on: bool | None = None) -> bool:
    """Read (on=None) or set the HKCU Run entry that starts PR7-LN (quietly) when you sign in."""
    if sys.platform != "win32":
        return False
    import winreg
    exe = f'"{sys.executable}" --tray' if getattr(sys, "frozen", False) else \
        f'"{sys.executable.replace("python.exe", "pythonw.exe")}" -m pr7ln --tray'
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
        if on is None:
            try:
                winreg.QueryValueEx(k, "Paragon PR7-LN")
                return True
            except OSError:
                return False
        if on:
            winreg.SetValueEx(k, "Paragon PR7-LN", 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(k, "Paragon PR7-LN")
            except OSError:
                pass
        return on


def make_engine(history: History | None = None, plugin_list=None) -> Engine:
    hist = history or History(os.path.join(data_folder(), "history.json"))
    return Engine(plugin_list if plugin_list is not None else default_plugins(option("engine")), hist,
                  set(option("disabled")))


class TrayApp(QObject):
    def __init__(self, engine: Engine | None = None, show_tray: bool = True, find=None):
        super().__init__()
        self.answers: dict = {}
        self.engine = engine or make_engine()
        self.launcher = Launcher(self.engine, find=find)
        self.apply_options()
        self.hotkeys = hotkeys.Hotkeys()
        self.anchor = None
        self._build_menu()
        self.tray = None
        if show_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(QApplication.windowIcon() or QIcon(), self)
            self.tray.setToolTip("Paragon PR7-LN")
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(lambda reason: self.launcher.show_launcher()
                                        if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray.show()
        self.key_problems = self.register_keys()

    def apply_options(self):
        self.launcher.hide_on_blur = option("hide_on_blur")
        self.launcher.keep_query = option("keep_query")
        self.engine.disabled = set(option("disabled"))
        web = self.engine.plugin("web")
        if web is not None:
            web.engine = option("engine") if option("engine") in plugins.ENGINES else "g"

    def _build_menu(self):
        m = QMenu()
        self.acts = {}
        self.acts["show"] = m.addAction(self._show_text(), self.launcher.show_launcher)
        m.addAction("Settings...", self.options)
        fin = m.addMenu("Finish")
        for name in ("obsidian", "aurora"):
            a = fin.addAction(name.upper(), lambda n=name: self.set_finish(n))
            a.setCheckable(True)
            a.setChecked(theme.FINISH == name)
            self.acts[f"finish_{name}"] = a
        m.addSeparator()
        m.addAction("Check for updates...", self.check_updates)
        m.addAction("About PR7-LN", lambda: self._say("info", f"Paragon PR7-LN {__version__}\nA launcher, the way "
                                                              "Flow Launcher opens things."))
        m.addSeparator()
        m.addAction("Exit", self.quit)
        self.menu = m

    def _show_text(self) -> str:
        return f"Open the launcher\t{option('key_show')}"

    def register_keys(self) -> dict:
        problems = self.hotkeys.register({"show": (option("key_show"), self.launcher.toggle)})
        if problems and hotkeys.available() and self.tray:
            self.tray.showMessage("PR7-LN", "\n".join(dict.fromkeys(problems.values())),
                                  QSystemTrayIcon.MessageIcon.Warning, 8000)
        self.acts["show"].setText(self._show_text())
        return problems

    def set_finish(self, name: str):
        theme.set_finish(name)
        finish.set(theme.FINISH)                 # every family app follows (finish.py)
        settings.set("finish", theme.FINISH)
        QApplication.instance().setPalette(theme.palette())
        self.launcher.restyle()
        for n in ("obsidian", "aurora"):
            self.acts[f"finish_{n}"].setChecked(theme.FINISH == n)

    def options(self):
        d = SettingsDialog(self)
        self.settings_dialog = d
        ok = self.answers["options"](d) if "options" in self.answers else d.exec() == QDialog.DialogCode.Accepted
        if ok:
            d.save()
            self.apply_options()
            self.key_problems = self.register_keys()

    def check_updates(self):
        from . import update_ui
        update_ui.check(self.anchor, manual=True)

    def quit(self):
        self.hotkeys.unregister()
        QApplication.instance().quit()

    def _say(self, kind: str, text: str):
        if "say" in self.answers:
            self.answers["say"](kind, text)
            return
        QMessageBox.information(None, "Paragon PR7-LN", text)


class SettingsDialog(QDialog):
    """The mock-up's Settings: the key and switches, the plugins (on / off, their keywords), the finish, about."""

    def __init__(self, app: TrayApp):
        super().__init__()
        self.app = app
        self.setWindowTitle("PR7-LN Settings")
        self.setPalette(theme.palette())
        self.setStyleSheet(theme.stylesheet() + f"""QPushButton[kind="primary"] {{ background: {theme.qss_gradient()};
            color: #FFFFFF; border: none; font-weight: 600; padding: 7px 22px; }}
            QDialog {{ background: {theme.BACKGROUND}; }}""")
        self.resize(980, 640)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(widgets.Header("LAUNCHER"))
        tabs = QTabWidget()
        self.tabs = tabs
        # plugins
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(12, 12, 12, 12)
        row = QHBoxLayout()
        lab = QLabel("HOTKEY")
        lab.setProperty("role", "field")
        row.addWidget(lab)
        self.key = QKeySequenceEdit(QKeySequence(option("key_show")))
        self.key.setFixedWidth(200)
        row.addWidget(self.key)
        row.addSpacing(20)
        self.startup = QCheckBox("Start with Windows")
        self.startup.setChecked(start_with_windows())
        self.startup.setEnabled(sys.platform == "win32")
        self.blur = QCheckBox("Hide when it loses focus")
        self.blur.setChecked(option("hide_on_blur"))
        self.keep = QCheckBox("Remember the last query")
        self.keep.setChecked(option("keep_query"))
        for c in (self.startup, self.blur, self.keep):
            row.addWidget(c)
        row.addStretch(1)
        pl.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ON", "PLUGIN", "KEYWORD", "WHAT IT DOES"])
        self.tree.setRootIsDecorated(False)
        off = set(option("disabled"))
        for p in app.engine.plugins:
            keys = (["*"] if p.default else []) + list(p.keywords)
            it = QTreeWidgetItem(["", p.title, "  ·  ".join(keys), p.about])
            it.setData(0, Qt.ItemDataRole.UserRole, p.name)
            it.setCheckState(0, Qt.CheckState.Unchecked if p.name in off else Qt.CheckState.Checked)
            self.tree.addTopLevelItem(it)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 2):
            self.tree.header().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        pl.addWidget(self.tree, 1)
        erow = QHBoxLayout()
        lab = QLabel("WEB SEARCH WITHOUT A KEYWORD")
        lab.setProperty("role", "field")
        erow.addWidget(lab)
        self.engine_box = QComboBox()
        for k, (name, _url) in plugins.ENGINES.items():
            self.engine_box.addItem(f"{name}  ({k})", k)
        self.engine_box.setCurrentIndex(max(0, self.engine_box.findData(option("engine"))))
        erow.addWidget(self.engine_box)
        erow.addStretch(1)
        pl.addLayout(erow)
        note = QLabel("“*” answers without a keyword. Programs you open often come first.")
        note.setProperty("role", "dim")
        pl.addWidget(note)
        if app.key_problems and hotkeys.available():
            warn = QLabel("\n".join(dict.fromkeys(app.key_problems.values())))
            warn.setWordWrap(True)
            pl.addWidget(warn)
        tabs.addTab(page, "PLUGINS")
        # appearance
        look = QWidget()
        ll = QVBoxLayout(look)
        ll.setContentsMargins(16, 16, 16, 16)
        lab = QLabel("FINISH")
        lab.setProperty("role", "field")
        ll.addWidget(lab)
        self.finish_group = QButtonGroup(self)
        for name in ("obsidian", "aurora"):
            r = QRadioButton(name.upper())
            r.setChecked(theme.FINISH == name)
            r.setProperty("finish", name)
            self.finish_group.addButton(r)
            ll.addWidget(r)
        dim = QLabel("One finish for the whole Paragon family: the other apps follow.")
        dim.setProperty("role", "dim")
        ll.addWidget(dim)
        ll.addStretch(1)
        tabs.addTab(look, "APPEARANCE")
        # about
        about = QWidget()
        al = QVBoxLayout(about)
        al.setContentsMargins(16, 16, 16, 16)
        al.addWidget(QLabel(f"Paragon PR7-LN {__version__}"))
        t = QLabel("A launcher, the way Flow Launcher opens things: programs, files through PR7-IS's index, sums, "
                   "web searches, commands and the Paragon family, from one key.")
        t.setWordWrap(True)
        t.setProperty("role", "dim")
        al.addWidget(t)
        from . import update_ui
        self.updates = QCheckBox("Check for updates automatically")
        self.updates.setChecked(update_ui.auto_enabled())
        al.addWidget(self.updates)
        al.addStretch(1)
        tabs.addTab(about, "ABOUT")
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(16, 10, 16, 10)
        wl.addWidget(tabs)
        v.addWidget(wrap, 1)
        foot = QFrame()
        foot.setStyleSheet(f"QFrame {{ background: {theme.TAB_FRAME}; border-top: 1px solid {theme.PANEL_EDGE}; }}")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 8, 16, 8)
        self.status = QLabel(self.status_text())
        self.status.setProperty("role", "dim")
        fl.addWidget(self.status, 1)
        ok = QPushButton("OK")
        ok.setProperty("kind", "primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        fl.addWidget(ok)
        fl.addWidget(cancel)
        v.addWidget(foot)

    def status_text(self) -> str:
        progs = self.app.engine.plugin("programs")
        n = len(progs.items) if progs is not None else 0
        if progs is not None and not progs.loaded:
            progs.load()
            n = len(progs.items)
        files = "files through PR7-IS" if plugins.is_search("a", 1, 0.3) is not None else \
            "files: your recent ones (PR7-IS isn't running)"
        return f"Programs: {n}  ·  {files}  ·  in the notification area"

    def save(self):
        seq = self.key.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        settings.set("key_show", seq or DEFAULTS["key_show"])
        settings.set("hide_on_blur", self.blur.isChecked())
        settings.set("keep_query", self.keep.isChecked())
        settings.set("engine", self.engine_box.currentData())
        off = [self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(self.tree.topLevelItemCount())
               if self.tree.topLevelItem(i).checkState(0) != Qt.CheckState.Checked]
        settings.set("disabled", off)
        chosen = self.finish_group.checkedButton()
        if chosen is not None and chosen.property("finish") != theme.FINISH:
            self.app.set_finish(chosen.property("finish"))
        if sys.platform == "win32" and self.startup.isChecked() != start_with_windows():
            start_with_windows(self.startup.isChecked())
        from . import update_ui
        update_ui.set_auto(self.updates.isChecked())
