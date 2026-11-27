"""Linux's programs (no Qt): the freedesktop.org menu entries (.desktop files) that Plasma's own launcher lists, read
from $XDG_DATA_HOME/applications and each $XDG_DATA_DIRS/applications. An entry in an earlier folder hides one with
the same id in a later one (your own ~/.local/share/applications overrides the system's), as the specification says.

Left out, as Plasma's menu leaves them out: NoDisplay / Hidden entries, OnlyShowIn without KDE, NotShowIn KDE, a
TryExec that isn't installed, and anything but Type=Application. `command(entry, files)` is the Exec line ready to
start: field codes (%f %F %u %U %i %c %k) replaced or dropped, quoting as the specification describes.
"""
from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass


@dataclass
class Entry:
    id: str                 # "org.kde.dolphin.desktop" (sub-folders joined with "-")
    path: str
    name: str
    generic: str = ""
    exec: str = ""
    icon: str = ""
    terminal: bool = False
    keywords: str = ""


def folders() -> list[str]:
    home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    return [os.path.join(d, "applications") for d in [home, *dirs] if d]


def parse(text: str) -> dict[str, str]:
    """The [Desktop Entry] group's keys (unlocalised ones: Name, not Name[de])."""
    out, inside = {}, False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
            continue
        if inside and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            if "[" not in k:
                out[k] = v.strip()
    return out


def shown(keys: dict[str, str], desktop: str = "KDE") -> bool:
    if keys.get("Type", "Application") != "Application":
        return False
    if keys.get("NoDisplay", "").lower() == "true" or keys.get("Hidden", "").lower() == "true":
        return False
    only = [x for x in keys.get("OnlyShowIn", "").split(";") if x]
    if only and desktop not in only:
        return False
    if desktop in keys.get("NotShowIn", "").split(";"):
        return False
    tryexec = keys.get("TryExec", "")
    if tryexec and not (os.path.isabs(tryexec) and os.access(tryexec, os.X_OK)) and not shutil.which(tryexec):
        return False
    return bool(keys.get("Name") and keys.get("Exec"))


def entries(dirs: list[str] | None = None, desktop: str = "KDE") -> list[Entry]:
    seen: set[str] = set()
    out = []
    for base in dirs if dirs is not None else folders():
        if not os.path.isdir(base):
            continue
        for folder, _subdirs, files in os.walk(base):
            for f in sorted(files):
                if not f.endswith(".desktop"):
                    continue
                path = os.path.join(folder, f)
                ident = os.path.relpath(path, base).replace(os.sep, "-")
                if ident in seen:
                    continue
                seen.add(ident)                  # hidden or not, it overrides later folders' entry of this id
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        keys = parse(fh.read())
                except OSError:
                    continue
                if shown(keys, desktop):
                    out.append(Entry(ident, path, keys["Name"], keys.get("GenericName", ""), keys["Exec"],
                                     keys.get("Icon", ""), keys.get("Terminal", "").lower() == "true",
                                     keys.get("Keywords", "")))
    return out


def command(entry: Entry, files: list[str] | None = None) -> list[str]:
    """The Exec line as arguments: %f / %u = the first file, %F / %U = all of them, %i = --icon ICON, %c = the name,
    %k = the entry's path, %% = %; the deprecated codes (%d %D %n %N %v %m) are dropped."""
    files = files or []
    try:
        words = shlex.split(entry.exec.replace("\\\\", "\\"))
    except ValueError:
        words = entry.exec.split()
    out: list[str] = []
    for w in words:
        if w in ("%f", "%u"):
            out += files[:1]
        elif w in ("%F", "%U"):
            out += files
        elif w == "%i":
            out += ["--icon", entry.icon] if entry.icon else []
        elif w in ("%d", "%D", "%n", "%N", "%v", "%m"):
            continue
        else:
            out.append(w.replace("%c", entry.name).replace("%k", entry.path).replace("%%", "%"))
    return [w for w in out if w]
