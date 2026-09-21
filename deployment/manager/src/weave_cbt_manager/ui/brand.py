"""Official unpaired Weave mark, shared by Qt and the Windows icon builder."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Keep these paths/colors aligned with frontend/src/shared/ui/index.jsx.
MARK = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none">
<defs>
<linearGradient id="blue" x1="64" y1="128" x2="448" y2="384" gradientUnits="userSpaceOnUse">
<stop stop-color="#60a5fa"/><stop offset=".45" stop-color="#1d4ed8"/><stop offset="1" stop-color="#1e3a8a"/>
</linearGradient>
<linearGradient id="gold" x1="448" y1="128" x2="64" y2="384" gradientUnits="userSpaceOnUse">
<stop stop-color="#fde68a"/><stop offset=".46" stop-color="#f59e0b"/><stop offset="1" stop-color="#b45309"/>
</linearGradient>
</defs><g fill="none" stroke-linecap="round">
<path d="M72 174c76 0 82 164 184 164s108-164 184-164" stroke="#bfdbfe" stroke-width="84" opacity=".7"/>
<path d="M72 174c76 0 82 164 184 164s108-164 184-164" stroke="url(#blue)" stroke-width="58"/>
<path d="M72 338c76 0 82-164 184-164s108 164 184 164" stroke="#fef3c7" stroke-width="84" opacity=".78"/>
<path d="M72 338c76 0 82-164 184-164s108 164 184 164" stroke="url(#gold)" stroke-width="58"/>
<path d="M188 256h136" stroke="#fff" stroke-width="18" opacity=".88"/>
</g></svg>'''


def mark_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(MARK).render(painter)
    painter.end()
    return pixmap


def application_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(mark_pixmap(size))
    return icon
