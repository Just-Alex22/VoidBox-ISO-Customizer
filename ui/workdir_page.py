import os
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QFileDialog, QFrame, QScrollArea
)
from PySide6.QtCore import Qt

RECENT_FILE = os.path.join(os.path.expanduser("~"), ".voidbox_recent.json")
MAX_RECENT  = 5


def load_recent():
    try:
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE) as f:
                data = json.load(f)
            return [d for d in data if os.path.isdir(d)]
    except Exception:
        pass
    return []


def save_recent(path):
    recent = load_recent()
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    recent = recent[:MAX_RECENT]
    try:
        with open(RECENT_FILE, "w") as f:
            json.dump(recent, f)
    except Exception:
        pass


def detect_project(work_dir):
    if not work_dir or not os.path.isdir(work_dir):
        return {"has_rootfs": False, "rootfs_dir": None, "iso_path": None}

    rootfs    = os.path.join(work_dir, "rootfs")
    has_rootfs = os.path.exists(os.path.join(rootfs, "usr", "bin"))

    iso_path = None
    try:
        for f in sorted(os.listdir(work_dir)):
            if f.endswith(".iso"):
                iso_path = os.path.join(work_dir, f)
                break
    except Exception:
        pass

    return {
        "has_rootfs": has_rootfs,
        "rootfs_dir": rootfs if has_rootfs else None,
        "iso_path":   iso_path,
    }


class ProjectCard(QFrame):
    def __init__(self, work_dir, info, on_click, parent=None):
        super().__init__(parent)
        self.work_dir = work_dir
        self._on_click = on_click
        self.setObjectName("isoCard")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        name = QLabel(os.path.basename(work_dir))
        name.setObjectName("isoCardTitle")

        path_label = QLabel(work_dir)
        path_label.setObjectName("isoCardDesc")
        path_label.setWordWrap(True)

        status_parts = []
        if info["has_rootfs"]:
            status_parts.append("rootfs extracted")
        if info["iso_path"]:
            status_parts.append(f"ISO: {os.path.basename(info['iso_path'])}")
        status_text = "  |  ".join(status_parts) if status_parts else "Empty project"

        status = QLabel(status_text)
        status.setObjectName("isoCardDesc")

        layout.addWidget(name)
        layout.addWidget(path_label)
        layout.addWidget(status)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self._on_click(self.work_dir)
        super().mousePressEvent(event)


class WorkdirPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window  = parent
        self._selected_dir = None
        self._cards        = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(20)

        title = QLabel("Work Directory")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Choose where VoidBox stores the extracted rootfs, ISO, and build files. "
            "Select an existing project to resume it, or pick a new directory."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Browse row
        browse_card = QFrame()
        browse_card.setObjectName("infoCard")
        browse_layout = QHBoxLayout(browse_card)
        browse_layout.setContentsMargins(20, 14, 20, 14)

        browse_label = QLabel("New project - select or create a directory")
        browse_label.setObjectName("stepDesc")

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setObjectName("btnPrimary")
        self.btn_browse.setFixedWidth(120)
        self.btn_browse.clicked.connect(self._browse)

        browse_layout.addWidget(browse_label, stretch=1)
        browse_layout.addWidget(self.btn_browse)
        layout.addWidget(browse_card)

        # Selection status
        self.selected_label = QLabel("No directory selected.")
        self.selected_label.setObjectName("pageSubtitle")
        self.selected_label.setWordWrap(True)
        layout.addWidget(self.selected_label)

        # Recent projects label
        self.recent_title = QLabel("Recent projects:")
        self.recent_title.setObjectName("logHeader")
        layout.addWidget(self.recent_title)

        # Scrollable recent cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll, stretch=1)

    def on_enter(self):
        self._refresh_cards()

    def _refresh_cards(self):
        # Remove old cards
        for card in self._cards.values():
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        recent = load_recent()
        self.recent_title.setVisible(bool(recent))

        for work_dir in recent:
            info = detect_project(work_dir)
            card = ProjectCard(work_dir, info, self._select_dir, self.cards_widget)
            card.set_selected(work_dir == self._selected_dir)
            # Insert before the stretch
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            self._cards[work_dir] = card

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Work Directory", os.path.expanduser("~")
        )
        if path:
            self._select_dir(path)

    def _select_dir(self, path):
        os.makedirs(path, exist_ok=True)
        self._selected_dir = path
        save_recent(path)

        info = detect_project(path)
        parts = []
        if info["has_rootfs"]:
            parts.append("rootfs found - will resume.")
        if info["iso_path"]:
            parts.append(f"ISO: {os.path.basename(info['iso_path'])}")
        status = "  |  ".join(parts) if parts else "New project."
        self.selected_label.setText(f"{path}\n{status}")

        self._refresh_cards()

    def get_selection(self):
        return self._selected_dir

    def get_project_info(self):
        return detect_project(self._selected_dir)

    def validate(self):
        if not self._selected_dir:
            return False, "Please select a work directory before continuing."
        try:
            os.makedirs(self._selected_dir, exist_ok=True)
        except Exception as e:
            return False, f"Could not create directory:\n{e}"
        return True, ""
