"""The launcher's plugins (no Qt): each answers a query with results. A result says what to do as a plain action dict
({"type": "open", "path": ...}), which the launcher carries out, so tests check the action without running anything.

    programs   Start menu shortcuts (both Start menus), uninstallers left out           answers without a keyword
    files      PR7-IS's index through its service (its port + token); else Recent files  without a keyword, and "f"
    calc       sums (calc.py)                                                              "=", and math-looking text
    web        a search engine per keyword                                                 "g" "ddg" "b" "wiki" "yt"
    shell      a command in a console window (Ctrl+Enter: as administrator)                ">"
    family     the installed Paragon apps                                                  "pr7"
    system     lock, sleep, restart, shut down, sign out, empty the Recycle Bin, Settings  without a keyword
"""

from __future__ import annotations

import json
import shutil
import os
import socket
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import quote

from . import actions, calc, desktop, family, lnk
from .match import score

ENGINES = {"g": ("Google", "https://www.google.com/search?q="), "ddg": ("DuckDuckGo", "https://duckduckgo.com/?q="),
           "b": ("Bing", "https://www.bing.com/search?q="),
           "wiki": ("Wikipedia", "https://en.wikipedia.org/wiki/Special:Search?search="),
           "yt": ("YouTube", "https://www.youtube.com/results?search_query=")}
FAMILY = {  # what each family app is, and the files it opens (Shift+Enter offers it for them)
    "PR7-Z": ("Archive manager", "7z zip rar tar gz xz bz2 iso"), "PR7-W": ("Text editor", "txt md log ini cfg json xml csv py "
                                                                       "js ts html css bat ps1 reg yaml yml toml"),
    "PR7-L": ("Tag editor", "mp3 flac m4a ogg opus wma"), "PR7-F": ("File transfer", ""),
    "PR7-E": ("File manager", ""), "PR7-R": ("PDF reader", "pdf"),
    "PR7-P": ("Image viewer", "jpg jpeg png gif webp bmp tif tiff heic avif"),
    "PR7-M": ("Media player", "mp4 mkv avi mov webm wmv wav mp3 flac"), "PR7-Q": ("Screenshot tool", ""),
    "PR7-U": ("Family installer", ""), "PR7-DU": ("Disk usage", ""), "PR7-CB": ("Clipboard history", ""),
    "PR7-IS": ("File search", ""), "PR7-PM": ("Password manager", "kdbx"), "PR7-SM": ("System monitor", ""),
    "PR7-HB": ("Video converter", ""), "PR7-FS": ("Folder sync", ""), "PR7-AR": ("Startup manager", ""),
    "PR7-WM": ("File compare", ""), "PR7-HX": ("Hex editor", "*"), "PR7-DB": ("SQLite browser", "db sqlite sqlite3"),
    "PR7-UN": ("Uninstaller", ""), "PR7-LN": ("Launcher", "")}


@dataclass
class Result:
    title: str
    subtitle: str = ""
    icon: str = "app"             # app / folder / file / text / calc / search / shell / system / family
    score: float = 0.0
    plugin: str = ""
    key: str = ""                 # what the pick history counts
    action: dict = field(default_factory=dict)
    path: str = ""                # a file or program behind it (Ctrl+Enter: its folder; Shift+Enter: more actions)


class Plugin:
    name = ""
    keywords: tuple = ()
    default = True                # answers without a keyword
    title = ""
    about = ""

    def query(self, text: str, keyword: str | None) -> list[Result]:
        raise NotImplementedError


# ------------------------------------------------------------------ programs
def start_menus() -> list[str]:
    e = os.environ
    return [os.path.join(e.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(e.get("ProgramData", r"C:\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs")]


class Programs(Plugin):
    name, title = "programs", "Programs"
    about = "Start menu programs, ranked by how often you pick them (Linux: the menu's programs)"
    REFRESH = 600

    def __init__(self, folders: list[str] | None = None, linux: bool | None = None):
        # Linux reads menu entries; given Start menu folders (the made-up PC of the tests and --selftest), Windows' way
        self.linux = (actions.LINUX and folders is None) if linux is None else linux
        self.folders = folders if folders is not None else (desktop.folders() if self.linux else start_menus())
        self.items: list[tuple[str, str, str]] = []        # (name, shortcut path, target)
        self.loaded = 0.0

    def load(self):
        if self.linux:                                     # freedesktop.org menu entries, as Plasma's menu lists them
            items = []
            for e in desktop.entries(self.folders):
                if "uninstall" in e.name.casefold():
                    continue
                words = desktop.command(e)
                target = (shutil.which(words[0]) or words[0]) if words else ""
                items.append((e.name, e.path, target))
            self.items = items
            self.loaded = time.time()
            return
        seen, items = set(), []
        for root in self.folders:
            for folder, _dirs, files in os.walk(root):
                for f in files:
                    stem, ext = os.path.splitext(f)
                    if ext.lower() not in (".lnk", ".url", ".appref-ms", ".exe"):
                        continue
                    low = stem.casefold()
                    if low.startswith("uninstall") or "uninstall " in low or low in seen:
                        continue                              # Flow Launcher leaves uninstallers out too
                    full = os.path.join(folder, f)
                    target = ""
                    if ext.lower() == ".lnk":
                        try:
                            with open(full, "rb") as fh:
                                target = lnk.lnk_target(fh.read()) or ""
                        except OSError:
                            pass
                    seen.add(low)
                    items.append((stem, full, target))
        self.items = items
        self.loaded = time.time()

    def query(self, text, keyword):
        if not self.loaded or time.time() - self.loaded > self.REFRESH:
            self.load()
        out = []
        for name, path, target in self.items:
            s = score(text, name)
            if s is None and target:
                s2 = score(text, os.path.splitext(os.path.basename(target))[0])
                s = s2 - 15 if s2 is not None else None
            if s is not None:
                action = {"type": "app", "path": path} if self.linux else {"type": "open", "path": path}
                out.append(Result(name, f"Program  ·  {target or path}", "app", s + 5, self.name, f"program:{name}",
                                  action, target or path))
        return out


# ------------------------------------------------------------------ files
def is_address() -> str:
    """PR7-IS's service.json (PR7IS_ADDRESS in tests)."""
    if os.environ.get("PR7IS_ADDRESS"):
        return os.environ["PR7IS_ADDRESS"]
    base = os.environ.get("LOCALAPPDATA") if sys.platform == "win32" else os.path.join(os.path.expanduser("~"),
                                                                                         ".local", "share")
    return os.path.join(base or os.path.expanduser("~"), "Paragon", "PR7-IS", "service.json")


def is_search(query: str, limit: int = 5, timeout: float = 0.6) -> list[dict] | None:
    """Ask PR7-IS's index service; None when it isn't running."""
    try:
        with open(is_address(), encoding="utf-8") as fh:
            where = json.load(fh)
        with socket.create_connection(("127.0.0.1", int(where["port"])), timeout=timeout) as s:
            s.settimeout(timeout)
            msg = {"op": "search", "q": query, "kind": "everything", "sort": "name", "desc": False, "offset": 0,
                   "limit": limit, "token": where["token"]}
            s.sendall(json.dumps(msg).encode() + b"\n")
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(1 << 20)
                if not chunk:
                    return None
                buf += chunk
        reply = json.loads(buf.split(b"\n", 1)[0])
        return reply.get("rows") if "rows" in reply else None
    except (OSError, ValueError, KeyError):
        return None


def recent_folder() -> str:
    if sys.platform != "win32":                # freedesktop.org's recent files list (Plasma keeps it)
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, "recently-used.xbel")
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")


def recent_xbel(path: str) -> list[str]:
    """The files in a recently-used.xbel (newest first, ones that still exist)."""
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote, urlparse
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    marks = [(b.get("modified") or b.get("visited") or "", b.get("href", "")) for b in root.iter("bookmark")]
    out = []
    for _when, href in sorted(marks, reverse=True):
        if href.startswith("file://"):
            f = unquote(urlparse(href).path)
            if os.path.exists(f):
                out.append(f)
    return out


def human(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


class Files(Plugin):
    name, title, keywords = "files", "Files (PR7-IS)", ("f",)
    about = "Files and folders from PR7-IS's index: instant on the whole PC (else your recent files)"

    def __init__(self, recent: str | None = None):
        self.recent = recent if recent is not None else recent_folder()

    def query(self, text, keyword):
        if len(text.strip()) < (1 if keyword else 3):
            return []
        limit = 9 if keyword else 4
        rows = is_search(text.strip(), limit)
        out = []
        if rows is not None:
            for i, r in enumerate(rows):
                when = time.strftime("%Y-%m-%d", time.localtime(r["mtime"])) if r.get("mtime") else ""
                bits = [r.get("folder", "")] + ([] if r.get("dir") else [human(int(r.get("size") or 0))]) + \
                    ([when] if when else []) + ["PR7-IS"]
                s = score(text, r["name"])
                out.append(Result(r["name"], "  ·  ".join(b for b in bits if b), "folder" if r.get("dir") else
                                  kind_icon(r["name"]), (s if s is not None else 30) - 8 - i * 0.1, self.name,
                                  f"file:{r['path']}", {"type": "open", "path": r["path"]}, r["path"]))
            return out
        if self.recent.endswith(".xbel"):                # Linux
            for target in recent_xbel(self.recent):
                s = score(text, os.path.basename(target))
                if s is not None:
                    out.append(Result(os.path.basename(target), f"Recent  ·  {os.path.dirname(target)}",
                                      kind_icon(target), s - 10, self.name, f"file:{target}",
                                      {"type": "open", "path": target}, target))
            return sorted(out, key=lambda r: -r.score)[:limit]
        try:
            names = os.listdir(self.recent)
        except OSError:
            return []
        for f in names:
            if not f.lower().endswith(".lnk"):
                continue
            stem = f[:-4]
            s = score(text, stem)
            if s is None:
                continue
            target = ""
            try:
                with open(os.path.join(self.recent, f), "rb") as fh:
                    target = lnk.lnk_target(fh.read()) or ""
            except OSError:
                pass
            if not target:
                continue
            out.append(Result(stem, f"Recent  ·  {os.path.dirname(target)}", kind_icon(target), s - 10, self.name,
                              f"file:{target}", {"type": "open", "path": target}, target))
        return sorted(out, key=lambda r: -r.score)[:limit]


def kind_icon(name: str) -> str:
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext in FAMILY["PR7-W"][1].split():
        return "text"
    return "file"


# ------------------------------------------------------------------ calculator, web, shell
class Calculator(Plugin):
    name, title, keywords = "calc", "Calculator", ("=",)
    about = "Sums as you type; Enter copies the answer"

    def query(self, text, keyword):
        if not keyword and not calc.looks_like_math(text):
            return []
        try:
            v = calc.evaluate(text)
            answer = calc.show(v)
        except (calc.CalcError, OverflowError, TypeError):
            return [] if not keyword else [Result("…", "Not a sum yet", "calc", 0, self.name)]
        return [Result(answer, f"{text.strip()}  ·  Enter copies it", "calc", 95, self.name, "",
                       {"type": "copy", "text": answer})]


class Web(Plugin):
    name, title, keywords = "web", "Web search", tuple(ENGINES)
    default = False
    about = "Your browser, a search engine per keyword"

    def __init__(self, engine: str = "g"):
        self.engine = engine if engine in ENGINES else "g"

    def query(self, text, keyword):
        if not text.strip():
            return []
        k = keyword or self.engine
        name, url = ENGINES[k]
        return [Result(f"Search {name} for \u201c{text.strip()}\u201d", f"Web search  ·  {k} {text.strip()}", "search",
                       50 if keyword else -1, self.name, "", {"type": "url", "url": url + quote(text.strip())})]


class Shell(Plugin):
    name, title, keywords = "shell", "Shell", (">",)
    default = False
    about = "Run a command (Ctrl+Enter: as administrator)"

    def query(self, text, keyword):
        where = "a terminal" if actions.LINUX else "a console window"
        if not text.strip():
            return [Result("Type a command", f"It runs in {where}", "shell", 0, self.name)]
        return [Result(f"> {text.strip()}", f"Run in {where}  ·  Ctrl+Enter as administrator", "shell", 90, self.name,
                       "", {"type": "shell", "command": text.strip()})]


# ------------------------------------------------------------------ the family, the system
class Family(Plugin):
    name, title, keywords = "family", "Paragon family", ("pr7",)
    about = "Every installed PR7 app"
    default = False

    def __init__(self, find=None):
        self.find = find or family.find

    def query(self, text, keyword):
        out = []
        for app, (what, _) in FAMILY.items():
            if app == "PR7-LN" or not self.find(app):
                continue
            s = score(text, f"{app} {what}") if text.strip() else 50.0
            if s is not None:
                out.append(Result(f"{app}  ·  {what}", "Paragon family", "family", s, self.name, f"family:{app}",
                                  {"type": "family", "app": app}))
        return out


SYSTEM = [("Lock", "Lock the PC", "lock", False), ("Sleep", "Put the PC to sleep", "sleep", True),
          ("Restart", "Restart Windows", "restart", True), ("Shut down", "Shut down Windows", "shutdown", True),
          ("Sign out", "Sign out of Windows", "signout", True),
          ("Empty Recycle Bin", "Delete everything in the Recycle Bin", "emptybin", True),
          ("Settings", "Windows Settings", "settings", False)]
SYSTEM_LINUX = [("Lock", "Lock the screen", "lock", False), ("Sleep", "Put the PC to sleep", "sleep", True),
              ("Restart", "Restart the PC", "restart", True), ("Shut down", "Shut down the PC", "shutdown", True),
              ("Sign out", "Sign out of Plasma", "signout", True),
              ("Empty Trash", "Delete everything in the Trash", "emptybin", True),
              ("Settings", "System Settings", "settings", False)]                 # the same, in Linux's words


class System(Plugin):
    name, title = "system", "System"
    about = "Lock, sleep, restart, shut down, sign out, empty Recycle Bin (each asks first)"

    def query(self, text, keyword):
        out = []
        for title, sub, cmd, ask in (SYSTEM_LINUX if actions.LINUX else SYSTEM):
            s = score(text, title)
            if s is not None and (len(text.strip()) >= 2 or s >= 90):
                out.append(Result(title, sub, "system", s - 2, self.name, f"system:{cmd}",
                                  {"type": "system", "command": cmd, "confirm": ask}))
        return out


# ------------------------------------------------------------------ PR7-CB's clipboard history (off at first)
def cb_database() -> str:
    """PR7-CB's clips.db (PR7CB_DATA in tests), read only: PR7-LN never changes another app's data."""
    if os.environ.get("PR7CB_DATA"):
        return os.path.join(os.environ["PR7CB_DATA"], "clips.db")
    base = os.environ.get("APPDATA") if sys.platform == "win32" else os.path.join(os.path.expanduser("~"), ".local",
                                                                                    "share")
    return os.path.join(base or os.path.expanduser("~"), "Paragon", "PR7-CB", "clips.db")


class Clipboard(Plugin):
    name, title, keywords = "clipboard", "Clipboard (PR7-CB)", ("cb",)
    default = False
    about = "Search PR7-CB's clipboard history; Enter copies the clip again"

    def __init__(self, path: str | None = None):
        self.path = path

    def query(self, text, keyword):
        path = self.path or cb_database()
        if not os.path.exists(path):
            return [Result("PR7-CB keeps no history here", "Install PR7-CB to search your clipboard", "copy", 0,
                           self.name)]
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.5)
            try:
                rows = con.execute("SELECT text, source, created FROM clips WHERE kind = 'text' ORDER BY pinned DESC, "
                                   "created DESC LIMIT 500").fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return []
        words = text.casefold().split()
        out = []
        for i, (clip, source, created) in enumerate(rows):
            if words and not all(w in clip.casefold() for w in words):
                continue
            line = " ⏎ ".join(x.strip() for x in clip.splitlines() if x.strip())[:200] or clip[:200]
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(created))
            out.append(Result(line, "  ·  ".join(b for b in ("Clipboard", source, when) if b), "copy", 50 - i * 0.01,
                              self.name, "", {"type": "copy", "text": clip}))
            if len(out) >= 9:
                break
        return out


def file_actions(path: str, find=None) -> list[Result]:
    """Shift+Enter on a file or program: what can be done with it (family apps only when installed)."""
    find = find or family.find
    out = [Result("Open", "With its program", "open", 0, "", "", {"type": "open", "path": path}),
           Result("Show in folder", "In PR7-E" if find("PR7-E") else "In Explorer", "folder", 0, "", "",
                  {"type": "folder", "path": path})]
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if os.path.splitext(path)[1].lower() in (".exe", ".lnk", ".bat", ".cmd"):
        out.append(Result("Run as administrator", "Windows asks first", "shell", 0, "", "",
                          {"type": "admin", "path": path}))
    for app, (what, exts) in FAMILY.items():
        if exts and app not in ("PR7-HX",) and ext in exts.split() and find(app):
            verb = {"PR7-W": "Edit in", "PR7-L": "Edit tags in"}.get(app, "Open in")
            out.append(Result(f"{verb} {app}", f"The family's {what.lower()}", "edit" if verb.startswith("Edit") else
                              "app", 0, "", "",
                              {"type": "family", "app": app, "path": path}))
    if find("PR7-HX") and not os.path.isdir(path):
        out.append(Result("Open in PR7-HX", "The family's hex editor", "family", 0, "", "",
                          {"type": "family", "app": "PR7-HX", "path": path}))
    out.append(Result("Copy path", path, "copy", 0, "", "", {"type": "copy", "text": path}))
    return out
