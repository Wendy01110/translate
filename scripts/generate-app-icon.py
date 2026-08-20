#!/usr/bin/env python3
"""Render the macOS app iconset from the editable SVG source."""

from __future__ import annotations

import subprocess
import struct
from pathlib import Path

from AppKit import NSBitmapImageFileTypePNG, NSBitmapImageRep, NSImage


ICON_SIZES: tuple[tuple[str, int], ...] = (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
)

ICNS_IMAGES: tuple[tuple[str, str], ...] = (
    ("icp4", "icon_16x16.png"),
    ("ic11", "icon_16x16@2x.png"),
    ("icp5", "icon_32x32.png"),
    ("ic12", "icon_32x32@2x.png"),
    ("ic07", "icon_128x128.png"),
    ("ic13", "icon_128x128@2x.png"),
    ("ic08", "icon_256x256.png"),
    ("ic14", "icon_256x256@2x.png"),
    ("ic09", "icon_512x512.png"),
    ("ic10", "icon_512x512@2x.png"),
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    source = root / "macos" / "AppIcon.svg"
    iconset = root / "macos" / "AppIcon.iconset"
    iconset.mkdir(exist_ok=True)

    image = NSImage.alloc().initWithContentsOfFile_(str(source))
    if image is None:
        raise RuntimeError(f"cannot render {source}")
    representation = NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
    if representation is None:
        raise RuntimeError(f"cannot rasterize {source}")
    png = representation.representationUsingType_properties_(
        NSBitmapImageFileTypePNG,
        {},
    )
    master = iconset / "icon_512x512@2x.png"
    if png is None or not png.writeToFile_atomically_(str(master), True):
        raise RuntimeError(f"cannot write {master}")

    for filename, size in ICON_SIZES:
        output = iconset / filename
        if output == master:
            continue
        subprocess.run(
            [
                "/usr/bin/sips",
                "-z",
                str(size),
                str(size),
                str(master),
                "--out",
                str(output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    chunks = []
    for icon_type, filename in ICNS_IMAGES:
        data = (iconset / filename).read_bytes()
        chunks.append(
            icon_type.encode("ascii") + struct.pack(">I", len(data) + 8) + data
        )
    payload = b"".join(chunks)
    icns = root / "macos" / "AppIcon.icns"
    icns.write_bytes(b"icns" + struct.pack(">I", len(payload) + 8) + payload)

    print(iconset)
    print(icns)


if __name__ == "__main__":
    main()
