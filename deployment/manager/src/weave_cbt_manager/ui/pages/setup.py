"""A staff-friendly welcome; database credentials belong to the installer."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from ..theme import button, label

class SetupPage(QWidget):
    install_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(32)
        copy = QVBoxLayout()
        copy.setSpacing(18)
        copy.addStretch()
        copy.addWidget(label("YOUR SCHOOL. YOUR SERVER.", "eyebrow"))
        copy.addWidget(label("A smoother start\nto every exam.", "heading"))
        copy.addWidget(label("Turn this computer into your school's Weave CBT server. We'll prepare everything you need, then guide you into Weave."))
        copy.addSpacing(8)
        for title, detail in [
            ("01  Prepare this computer", "We check Windows, storage and the local runtime."),
            ("02  Set up your server", "We install the services and secure the local database."),
            ("03  Connect your school", "Open Weave to pair your school and get exam-ready."),
        ]:
            copy.addWidget(label(title, "section"))
            copy.addWidget(label(detail))
        copy.addSpacing(10)
        self.install_button = button("Set up this computer  →", self.install_requested.emit, primary=True)
        copy.addWidget(self.install_button)
        copy.addWidget(label("Internet is needed for the initial download. Windows may need a restart."))
        copy.addStretch()
        layout.addLayout(copy, 6)
        hero = QFrame()
        hero.setObjectName("hero")
        right = QVBoxLayout(hero)
        right.setContentsMargins(32, 36, 32, 36)
        right.setSpacing(24)
        right.addWidget(label("WEAVE CBT / WINDOWS", "heroBody"))
        right.addStretch()
        right.addWidget(label("Ready for\nthe next\nbright mind.", "heroTitle"))
        right.addWidget(label("One local server.\nA connected classroom.\nMore room to focus.", "heroBody"))
        right.addStretch()
        right.addWidget(label("Built for your school network", "heroBody"))
        layout.addWidget(hero, 5)
