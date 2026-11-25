"""Screenshots of the real PR7-LN on the made-up PC of tools/sample_pc.py, offscreen:
QT_SCALE_FACTOR=2 python tools/screenshots.py OUT_DIR

launcher.png         "blen": the program, a recent file, the web search (OBSIDIAN)
calc_aurora.png      a sum answered as you type (AURORA)
actions_aurora.png   Shift+Enter on a file: open, its folder in PR7-E, edit in PR7-W, copy the path (AURORA)
settings.png         Settings: the key, the plugins (OBSIDIAN)
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["PR7LN_DATA"] = tempfile.mkdtemp()
os.environ["PR7IS_ADDRESS"] = os.path.join(tempfile.mkdtemp(), "service.json")
os.environ["PARAGON_FAMILY_FILE"] = os.path.join(tempfile.mkdtemp(), "finish")

from PySide6.QtCore import QPointF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

import sample_pc  # noqa: E402
from pr7ln import theme  # noqa: E402
from pr7ln.engine import History  # noqa: E402
from pr7ln.plugins import Calculator, Clipboard, Family, Files, Programs, Shell, System, Web  # noqa: E402
from pr7ln.tray import SettingsDialog, TrayApp, make_engine  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
app.setFont(QFont("Inter", 10))
pc = sample_pc.build(tempfile.mkdtemp())
found = {"PR7-E": "PR7-E.exe", "PR7-W": "PR7-W.exe", "PR7-Z": "PR7-Z.exe", "PR7-IS": "PR7-IS.exe"}.get
engine = make_engine(History(None), [Programs(pc["start"]), Files(pc["recent"]), Calculator(), Web(), Shell(),
                                     Family(find=found), System(), Clipboard()])
tray = TrayApp(engine, show_tray=False, find=found)
la = tray.launcher
la.sync = la.keep_open = True


def finish(name):
    tray.set_finish(name)
    app.setStyleSheet(theme.stylesheet())


def over_desktop(name, query, actions=False):
    la.show_launcher()
    la.edit.setText(query)
    if actions:
        la.show_actions(0)
    app.processEvents()
    shot = la.grab().toImage()
    ratio = shot.devicePixelRatio()
    shot.setDevicePixelRatio(1)
    dark = theme.FINISH == "obsidian"
    w, h = shot.width() + 240 * ratio, shot.height() + 200 * ratio
    img = QImage(int(w), int(h), QImage.Format.Format_ARGB32)
    p = QPainter(img)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, QColor("#1A0E14" if dark else "#E8DCE0"))
    bg.setColorAt(1, QColor("#3A1418" if dark else "#D9B9B4"))
    p.fillRect(img.rect(), bg)
    glow = QRadialGradient(QPointF(w * .75, h * .2), w * .6)
    c = QColor(theme.GLOW)
    c.setAlphaF(.18)
    glow.setColorAt(0, c)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(img.rect(), glow)
    p.drawImage(int((w - shot.width()) / 2), int(80 * ratio), shot)
    p.end()
    img.save(str(out / name))
    la.hide()


finish("obsidian")
over_desktop("launcher.png", "blen")
finish("aurora")
over_desktop("calc_aurora.png", "= 3840 * 2160 * 23.976 / 1e6")
over_desktop("actions_aurora.png", "credits", actions=True)
finish("obsidian")
d = SettingsDialog(tray)
d.resize(1100, 680)
d.show()
app.processEvents()
d.grab().save(str(out / "settings.png"))
d.close()
app.clipboard().clear()
print("ok", out)
