"""PR7-LN on Linux (PR7-OS): programs from the freedesktop.org menu entries (what Plasma's menu lists), Linux's plans
for every action (nothing is started: plans are checked), recent files from recently-used.xbel, start at sign-in."""
import os
import sys
from pathlib import Path

import pytest

from pr7ln import actions, desktop, plugins, tray


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(actions, "LINUX", True)


def entry(folder: Path, name: str, text: str) -> Path:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[Desktop Entry]\n" + text)
    return p


@pytest.fixture
def menus(tmp_path):
    user, system = tmp_path / "home/applications", tmp_path / "usr/applications"
    entry(system, "org.kde.dolphin.desktop", "Type=Application\nName=Dolphin\nName[de]=Dolphin DE\n"
                                             "GenericName=File Manager\nExec=dolphin %u\nIcon=system-file-manager\n")
    entry(system, "pr7-w.desktop", "Type=Application\nName=PR7-W Text\nExec=pr7-w %F\nIcon=paragon-pr7-w\n")
    entry(system, "htop.desktop", "Type=Application\nName=Htop\nExec=htop\nTerminal=true\n")
    entry(system, "gnome-only.desktop", "Type=Application\nName=Gnome Thing\nExec=gthing\nOnlyShowIn=GNOME;\n")
    entry(system, "not-kde.desktop", "Type=Application\nName=No KDE\nExec=nokde\nNotShowIn=KDE;\n")
    entry(system, "hidden.desktop", "Type=Application\nName=Helper\nExec=helper\nNoDisplay=true\n")
    entry(system, "missing.desktop", "Type=Application\nName=Missing\nExec=missing\nTryExec=/no/such/program\n")
    entry(system, "link.desktop", "Type=Link\nName=A link\nURL=https://example.com\n")
    entry(system, "kde/org.kde.konsole.desktop", "Type=Application\nName=Konsole\nExec=konsole\n")
    entry(system, "firefox-esr.desktop", "Type=Application\nName=Firefox ESR\nExec=/usr/lib/firefox-esr/firefox-esr %u\n")
    # yours overrides the system's: a different name, and one you hid
    entry(user, "firefox-esr.desktop", "Type=Application\nName=Firefox (mine)\nExec=firefox-esr --private %u\n")
    entry(user, "htop.desktop", "Type=Application\nName=Htop\nExec=htop\nHidden=true\n")
    return [str(user), str(system)]


def test_the_menu_entries_plasma_lists(menus):
    found = {e.name: e for e in desktop.entries(menus)}
    assert sorted(found) == ["Dolphin", "Firefox (mine)", "Konsole", "PR7-W Text"]
    assert found["Konsole"].id == "kde-org.kde.konsole.desktop"           # sub-folders join the id with "-"
    assert found["Dolphin"].generic == "File Manager"


def test_exec_field_codes(menus):
    e = next(x for x in desktop.entries(menus) if x.name == "PR7-W Text")
    assert desktop.command(e, ["/home/ari/a b.txt", "/home/ari/c.txt"]) == ["pr7-w", "/home/ari/a b.txt", "/home/ari/c.txt"]
    assert desktop.command(e) == ["pr7-w"]
    quoted = desktop.Entry("x", "/x.desktop", "Thing", exec='sh -c "echo 100%%; run %f" %i %c %k', icon="ico")
    assert desktop.command(quoted, ["/f"]) == ["sh", "-c", "echo 100%; run %f", "--icon", "ico", "Thing", "/x.desktop"]


def test_programs_plugin_reads_the_menu(linux, menus):
    p = plugins.Programs(menus, linux=True)
    got = p.query("dolph", None)
    assert [r.title for r in got] == ["Dolphin"] and got[0].action["type"] == "app"
    assert got[0].action["path"].endswith("org.kde.dolphin.desktop")


def test_linux_plans(linux, menus, tmp_path):
    dolphin = next(e for e in desktop.entries(menus) if e.name == "Dolphin")
    assert actions.plan({"type": "app", "path": dolphin.path}) == {"kind": "start", "args": ["dolphin"]}
    term = entry(tmp_path / "t", "top.desktop", "Type=Application\nName=Top\nExec=top -d 2\nTerminal=true\n")
    top = actions.plan({"type": "app", "path": str(term)})
    assert top["args"][:4] == ["x-terminal-emulator", "-e", "sh", "-c"] and top["args"][4].startswith("top -d 2;")
    shell = actions.plan({"type": "shell", "command": "ls -la ~"})
    assert shell["args"][4] == 'ls -la ~; exec "${SHELL:-/bin/bash}"'               # the terminal stays open
    admin = actions.plan({"type": "shell", "command": "apt update"}, admin=True)
    assert admin["args"][4].startswith("sudo sh -c 'apt update';")
    assert actions.plan({"type": "open", "path": "/home/ari/a.pdf"}) == {"kind": "start", "args": ["xdg-open", "/home/ari/a.pdf"]}
    assert actions.plan({"type": "url", "url": "https://example.com"})["args"] == ["xdg-open", "https://example.com"]
    folder = actions.plan({"type": "folder", "path": str(term)}, find=lambda app: "/usr/bin/pr7-e" if app == "PR7-E" else None)
    assert folder["args"] == ["/usr/bin/pr7-e", str(term.parent)]
    assert actions.plan({"type": "folder", "path": str(term)}, find=lambda app: None)["args"] == ["xdg-open", str(term.parent)]
    assert actions.plan({"type": "system", "command": "lock"})["args"] == ["loginctl", "lock-session"]
    assert actions.plan({"type": "system", "command": "shutdown"})["args"] == ["systemctl", "poweroff"]
    assert actions.plan({"type": "system", "command": "emptybin"})["args"] == ["kioclient", "empty", "trash:/"]
    assert actions.plan({"type": "family", "app": "PR7-W", "path": "/a.txt"},
                        find=lambda app: "/usr/bin/pr7-w")["args"] == ["/usr/bin/pr7-w", "/a.txt"]


def test_system_items_use_linux_words(linux):
    titles = {r.title: r.subtitle for r in plugins.System().query("empty", None)}
    assert titles == {"Empty Trash": "Delete everything in the Trash"}
    assert "Plasma" in plugins.System().query("sign out", None)[0].subtitle


@pytest.mark.skipif(sys.platform == "win32", reason="Linux's recently-used.xbel (file:// addresses of Linux paths)")
def test_recent_files_from_recently_used_xbel(tmp_path):
    old, new = tmp_path / "old report.odt", tmp_path / "new report.odt"
    old.write_text("o"); new.write_text("n")
    xbel = tmp_path / "recently-used.xbel"
    xbel.write_text('<?xml version="1.0"?>\n<xbel version="1.0">'
                    f'<bookmark href="file://{str(old).replace(" ", "%20")}" modified="2026-01-01T10:00:00Z"/>'
                    f'<bookmark href="file://{str(new).replace(" ", "%20")}" modified="2026-11-27T10:00:00Z"/>'
                    '<bookmark href="file:///gone/away.txt" modified="2026-11-28T10:00:00Z"/></xbel>')
    assert plugins.recent_xbel(str(xbel)) == [str(new), str(old)]          # newest first, gone files left out
    got = plugins.Files(str(xbel)).query("report", "f")
    assert [r.title for r in got][:2] and {r.title for r in got} == {"new report.odt", "old report.odt"}


@pytest.mark.skipif(sys.platform == "win32", reason="Linux's autostart")
def test_start_at_sign_in(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "xdg"))
    assert tray.start_with_windows() is False
    tray.start_with_windows(True)
    assert "--tray" in (tmp_path / "config/autostart/paragon-pr7-ln.desktop").read_text()
    (tmp_path / "xdg/autostart").mkdir(parents=True)
    (tmp_path / "xdg/autostart/paragon-pr7-ln.desktop").write_text("[Desktop Entry]\nExec=pr7-ln --tray\n")
    tray.start_with_windows(False)                                          # PR7-OS starts it: your Hidden=true says no
    assert "Hidden=true" in (tmp_path / "config/autostart/paragon-pr7-ln.desktop").read_text()
    assert tray.start_with_windows() is False
