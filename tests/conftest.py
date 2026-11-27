import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PARAGON_FAMILY_FILE"] = os.path.join(tempfile.mkdtemp(prefix="family-"), "finish")  # never the real choice
os.environ["PR7LN_DATA"] = tempfile.mkdtemp(prefix="pr7ln-data-")      # never the real data folder
os.environ["PR7IS_ADDRESS"] = os.path.join(tempfile.mkdtemp(prefix="pr7is-"), "service.json")  # no real PR7-IS
os.environ["PR7CB_DATA"] = tempfile.mkdtemp(prefix="pr7cb-")            # no real PR7-CB history


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)           # never the real settings
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    app = QApplication.instance() or QApplication([])
    from pr7ln import theme
    theme.load_fonts()
    yield app
    app.clipboard().clear()


@pytest.fixture
def pc(tmp_path):
    """A made-up PC (tools/sample_pc.py): Start menus with real .lnk files, a Recent folder."""
    import sample_pc
    return sample_pc.build(tmp_path)


@pytest.fixture
def tray(qapp, pc, tmp_path):
    """The real tray app and launcher on the made-up PC; plans are kept, never run; questions answered."""
    from pr7ln import settings
    from pr7ln.engine import History
    from pr7ln.plugins import Calculator, Clipboard, Family, Files, Programs, Shell, System, Web
    from pr7ln.tray import DEFAULTS, TrayApp, make_engine
    for k, v in DEFAULTS.items():
        settings.set(k, v)                 # the defaults, whatever an earlier test changed
    found = {"PR7-E": "C:\\PR7-E\\PR7-E.exe", "PR7-W": "C:\\PR7-W\\PR7-W.exe"}
    engine = make_engine(History(str(tmp_path / "history.json")),
                         [Programs(pc["start"]), Files(pc["recent"]), Calculator(), Web(), Shell(),
                          Family(find=found.get), System(), Clipboard()])
    t = TrayApp(engine, show_tray=False, find=found.get)
    la = t.launcher
    la.sync = la.keep_open = True
    la.plans = []
    la.run = lambda p: la.plans.append(p) or True
    la.said = []
    la.answers.update({"say": lambda kind, text: la.said.append((kind, text)), "confirm": True})
    t.said = []
    t.answers["say"] = lambda kind, text: t.said.append((kind, text))
    yield t
    la.hide()
    t.hotkeys.unregister()
    qapp.clipboard().clear()


@pytest.fixture(autouse=True)
def windows_rules(monkeypatch):
    """The made-up PC is a Windows one: the shared tests check Windows' plans and words on any system
    (tests/test_linux.py switches this back on for Linux's)."""
    from pr7ln import actions
    monkeypatch.setattr(actions, "LINUX", False)
