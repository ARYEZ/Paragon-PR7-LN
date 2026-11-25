"""The launcher's brain (no Qt): which plugins a query goes to (a keyword first, "=" and ">" even without a space), the
results ranked by match and by how often each was picked (Flow Launcher's way), at most LIMIT, and a web search last
when nothing else fits."""

from __future__ import annotations

import json
import math
import os
import threading

from .plugins import Calculator, Clipboard, Family, Files, Plugin, Programs, Result, Shell, System, Web

LIMIT = 9
DEFAULT_OFF = {"clipboard"}       # the mock-up's Settings: PR7-CB's history is opt-in


class History:
    """How often each result was picked: <data>/history.json (PR7LN_DATA in tests)."""

    def __init__(self, path: str | None):
        self.path = path
        self.counts: dict[str, int] = {}
        self.lock = threading.Lock()
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    self.counts = {k: int(v) for k, v in json.load(f).items()}
            except (OSError, ValueError, AttributeError):
                self.counts = {}

    def boost(self, key: str) -> float:
        n = self.counts.get(key, 0) if key else 0
        return 12 * math.log2(1 + n)                 # the first picks count most; never more than a few ranks

    def picked(self, key: str):
        if not key:
            return
        with self.lock:
            self.counts[key] = self.counts.get(key, 0) + 1
            if self.path:
                try:
                    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                    tmp = self.path + ".part"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(self.counts, f)
                    os.replace(tmp, self.path)
                except OSError:
                    pass


def default_plugins(engine: str = "g") -> list[Plugin]:
    return [Programs(), Files(), Calculator(), Web(engine), Shell(), Family(), System(), Clipboard()]


class Engine:
    def __init__(self, plugins: list[Plugin] | None = None, history: History | None = None,
                 disabled: set[str] | None = None):
        self.plugins = plugins if plugins is not None else default_plugins()
        self.history = history or History(None)
        self.disabled = set(DEFAULT_OFF if disabled is None else disabled)

    def plugin(self, name: str) -> Plugin | None:
        return next((p for p in self.plugins if p.name == name), None)

    def split(self, text: str) -> tuple[Plugin | None, str | None, str]:
        """(plugin, keyword, the rest) when the query starts with an active keyword."""
        t = text.lstrip()
        for p in self.plugins:
            if p.name in self.disabled:
                continue
            for k in p.keywords:
                if k in ("=", ">") and t.startswith(k):
                    return p, k, t[len(k):].strip()
                if t.lower().startswith(k + " "):
                    return p, k, t[len(k) + 1:].strip()
                if t.lower() == k and k not in ("f",):
                    return p, k, ""
        return None, None, text.strip()

    def query(self, text: str) -> list[Result]:
        if not text.strip():
            return []
        plugin, keyword, rest = self.split(text)
        results: list[Result] = []
        if plugin is not None:
            results = list(plugin.query(rest, keyword))
        else:
            for p in self.plugins:
                if p.default and p.name not in self.disabled:
                    try:
                        results += p.query(rest, None)
                    except Exception:  # noqa: BLE001 - one plugin's trouble never empties the list
                        continue
        for r in results:
            r.score += self.history.boost(r.key)
        results.sort(key=lambda r: -r.score)
        results = results[:LIMIT]
        web = self.plugin("web")
        if plugin is None and web is not None and "web" not in self.disabled and len(results) < LIMIT:
            results += web.query(rest, None)                 # always offered last
        return results
