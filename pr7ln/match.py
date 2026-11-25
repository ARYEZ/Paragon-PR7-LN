"""How well a query matches a name (no Qt), the way launchers rank: the whole name, then its start, then the start of
a word, then the words' initials ("vs" -> Visual Studio), then the letters in order. None: no match."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9]+")


def _fold(s: str) -> str:
    return s.casefold().strip()


def score(query: str, name: str) -> float | None:
    q, n = _fold(query), _fold(name)
    if not q:
        return 0.0
    if not n:
        return None
    if n == q:
        return 100.0
    if n.startswith(q):
        return 90.0 - min(20, len(n) - len(q)) * 0.2
    words = _WORD.findall(n)
    for i, w in enumerate(words):
        if w.startswith(q):
            return 80.0 - i
    initials = "".join(w[0] for w in words)
    if len(q) >= 2 and initials.startswith(q):
        return 70.0
    if q in n:
        return 60.0 - n.index(q) * 0.1
    parts = q.split()
    if len(parts) > 1 and all(any(w.startswith(p) for w in words) for p in parts):
        return 55.0
    # the letters in order (fuzzy), worth less the more spread out they are
    pos, gaps = -1, 0
    for ch in q.replace(" ", ""):
        nxt = n.find(ch, pos + 1)
        if nxt < 0:
            return None
        gaps += nxt - pos - 1
        pos = nxt
    return max(1.0, 40.0 - gaps)
