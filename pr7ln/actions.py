"""Carrying out a result's action (no Qt). `plan(action, admin)` turns the action dict into exactly what will be run
(a command line, a ShellExecute, a Windows call, text to copy), and `run(plan)` runs it. Tests check the plans, so
nothing is started, locked or shut down by a test.

    open      ShellExecute "open" (the file's own program, a folder in its file manager)
    folder    the folder in PR7-E when it's installed, else Explorer with the file selected
    admin     ShellExecute "runas" (Windows asks first)
    url       the default browser
    copy      the clipboard (the window does that part)
    shell     cmd.exe /k COMMAND (a console that stays open); admin: the same through "runas"
    family    a family app, with the file when there is one
    system    lock / sleep / restart / shutdown / signout / emptybin / settings
    app       Linux: a menu entry's program (its Exec line; Terminal=true ones in a terminal)

On Linux (PR7-OS) the same actions plan Linux's commands: xdg-open, a terminal for commands (x-terminal-emulator,
Debian's name for the installed one), loginctl / systemctl / Plasma's logout, the Trash through kioclient.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

from . import desktop, family

LINUX = sys.platform != "win32"
TERMINAL = "x-terminal-emulator"
LINUX_SYSTEM = {"lock": {"kind": "start", "args": ["loginctl", "lock-session"]},
                "sleep": {"kind": "start", "args": ["systemctl", "suspend"]},
                "restart": {"kind": "start", "args": ["systemctl", "reboot"]},
                "shutdown": {"kind": "start", "args": ["systemctl", "poweroff"]},
                "signout": {"kind": "start", "args": ["qdbus6", "org.kde.Shutdown", "/Shutdown", "logout"]},
                "emptybin": {"kind": "start", "args": ["kioclient", "empty", "trash:/"]},
                "settings": {"kind": "start", "args": ["systemsettings"]}}


def in_terminal(command: str, admin: bool = False) -> list[str]:
    """A command in a terminal that stays open afterwards (Windows' cmd /k); admin: through sudo."""
    inner = f"sudo sh -c {shlex.quote(command)}" if admin else command
    return [TERMINAL, "-e", "sh", "-c", f'{inner}; exec "${{SHELL:-/bin/bash}}"']

SYSTEM_PLANS = {"lock": {"kind": "call", "name": "lock"}, "sleep": {"kind": "call", "name": "sleep"},
                "restart": {"kind": "start", "args": ["shutdown.exe", "/r", "/t", "0"]},
                "shutdown": {"kind": "start", "args": ["shutdown.exe", "/s", "/t", "0"]},
                "signout": {"kind": "start", "args": ["shutdown.exe", "/l"]},
                "emptybin": {"kind": "call", "name": "emptybin"},
                "settings": {"kind": "shell", "file": "ms-settings:", "verb": "open"}}


def plan(action: dict, admin: bool = False, find=None, linux: bool | None = None) -> dict | None:
    find = find or family.find
    linux = LINUX if linux is None else linux
    t = action.get("type")
    if linux:
        p = _linux_plan(action, admin, find)
        if p is not False:
            return p
    if t == "open":
        if admin:
            return {"kind": "shell", "file": action["path"], "verb": "runas"}
        return {"kind": "shell", "file": action["path"], "verb": "open"}
    if t == "admin":
        return {"kind": "shell", "file": action["path"], "verb": "runas"}
    if t == "folder":
        path = action["path"]
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        exe = find("PR7-E")
        if exe:
            return {"kind": "start", "args": [exe, folder]}
        return {"kind": "start", "args": ["explorer.exe", f"/select,{path}"]}
    if t == "url":
        return {"kind": "shell", "file": action["url"], "verb": "open"}
    if t == "copy":
        return {"kind": "copy", "text": action["text"]}
    if t == "shell":
        if admin:
            return {"kind": "shell", "file": "cmd.exe", "params": f"/k {action['command']}", "verb": "runas"}
        return {"kind": "start", "args": ["cmd.exe", "/k", action["command"]], "console": True}
    if t == "family":
        exe = find(action["app"])
        if not exe:
            return None
        return {"kind": "start", "args": [exe] + ([action["path"]] if action.get("path") else [])}
    if t == "system":
        return dict(SYSTEM_PLANS[action["command"]])
    return None


def _linux_plan(action: dict, admin: bool, find):
    """Linux's plan for an action, or False to use the shared one (url, copy, family)."""
    t = action.get("type")
    if t == "app":
        try:
            with open(action["path"], encoding="utf-8", errors="replace") as fh:
                keys = desktop.parse(fh.read())
        except OSError:
            return None
        e = desktop.Entry("", action["path"], keys.get("Name", ""), exec=keys.get("Exec", ""),
                          icon=keys.get("Icon", ""), terminal=keys.get("Terminal", "").lower() == "true")
        words = desktop.command(e)
        if not words:
            return None
        if e.terminal or admin:
            return {"kind": "start", "args": in_terminal(shlex.join(words), admin)}
        return {"kind": "start", "args": words}
    if t in ("open", "admin"):
        if admin or t == "admin":                    # Linux has no "run as administrator" for a file: a terminal
            return {"kind": "start", "args": in_terminal(shlex.quote(action["path"]), True)}
        return {"kind": "start", "args": ["xdg-open", action["path"]]}
    if t == "folder":
        path = action["path"]
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        exe = find("PR7-E")
        return {"kind": "start", "args": [exe, folder] if exe else ["xdg-open", folder]}
    if t == "url":
        return {"kind": "start", "args": ["xdg-open", action["url"]]}
    if t == "shell":
        return {"kind": "start", "args": in_terminal(action["command"], admin)}
    if t == "system":
        return dict(LINUX_SYSTEM[action["command"]])
    return False


def run(p: dict) -> bool:
    """Run a plan (copy plans are the window's). False when Windows refused (Cancel on the admin prompt too)."""
    kind = p["kind"]
    if kind == "start":
        flags = 0
        if sys.platform == "win32" and p.get("console"):
            flags = subprocess.CREATE_NEW_CONSOLE
        args = p["args"]
        if sys.platform == "win32" and p.get("console"):
            # the command goes to cmd.exe as typed: a list would be quoted by Python's rules (\" inside), which cmd.exe
            # doesn't read, so `dir "C:\Program Files"` would fail
            args = f"{args[0]} {args[1]} {args[2]}"
        try:
            subprocess.Popen(args, close_fds=True, creationflags=flags)
            return True
        except OSError:
            return False
    if kind == "shell":
        return shell_execute(p["file"], p.get("params", ""), p.get("verb", "open"))
    if kind == "call":
        return system_call(p["name"])
    return False


def shell_execute(file: str, params: str = "", verb: str = "open") -> bool:
    if sys.platform != "win32":
        try:
            subprocess.Popen(["xdg-open", file], close_fds=True)
            return True
        except OSError:
            return False
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, verb, file, params or None,
                                            os.path.dirname(file) if os.path.isabs(file) else None, 1)
    return r > 32                      # ShellExecute's own rule: more than 32 is success


def system_call(name: str) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    if name == "lock":
        return bool(ctypes.windll.user32.LockWorkStation())
    if name == "sleep":
        return bool(ctypes.windll.powrprof.SetSuspendState(False, False, False))
    if name == "emptybin":
        SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI, SHERB_NOSOUND = 1, 2, 4      # PR7-LN asked already
        r = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI |
                                                     SHERB_NOSOUND)
        return r in (0, -2147418113)    # S_OK, or E_UNEXPECTED: the bin was already empty
    return False
