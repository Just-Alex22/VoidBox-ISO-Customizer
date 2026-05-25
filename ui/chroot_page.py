import os
import subprocess
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QPlainTextEdit
)
from PySide6.QtCore import Qt, QTimer, QProcess

try:
    import vb_mount
    _NATIVE_MOUNT = True
except ImportError:
    _NATIVE_MOUNT = False

BIND_MOUNTS = ["/dev", "/dev/pts", "/proc", "/sys"]
SCRIPT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ChrootPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window      = parent
        self._extract_proc     = None
        self._xterm_proc       = None
        self._poll_timer       = None
        self._work_dir         = None
        self._rootfs_dir       = None
        self._ready            = False
        self._chroot_completed = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title  = QLabel("Customize - Interactive Chroot")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("Preparing...")
        self.status_label.setObjectName("statusLabel")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.subtitle = QLabel(
            "A terminal window will open with the Void Linux chroot. "
            "Install packages, edit configs, modify /etc/os-release - anything you need. "
            "Close the terminal when done."
        )
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.log_label = QLabel("Log:")
        self.log_label.setObjectName("logHeader")
        layout.addWidget(self.log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        layout.addWidget(self.log_view, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_done = QPushButton("Done - chroot finished")
        self.btn_done.setObjectName("btnPrimary")
        self.btn_done.setEnabled(False)
        self.btn_done.clicked.connect(self._on_done)
        btn_row.addWidget(self.btn_done)
        layout.addLayout(btn_row)

    def on_enter(self):
        # Reset state for re-entry
        self._chroot_completed = False
        self._ready = False
        self.btn_done.setEnabled(False)
        self._main_window.btn_next.setVisible(False)
        self.log_view.clear()

        mw       = self._main_window
        iso_path = mw.state.get("iso_path")
        work_dir = mw.state.get("work_dir")

        if not work_dir:
            self.log_view.appendPlainText("[Error] No work directory set.")
            return

        self._work_dir   = work_dir
        self._rootfs_dir = os.path.join(work_dir, "rootfs")

        # If rootfs already exists, skip extraction
        if os.path.exists(os.path.join(self._rootfs_dir, "usr", "bin")):
            self.log_view.appendPlainText("[VoidBox] Existing rootfs found - resuming project.")
            mw.state["squashfs_dir"] = self._rootfs_dir
            self._prepare_chroot(self._rootfs_dir)
        else:
            if not iso_path or not os.path.exists(iso_path):
                self.log_view.appendPlainText(f"[Error] ISO not found: {iso_path}")
                return
            self.log_view.appendPlainText("[VoidBox] Starting extraction...")
            self._run_extract(iso_path, work_dir)

    def on_leave(self):
        if not self._chroot_completed:
            self._umount_all()

    def _run_extract(self, iso_path, work_dir):
        extractor = os.path.join(SCRIPT_DIR, "vb_extract.py")
        self._extract_proc = QProcess(self)
        self._extract_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._extract_proc.readyRead.connect(self._on_extract_output)
        self._extract_proc.finished.connect(self._on_extract_done)
        self._extract_proc.start("python3", [extractor, iso_path, work_dir])

    def _on_extract_output(self):
        data = bytes(self._extract_proc.readAll()).decode("utf-8", errors="replace")
        self.log_view.appendPlainText(data.rstrip())

    def _on_extract_done(self, exit_code, exit_status):
        if exit_code != 0:
            self.log_view.appendPlainText("\n[Error] Extraction failed.")
            self.status_label.setText("Extraction failed")
            self._main_window.btn_next.setVisible(True)
            self._main_window.btn_next.setEnabled(False)
            return

        if not os.path.exists(os.path.join(self._rootfs_dir, "usr", "bin")):
            self.log_view.appendPlainText("\n[Error] rootfs looks incomplete.")
            return

        self._main_window.state["squashfs_dir"] = self._rootfs_dir
        self._prepare_chroot(self._rootfs_dir)

    def _prepare_chroot(self, rootfs_dir):
        iso_path = self._main_window.state.get("iso_path")

        self.log_view.appendPlainText("[VoidBox] Setting up network...")
        self._copy_resolv_conf(rootfs_dir)

        self.log_view.appendPlainText("[VoidBox] Writing repository configuration...")
        self._write_repo_conf(rootfs_dir)

        if iso_path and os.path.exists(iso_path):
            self.log_view.appendPlainText("[VoidBox] Mounting ISO repo...")
            self._mount_iso_repo(iso_path, self._work_dir, rootfs_dir)

        self.log_view.appendPlainText("[VoidBox] Mounting filesystems...")
        self._do_bind_mounts(rootfs_dir)

        self.log_view.appendPlainText("[VoidBox] Launching chroot terminal...")
        QTimer.singleShot(300, lambda: self._spawn_terminal(rootfs_dir))

    def _mount_iso_repo(self, iso_path, work_dir, rootfs_dir):
        iso_mount_dir = os.path.join(work_dir, "iso_mount_repo")
        os.makedirs(iso_mount_dir, exist_ok=True)
        if not os.path.ismount(iso_mount_dir):
            subprocess.run(["mount", "-o", "loop,ro", iso_path, iso_mount_dir], capture_output=True)

        iso_repo_dir    = os.path.join(iso_mount_dir, "repo")
        chroot_repo_dir = os.path.join(rootfs_dir, "repo")
        if os.path.exists(iso_repo_dir):
            os.makedirs(chroot_repo_dir, exist_ok=True)
            if not os.path.ismount(chroot_repo_dir):
                subprocess.run(["mount", "--bind", iso_repo_dir, chroot_repo_dir], capture_output=True)
            self._extract_keys_from_iso_repo(iso_repo_dir, rootfs_dir)

    def _extract_keys_from_iso_repo(self, iso_repo_dir, rootfs_dir):
        keys_dir = os.path.join(rootfs_dir, "var", "db", "xbps", "keys")
        os.makedirs(keys_dir, exist_ok=True)
        if os.listdir(keys_dir):
            return
        for root, dirs, files in os.walk(iso_repo_dir):
            for f in files:
                if f.startswith("xbps-keys") and f.endswith(".xbps"):
                    try:
                        subprocess.run(["tar", "-xf", os.path.join(root, f), "-C", rootfs_dir],
                                       capture_output=True, check=True)
                        self.log_view.appendPlainText("GPG keys extracted.")
                    except Exception as e:
                        self.log_view.appendPlainText(f"[Warning] Could not extract keys: {e}")
                    return

    def _write_repo_conf(self, rootfs_dir):
        xbps_d = os.path.join(rootfs_dir, "etc", "xbps.d")
        os.makedirs(xbps_d, exist_ok=True)

        if os.path.ismount(os.path.join(rootfs_dir, "repo")):
            with open(os.path.join(xbps_d, "00-repo-local.conf"), "w") as f:
                f.write("repository=/repo\n")

        arch = self._main_window.state.get("arch", "x86_64")
        if "musl" in arch:
            url = "https://repo-default.voidlinux.org/current/musl"
        elif "aarch64" in arch:
            url = "https://repo-default.voidlinux.org/current/aarch64"
        else:
            url = "https://repo-default.voidlinux.org/current"

        with open(os.path.join(xbps_d, "10-repo-network.conf"), "w") as f:
            f.write(f"repository={url}\n")

    def _copy_resolv_conf(self, rootfs_dir):
        src = "/etc/resolv.conf"
        dst = os.path.join(rootfs_dir, "etc", "resolv.conf")
        if not os.path.exists(src):
            return
        try:
            if os.path.islink(dst) or os.path.exists(dst):
                os.remove(dst)
            shutil.copy2(src, dst)
        except Exception as e:
            self.log_view.appendPlainText(f"[Warning] resolv.conf: {e}")

    def _do_bind_mounts(self, rootfs_dir):
        if _NATIVE_MOUNT:
            try:
                vb_mount.bind_all(rootfs_dir)
            except OSError as e:
                self.log_view.appendPlainText(f"[Warning] native bind: {e}")
        else:
            for src in BIND_MOUNTS:
                dst = rootfs_dir + src
                os.makedirs(dst, exist_ok=True)
                subprocess.run(["mount", "--bind", src, dst], capture_output=True)

        # Extra mounts not in BIND_MOUNTS
        security = os.path.join(rootfs_dir, "sys", "kernel", "security")
        os.makedirs(security, exist_ok=True)
        subprocess.run(["mount", "-t", "tmpfs", "tmpfs", security], capture_output=True)

        run_dst = os.path.join(rootfs_dir, "run")
        os.makedirs(run_dst, exist_ok=True)
        subprocess.run(["mount", "-t", "tmpfs", "tmpfs", run_dst], capture_output=True)

        dbus_src = "/run/dbus"
        if os.path.exists(dbus_src):
            dbus_dst = os.path.join(rootfs_dir, "run", "dbus")
            os.makedirs(dbus_dst, exist_ok=True)
            subprocess.run(["mount", "--bind", dbus_src, dbus_dst], capture_output=True)

    def _set_apparmor_complain(self, enable):
        profile = "/etc/apparmor.d/flatpak"
        if not os.path.exists(profile):
            return
        if not os.path.exists("/sys/kernel/security/apparmor"):
            return
        try:
            cmd = ["aa-complain" if enable else "aa-enforce", profile]
            subprocess.run(cmd, capture_output=True)
        except Exception:
            pass

    def _spawn_terminal(self, rootfs_dir):
        chroot_bin = shutil.which("chroot") or "/usr/sbin/chroot"
        env = os.environ.copy()
        env.update({
            "HOME": "/root",
            "TERM": "xterm-256color",
            "LANG": "C.UTF-8",
        })

        # Ensure XAUTHORITY is set — pkexec sometimes drops it
        if "XAUTHORITY" not in env or not os.path.exists(env.get("XAUTHORITY", "")):
            for candidate in [
                "/root/.Xauthority",
                "/tmp/.Xauthority",
                "/run/user/1000/gdm/Xauthority",
            ]:
                if os.path.exists(candidate):
                    env["XAUTHORITY"] = candidate
                    break

        # Allow root to connect to the user's X display
        display = env.get("DISPLAY", ":0")
        subprocess.run(["xhost", "+SI:localuser:root"],
                       env=env, capture_output=True)

        # Put flatpak AppArmor profile in complain while chroot is active
        self._set_apparmor_complain(True)

        try:
            self._xterm_proc = subprocess.Popen(
                ["xterm", "-display", display,
                 "-title", "VoidBox Chroot",
                 "-bg", "#111111", "-fg", "#d4d4d4",
                 "-fa", "Monospace", "-fs", "11",
                 "-e", chroot_bin, rootfs_dir, "/bin/bash", "--login"],
                env=env,
            )
        except FileNotFoundError:
            self._set_apparmor_complain(False)
            self.log_view.appendPlainText("[Error] xterm not found. Install: apt install xterm")
            self.btn_done.setEnabled(True)
            return

        self.log_view.appendPlainText(
            "Terminal open in separate window.\n"
            "Close it when done, then click 'Done' below."
        )
        self._ready = True
        self.status_label.setText("Chroot active")
        self.btn_done.setEnabled(True)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._check_xterm)
        self._poll_timer.start()

    def _check_xterm(self):
        if self._xterm_proc and self._xterm_proc.poll() is not None:
            self._poll_timer.stop()
            self._poll_timer = None
            self._on_chroot_closed()

    def _on_done(self):
        if self._xterm_proc and self._xterm_proc.poll() is None:
            self._xterm_proc.terminate()
            try:
                self._xterm_proc.wait(timeout=2)
            except Exception:
                self._xterm_proc.kill()
        self._on_chroot_closed()

    def _on_chroot_closed(self):
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

        self._set_apparmor_complain(False)
        self._umount_all()
        self._ready            = False
        self._chroot_completed = True
        self.status_label.setText("Chroot closed.")
        self.btn_done.setEnabled(False)
        self._main_window.btn_next.setVisible(True)
        self._main_window.btn_next.setEnabled(True)

    def _umount_all(self):
        rootfs = self._rootfs_dir
        if not rootfs:
            return

        # Always unmount everything manually in correct order regardless of _NATIVE_MOUNT
        # Deepest/most specific first, then progressively shallower
        all_mounts = [
            os.path.join(rootfs, "run", "dbus"),
            os.path.join(rootfs, "run", "user"),
            os.path.join(rootfs, "sys", "kernel", "security"),
            os.path.join(rootfs, "sys", "firmware", "efi", "efivars"),
            os.path.join(rootfs, "repo"),
            os.path.join(rootfs, "dev", "pts"),
            os.path.join(rootfs, "dev", "shm"),
            os.path.join(rootfs, "dev"),
            os.path.join(rootfs, "proc"),
            os.path.join(rootfs, "sys"),
            os.path.join(rootfs, "run"),
        ]

        for dst in all_mounts:
            if os.path.ismount(dst):
                r = subprocess.run(["umount", "-l", dst], capture_output=True)
                if r.returncode != 0:
                    # Force unmount if lazy failed
                    subprocess.run(["umount", "-f", dst], capture_output=True)

        # Read /proc/mounts and unmount anything still under rootfs
        try:
            with open("/proc/mounts") as f:
                mounts = f.readlines()
            # Reverse order so deepest paths unmount first
            remaining = sorted(
                [line.split()[1] for line in mounts if rootfs in line.split()[1]],
                reverse=True
            )
            for dst in remaining:
                subprocess.run(["umount", "-l", dst], capture_output=True)
        except Exception:
            pass

        iso_mount = os.path.join(self._work_dir, "iso_mount_repo") if self._work_dir else None
        if iso_mount and os.path.ismount(iso_mount):
            subprocess.run(["umount", "-l", iso_mount], capture_output=True)

    def validate(self):
        if self._chroot_completed:
            return True, ""
        if self._ready:
            return False, "Please close the chroot terminal before continuing."
        return False, "Extraction or chroot setup is not complete."
