"""Pure-Python Xcursor ('Xcur') binary writer supporting multi-size and animated cursors.

Implements the official freedesktop Xcursor file format (version 1.0):
  - 16-byte file header ("Xcur", header=16, version=0x00010000, ntoc)
  - 12-byte TOC entries (type=0xFFFD0002, subtype=nominal_size, position)
  - 36-byte image chunk headers + premultiplied BGRA/ARGB32 pixel data
Zero external dependencies (no xcursorgen required).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

XCUR_MAGIC = b"Xcur"
XCUR_HEADER_SIZE = 16
XCUR_VERSION = 0x00010000
XCUR_IMAGE_TYPE = 0xFFFD0002
XCUR_IMAGE_HEADER_SIZE = 36
XCUR_IMAGE_VERSION = 1


@dataclass
class CursorFrame:
    nominal_size: int
    width: int
    height: int
    xhot: int
    yhot: int
    delay_ms: int
    argb_premul_bytes: bytes  # little-endian 0xAARRGGBB (BGRA bytes on x86_64)


def write_xcursor(path: Path, frames: list[CursorFrame]) -> None:
    """Write one or more CursorFrames (multi-size and/or animated) to an Xcursor binary."""
    if not frames:
        raise ValueError("Cannot write empty Xcursor file")

    ntoc = len(frames)
    toc_offset = XCUR_HEADER_SIZE
    data_offset = toc_offset + ntoc * 12

    toc_entries: list[bytes] = []
    chunks: list[bytes] = []
    pos = data_offset

    for f in frames:
        expected_len = f.width * f.height * 4
        if len(f.argb_premul_bytes) != expected_len:
            raise ValueError(
                f"Expected {expected_len} pixel bytes for {f.width}x{f.height}, got {len(f.argb_premul_bytes)}"
            )
        toc_entries.append(struct.pack("<III", XCUR_IMAGE_TYPE, f.nominal_size, pos))
        chunk_hdr = struct.pack(
            "<IIIIIIIII",
            XCUR_IMAGE_HEADER_SIZE,
            XCUR_IMAGE_TYPE,
            f.nominal_size,
            XCUR_IMAGE_VERSION,
            f.width,
            f.height,
            f.xhot,
            f.yhot,
            f.delay_ms,
        )
        chunks.append(chunk_hdr)
        chunks.append(f.argb_premul_bytes)
        pos += XCUR_IMAGE_HEADER_SIZE + expected_len

    header = struct.pack("<4sIII", XCUR_MAGIC, XCUR_HEADER_SIZE, XCUR_VERSION, ntoc)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fp:
        fp.write(header)
        for entry in toc_entries:
            fp.write(entry)
        for chunk in chunks:
            fp.write(chunk)
