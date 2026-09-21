"""Generate the multi-resolution Windows icon used by the Manager and installer."""

from __future__ import annotations

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from weave_cbt_manager.ui.brand import MARK


SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def _render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(0)

    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Unable to create the in-memory icon buffer.")
    try:
        if not image.save(buffer, "PNG"):
            raise RuntimeError(f"Unable to render the {size}px Weave icon.")
    finally:
        buffer.close()
    return bytes(payload)


def _write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    # Windows ICO containers can embed PNG frames. This keeps the generated
    # multi-resolution icon compact while preserving the SVG mark cleanly at
    # high DPI. A width/height byte of zero represents 256 pixels.
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = bytearray()
    payload = bytearray()
    offset = 6 + (16 * len(images))

    for size, png in images:
        dimension = 0 if size == 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(png),
                offset,
            )
        )
        payload.extend(png)
        offset += len(png)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + directory + payload)


def main() -> int:
    application = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(MARK)
    if not renderer.isValid():
        raise RuntimeError("The embedded Weave SVG mark is invalid.")

    images = [(size, _render_png(renderer, size)) for size in SIZES]
    manager_root = Path(__file__).resolve().parents[1]
    destination = manager_root / "resources" / "weave.ico"
    _write_ico(destination, images)

    if not destination.is_file() or destination.stat().st_size < 1024:
        raise RuntimeError("The generated Weave Windows icon is invalid or empty.")

    application.processEvents()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
