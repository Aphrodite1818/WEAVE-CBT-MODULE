"""Recoverable installation progress with a readable activity trail."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget
from ..theme import button, card, label

class InstallingPage(QWidget):
    restart_requested = Signal()
    retry_requested = Signal()
    logs_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(18)
        layout.addWidget(label("GETTING THINGS READY", "eyebrow"))
        self.title = label("Let's get your server ready.", "heading")
        layout.addWidget(self.title)
        layout.addWidget(label("Keep this computer connected to power and the internet while setup runs."))
        panel, content = card()
        self.message = label("Checking this computer…", "section")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        content.addWidget(self.message)
        content.addWidget(self.progress)
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(200)
        self.activity.setAccessibleName("Setup activity")
        content.addWidget(self.activity, 1)
        actions = QHBoxLayout()
        self.retry_button = button("Try again", self.retry_requested.emit, primary=True)
        self.restart_button = button("Restart Windows and continue", self.restart_requested.emit, primary=True)
        self.logs_button = button("Open diagnostic logs", self.logs_requested.emit)
        for widget in (self.retry_button, self.restart_button, self.logs_button):
            actions.addWidget(widget)
            widget.hide()
        actions.addStretch()
        content.addLayout(actions)
        layout.addWidget(panel, 1)
        layout.addWidget(label("Your progress is saved. Retrying keeps your existing school data and configuration."))

    def begin(self, message: str) -> None:
        self.title.setText("Let's get your server ready.")
        self.progress.show()
        self.retry_button.hide()
        self.restart_button.hide()
        self.logs_button.hide()
        self.set_message(message)

    def set_message(self, message: str) -> None:
        self.message.setText(message)
        self.activity.appendPlainText(message)

    def show_reboot(self) -> None:
        self.title.setText("A quick restart, then we're back.")
        self.set_message("Windows needs to restart. Sign back in with this Windows account and setup will resume.")
        self.progress.hide()
        self.restart_button.show()

    def show_error(self, message: str) -> None:
        self.title.setText("Let's get this sorted.")
        self.message.setText("Setup paused. Review the details below, then try again.")
        self.activity.appendPlainText("\n" + message)
        self.progress.hide()
        self.retry_button.show()
        self.logs_button.show()
