"""Check a real install of PR7-LN-Setup.exe (CI, Windows): verify_install.py installed|uninstalled

`installed`: the files, the Start menu entry, the uninstall entry, the start-up entry (the "startup" task is ticked),
and the installed exe's --selftest: a made-up Start menu, a sum, a file, a web search and a command through the real
launcher (planned, not started), and the runner's real Start menu read. `uninstalled`: all of it gone."""
import json
import os
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

HKCU = winreg.HKEY_CURRENT_USER
APP = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PR7-LN"
SHORTCUT = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Paragon PR7-LN.lnk"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{CF87A58B-036E-4398-BC81-BCECF5A010A7}_is1"


def value(root, path, name=""):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def check(ok, what, p):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        p.append(what)


def installed():
    p = []
    exe = APP / "PR7-LN.exe"
    for f in (exe, APP / "unins000.exe", APP / "_internal" / "pr7ln" / "fonts" / "Inter-Regular.ttf"):
        check(f.is_file(), f"file {f}", p)
    check(SHORTCUT.is_file(), "Start menu shortcut", p)
    check(value(HKCU, UNINSTALL, "DisplayName") == "Paragon PR7-LN", "Installed apps entry", p)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.json"
        try:
            subprocess.run([str(exe), "--selftest", str(out)], timeout=600, check=False)
        except subprocess.TimeoutExpired:
            pass
        got = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        found = got.get("found", {})
        check(found.get("blen", [""])[0] == "Blender 4.3" and found.get("3840*2160", [""])[0] == "8294400"
              and got.get("copied") == "8294400" and got.get("fonts") is True,
              f"the installed exe finds a program and answers a sum ({got})", p)
        check(len(got.get("plans", [])) == 4 and got["plans"][-1].get("args") == ["cmd.exe", "/k", "ver"],
              "it plans opening, the web search and the command", p)
        check(got.get("real_start_menu", 0) > 3, f"it reads the real Start menu ({got.get('real_start_menu')})", p)
    run = value(HKCU, RUN, "Paragon PR7-LN") or ""
    check(str(exe).lower() in run.lower() and "--tray" in run, f"starts with Windows ({run})", p)
    return p


def uninstalled():
    deadline = time.time() + 60
    while True:
        p = []
        check(not (APP / "PR7-LN.exe").exists(), "program files removed", p)
        check(not SHORTCUT.exists(), "Start menu shortcut removed", p)
        check(value(HKCU, UNINSTALL, "DisplayName") is None, "Installed apps entry removed", p)
        check(value(HKCU, RUN, "Paragon PR7-LN") is None, "start-up entry removed", p)
        if not p or time.time() > deadline:
            return p
        print("... waiting for the uninstaller to finish")
        time.sleep(3)


if __name__ == "__main__":
    problems = {"installed": installed, "uninstalled": uninstalled}[sys.argv[1]]()
    print("\nALL OK" if not problems else f"\n{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
