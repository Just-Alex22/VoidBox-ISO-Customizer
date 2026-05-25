from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt


class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(24)

        title = QLabel("Welcome to VoidBox")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Create your own custom Void Linux ISO.\n"
            "This tool will guide you through the process step by step."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        card_title = QLabel("What this tool does")
        card_title.setObjectName("cardTitle")
        card_layout.addWidget(card_title)

        for num, text in [
            ("1", "Select a work directory - resume an existing project or start fresh"),
            ("2", "Select a Void Linux base ISO if needed (glibc, musl, or aarch64)"),
            ("3", "Download the ISO automatically if not already present"),
            ("4", "Drop into an interactive chroot - install packages, configure, edit os-release"),
            ("5", "Build your custom ISO ready to burn or boot"),
        ]:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(12)

            badge = QLabel(num)
            badge.setObjectName("stepBadge")
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignCenter)

            desc = QLabel(text)
            desc.setObjectName("stepDesc")
            desc.setWordWrap(True)

            h.addWidget(badge)
            h.addWidget(desc, stretch=1)
            card_layout.addWidget(row)

        layout.addWidget(card)

        warn = QLabel(
            "VoidBox requires root privileges and the following tools:\n"
            "unsquashfs  mksquashfs  xorriso  wget  xterm"
        )
        warn.setObjectName("warningLabel")
        warn.setWordWrap(True)
        layout.addWidget(warn)
        layout.addStretch()
