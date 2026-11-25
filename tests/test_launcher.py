import json
import os
import subprocess
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from pr7ln import __version__
from pr7ln.tray import SettingsDialog, option


def type_in(la, text):
    la.show_launcher()
    QTest.keyClicks(la.edit, text)


def test_finds_and_opens_a_program(tray, pc):
    la = tray.launcher
    type_in(la, "blen")
    assert la.isVisible() and la.items[0].title == "Blender 4.3"
    assert la.items[-1].plugin == "web"                       # the web search last
    la.grab()                                                 # paints without trouble
    QTest.keyClick(la.edit, Qt.Key.Key_Return)
    assert not la.isVisible()
    assert la.plans == [{"kind": "shell", "file": os.path.join(pc["start"][0], "Blender 4.3.lnk"), "verb": "open"}]
    assert tray.engine.history.counts["program:Blender 4.3"] == 1


def test_keys_move_alt_number_and_escape(tray):
    la = tray.launcher
    type_in(la, "s")
    titles = [r.title for r in la.items]
    QTest.keyClick(la.edit, Qt.Key.Key_Down)
    assert la.current == 1
    QTest.keyClick(la.edit, Qt.Key.Key_Up)
    QTest.keyClick(la.edit, Qt.Key.Key_Up)
    assert la.current == 0
    QTest.keyClick(la.edit, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)
    assert len(la.plans) == 1 and tray.engine.history.counts[la.results[1].key] == 1     # the second row ran
    assert la.results[1].title == titles[1] and la.plans[0]["file"].endswith(f"{titles[1]}.lnk")
    type_in(la, "x")
    QTest.keyClick(la.edit, Qt.Key.Key_Escape)
    assert not la.isVisible()


def test_calculator_copies(tray, qapp):
    la = tray.launcher
    type_in(la, "= 3840 * 2160 * 23.976 / 1e6")
    assert la.items[0].title == "198.8665344"
    la.grab()
    QTest.keyClick(la.edit, Qt.Key.Key_Return)
    assert qapp.clipboard().text() == "198.8665344" and la.plans == []        # copied, nothing started


def test_ctrl_enter_folder_and_shift_enter_actions(tray, pc):
    la = tray.launcher
    type_in(la, "credits")
    assert la.items[0].title == "credits.txt"
    QTest.keyClick(la.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert la.plans[-1] == {"kind": "start", "args": ["C:\\PR7-E\\PR7-E.exe", pc["docs"]]}      # its folder, in PR7-E
    type_in(la, "credits")
    QTest.keyClick(la.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert [r.title for r in la.items] == ["credits.txt", "Open", "Show in folder", "Edit in PR7-W", "Copy path"]
    assert la.current == 1
    la.grab()
    QTest.keyClick(la.edit, Qt.Key.Key_Left)                  # back to the results
    assert la.actions_of is None and la.items[0].title == "credits.txt"
    QTest.keyClick(la.edit, Qt.Key.Key_Right)                 # Right lists them too
    QTest.keyClick(la.edit, Qt.Key.Key_Down)
    QTest.keyClick(la.edit, Qt.Key.Key_Down)
    QTest.keyClick(la.edit, Qt.Key.Key_Return)                # Edit in PR7-W
    assert la.plans[-1] == {"kind": "start", "args": ["C:\\PR7-W\\PR7-W.exe", os.path.join(pc["docs"], "credits.txt")]}
    assert tray.engine.history.counts[f"file:{os.path.join(pc['docs'], 'credits.txt')}"] == 2


def test_shell_web_and_admin(tray):
    la = tray.launcher
    type_in(la, ">ipconfig")
    QTest.keyClick(la.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert la.plans[-1] == {"kind": "shell", "file": "cmd.exe", "params": "/k ipconfig", "verb": "runas"}
    type_in(la, "wiki Flow Launcher")
    QTest.keyClick(la.edit, Qt.Key.Key_Return)
    assert la.plans[-1]["file"] == "https://en.wikipedia.org/wiki/Special:Search?search=Flow%20Launcher"


def test_system_asks_first(tray):
    la = tray.launcher
    la.answers["confirm"] = False
    type_in(la, "shut down")
    assert la.items[0].title == "Shut down"
    QTest.keyClick(la.edit, Qt.Key.Key_Return)
    assert la.plans == [] and la.isVisible()                  # said no: nothing happens
    la.answers["confirm"] = True
    QTest.keyClick(la.edit, Qt.Key.Key_Return)
    assert la.plans == [{"kind": "start", "args": ["shutdown.exe", "/s", "/t", "0"]}]


def test_mouse_and_tab(tray):
    la = tray.launcher
    type_in(la, "vis")
    QTest.keyClick(la.edit, Qt.Key.Key_Tab)
    assert la.edit.text() == "Visual Studio Code"
    rect = la.row_rect(0)
    QTest.mouseClick(la, Qt.MouseButton.LeftButton, pos=QPoint(int(rect.center().x()), int(rect.center().y())))
    assert la.plans and la.plans[-1]["file"].endswith("Visual Studio Code.lnk")


def test_family_keyword(tray):
    la = tray.launcher
    type_in(la, "pr7 ")
    assert sorted(r.title.split("  ·  ")[0] for r in la.items) == ["PR7-E", "PR7-W"]


def test_settings_save_and_take_effect(tray):
    la = tray.launcher
    d = SettingsDialog(tray)
    d.grab()
    names = [d.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(d.tree.topLevelItemCount())]
    assert "clipboard" in names
    assert d.tree.topLevelItem(names.index("clipboard")).checkState(0) == Qt.CheckState.Unchecked   # off at first
    d.tree.topLevelItem(names.index("programs")).setCheckState(0, Qt.CheckState.Unchecked)
    d.engine_box.setCurrentIndex(d.engine_box.findData("ddg"))
    d.keep.setChecked(True)
    tray.answers["options"] = lambda dlg: (dlg.tree.topLevelItem(names.index("programs")).setCheckState(
        0, Qt.CheckState.Unchecked), dlg.engine_box.setCurrentIndex(dlg.engine_box.findData("ddg")),
        dlg.keep.setChecked(True)) and True
    tray.options()
    assert set(option("disabled")) == {"programs", "clipboard"} and option("engine") == "ddg" and option("keep_query")
    type_in(la, "blender")
    assert [r.plugin for r in la.items] == ["web"] and "duckduckgo" in la.items[0].action["url"]
    la.hide()
    la.show_launcher()
    assert la.edit.text() == "blender"                        # remembered
    assert "Programs" in d.status_text()


def test_finish_switch(tray):
    from pr7ln import finish, theme
    tray.set_finish("aurora")
    assert theme.FINISH == "aurora" and finish.get() == "aurora" and tray.acts["finish_aurora"].isChecked()
    tray.launcher.show_launcher()
    tray.launcher.grab()
    tray.set_finish("obsidian")


def test_selftest(tmp_path):
    out = tmp_path / "self.json"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-m", "pr7ln", "--selftest", str(out)], cwd=root, capture_output=True,
                       text=True, timeout=120)
    got = json.loads(out.read_text())
    assert r.returncode == 0, (got, r.stderr)
    assert got["version"] == __version__ and got["fonts"]
    assert got["found"]["blen"][0] == "Blender 4.3" and got["found"]["3840*2160"][0] == "8294400"
    assert got["copied"] == "8294400"
    assert [p["kind"] for p in got["plans"]] == ["shell", "shell", "shell", "start"]
    assert got["plans"][2]["file"].startswith("https://www.google.com/search?q=paragon")
    assert got["plans"][3]["args"] == ["cmd.exe", "/k", "ver"]
    assert got["history"] == {"program:Blender 4.3": 1, **{k: 1 for k in got["history"] if k.startswith("file:")}}


def test_second_start_hands_over(tmp_path):
    """A second PR7-LN opens the launcher in the first (a separate process, PR7-R's test)."""
    from pr7ln import app
    code = ("import sys, os; sys.path.insert(0, sys.argv[1]); os.environ['QT_QPA_PLATFORM']='offscreen';"
            "from PySide6.QtWidgets import QApplication; a = QApplication([]);"
            "from pr7ln import app; print(app.hand_over(True))")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", code, root], capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == "False"                       # nobody is listening: it would start itself
    assert app.server_name().startswith("Paragon-PR7-LN-")
