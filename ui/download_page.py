import os
import re
import tempfile

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QPlainTextEdit
)
from PySide6.QtCore import QProcess, Signal, QObject

VOID_LIVE_INDEX = "https://repo-default.voidlinux.org/live/current/"
ISO_URL_TEMPLATES = {
    "x86_64":      "void-live-x86_64-{date}-base.iso",
    "x86_64-musl": "void-live-x86_64-musl-{date}-base.iso",
    "aarch64":     "void-live-aarch64-{date}-base.iso",
}

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DownloadPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window  = parent
        self._done         = False
        self._dest_path    = None
        self._resolve_proc = None
        self._wget_proc    = None
        self._buf          = ""  # Buffer for partial wget output
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(20)

        self.title = QLabel("Downloading Base ISO")
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel("Please wait while the base ISO is downloaded.")
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("downloadProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        layout.addWidget(self.progress_bar)

        self.speed_label = QLabel("")
        self.speed_label.setObjectName("speedLabel")
        layout.addWidget(self.speed_label)

        log_label = QLabel("Download log:")
        log_label.setObjectName("logHeader")
        layout.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        layout.addWidget(self.log_view, stretch=1)

    def on_enter(self):
        if self._done:
            return

        # Prevent re-entrancy if processes are already running
        is_resolving = self._resolve_proc and self._resolve_proc.state() != QProcess.NotRunning
        is_downloading = self._wget_proc and self._wget_proc.state() != QProcess.NotRunning

        if is_resolving or is_downloading:
            return

        mw       = self._main_window
        self._arch = mw.state.get("arch", "x86_64")
        work_dir = mw.state.get("work_dir")
        if not work_dir:
            import tempfile
            work_dir = tempfile.mkdtemp(prefix="voidbox_")
            mw.state["work_dir"] = work_dir
        self._work_dir = work_dir

        # Reset UI if re-entered after a failure
        self.progress_bar.setValue(0)
        self.speed_label.setText("")

        self._log("Fetching mirror index...")
        self._resolve_latest()

    def on_leave(self):
        """Called when the user navigates away from the page. Cancels active downloads."""
        for proc in (self._resolve_proc, self._wget_proc):
            if proc and proc.state() != QProcess.NotRunning:
                proc.terminate()
                if not proc.waitForFinished(2000):
                    proc.kill()

    def _log(self, text):
        self.log_view.appendPlainText(text)

    def _resolve_latest(self):
        self._resolve_proc = QProcess(self)
        self._resolve_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._resolve_proc.finished.connect(self._on_resolve_done)
        self._resolve_proc.start(
            "wget", ["-qO-", "--timeout=15", VOID_LIVE_INDEX]
        )

    def _on_resolve_done(self, exit_code, exit_status):
        # 1. Check exit code of the resolve step
        if exit_code != 0:
            self._log(f"[Error] Failed to fetch mirror index (exit code {exit_code}).")
            self.subtitle.setText("Could not reach the mirror. Check your connection.")
            return

        html = bytes(self._resolve_proc.readAll()).decode("utf-8", errors="replace")

        # 2. Catch unsupported architectures before building broken URLs
        template = ISO_URL_TEMPLATES.get(self._arch)
        if not template:
            self._log(f"[Error] Unsupported architecture: {self._arch}")
            self.subtitle.setText(f"Unsupported architecture: {self._arch}")
            return

        prefix   = template.split("{date}")[0]
        pattern  = re.escape(prefix) + r'(\d{8})-base\.iso'
        matches  = re.findall(pattern, html)

        if not matches:
            self._log("[Error] Could not resolve latest ISO from mirror.")
            self.subtitle.setText("Could not find ISO on mirror.")
            return

        date     = sorted(set(matches))[-1]
        filename = template.format(date=date)
        url      = VOID_LIVE_INDEX + filename
        self._dest_path = os.path.join(self._work_dir, filename)

        self._log(f"Date : {date}")
        self._log(f"File : {filename}")
        self._log(f"URL  : {url}")
        self._log(f"Dest : {self._dest_path}")
        self._log("Starting download...")

        self._start_wget(url, self._dest_path)

    def _start_wget(self, url, dest):
        self._wget_proc = QProcess(self)
        self._wget_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wget_proc.readyRead.connect(self._on_wget_output)
        self._wget_proc.finished.connect(self._on_wget_done)

        # 3. Added --timeout=30 (stall detection) and -c (resume partial downloads)
        self._wget_proc.start(
            "wget", ["--progress=dot:giga", "--timeout=30", "-c", "-O", dest, url]
        )

    def _on_wget_output(self):
        data = bytes(self._wget_proc.readAll()).decode("utf-8", errors="replace")
        self._buf += data

        # 4. Buffer partial lines so we don't log garbled/cut-off text
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            line = line.strip()
            if not line:
                continue

            self._log(line)

            # Parse percentage
            m = re.search(r'(\d+)%', line)
            if m:
                pct = int(m.group(1))
                self.progress_bar.setValue(pct)

                # Parse speed (e.g., 5.60MB/s, 123KB/s)
                sm = re.search(r'([\d.]+\s*[KMG]?B/s)', line)
                if sm:
                    self.speed_label.setText(f"Speed: {sm.group(1)}")

    def _on_wget_done(self, exit_code, exit_status):
        # 5. File size validation: Ensure the download is actually an ISO and not an HTML error page
        if exit_code != 0:
            self._log(f"\n[Error] wget exited with code {exit_code}.")
            self.subtitle.setText("Download failed. See log above.")
            return

        if not os.path.exists(self._dest_path) or os.path.getsize(self._dest_path) < 100 * 1024 * 1024:
            self._log("\n[Error] Downloaded file is missing or suspiciously small (<100MB).")
            self.subtitle.setText("Download failed. File size is invalid.")
            return

        self._main_window.state["iso_path"] = self._dest_path
        self._done = True
        self.subtitle.setText(f"Download complete.\n{self._dest_path}")
        self.speed_label.setText("")
        self._log("Download complete.")

    def validate(self):
        if not self._done:
            return False, "Please wait for the download to complete."
        return True, ""
