import json
import os
import socket
import sqlite3
import threading
import time

import pytest

from pr7ln import actions, calc
from pr7ln.engine import Engine, History
from pr7ln.match import score
from pr7ln.plugins import (Calculator, Clipboard, Family, Files, Programs, Shell, System, Web, file_actions)


def test_score_order():
    assert score("blender", "Blender") == 100
    assert score("blen", "Blender 4.3") > score("4.3", "Blender 4.3") > 0
    assert score("vsc", "Visual Studio Code") == 70                       # the words' initials
    assert score("code", "Visual Studio Code") > score("ode", "Visual Studio Code")   # a word's start beats inside
    assert score("fx", "Firefox") is not None and score("fx", "Firefox") < 41      # letters in order only
    assert score("zzz", "Firefox") is None


@pytest.mark.parametrize("text, want", [("2+2", "4"), ("3840 * 2160 * 23.976 / 1e6", "198.8665344"),
                                        ("2^10", "1024"), ("sqrt(2)", "1.414213562"), ("10 ÷ 4", "2.5"),
                                        ("1,000 * 3", "3000"), ("(1+2)*3", "9"), ("-5 + 2", "-3")])
def test_calc(text, want):
    assert calc.show(calc.evaluate(text)) == want


@pytest.mark.parametrize("text", ["__import__('os')", "9**9**9", "1/0", "open('x')", "a.b", "[1, 2]", "lambda: 1"])
def test_calc_refuses(text):
    with pytest.raises(calc.CalcError):
        calc.evaluate(text)


def test_looks_like_math():
    assert calc.looks_like_math("12*4") and calc.looks_like_math("sqrt(9)") and calc.looks_like_math("(2+3)/4")
    assert not calc.looks_like_math("blender") and not calc.looks_like_math("2026") and \
        not calc.looks_like_math("win 11")


def test_programs_from_both_start_menus(pc):
    p = Programs(pc["start"])
    names = [r.title for r in p.query("", None)]
    assert "Blender 4.3" in names and "Firefox" in names and "Windows Terminal" in names    # sub-folders too
    assert not any("Uninstall" in n for n in names)                                          # left out
    top = sorted(p.query("blen", None), key=lambda r: -r.score)[0]
    assert top.title == "Blender 4.3" and top.action == {"type": "open", "path": top.action["path"]}
    assert top.action["path"].endswith("Blender 4.3.lnk")
    assert top.path.replace("\\", "/").endswith("Blender Foundation/blender.exe")    # the shortcut's target, read
    assert [r.title for r in p.query("vsc", None)] == ["Visual Studio Code"]


def test_files_recent_fallback(pc):
    f = Files(pc["recent"])
    got = f.query("credits", None)
    assert [r.title for r in got] == ["credits.txt"] and got[0].action["path"] == os.path.join(pc["docs"], "credits.txt")
    assert f.query("cr", None) == []                          # too short without the keyword: no noise
    assert [r.title for r in f.query("bud", "f")] == ["budget 2026.xlsx"]


class FakeIS:
    """PR7-IS's service as the real one speaks: a port and a token in service.json, JSON lines."""

    def __init__(self, path, rows):
        self.rows, self.asked = rows, []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        with open(path, "w") as fh:
            json.dump({"port": self.sock.getsockname()[1], "token": "t0k", "pid": os.getpid()}, fh)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            data = b""
            while not data.endswith(b"\n"):
                data += c.recv(4096)
            msg = json.loads(data)
            self.asked.append(msg)
            reply = {"total": len(self.rows), "rows": self.rows} if msg.get("token") == "t0k" else {"error": "token"}
            c.sendall(json.dumps(reply).encode() + b"\n")
            c.close()


def test_files_through_pr7is(tmp_path, monkeypatch):
    path = tmp_path / "service.json"
    monkeypatch.setenv("PR7IS_ADDRESS", str(path))
    rows = [{"name": "Blender projects", "folder": "D:\\Studio", "path": "D:\\Studio\\Blender projects", "size": 0,
             "mtime": 0, "dir": True},
            {"name": "logo.blend", "folder": "D:\\Studio", "path": "D:\\Studio\\logo.blend", "size": 9_120_000,
             "mtime": time.time(), "dir": False}]
    srv = FakeIS(path, rows)
    got = Files(str(tmp_path / "none")).query("blen", None)
    assert [r.title for r in got] == ["Blender projects", "logo.blend"]
    assert got[0].icon == "folder" and "8.7 MB" in got[1].subtitle and "PR7-IS" in got[1].subtitle
    assert srv.asked[0]["q"] == "blen" and srv.asked[0]["op"] == "search" and srv.asked[0]["limit"] == 4
    srv.sock.close()


def test_calc_web_shell_system():
    assert Calculator().query("12*4", None)[0].action == {"type": "copy", "text": "48"}
    assert Calculator().query("hello", None) == []
    w = Web("ddg").query("paragon pr7", None)[0]
    assert w.action["url"] == "https://duckduckgo.com/?q=paragon%20pr7"
    assert Web().query("x y", "wiki")[0].action["url"].endswith("search=x%20y")
    assert Shell().query("ipconfig /all", ">")[0].action == {"type": "shell", "command": "ipconfig /all"}
    sys_ = {r.title: r.action for r in System().query("sh", None)}
    assert sys_["Shut down"] == {"type": "system", "command": "shutdown", "confirm": True}
    assert System().query("lo", None)[0].action["confirm"] is False                         # Lock doesn't ask


def test_family_only_installed():
    found = {"PR7-W": "C:\\PR7-W\\PR7-W.exe", "PR7-E": "C:\\PR7-E\\PR7-E.exe"}
    got = Family(find=found.get).query("", "pr7")
    assert sorted(r.action["app"] for r in got) == ["PR7-E", "PR7-W"]
    assert [r.action["app"] for r in Family(find=found.get).query("text", "pr7")] == ["PR7-W"]


def test_file_actions():
    found = {"PR7-W": "W.exe", "PR7-E": "E.exe", "PR7-HX": "HX.exe", "PR7-R": "R.exe"}
    acts = file_actions("D:\\Projects\\credits.txt", find=found.get)
    titles = [a.title for a in acts]
    assert titles == ["Open", "Show in folder", "Edit in PR7-W", "Open in PR7-HX", "Copy path"]
    assert acts[1].subtitle == "In PR7-E"
    assert [a.title for a in file_actions("x.pdf", find=found.get)][2] == "Open in PR7-R"
    assert "Run as administrator" in [a.title for a in file_actions("C:\\x\\setup.exe", find={}.get)]


def test_engine_keywords_ranking_history(pc, tmp_path):
    hist = History(str(tmp_path / "history.json"))
    e = Engine([Programs(pc["start"]), Files(pc["recent"]), Calculator(), Web(), Shell(), System()], hist)
    assert e.split("=2+2")[1:] == ("=", "2+2") and e.split(">dir")[1:] == (">", "dir")
    assert e.split("g cats")[1:] == ("g", "cats") and e.split("gimp")[0] is None
    got = e.query("f")
    assert got[-1].plugin == "web"                                   # the web search is always offered last
    first = [r.title for r in e.query("fi")]
    assert first[0] == "Firefox"
    # picking another result a few times lifts it above a better match (Flow Launcher's way)
    assert [r.title for r in e.query("s")][:2] == ["Steam", "Visual Studio Code"]
    code = next(r for r in e.query("s") if r.title == "Visual Studio Code")
    for _ in range(3):
        hist.picked(code.key)
    assert [r.title for r in e.query("s")][:2] == ["Visual Studio Code", "Steam"]
    paint = code
    assert json.load(open(tmp_path / "history.json"))[paint.key] == 3
    assert History(str(tmp_path / "history.json")).counts[paint.key] == 3      # kept for next time
    assert e.query("2*21")[0].title == "42"
    assert [r.plugin for r in e.query("g blender")] == ["web"]


def test_engine_disabled_and_broken_plugin(pc):
    class Broken(Programs):
        name = "broken"

        def query(self, text, keyword):
            raise RuntimeError("boom")
    e = Engine([Broken(pc["start"]), Programs(pc["start"]), Web()], disabled={"programs"})
    assert [r.plugin for r in e.query("blender")] == ["web"]          # off, and one plugin's trouble is ignored
    e.disabled = set()
    assert e.query("blender")[0].title == "Blender 4.3"


def test_clipboard_reads_pr7cb(tmp_path):
    db = tmp_path / "clips.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE clips (id INTEGER PRIMARY KEY, kind TEXT, text TEXT, html TEXT, image BLOB, files TEXT,"
                " source TEXT, created REAL, pinned INTEGER, width INTEGER, height INTEGER, digest TEXT)")
    for i, (t, src) in enumerate((("ssh user@studio.local", "PR7-W"), ("Meeting at 10", "firefox"))):
        con.execute("INSERT INTO clips (kind, text, source, created, pinned) VALUES ('text', ?, ?, ?, 0)",
                    (t, src, time.time() - i))
    con.commit()
    con.close()
    before = db.read_bytes()
    got = Clipboard(str(db)).query("studio", "cb")
    assert [r.action for r in got] == [{"type": "copy", "text": "ssh user@studio.local"}]
    assert len(Clipboard(str(db)).query("", "cb")) == 2
    assert db.read_bytes() == before                                   # read only
    assert Engine([Clipboard(str(db))]).query("studio") == []         # off until switched on
    assert Engine([Clipboard(str(db))], disabled=set()).query("cb studio")[0].title.startswith("ssh")


def test_plans():
    found = {"PR7-E": "C:\\E\\PR7-E.exe", "PR7-W": "C:\\W\\PR7-W.exe"}.get
    assert actions.plan({"type": "open", "path": "C:\\a.txt"}) == {"kind": "shell", "file": "C:\\a.txt",
                                                                   "verb": "open"}
    assert actions.plan({"type": "open", "path": "C:\\a.exe"}, admin=True)["verb"] == "runas"
    assert actions.plan({"type": "folder", "path": "/tmp/x/a.txt"}, find=found)["args"] == ["C:\\E\\PR7-E.exe",
                                                                                              "/tmp/x"]
    assert actions.plan({"type": "folder", "path": "C:\\x\\a.txt"}, find={}.get)["args"] == \
        ["explorer.exe", "/select,C:\\x\\a.txt"]
    assert actions.plan({"type": "shell", "command": "dir"}) == {"kind": "start", "args": ["cmd.exe", "/k", "dir"],
                                                                 "console": True}
    assert actions.plan({"type": "shell", "command": "dir"}, admin=True) == {"kind": "shell", "file": "cmd.exe",
                                                                            "params": "/k dir", "verb": "runas"}
    assert actions.plan({"type": "family", "app": "PR7-W", "path": "a.txt"}, find=found)["args"] == \
        ["C:\\W\\PR7-W.exe", "a.txt"]
    assert actions.plan({"type": "family", "app": "PR7-HX"}, find=found) is None
    assert actions.plan({"type": "system", "command": "restart"})["args"] == ["shutdown.exe", "/r", "/t", "0"]
