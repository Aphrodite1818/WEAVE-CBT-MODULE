"""Native Qt presentation using the unpaired Weave frontend palette."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

STYLESHEET = """
QWidget { font-family: 'Segoe UI'; font-size: 14px; color: #0f172a; }
QMainWindow, QStackedWidget, QScrollArea, QWidget#page { background: #faf8f2; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #1d4ed8; font-size: 11px; font-weight: 700; }
QLabel#heading { font-size: 32px; font-weight: 700; }
QLabel#body { color: #64748b; font-size: 14px; }
QLabel#section { font-size: 18px; font-weight: 600; }
QLabel#brand { font-size: 25px; font-weight: 700; color: #1d4ed8; }
QLabel#badge { background: #eff6ff; color: #1d4ed8; border-radius: 12px; padding: 6px 12px; font-size: 12px; }
QFrame#card { background: #fffefa; border: 1px solid #e2e8f0; border-radius: 18px; }
QFrame#hero { background: #1555e8; border-radius: 20px; }
QFrame#hero QLabel { color: white; }
QLabel#heroTitle { font-size: 36px; font-weight: 700; }
QLabel#heroBody { color: #dbeafe; font-size: 15px; }
QPushButton { background: #fffefa; border: 1px solid #cbd5e1; border-radius: 10px; padding: 11px 17px; font-weight: 600; }
QPushButton:hover { background: #eff6ff; border-color: #93c5fd; }
QPushButton:focus { border: 2px solid #1d4ed8; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0; }
QPushButton#primary { background: #1d4ed8; color: white; border-color: #1d4ed8; }
QPushButton#primary:hover { background: #1e40af; }
QPushButton#primary:disabled { background: #94a3b8; border-color: #94a3b8; }
QPushButton#danger { color: #b91c1c; }
QPushButton#link { border: none; background: transparent; color: #64748b; padding: 6px; }
QProgressBar { border: none; background: #e2e8f0; border-radius: 4px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #1d4ed8; border-radius: 4px; }
QPlainTextEdit { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; font-family: Consolas; font-size: 12px; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

def label(text: str, role: str = "body") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.PlainText)
    return widget

def button(text: str, callback, *, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(lambda _checked=False: callback())
    return widget

def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(12)
    return frame, layout
