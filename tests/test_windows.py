"""What only real Windows can show (CI runs these): the key, the start-up entry, the real Start menu, running a plan."""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only (CI)")


def test_the_key_registers_and_lets_go(qapp):
    from pr7ln import hotkeys
    h = hotkeys.Hotkeys()
    problems = h.register({"show": ("Ctrl+Alt+Shift+F24", lambda: None)})     # a key nothing else holds
    assert problems == {} and len(h.ids) == 1
    h.unregister()
    assert not h.ids


@pytest.mark.skipif(not os.environ.get("CI"), reason="writes the registry: CI only")
def test_start_with_windows():
    from pr7ln.tray import start_with_windows
    try:
        assert start_with_windows(True) and start_with_windows() is True
        assert start_with_windows(False) is False and start_with_windows() is False
    finally:
        start_with_windows(False)


def test_the_real_start_menu():
    """The runner's Start menus hold real shortcuts (Windows' own tools at least): they're found and read."""
    from pr7ln.plugins import Programs
    p = Programs()
    p.load()
    assert len(p.items) > 3
    assert any(target.lower().endswith(".exe") for _name, _path, target in p.items)


def test_a_plan_really_runs(tmp_path):
    """A start plan runs for real: cmd writes a file, which shows it ran."""
    import time
    from pr7ln import actions
    out = tmp_path / "ran.txt"
    assert actions.run({"kind": "start", "args": ["cmd.exe", "/c", f"echo ran> \"{out}\""]})
    for _ in range(100):
        if out.exists() and out.read_text().strip():
            break
        time.sleep(0.05)
    assert out.read_text().strip() == "ran"
