"""Start PR7-LN.

    PR7-LN.exe                    run in the notification area (Alt+Space opens the launcher); started again, it opens
                                  the launcher in the running PR7-LN instead of starting twice
    PR7-LN.exe --tray             start quietly (Windows' start-up entry)
    PR7-LN.exe --startup on|off   start with Windows or not (the installer's task)
    PR7-LN.exe --unregister       take the start-up entry away (the uninstaller)
    PR7-LN.exe --version
    PR7-LN.exe --selftest OUT.json   a made-up Start menu, a sum, a file, a web search and a command through the real
                                     launcher offscreen (nothing is started), and the real Start menu read; writes
                                     what was found and planned (CI checks the installed exe)
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys

TIMEOUT_MS = 1500


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return "Paragon-PR7-LN-" + hashlib.sha1(user.encode()).hexdigest()[:12]


def hand_over(show: bool) -> bool:
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(server_name())
    if not s.waitForConnected(TIMEOUT_MS):
        return False
    s.write(json.dumps({"show": show}).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(TIMEOUT_MS)
    if not s.waitForDisconnected(TIMEOUT_MS):
        s.disconnectFromServer()
    return True


def listen(tray):
    """Later starts hand over to this PR7-LN (PR7-R's hand-off, with its Windows fix: data may already be waiting)."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(tray)
    QLocalServer.removeServer(server_name())
    if not server.listen(server_name()):
        return None

    def connection():
        sock = server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = []

        def read():
            buf.extend(bytes(sock.readAll()))
            if buf.endswith(b"\n") and not done:
                done.append(True)
                try:
                    msg = json.loads(buf.decode())
                except ValueError:
                    return
                if msg.get("show"):
                    tray.launcher.show_launcher()
                sock.disconnectFromServer()
        sock.readyRead.connect(read)
        sock.disconnected.connect(read)
        if sock.bytesAvailable():
            read()
    server.newConnection.connect(connection)
    tray.instance_server = server
    return server


def selftest(out: str) -> int:
    import tempfile
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    data = tempfile.mkdtemp()
    os.environ["PR7LN_DATA"] = data
    result = {}
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtWidgets import QApplication
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())
        from . import __version__, lnk, theme
        from .engine import History
        from .plugins import Calculator, Files, Programs, Shell, System, Web
        from .tray import TrayApp, make_engine
        app = QApplication.instance() or QApplication(sys.argv[:1])
        theme.load_fonts()
        # a made-up Start menu and Recent folder, with shortcuts this exe writes and reads back
        start = os.path.join(data, "Start")
        recent = os.path.join(data, "Recent")
        os.makedirs(start)
        os.makedirs(recent)
        exe = os.path.join(data, "Blender", "blender.exe")
        os.makedirs(os.path.dirname(exe))
        open(exe, "wb").write(b"MZ")
        open(os.path.join(start, "Blender 4.3.lnk"), "wb").write(lnk.make_lnk(exe))
        doc = os.path.join(data, "credits.txt")
        open(doc, "w").write("x")
        open(os.path.join(recent, "credits.txt.lnk"), "wb").write(lnk.make_lnk(doc))
        engine = make_engine(History(os.path.join(data, "history.json")),
                             [Programs([start]), Files(recent), Calculator(), Web(), Shell(), System()])
        tray = TrayApp(engine, show_tray=False, find=lambda app_: None)
        la = tray.launcher
        la.sync = la.keep_open = True
        plans = []
        la.run = lambda p: plans.append(p) or True
        found = {}
        for q in ("blen", "3840*2160", "credits", "g paragon", "> ver"):
            la.show_launcher()
            la.edit.setText(q)
            found[q] = [r.title for r in la.items]
            la.grab()
            la.activate()
        real = Programs()
        real.load()
        result = {"version": __version__, "found": found, "plans": plans, "copied": app.clipboard().text(),
                  "history": json.load(open(os.path.join(data, "history.json"))),
                  "real_start_menu": len(real.items), "fonts": "Inter" in QFontDatabase.families()}
        app.clipboard().clear()   # PySide's offscreen clipboard crashes at exit while it holds data (PR7-CB's lesson)
    except Exception as e:  # noqa: BLE001 - reported in the output
        result = {"error": f"{type(e).__name__}: {e}"}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return 0 if "found" in result else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv[:1] == ["--version"]:
            from . import __version__
            print(__version__)
            return 0
        if argv[:1] == ["--selftest"] and len(argv) == 2:
            return selftest(argv[1])
        if argv[:1] == ["--startup"] and len(argv) == 2:
            from .tray import start_with_windows
            start_with_windows(argv[1].lower() in ("on", "1", "yes"))
            return 0
        if argv[:1] == ["--unregister"]:
            from .tray import start_with_windows
            start_with_windows(False)
            return 0
    except Exception:  # noqa: BLE001 - a command-line mode never waits on an error box (PR7-IS's lesson)
        return 1
    quiet = "--tray" in argv
    from PySide6.QtWidgets import QApplication

    from . import settings, theme
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("Paragon")
    app.setApplicationName("PR7-LN")
    app.setQuitOnLastWindowClosed(False)          # it lives in the notification area
    if hand_over(not quiet):
        return 0
    from . import finish
    theme.set_finish(finish.start(settings.get("finish", "obsidian")))
    theme.load_fonts()
    app.setPalette(theme.palette())
    from PySide6.QtGui import QFont, QIcon
    app.setFont(QFont("Inter", 10))
    icon = os.path.join(os.path.dirname(__file__), "icons", "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    from .tray import TrayApp, option
    tray = TrayApp()
    from PySide6.QtCore import QTimer
    _follow = QTimer(tray)                        # one finish for the family: follow another app's switch
    _follow.timeout.connect(lambda: finish.follow(theme.FINISH, tray.set_finish))
    _follow.start(2000)
    listen(tray)
    if not quiet and tray.tray:
        tray.tray.showMessage("PR7-LN is ready", f"{option('key_show')} opens the launcher. Its menu is here in the "
                              "notification area.", tray.tray.MessageIcon.Information, 5000)
    from PySide6.QtWidgets import QWidget
    tray.anchor = QWidget()                       # a parent for the update dialog
    from . import update_ui
    update_ui.start(tray.anchor)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
