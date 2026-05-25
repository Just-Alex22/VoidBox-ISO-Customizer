import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QFrame, QFileDialog, QPushButton
)
from PySide6.QtCore import Qt, Signal

ISO_OPTIONS = [
    {"id": "x86_64",      "label": "x86_64  (glibc)",   "desc": "Standard 64-bit build using the GNU C Library. Best compatibility - recommended for most hardware."},
    {"id": "x86_64-musl", "label": "x86_64  (musl)",    "desc": "64-bit build using the musl libc. Lighter footprint, great for containers and minimal systems."},
    {"id": "aarch64",     "label": "aarch64  (glibc)",  "desc": "64-bit ARM build (glibc). Supports Raspberry Pi 4/5, Pinebook Pro, and other AArch64 SBCs."},
    {"id": "custom",      "label": "Load my own ISO",   "desc": "Use a local ISO file you already have. Must be a Void Linux live ISO."},
]


class IsoCard(QFrame):
    selected = Signal(str)

    def __init__(self, option, parent=None):
        super().__init__(parent)
        self.option_id = option["id"]
        self._selected = False
        self.setObjectName("isoCard")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.radio = QLabel("○")
        self.radio.setObjectName("isoRadio")
        self.radio.setFixedWidth(20)
        title = QLabel(option["label"])
        title.setObjectName("isoCardTitle")
        header.addWidget(self.radio)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        desc = QLabel(option["desc"])
        desc.setObjectName("isoCardDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        if option["id"] == "custom":
            path_row = QHBoxLayout()
            self.path_label = QLabel("No file selected")
            self.path_label.setObjectName("isoCardDesc")
            self.path_label.setWordWrap(True)
            self.btn_browse = QPushButton("Browse...")
            self.btn_browse.setObjectName("btnSecondary")
            self.btn_browse.setFixedWidth(90)
            self.btn_browse.clicked.connect(self._browse)
            path_row.addWidget(self.path_label, stretch=1)
            path_row.addWidget(self.btn_browse)
            layout.addLayout(path_row)
        self._custom_path = None

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select ISO", os.path.expanduser("~"), "ISO Images (*.iso)"
        )
        if path:
            self._custom_path = path
            self.path_label.setText(path)
            self.selected.emit(self.option_id)
            self.set_selected(True)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.radio.setText("●" if selected else "○")
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if self.option_id == "custom":
            if not self._custom_path:
                self._browse()
            else:
                self.selected.emit(self.option_id)
        else:
            self.selected.emit(self.option_id)
        super().mousePressEvent(event)

    def get_custom_path(self):
        return self._custom_path


class IsoSelectorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id = None
        self._cards = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(20)

        title = QLabel("Select Base ISO")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Choose the Void Linux variant to use as your base. The ISO will be downloaded automatically, or load your own.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        for opt in ISO_OPTIONS:
            card = IsoCard(opt)
            card.selected.connect(self._on_select)
            self._cards[opt["id"]] = card
            layout.addWidget(card)

        layout.addStretch()

    def _on_select(self, option_id):
        self._selected_id = option_id
        for cid, card in self._cards.items():
            card.set_selected(cid == option_id)

    def get_selection(self):
        return self._selected_id

    def get_custom_path(self):
        return self._cards["custom"].get_custom_path()

    def validate(self):
        if not self._selected_id:
            return False, "Please select an ISO variant before continuing."
        if self._selected_id == "custom":
            path = self.get_custom_path()
            if not path:
                return False, "Please select an ISO file."
            if not os.path.exists(path):
                return False, f"File not found:\n{path}"
        return True, ""
