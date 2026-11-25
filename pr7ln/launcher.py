"""The launcher: one search line over the desktop and the results under it, the way Flow Launcher shows them.

Keys: Up / Down (PgUp / PgDn, Home / End) choose, Enter runs, Ctrl+Enter opens a file's folder (a command or program:
as administrator), Shift+Enter (or Right) lists the result's actions (Left / Esc goes back), Alt+1..9 runs that row,
Tab puts the result's name in the line, Esc hides it. It hides when another window is clicked (Options).

The whole thing is painted (the panel with the family edge, the rows, the band on the current one) except the line,
a QLineEdit with no frame. What a result does is `actions.plan`; `run` (tests: a stand-in) carries it out."""

from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from . import actions, theme, widgets
from .engine import Engine
from .plugins import Result, file_actions

WIDTH = 760
TOP = 92                  # the search line's height, the rule under it
ROW = 62
FOOT = 44
EDGE = 14                 # room for the shadow round the panel
DEBOUNCE_MS = 40
ICON_FILES = {"folder": "folder", "file": "file", "text": "text"}
ICON_LINES = {"app": "app", "calc": "copy", "copy": "copy", "search": "search", "shell": "text", "system": "gear",
              "family": "home", "open": "open", "edit": "edit"}


class Launcher(QWidget):
    ran = Signal(dict)                         # every plan carried out (tests and the selftest watch it)

    def __init__(self, engine: Engine, history=None, find=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("PR7-LN")
        self.engine = engine
        self.find = find
        self.answers: dict = {}
        self.run = actions.run                 # tests: a stand-in that keeps the plans
        self.sync = False                      # tests: query at once, not after the debounce
        self.keep_open = False                 # tests: offscreen windows don't keep the focus
        self.hide_on_blur = True
        self.keep_query = False
        self.results: list[Result] = []
        self.current = 0
        self.actions_of: Result | None = None  # Shift+Enter: whose actions are listed
        self.items: list[Result] = []          # the rows shown (results, or the chosen one plus its actions)
        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        self.edit.setPlaceholderText("Search programs, files, sums, the web ...")
        f = QFont("Inter")
        f.setPixelSize(26)
        self.edit.setFont(f)
        self.edit.textChanged.connect(self._changed)
        self.edit.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.refresh)
        self.setMouseTracking(True)
        self.restyle()
        self._layout()

    # ---------------------------------------------------------------- look
    def restyle(self):
        self.edit.setStyleSheet(f"QLineEdit {{ background: transparent; border: none; color: {theme.TEXT}; "
                                f"font-family: Inter; font-size: 26px; padding: 0; "
                                f"selection-background-color: {theme.ACCENT_DIM}; selection-color: {theme.TEXT}; }}")
        self.update()

    def panel(self) -> QRectF:
        return QRectF(EDGE, EDGE, WIDTH, self._panel_height())

    def _panel_height(self) -> int:
        n = len(self.items)
        return TOP + (n * ROW + 8 + FOOT if n else 0) + (0 if n else 4)

    def _layout(self):
        self.setFixedSize(WIDTH + 2 * EDGE, self._panel_height() + 2 * EDGE + 8)
        self.edit.setGeometry(EDGE + 66, EDGE + 18, WIDTH - 96, 48)
        self.update()

    def row_rect(self, i: int) -> QRectF:
        return QRectF(EDGE + 10, EDGE + TOP + i * ROW, WIDTH - 20, ROW - 4)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = theme.FINISH == "obsidian"
        panel = self.panel()
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(12, 0, -3):
            p.setBrush(QColor(0, 0, 0, 14))
            p.drawRoundedRect(panel.adjusted(-k, -k + 6, k, k + 6), 18 + k, 18 + k)
        edge = QPainterPath()
        edge.addRoundedRect(panel.adjusted(-1.5, -1.5, 1.5, 1.5), 17, 17)
        p.fillPath(edge, theme.family_gradient(panel.left(), 0, panel.right(), 0))
        p.setBrush(QColor(theme.PANEL if dark else "#F1ECEE"))
        p.drawRoundedRect(panel, 16, 16)
        x0, y0, w = panel.left(), panel.top(), panel.width()
        widgets.draw_icon(p, "search", QRectF(x0 + 24, y0 + 28, 28, 28), QColor(theme.TEXT_DIM), 2)
        answer = self.items[0].title if self.items and self.items[0].plugin == "calc" and not self.actions_of else ""
        if answer and answer != "…":
            f = QFont("Inter")
            f.setPixelSize(22)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor(theme.LED_ORANGE))
            used = self.edit.fontMetrics().horizontalAdvance(self.edit.text()) + 90
            if p.fontMetrics().horizontalAdvance(answer) < w - used - 40:
                p.drawText(QRectF(x0 + 66, y0 + 18, w - 96, 48), Qt.AlignmentFlag.AlignVCenter |
                           Qt.AlignmentFlag.AlignRight, answer)
        if not self.items:
            return
        p.setPen(QPen(QColor(theme.PANEL_EDGE), 1))
        p.drawLine(QPointF(x0 + 16, y0 + 84), QPointF(x0 + w - 16, y0 + 84))
        for i, r in enumerate(self.items):
            self._paint_row(p, i, r, dark)
        f = QFont("Inter")
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT_DIM))
        keys = ("ENTER RUN   ·   ← BACK   ·   ESC CLOSE" if self.actions_of else
                "ENTER OPEN   ·   CTRL+ENTER ITS FOLDER   ·   SHIFT+ENTER MORE ACTIONS   ·   ESC CLOSE")
        p.drawText(QRectF(x0, panel.bottom() - 40, w, 36), Qt.AlignmentFlag.AlignCenter, keys)

    def _paint_row(self, p: QPainter, i: int, r: Result, dark: bool):
        row = self.row_rect(i)
        is_action = self.actions_of is not None and i > 0
        if i == self.current:
            band = QPainterPath()
            band.addRoundedRect(row, 10, 10)
            p.save()
            p.setOpacity(.28 if dark else .22)
            p.fillPath(band, theme.family_gradient(row.left(), 0, row.right(), 0))
            p.restore()
            p.setPen(QPen(QColor(theme.ACCENT), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(band)
        ix = row.left() + (44 if is_action else 14)
        y = row.top()
        if r.icon in ICON_FILES:
            p.drawPixmap(QRectF(ix, y + 13, 32, 32).toRect(), widgets.file_pixmap(ICON_FILES[r.icon], 32))
        elif r.icon == "app":
            widgets.draw_icon(p, "app", QRectF(ix, y + 13, 32, 32), QColor(theme.LED_ORANGE), 2)
        else:
            widgets.draw_icon(p, ICON_LINES.get(r.icon, r.icon), QRectF(ix + 4, y + 17, 24, 24),
                              QColor(theme.LED_ORANGE), 1.8)
        tag = self._tag(i)
        right = row.right() - (p.fontMetrics().horizontalAdvance(tag) + 60 if tag else 20)
        f = QFont("Inter")
        f.setPixelSize(16)
        f.setWeight(QFont.Weight.Normal if is_action else QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        tw = right - (ix + 46)
        p.drawText(QRectF(ix + 46, y + 8, tw, 24), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(r.title, Qt.TextElideMode.ElideRight, int(tw)))
        f = QFont("Inter")
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(ix + 46, y + 31, tw, 18), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(r.subtitle, Qt.TextElideMode.ElideMiddle, int(tw)))
        if tag:
            f = QFont("Inter")
            f.setPixelSize(11)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            tag_w = p.fontMetrics().horizontalAdvance(tag) + 18
            chip = QRectF(row.right() - tag_w - 14, y + 18, tag_w, 22)
            p.setBrush(QColor(theme.BUTTON))
            p.setPen(QPen(QColor(theme.PANEL_EDGE), 1))
            p.drawRoundedRect(chip, 5, 5)
            p.setPen(QColor(theme.ON_DARK))
            p.drawText(chip, Qt.AlignmentFlag.AlignCenter, tag)

    def _tag(self, i: int) -> str:
        if self.actions_of is not None:
            return {1: "ENTER", 2: "CTRL+ENTER"}.get(i, "")
        return f"ALT+{i + 1}" if i < 9 else ""

    # ---------------------------------------------------------------- showing
    def show_launcher(self):
        if not self.keep_query:
            self.edit.clear()
        self.edit.selectAll()
        self._place()
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()
        if self.keep_query and self.edit.text():
            self.refresh()

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_launcher()

    def _place(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        self.move(int(g.center().x() - self.width() / 2), int(g.top() + g.height() * .22))

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and self.isVisible() \
                and self.hide_on_blur and not self.keep_open and not QApplication.activeModalWidget():
            QTimer.singleShot(0, self._blur)

    def _blur(self):
        if not self.isActiveWindow() and not QApplication.activeModalWidget():
            self.hide()

    # ---------------------------------------------------------------- searching
    def _changed(self, _text: str):
        if self.sync:
            self.refresh()
        else:
            self.timer.start(DEBOUNCE_MS)

    def refresh(self):
        self.actions_of = None
        self.results = self.engine.query(self.edit.text())
        self.items = list(self.results)
        self.current = 0
        self._layout()

    def show_actions(self, i: int | None = None):
        i = self.current if i is None else i
        if self.actions_of is not None or not (0 <= i < len(self.items)):
            return
        r = self.items[i]
        if not r.path:
            return
        self.actions_of = r
        self.items = [r] + file_actions(r.path, find=self.find)
        self.current = 1
        self._layout()

    def back(self):
        if self.actions_of is None:
            return False
        chosen = self.actions_of
        self.actions_of = None
        self.items = list(self.results)
        self.current = max(0, self.items.index(chosen)) if chosen in self.items else 0
        self._layout()
        return True

    def move_current(self, step: int):
        if self.items:
            low = 1 if self.actions_of is not None else 0
            self.current = max(low, min(len(self.items) - 1, self.current + step))
            self.update()

    # ---------------------------------------------------------------- running
    def activate(self, i: int | None = None, admin: bool = False, folder: bool = False) -> bool:
        i = self.current if i is None else i
        if not (0 <= i < len(self.items)):
            return False
        r = self.items[i]
        if self.actions_of is not None and i == 0:
            r = self.items[1]
        owner = self.actions_of or r
        action = r.action
        if folder and owner.path and owner.plugin in ("programs", "files"):
            action = {"type": "folder", "path": owner.path if owner.plugin == "files" else owner.path}
            admin = False
        if not action:
            return False
        if action.get("type") == "system" and action.get("confirm") and \
                not self._ask("confirm", f"{r.title}: {r.subtitle.rstrip('.')}?"):
            return False
        plan = actions.plan(action, admin=admin and action.get("type") in ("open", "shell", "admin"), find=self.find)
        if plan is None:
            self._say("warning", "That app isn't installed any more.")
            return False
        if plan["kind"] == "copy":
            QApplication.clipboard().setText(plan["text"])
        elif not self.run(plan):
            self._say("warning", "Windows couldn't start it.")
            return False
        self.engine.history.picked(owner.key)
        self.ran.emit(plan)
        self.hide()
        return True

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == e.Type.KeyPress:
            return self.key(e.key(), e.modifiers()) or False
        return super().eventFilter(obj, e)

    def key(self, k, mods) -> bool:
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if self.timer.isActive() and k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.timer.stop()
            self.refresh()                     # Enter right after typing: answer the line as it is now
        if k == Qt.Key.Key_Escape:
            if not self.back():
                self.hide()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if shift:
                self.show_actions()
            elif ctrl:
                self.activate(admin=True, folder=True)
            else:
                self.activate()
            return True
        if k == Qt.Key.Key_Down:
            self.move_current(1)
            return True
        if k == Qt.Key.Key_Up:
            self.move_current(-1)
            return True
        if k == Qt.Key.Key_PageDown:
            self.move_current(5)
            return True
        if k == Qt.Key.Key_PageUp:
            self.move_current(-5)
            return True
        if k == Qt.Key.Key_Right and self.edit.cursorPosition() == len(self.edit.text()) and self.actions_of is None \
                and self.items and self.items[self.current].path:
            self.show_actions()
            return True
        if k == Qt.Key.Key_Left and self.actions_of is not None:
            self.back()
            return True
        if k == Qt.Key.Key_Tab:
            if self.items and self.actions_of is None:
                r = self.items[self.current]
                if r.plugin in ("programs", "files", "family"):
                    self.edit.setText(r.title.split("  ·  ")[0])
            return True
        if alt and Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
            self.activate(k - Qt.Key.Key_1)
            return True
        return False

    def _row_at(self, pos) -> int | None:
        for i in range(len(self.items)):
            if self.row_rect(i).contains(QPointF(pos)):
                return i
        return None

    def mouseMoveEvent(self, e):
        i = self._row_at(e.position())
        if i is not None and i != self.current and not (self.actions_of and i == 0):
            self.current = i
            self.update()

    def mousePressEvent(self, e):
        i = self._row_at(e.position())
        if i is None:
            return
        if e.button() == Qt.MouseButton.RightButton:
            self.show_actions(i)
        elif e.button() == Qt.MouseButton.LeftButton:
            self.activate(i)

    # ---------------------------------------------------------------- questions
    def _ask(self, kind: str, text: str) -> bool:
        if kind in self.answers:
            a = self.answers[kind]
            return a(text) if callable(a) else a
        from PySide6.QtWidgets import QMessageBox
        return QMessageBox.question(self, "Paragon PR7-LN", text) == QMessageBox.StandardButton.Yes

    def _say(self, kind: str, text: str):
        if "say" in self.answers:
            self.answers["say"](kind, text)
            return
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Paragon PR7-LN", text)


def data_folder() -> str:
    env = os.environ.get("PR7LN_DATA")
    if env:
        return env
    import sys
    base = os.environ.get("APPDATA") if sys.platform == "win32" else os.path.join(os.path.expanduser("~"), ".local",
                                                                                    "share")
    return os.path.join(base or os.path.expanduser("~"), "Paragon", "PR7-LN")
