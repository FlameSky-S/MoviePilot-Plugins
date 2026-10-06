#!/usr/bin/env python3
"""Generate icons/AutoRenew.png (256x256 RGBA) using only the stdlib.

Run:  python tools/gen_icon.py
The PNG is committed to the repo; this script exists so the icon is reproducible.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

SIZE = 256
TEAL = (38, 166, 154, 255)
CLEAR = (0, 0, 0, 0)
CX = CY = (SIZE - 1) / 2.0
OUTER, INNER = 98.0, 70.0
GAP_START, GAP_END = 300.0, 340.0  # degrees of the ring removed by the "renew" gap


def _polar(angle_deg: float, radius: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (CX + radius * math.cos(angle), CY + radius * math.sin(angle))


def _in_ring(x: float, y: float) -> bool:
    dx, dy = x - CX, y - CY
    radius = math.hypot(dx, dy)
    if not (INNER <= radius <= OUTER):
        return False
    angle = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
    return not (GAP_START <= angle <= GAP_END)


def _tri_contains(px: float, py: float, a, b, c) -> bool:
    def cross(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1, d2, d3 = cross((px, py), a, b), cross((px, py), b, c), cross((px, py), c, a)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def main() -> None:
    tip = _polar(GAP_START - 26.0, (OUTER + INNER) / 2.0)
    base_outer = _polar(GAP_START, OUTER + 16.0)
    base_inner = _polar(GAP_START, INNER - 16.0)

    rows = []
    for y in range(SIZE):
        row = bytearray([0])  # PNG filter type 0 for this scanline
        for x in range(SIZE):
            hit = _in_ring(x, y) or _tri_contains(x, y, tip, base_outer, base_inner)
            row.extend(TEAL if hit else CLEAR)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")

    out = Path(__file__).resolve().parents[1] / "icons" / "AutoRenew.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
