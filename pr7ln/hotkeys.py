"""The key that works from any program (Windows' RegisterHotKey): Alt+Space opens the launcher, as in Flow Launcher.

Windows delivers them as WM_HOTKEY messages to this program; a native event filter turns those into callbacks.
A key another program already holds can't be registered: `register` reports which, so PR7-LN can say so and the
key can be changed in Options. (PR7-CB's module, PR7-Q's with the punctuation keys.)"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312
NAMED_KEYS = {"print": 0x2C, "printscreen": 0x2C, "prtsc": 0x2C, "pause": 0x13, "scrolllock": 0x91,
              "insert": 0x2D, "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdown": 0x22}
NAMED_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})
# punctuation on a US layout: Windows' VK_OEM_* codes (the key's place, whatever the layout prints on it)
NAMED_KEYS.update({"`": 0xC0, "~": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA,
                   "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "space": 0x20})

DEFAULT_KEYS = {"show": "Alt+Space"}


def parse(text: str) -> tuple[int, int] | None:
    """"Ctrl+Shift+Print" -> (modifiers, virtual key), or None if it isn't a key Windows can register."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        m = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN,
             "meta": MOD_WIN}.get(p)
        if m is None:
            return None
        mods |= m
    key = parts[-1]
    if key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        return None
    return mods, vk


def available() -> bool:
    return sys.platform == "win32"


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.owner.ids:
                self.owner.ids[msg.wParam]()
                return True, 0
        return False, 0


class Hotkeys:
    """register({"region": ("Print", callback), ...}) -> {name: problem} for the keys that couldn't be had."""

    def __init__(self):
        self.ids: dict[int, callable] = {}
        self._filter = None
        self._next = 0xA000

    def register(self, keys: dict[str, tuple[str, callable]]) -> dict[str, str]:
        self.unregister()
        problems = {}
        if not available():
            return {name: "Keys that work from any program are a Windows feature." for name in keys}
        import ctypes
        user32 = ctypes.windll.user32
        if self._filter is None:
            self._filter = _Filter(self)
            QCoreApplication.instance().installNativeEventFilter(self._filter)
        for name, (text, callback) in keys.items():
            if not text:
                continue
            parsed = parse(text)
            if parsed is None:
                problems[name] = f"{text} isn't a key PR7-LN can use."
                continue
            mods, vk = parsed
            hid = self._next
            self._next += 1
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                self.ids[hid] = callback
            else:
                problems[name] = f"{text} is taken by another program: choose another key in Options."
        return problems

    def unregister(self) -> None:
        if available() and self.ids:
            import ctypes
            for hid in list(self.ids):
                ctypes.windll.user32.UnregisterHotKey(None, hid)
        self.ids.clear()
