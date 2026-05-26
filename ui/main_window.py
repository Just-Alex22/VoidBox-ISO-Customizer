import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIcon

from ui.welcome_page      import WelcomePage
from ui.compression_page  import CompressionPage
from ui.workdir_page      import WorkdirPage
from ui.iso_selector_page import IsoSelectorPage
from ui.download_page     import DownloadPage
from ui.chroot_page       import ChrootPage
from ui.finish_page       import FinishPage

# Page indices — change here if order changes, nowhere else
P_WELCOME     = 0
P_WORKDIR     = 1
P_ISO         = 2
P_DOWNLOAD    = 3
P_CHROOT      = 4
P_COMPRESSION = 5
P_BUILD       = 6

PAGES = ["Welcome", "Work Directory", "Select ISO", "Download", "Customize", "Compression", "Build"]
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoidBox")
        self.setMinimumSize(900, 640)
        self.resize(960, 680)
        self.state = {
            "arch":         None,
            "iso_path":     None,
            "work_dir":     None,
            "squashfs_dir": None,
            "output_iso":   None,
        }
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        content = QWidget()
        content.setObjectName("contentArea")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self.stack = QStackedWidget()
        self.welcome_page      = WelcomePage(self)
        self.workdir_page      = WorkdirPage(self)
        self.iso_page          = IsoSelectorPage(self)
        self.download_page     = DownloadPage(self)
        self.chroot_page       = ChrootPage(self)
        self.compression_page  = CompressionPage(self)
        self.finish_page       = FinishPage(self)

        for page in [self.welcome_page, self.workdir_page, self.iso_page,
                     self.download_page, self.chroot_page, self.compression_page,
                     self.finish_page]:
            self.stack.addWidget(page)

        cl.addWidget(self.stack)
        cl.addWidget(self._build_nav_bar())
        root.addWidget(content, stretch=1)
        self._update_sidebar(0)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)



        self.step_widgets = []
        for i, name in enumerate(PAGES):
            w = self._make_step(i, name)
            layout.addWidget(w)
            self.step_widgets.append(w)

        layout.addStretch()
        footer = QLabel("v1.0-rc")
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
        return sidebar

    def _make_step(self, index, name):
        widget = QWidget()
        widget.setObjectName("stepWidget")
        h = QHBoxLayout(widget)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        badge = QLabel(str(index + 1))
        badge.setObjectName("stepNumber")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)

        label = QLabel(name)
        label.setObjectName("stepLabel")

        h.addWidget(badge)
        h.addWidget(label)
        h.addStretch()
        widget._badge = badge
        widget._label = label
        return widget

    def _build_nav_bar(self):
        bar = QFrame()
        bar.setObjectName("navBar")
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)

        self.btn_back = QPushButton("Back")
        self.btn_back.setObjectName("btnSecondary")
        self.btn_back.setFixedSize(100, 36)
        self.btn_back.clicked.connect(self.go_back)

        self.btn_next = QPushButton("Next")
        self.btn_next.setObjectName("btnPrimary")
        self.btn_next.setFixedSize(100, 36)
        self.btn_next.clicked.connect(self.go_next)

        layout.addWidget(self.btn_back)
        layout.addStretch()
        layout.addWidget(self.btn_next)
        return bar

    def _update_sidebar(self, index):
        for i, w in enumerate(self.step_widgets):
            state = "done" if i < index else ("active" if i == index else "pending")
            w.setProperty("state", state)
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()
            for child in w.findChildren(QLabel):
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
        self.btn_back.setEnabled(index > 0)
        self.btn_next.setVisible(index < len(PAGES) - 1)

    def _next_page(self, current):
        """Calculate which page to go to next, applying skip logic."""
        has_iso    = bool(self.state.get("iso_path"))
        has_rootfs = bool(self.state.get("squashfs_dir"))

        if current == P_WORKDIR:
            # If workdir already has ISO or rootfs, skip ISO selector
            if has_iso or has_rootfs:
                # If also has rootfs, skip download too
                if has_rootfs:
                    return P_CHROOT
                return P_DOWNLOAD
            return P_ISO

        if current == P_ISO:
            # custom ISO is already set in state, no need to download
            if self.state.get("arch") == "custom" or has_iso:
                return P_CHROOT
            return P_DOWNLOAD

        return current + 1

    def _prev_page(self, current):
        """Calculate which page to go back to, mirroring skip logic."""
        has_iso    = bool(self.state.get("iso_path"))
        has_rootfs = bool(self.state.get("squashfs_dir"))

        if current == P_BUILD:
            return P_COMPRESSION

        if current == P_CHROOT:
            return P_COMPRESSION

        if current == P_COMPRESSION:
            self.state["compression"] = self.compression_page.get_selection()
            return P_BUILD

        if current == P_DOWNLOAD:
            return P_ISO

        if current == P_ISO:
            return P_WORKDIR

        return current - 1

    def go_next(self):
        current = self.stack.currentIndex()
        page    = self.stack.currentWidget()

        if hasattr(page, "validate"):
            ok, msg = page.validate()
            if not ok:
                QMessageBox.warning(self, "VoidBox", msg)
                return

        if hasattr(page, "on_leave"):
            page.on_leave()

        # Collect state from current page
        if current == P_WORKDIR:
            info = self.workdir_page.get_project_info()
            self.state["work_dir"] = self.workdir_page.get_selection()
            if info["has_rootfs"]:
                self.state["squashfs_dir"] = info["rootfs_dir"]
            if info["iso_path"]:
                self.state["iso_path"] = info["iso_path"]
                iso_name = os.path.basename(info["iso_path"])
                if "musl" in iso_name:
                    self.state["arch"] = "x86_64-musl"
                elif "aarch64" in iso_name:
                    self.state["arch"] = "aarch64"
                else:
                    self.state["arch"] = "x86_64"

        elif current == P_COMPRESSION:
            self.state["compression"] = self.compression_page.get_selection()

        elif current == P_ISO:
            arch = self.iso_page.get_selection()
            self.state["arch"] = arch
            if arch == "custom":
                self.state["iso_path"] = self.iso_page.get_custom_path()

        self._go_to(self._next_page(current))

    def go_back(self):
        current = self.stack.currentIndex()
        if current > 0:
            if hasattr(self.stack.currentWidget(), "on_leave"):
                self.stack.currentWidget().on_leave()
            self._go_to(self._prev_page(current))

    def _go_to(self, index):
        self.stack.setCurrentIndex(index)
        self._update_sidebar(index)
        page = self.stack.currentWidget()
        if hasattr(page, "on_enter"):
            page.on_enter()

    def go_to_page(self, index):
        self._go_to(index)
