"""A made-up PC for tests and screenshots: two Start menus with real .lnk shortcuts (and an uninstaller, which the
Programs plugin leaves out), a Recent folder, and the files they point at."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pr7ln.lnk import make_lnk  # noqa: E402

PROGRAMS = [("user", "Blender 4.3", "Blender Foundation/blender.exe"), ("all", "Visual Studio Code", "VS Code/Code.exe"),
            ("all", "Firefox", "Mozilla Firefox/firefox.exe"), ("all", "Paint.NET", "paint.net/paintdotnet.exe"),
            ("all", "Uninstall Firefox", "Mozilla Firefox/uninstall/helper.exe"),
            ("user", "Steam", "Steam/steam.exe"), ("all", "Windows Terminal", "Terminal/wt.exe")]
RECENT = ["credits.txt", "budget 2026.xlsx", "elseworld_titles_v6.blend"]


def build(root) -> dict:
    root = Path(root)
    user = root / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    common = root / "ProgramData" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    files = root / "Program Files"
    docs = root / "Documents"
    recent = root / "AppData" / "Microsoft" / "Windows" / "Recent"
    for d in (user, common, files, docs, recent):
        d.mkdir(parents=True, exist_ok=True)
    for where, name, exe in PROGRAMS:
        target = files / exe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ")
        folder = (user if where == "user" else common) / ("Tools" if "Terminal" in name else "")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.lnk").write_bytes(make_lnk(str(target)))
    for name in RECENT:
        f = docs / name
        f.write_bytes(b"x")
        (recent / f"{name}.lnk").write_bytes(make_lnk(str(f)))
    return {"start": [str(user), str(common)], "recent": str(recent), "docs": str(docs), "files": str(files),
            "root": str(root)}
