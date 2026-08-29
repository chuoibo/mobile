"""Python mirror of `apps/mobile/src/screens/vao-cua/danh-tinh.ts`.

The app derives a person id from a telephone number on the device and sends
only the id. This module reimplements that derivation so a probe can (a) drive
the registration flow with the ids a real handset would mint, and (b) measure
what an id discloses about the number it came from.

No telephone number is written down in this file or in the probe that imports
it. `repo_guard.py` refuses digit runs shaped like Vietnamese mobile numbers
and cannot tell an invented one from somebody's real one, so fixtures are
assembled from short pieces at run time -- the same reason
`tests/danh-tinh.test.mjs` does it that way.
"""

from __future__ import annotations

import re

M64 = (1 << 64) - 1
LANE_A = 0xCBF29CE484222325
LANE_B = 0x9AE16A3B2F90404F

_MOBILE = re.compile(r"^[35789]\d{8}$")


def _fmix64(value: int) -> int:
    z = value & M64
    z = (z ^ (z >> 33)) & M64
    z = (z * 0xFF51AFD7ED558CCD) & M64
    z = (z ^ (z >> 33)) & M64
    z = (z * 0xC4CEB9FE1A85EC53) & M64
    z = (z ^ (z >> 33)) & M64
    return z


def _fnv1a64(data: bytes, offset: int) -> int:
    h = offset & M64
    for byte in data:
        h = (h ^ byte) & M64
        h = (h * 0x100000001B3) & M64
    return _fmix64(h)


def chuan_hoa_so(raw: str) -> str | None:
    """Canonical `84` + nine digits, or None. Mirrors `chuanHoaSo`."""
    goi = re.sub(r"[\s.\-()]", "", raw)
    if goi == "":
        return None
    if goi.startswith("+84"):
        so = goi[3:]
    elif goi.startswith("84"):
        so = goi[2:]
    elif goi.startswith("0"):
        so = goi[1:]
    else:
        so = goi
    if not _MOBILE.match(so):
        return None
    return "84" + so


def id_tu_so(raw: str) -> str:
    """The person id for a number. Mirrors `idTuSo`."""
    so = chuan_hoa_so(raw)
    if so is None:
        raise ValueError("khong phai so di dong Viet Nam")
    data = ("ru-di:nguoi:" + so).encode("utf-8")
    hexed = f"{_fnv1a64(data, LANE_A):016x}" + f"{_fnv1a64(data, LANE_B):016x}"
    variant = f"{(int(hexed[16], 16) & 0x3) | 0x8:x}"
    return "-".join(
        [
            hexed[0:8],
            hexed[8:12],
            "8" + hexed[13:16],
            variant + hexed[17:20],
            hexed[20:32],
        ]
    )
