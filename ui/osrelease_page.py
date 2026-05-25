from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFormLayout,
    QLineEdit, QFrame, QScrollArea
)
from PySide6.QtCore import Qt

DEFAULT_FIELDS = {
    "NAME": "Void Linux", "PRETTY_NAME": "Void Linux", "ID": "void",
    "ID_LIKE": "", "ANSI_COLOR": "1;33",
    "HOME_URL": "https://voidlinux.org/",
    "DOCUMENTATION_URL": "https://docs.voidlinux.org/",
    "SUPPORT_URL": "https://voidlinux.org/community/",
    "BUG_REPORT_URL": "https://github.com/void-linux/void-packages/issues",
    "LOGO": "void-logo", "BUILD_ID": "rolling",
}

FIELD_HINTS = {
    "NAME": "Short OS name", "PRETTY_NAME": "Full display name",
    "ID": "Machine-readable ID, lowercase, no spaces",
    "ID_LIKE": "Parent distros, space-separated",
    "ANSI_COLOR": "Terminal color code",
    "HOME_URL": "Project homepage URL", "DOCUMENTATION_URL": "Documentation URL",
    "SUPPORT_URL": "Community/support URL", "BUG_REPORT_URL": "Bug tracker URL",
    "LOGO": "Icon name from icon theme", "BUILD_ID": "Version/build identifier",
}


class OsReleasePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(60, 60, 60, 40)
        outer.setSpacing(24)

        title = QLabel("Edit OS Identity")
        title.setObjectName("pageTitle")
        subtitle = QLabel("These values will be written to <code>/etc/os-release</code> inside the chroot.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        outer.addWidget(title)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("formScroll")

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        for key, default in DEFAULT_FIELDS.items():
            label = QLabel(f"<b>{key}</b>")
            label.setObjectName("formKey")
            label.setToolTip(FIELD_HINTS.get(key, ""))

            edit = QLineEdit(default)
            edit.setObjectName("formEdit")
            edit.setPlaceholderText(FIELD_HINTS.get(key, ""))
            edit.setMinimumWidth(340)

            self._fields[key] = edit
            form.addRow(label, edit)

        scroll.setWidget(form_widget)
        outer.addWidget(scroll, stretch=1)

    def get_data(self):
        return {k: v.text().strip() for k, v in self._fields.items()}

    def validate(self):
        data = self.get_data()
        if not data.get("NAME"):
            return False, "NAME field cannot be empty."
        if not data.get("ID"):
            return False, "ID field cannot be empty."
        if " " in data.get("ID", ""):
            return False, "ID must not contain spaces."
        return True, ""
