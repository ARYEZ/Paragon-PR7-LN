"""Windows shortcuts (.lnk) for the Startup folders (no Qt): PR7-E's reader (MS-SHLLINK's LinkInfo) and its test
shortcut writer."""

from __future__ import annotations

import struct
import sys
import uuid

WINDOWS = sys.platform == "win32"


def lnk_target(data: bytes) -> str | None:
    """The target path of a Windows shortcut (.lnk), from its LinkInfo (MS-SHLLINK 2.3): the local base path
    (Unicode if present) plus the common path suffix. None if the shortcut has no LinkInfo."""
    if len(data) < 0x4C or struct.unpack_from("<I", data, 0)[0] != 0x4C:
        return None
    flags = struct.unpack_from("<I", data, 0x14)[0]
    pos = 0x4C
    if flags & 0x1:                               # HasLinkTargetIDList
        pos += 2 + struct.unpack_from("<H", data, pos)[0]
    if not flags & 0x2:                           # HasLinkInfo
        return None
    li = pos
    size, hsize, liflags, _vol, base, _net, suffix = struct.unpack_from("<7I", data, li)
    if not liflags & 0x1:                         # VolumeIDAndLocalBasePath
        return None

    def cstr(off, wide):
        if wide:
            end = off
            while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
                end += 2
            return data[off:end].decode("utf-16-le", "replace")
        end = data.index(b"\0", off)
        return data[off:end].decode("mbcs" if WINDOWS else "cp1252", "replace")
    if hsize >= 0x24:
        base_u, suffix_u = struct.unpack_from("<2I", data, li + 28)
        path = cstr(li + base_u, True) + (cstr(li + suffix_u, True) if suffix_u else "")
    else:
        path = cstr(li + base, False) + cstr(li + suffix, False)
    return path or None


def make_lnk(target: str) -> bytes:
    """A minimal shortcut with a Unicode LinkInfo (tests, and the format reference)."""
    header = struct.pack("<I16sI", 0x4C, uuid.UUID("00021401-0000-0000-C000-000000000046").bytes_le, 0x2 | 0x80)
    header += b"\0" * (0x4C - len(header))
    base_a = b"\0"
    base_u = target.encode("utf-16-le") + b"\0\0"
    hsize = 0x24
    off_base = hsize
    off_suffix = off_base + len(base_a)
    off_base_u = off_suffix + 1
    off_suffix_u = off_base_u + len(base_u)
    body = base_a + b"\0" + base_u + b"\0\0"
    size = hsize + len(body)
    li = struct.pack("<9I", size, hsize, 0x1, 0, off_base, 0, off_suffix, off_base_u, off_suffix_u) + body
    return header + li
