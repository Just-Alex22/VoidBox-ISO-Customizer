from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal


COMPRESSION_OPTIONS = [
    {
        "id":    "xz",
        "label": "xz  (default)",
        "desc":  "Best compression ratio. Same as official Void Linux ISOs. Slow — expect 20-40 min on a typical rootfs.",
    },
    {
        "id":    "zstd",
        "label": "zstd",
        "desc":  "Fast compression with good ratio. Recommended for testing and development builds. Supported since kernel 4.14.",
    },
    {
        "id":    "lz4",
        "label": "lz4",
        "desc":  "Fastest compression. Largest output. Good for quick iteration when ISO size does not matter.",
    },
    {
        "id":    "gzip",
        "label": "gzip",
        "desc":  "Traditional compression. Compatible with all kernels. Decent speed and size.",
    },
    {
        "id":    "lzo",
        "label": "lzo",
        "desc":  "Fast decompression. Good for systems with limited CPU.",
    },
]


class CompressionCard(QFrame):
    selected = Signal(str)

    def __init__(self, option, parent=None):
        super().__init__(parent)
        self.option_id = option["id"]
        self._selected = False
        self.setObjectName("isoCard")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
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

    def set_selected(self, selected: bool):
        self._selected = selected
        self.radio.setText("●" if selected else "○")
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.selected.emit(self.option_id)
        super().mousePressEvent(event)


class CompressionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id = "xz"
        self._cards = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(20)

        title = QLabel("Compression Algorithm")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Choose the squashfs compression algorithm for the ISO. "
            "This affects both the final ISO size and the time it takes to build."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        for opt in COMPRESSION_OPTIONS:
            card = CompressionCard(opt)
            card.selected.connect(self._on_select)
            self._cards[opt["id"]] = card
            layout.addWidget(card)

        layout.addStretch()

        # Select xz by default
        self._cards["xz"].set_selected(True)

    def _on_select(self, option_id: str):
        self._selected_id = option_id
        for cid, card in self._cards.items():
            card.set_selected(cid == option_id)

    def get_selection(self):
        return self._selected_id

    def validate(self):
        if not self._selected_id:
            return False, "Please select a compression algorithm."
        return True, ""
