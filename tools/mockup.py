"""Mock-up pictures of PR7-LN, drawn offscreen in the family theme (the PC is made up):
QT_SCALE_FACTOR=2 python tools/mockup.py OUT_DIR

1_launcher.png   Alt+Space over the desktop: "blen" finds the program, files (PR7-IS's index) and a web search (OBSIDIAN)
2_actions.png    A sum answered as you type; a file's actions: open, its folder in PR7-E, edit in PR7-W (AURORA)
3_settings.png   Settings: the hotkey and the plugins with their action keywords (OBSIDIAN)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QKeySequenceEdit,  # noqa: E402
                               QLabel, QLineEdit, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from pr7ln import theme, widgets  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mockup")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
app.setFont(QFont("Inter", 10))


def style():
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.stylesheet())


class Launcher(QWidget):
    """The launcher over a made-up desktop: the search line, the results, the keys at the bottom."""

    def __init__(self, query, results, current=0, actions=None, answer=None, width=1320):
        super().__init__()
        self.query, self.results, self.current, self.actions, self.answer = query, results, current, actions, answer
        self.resize(width, 820)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = theme.FINISH == "obsidian"
        # the desktop: a soft wallpaper, a taskbar
        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0, QColor("#1A0E14" if dark else "#E8DCE0"))
        bg.setColorAt(1, QColor("#3A1418" if dark else "#D9B9B4"))
        p.fillRect(self.rect(), bg)
        glow = QRadialGradient(QPointF(self.width() * .75, self.height() * .2), self.width() * .6)
        c = QColor(theme.GLOW)
        c.setAlphaF(.18)
        glow.setColorAt(0, c)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), glow)
        p.fillRect(QRectF(0, self.height() - 48, self.width(), 48), QColor(0, 0, 0, 150 if dark else 60))
        for i in range(6):
            p.setBrush(QColor(255, 255, 255, 40))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(self.width() / 2 - 150 + i * 52, self.height() - 38, 30, 30), 6, 6)
        # the launcher
        w = min(760, self.width() - 48)
        x0, y0 = (self.width() - w) / 2, 150
        rows = len(self.results) + (len(self.actions) if self.actions else 0)
        h = 92 + rows * 62 + 44
        panel = QRectF(x0, y0, w, h)
        shadow = QColor(0, 0, 0, 120)
        for k in range(12, 0, -3):
            p.setBrush(QColor(0, 0, 0, 12))
            p.drawRoundedRect(panel.adjusted(-k, -k + 6, k, k + 6), 18 + k, 18 + k)
        edge = QPainterPath()
        edge.addRoundedRect(panel.adjusted(-1.5, -1.5, 1.5, 1.5), 17, 17)
        p.fillPath(edge, theme.family_gradient(panel.left(), 0, panel.right(), 0))
        p.setBrush(QColor(theme.PANEL if dark else "#F1ECEE"))
        p.drawRoundedRect(panel, 16, 16)
        # the search line
        f = QFont("Inter")
        f.setPixelSize(26)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        widgets.draw_icon(p, "search", QRectF(x0 + 24, y0 + 28, 28, 28), QColor(theme.TEXT_DIM), 2)
        p.drawText(QRectF(x0 + 66, y0 + 18, w - 200, 48), Qt.AlignmentFlag.AlignVCenter, self.query)
        tw = p.fontMetrics().horizontalAdvance(self.query)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.drawLine(int(x0 + 68 + tw), int(y0 + 28), int(x0 + 68 + tw), int(y0 + 56))
        if self.answer:
            f2 = QFont("Inter")
            f2.setPixelSize(22)
            f2.setWeight(QFont.Weight.DemiBold)
            p.setFont(f2)
            p.setPen(QColor(theme.LED_ORANGE))
            p.drawText(QRectF(x0 + 66, y0 + 18, w - 96, 48), Qt.AlignmentFlag.AlignVCenter |
                       Qt.AlignmentFlag.AlignRight, self.answer)
        p.setPen(QPen(QColor(theme.PANEL_EDGE), 1))
        p.drawLine(int(x0 + 16), int(y0 + 84), int(x0 + w - 16), int(y0 + 84))
        # results
        y = y0 + 92
        all_rows = [(r, False) for r in self.results] + [(a, True) for a in (self.actions or [])]
        for i, (r, is_action) in enumerate(all_rows):
            icon, title, sub, tag = r
            row = QRectF(x0 + 10, y, w - 20, 58)
            if i == self.current:
                band = QPainterPath()
                band.addRoundedRect(row, 10, 10)
                fill = theme.family_gradient(row.left(), 0, row.right(), 0)
                p.save()
                p.setOpacity(.28 if dark else .22)
                p.fillPath(band, fill)
                p.restore()
                p.setPen(QPen(QColor(theme.ACCENT), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(band)
            ix = row.left() + (44 if is_action else 14)
            if icon in ("app", "folder", "file", "documents"):
                pm = widgets.file_pixmap("folder" if icon == "folder" else ("text" if icon == "documents" else "file"),
                                         32) if icon != "app" else None
                if pm is not None:
                    p.drawPixmap(QRectF(ix, y + 13, 32, 32).toRect(), pm)
                else:
                    widgets.draw_icon(p, "app", QRectF(ix, y + 13, 32, 32), QColor(theme.LED_ORANGE), 2)
            else:
                widgets.draw_icon(p, icon, QRectF(ix + 4, y + 17, 24, 24), QColor(theme.LED_ORANGE), 1.8)
            f3 = QFont("Inter")
            f3.setPixelSize(16)
            f3.setWeight(QFont.Weight.DemiBold if not is_action else QFont.Weight.Normal)
            p.setFont(f3)
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(ix + 46, y + 8, w - 240, 24), Qt.AlignmentFlag.AlignVCenter, title)
            f4 = QFont("Inter")
            f4.setPixelSize(12)
            p.setFont(f4)
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(ix + 46, y + 31, w - 240, 18), Qt.AlignmentFlag.AlignVCenter, sub)
            if tag:
                f5 = QFont("Inter")
                f5.setPixelSize(11)
                f5.setWeight(QFont.Weight.DemiBold)
                p.setFont(f5)
                tag_w = p.fontMetrics().horizontalAdvance(tag) + 18
                chip = QRectF(row.right() - tag_w - 14, y + 18, tag_w, 22)
                p.setBrush(QColor(theme.BUTTON))
                p.setPen(QPen(QColor(theme.PANEL_EDGE), 1))
                p.drawRoundedRect(chip, 5, 5)
                p.setPen(QColor(theme.ON_DARK))
                p.drawText(chip, Qt.AlignmentFlag.AlignCenter, tag)
            y += 62
        # the keys
        f6 = QFont("Inter")
        f6.setPixelSize(11)
        f6.setWeight(QFont.Weight.DemiBold)
        p.setFont(f6)
        p.setPen(QColor(theme.TEXT_DIM))
        keys = "ENTER OPEN   ·   CTRL+ENTER ITS FOLDER   ·   SHIFT+ENTER MORE ACTIONS   ·   ESC CLOSE" \
            if w > 700 else "ENTER   ·   CTRL+ENTER FOLDER   ·   SHIFT+ENTER ACTIONS   ·   ESC"
        p.drawText(QRectF(x0, y0 + h - 40, w, 36), Qt.AlignmentFlag.AlignCenter, keys)


def shoot(widget, name):
    widget.show()
    app.processEvents()
    widget.grab().save(str(out / name))
    widget.close()


theme.set_finish("obsidian")
style()
shoot(Launcher("blen", [
    ("app", "Blender 4.3", "Program  ·  C:\\Program Files\\Blender Foundation\\Blender 4.3", "ALT+1"),
    ("folder", "Blender projects", "D:\\Studio\\ELSEWORLD\\Blender projects  ·  PR7-IS", "ALT+2"),
    ("file", "elseworld_titles_v6.blend", "D:\\Studio\\ELSEWORLD\\Blender projects  ·  41.2 MB  ·  today", "ALT+3"),
    ("file", "logo_sting.blend", "D:\\Studio\\Archive\\2025  ·  8.7 MB  ·  2025-11-02", "ALT+4"),
    ("search", "Search the web for \u201cblen\u201d", "Web search  ·  g blen", "ALT+5")]), "1_launcher.png")

theme.set_finish("aurora")
style()
answer = 3840 * 2160 * 23.976 / 1e6                         # worked out, not typed
left = Launcher("= 3840 * 2160 * 23.976 / 1e6", [
    ("copy", f"{answer:.6f}".rstrip("0"), "3840 × 2160 × 23.976 ÷ 1,000,000  ·  Enter copies it", "ALT+1")],
    width=660)
right = Launcher("credits", [
    ("documents", "credits.txt", "D:\\Studio\\ELSEWORLD\\Projects  ·  4 KB  ·  today", "ALT+1")], current=2,
    actions=[("open", "Open", "With its program", "ENTER"),
             ("folders", "Show in folder", "In PR7-E", "CTRL+ENTER"),
             ("edit", "Edit in PR7-W", "The family's text editor", ""),
             ("copy", "Copy path", "D:\\Studio\\ELSEWORLD\\Projects\\credits.txt", "")], width=660)
both = QWidget()
bl = QHBoxLayout(both)
bl.setContentsMargins(0, 0, 0, 0)
bl.setSpacing(0)
bl.addWidget(left)
bl.addWidget(right)
both.resize(1320, 820)
shoot(both, "2_actions.png")

# ------------------------------------------------------------------ settings
theme.set_finish("obsidian")
style()
w = QWidget()
w.setObjectName("win")
w.setStyleSheet(f"QWidget#win {{ background: {theme.BACKGROUND}; }}")
lay = QVBoxLayout(w)
lay.setContentsMargins(0, 0, 0, 0)
lay.setSpacing(0)
lay.addWidget(widgets.Header("LAUNCHER"))
tabs = QTabWidget()
page = QWidget()
pl = QVBoxLayout(page)
pl.setContentsMargins(12, 12, 12, 12)
row = QHBoxLayout()
lab = QLabel("HOTKEY")
lab.setProperty("role", "field")
row.addWidget(lab)
k = QKeySequenceEdit()
k.setKeySequence("Alt+Space")
k.setFixedWidth(200)
row.addWidget(k)
row.addSpacing(20)
for text, on in (("Start with Windows", True), ("Hide when it loses focus", True), ("Remember the last query", False)):
    c = QCheckBox(text)
    c.setChecked(on)
    row.addWidget(c)
row.addStretch(1)
pl.addLayout(row)
t = QTreeWidget()
t.setHeaderLabels(["ON", "PLUGIN", "KEYWORD", "WHAT IT DOES"])
t.setRootIsDecorated(False)
for on, name, key, what in (
        (True, "Programs", "*", "Start menu programs and Windows apps, ranked by how often you pick them"),
        (True, "Files (PR7-IS)", "*  ·  f", "Files and folders from PR7-IS's index: instant on the whole PC"),
        (True, "Calculator", "=  ·  *", "Sums as you type; Enter copies the answer"),
        (True, "Web search", "g  ·  ddg  ·  wiki", "Your browser, a search engine per keyword"),
        (True, "Shell", ">", "Run a command (Ctrl+Enter: as administrator)"),
        (True, "Paragon family", "pr7", "Every installed PR7 app, and its actions (PR7-W new file, PR7-Q region ...)"),
        (True, "System", "*", "Lock, sleep, restart, shut down, empty Recycle Bin (each asks first)"),
        (False, "Clipboard (PR7-CB)", "cb", "Search PR7-CB's clipboard history")):
    it = QTreeWidgetItem(["", name, key, what])
    it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
    t.addTopLevelItem(it)
t.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
for c in (0, 1, 2):
    t.header().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
pl.addWidget(t, 1)
note = QLabel("\u201c*\u201d answers without a keyword. Programs you open often come first.")
note.setProperty("role", "dim")
pl.addWidget(note)
tabs.addTab(page, "PLUGINS")
tabs.addTab(QWidget(), "APPEARANCE")
tabs.addTab(QWidget(), "ABOUT")
wrap = QWidget()
wl = QVBoxLayout(wrap)
wl.setContentsMargins(16, 10, 16, 10)
wl.addWidget(tabs)
lay.addWidget(wrap, 1)
foot = QFrame()
foot.setStyleSheet(f"QFrame {{ background: {theme.TAB_FRAME}; border-top: 1px solid {theme.PANEL_EDGE}; }}")
fl = QHBoxLayout(foot)
fl.setContentsMargins(16, 6, 16, 6)
s = QLabel("Indexed: 214 programs  ·  files through PR7-IS (1.6 million)  ·  in the tray")
s.setProperty("role", "dim")
fl.addWidget(s)
lay.addWidget(foot)
w.resize(1320, 820)
shoot(w, "3_settings.png")
print("ok", out)
