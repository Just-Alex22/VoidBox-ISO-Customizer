import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(24)

        # Header row: logo + title aligned
        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.setAlignment(Qt.AlignVCenter)

        logo_path = os.path.join(ASSETS_DIR, "logo.svg")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            px = QPixmap(logo_path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(px)
            logo_label.setFixedSize(40, 40)
            header_row.addWidget(logo_label)

        title = QLabel("Welcome to VoidBox")
        title.setObjectName("pageTitle")
        f = QFont()
        f.setPointSize(26)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignVCenter)
        header_row.addWidget(title)
        header_row.addStretch()

        subtitle = QLabel(
            "Create your own custom Void Linux ISO.\n"
            "This tool will guide you through the process step by step."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(header_row)
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
