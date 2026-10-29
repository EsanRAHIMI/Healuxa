#!/usr/bin/env python3
"""Generates placeholder brand assets (app icon, adaptive icon, splash mark) with the stdlib only.

The mark is a geometric bronze "H" monogram. Replace with the final brand artwork before release
(tracked in apps/mobile/store/README.md).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
BRONZE = (140, 106, 67, 255)
IVORY = (247, 244, 239, 255)
CLEAR = (0, 0, 0, 0)


def png(path: Path, size: int, pixel) -> None:
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            rows.extend(pixel(x / size, y / size))
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def monogram(u: float, v: float, scale: float) -> bool:
    # Normalised coordinates centred on the canvas, mark occupies `scale` of the width.
    x = (u - 0.5) / scale + 0.5
    y = (v - 0.5) / scale + 0.5
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return False
    left = 0.18 <= x <= 0.34 and 0.12 <= y <= 0.88
    right = 0.66 <= x <= 0.82 and 0.12 <= y <= 0.88
    bar = 0.34 <= x <= 0.66 and 0.46 <= y <= 0.56
    return left or right or bar


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    png(ASSETS / "icon.png", 1024, lambda u, v: BRONZE if monogram(u, v, 0.62) else IVORY)
    png(ASSETS / "adaptive-icon.png", 1024, lambda u, v: BRONZE if monogram(u, v, 0.42) else CLEAR)
    png(ASSETS / "splash-icon.png", 512, lambda u, v: BRONZE if monogram(u, v, 0.9) else CLEAR)
    print("assets written to", ASSETS)


if __name__ == "__main__":
    main()
