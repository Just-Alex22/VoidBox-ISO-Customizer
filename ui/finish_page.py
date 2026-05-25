import os
import shutil
import subprocess
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar,
    QPlainTextEdit, QFileDialog, QPushButton, QHBoxLayout, QApplication
)
from PySide6.QtCore import QThread, Signal, QObject


class BuildWorker(QObject):
    log      = Signal(str)
    progress = Signal(int)
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, rootfs_dir, iso_path, work_dir, os_name):
        super().__init__()
        self.rootfs_dir = rootfs_dir
        self.iso_path   = iso_path
        self.work_dir   = work_dir
        self.os_name    = os_name.replace(" ", "_") or "void-custom"

    def _find_file(self, base_dir, filenames):
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f in filenames:
                    return os.path.join(root, f)
        return None

    def run(self):
        try:
            if hasattr(os, 'geteuid') and os.geteuid() != 0:
                self.error.emit("This operation requires root privileges (mount -o loop).")
                return

            # FIX: Prevent trying to mount the output ISO as the source ISO
            if self.iso_path.endswith("-custom.iso"):
                self.error.emit(
                    f"Source ISO ({self.iso_path}) looks like a custom build. "
                    "Please select the original official Void Linux ISO."
                )
                return

            if not os.path.exists(self.iso_path):
                self.error.emit(f"Source ISO not found: {self.iso_path}")
                return

            iso_out   = os.path.join(self.work_dir, f"{self.os_name}-custom.iso")
            iso_rw    = os.path.join(self.work_dir, "iso_rw")
            mount_dir = os.path.join(self.work_dir, "iso_mount")

            if os.path.exists(iso_out):
                os.remove(iso_out)

            # FIX: Clean up package caches and logs to prevent GBs of bloat
            self.log.emit("Cleaning package caches and logs from rootfs...")
            shutil.rmtree(os.path.join(self.rootfs_dir, "var/cache/xbps"), ignore_errors=True)
            shutil.rmtree(os.path.join(self.rootfs_dir, "var/log"), ignore_errors=True)
            shutil.rmtree(os.path.join(self.rootfs_dir, "var/tmp"), ignore_errors=True)

            self.log.emit("Repacking rootfs into squashfs...")
            self.log.emit("This may take several minutes depending on rootfs size.")
            self.progress.emit(5)

            new_squashfs = os.path.join(self.work_dir, "squashfs.img")
            if os.path.exists(new_squashfs):
                os.remove(new_squashfs)

            # FIX: Added "-Xbcj", "x86" to match Void's official compression
            proc = subprocess.Popen(
                ["mksquashfs", self.rootfs_dir, new_squashfs,
                 "-comp", "xz", "-b", "1M", "-noappend",
                 "-Xbcj", "x86"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r'(\d+)/(\d+)\s+(\d+)%', line)
                if m:
                    pct = int(m.group(3))
                    mapped = 5 + int(pct * 0.50)
                    self.progress.emit(mapped)
                elif not line.startswith("["):
                    self.log.emit(line)

            proc.wait()
            if proc.returncode != 0:
                self.error.emit("mksquashfs failed.")
                return

            size_mb = os.path.getsize(new_squashfs) // (1024 * 1024)
            self.log.emit(f"Squashfs ready: {size_mb} MB")
            self.progress.emit(55)

            self.log.emit("Copying ISO structure...")
            if os.path.exists(iso_rw):
                shutil.rmtree(iso_rw)
            if os.path.exists(mount_dir):
                shutil.rmtree(mount_dir)

            os.makedirs(mount_dir, exist_ok=True)
            os.makedirs(iso_rw, exist_ok=True)

            r = subprocess.run(
                ["mount", "-o", "loop,ro", self.iso_path, mount_dir],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                self.error.emit(f"Failed to mount original ISO: {r.stderr}")
                return

            try:
                r = subprocess.run(
                    ["rsync", "-aAX", f"{mount_dir}/.", iso_rw],
                    capture_output=True, text=True
                )
                if r.returncode != 0:
                    self.error.emit(f"rsync failed: {r.stderr}")
                    return
            finally:
                # FIX: Changed from "umount -l" to "umount -d" to free the loop device
                subprocess.run(["umount", "-d", mount_dir], capture_output=True)

            self.progress.emit(65)

            # Remove old ext3fs/rootfs images that confuse Dracut on boot
            self.log.emit("Checking for legacy ext images...")
            for root, dirs, files in os.walk(iso_rw):
                for f in files:
                    if f in ("rootfs.img", "ext3fs.img"):
                        target = os.path.join(root, f)
                        os.remove(target)
                        self.log.emit(f"Removed old ext image to prevent Dracut errors: {os.path.relpath(target, iso_rw)}")

            # Replace squashfs
            replaced = False
            for root, dirs, files in os.walk(iso_rw):
                for f in files:
                    if f == "squashfs.img" or f.endswith(".squashfs") or f.endswith(".sfs"):
                        target = os.path.join(root, f)
                        os.remove(target)
                        shutil.copy2(new_squashfs, target)
                        self.log.emit(f"Replaced: {os.path.relpath(target, iso_rw)}")
                        replaced = True
                        break
                if replaced:
                    break

            if not replaced:
                liveos = os.path.join(iso_rw, "LiveOS")
                os.makedirs(liveos, exist_ok=True)
                shutil.copy2(new_squashfs, os.path.join(liveos, "squashfs.img"))
                self.log.emit("Created: LiveOS/squashfs.img")

            self.progress.emit(75)

            # -----------------------------------------------------------------
            # FIX: SYNCHRONIZE VOLUME ID AND BOOT CONFIGURATIONS
            # Dracut fails if the GRUB config asks for CDLABEL=VOID_LIVE but the
            # ISO volume is named something else (e.g., FIGAROS). We must update them together.
            # -----------------------------------------------------------------
            custom_volid = re.sub(r'[^A-Z0-9_]', '_', self.os_name.upper())[:32]
            if not custom_volid:
                custom_volid = "VOID_LIVE"

            volid = custom_volid
            self.log.emit(f"Target ISO Volume ID: {volid}")

            self.log.emit("Updating boot configurations to match new Volume ID...")
            for root, dirs, files in os.walk(iso_rw):
                for f in files:
                    if f.endswith(".cfg"):  # grub.cfg, loopback.cfg, isolinux.cfg
                        cfg_path = os.path.join(root, f)
                        try:
                            with open(cfg_path, 'r', errors='ignore') as file:
                                content = file.read()

                            # Replace CDLABEL=XXX or LABEL=XXX with CDLABEL=<volid>
                            new_content = re.sub(
                                r'(CDLABEL|LABEL)=[A-Z0-9_]+',
                                f'CDLABEL={volid}',
                                content
                            )

                            if new_content != content:
                                with open(cfg_path, 'w') as file:
                                    file.write(new_content)
                                self.log.emit(f"Updated label in {os.path.relpath(cfg_path, iso_rw)}")
                        except Exception:
                            pass
            # -----------------------------------------------------------------

            self.log.emit("Building ISO with xorriso...")

            eltorito = self._find_file(iso_rw, ["eltorito.img", "boot.img"])
            efi_img  = self._find_file(iso_rw, ["efiboot.img", "efi.img", "EFI.img"])

            cmd = [
                "xorriso", "-as", "mkisofs",
                "-iso-level", "3",
                "-r",
                "-J",
                "-volid", volid,  # This now perfectly matches the grub.cfg update above
                "-output", iso_out,
                "-partition_offset", "16",
            ]

            if eltorito and os.path.exists(eltorito):
                eltorito_rel = os.path.relpath(eltorito, iso_rw)

                try:
                    load_size = os.path.getsize(eltorito) // 512
                    if load_size == 0:
                        load_size = 4
                except OSError:
                    load_size = 4

                boot_cat = self._find_file(iso_rw, ["boot.cat"])
                boot_cat_rel = os.path.relpath(boot_cat, iso_rw) if boot_cat else "boot/grub/boot.cat"

                cmd += [
                    "-eltorito-boot", eltorito_rel,
                    "-no-emul-boot", "-boot-load-size", str(load_size), "-boot-info-table",
                    "--eltorito-catalog", boot_cat_rel,
                ]

                if efi_img and os.path.exists(efi_img):
                    efi_rel = os.path.relpath(efi_img, iso_rw)
                    cmd += [
                        "-eltorito-alt-boot",
                        "-e", efi_rel,
                        "-no-emul-boot",
                        "-isohybrid-gpt-hfsplus",
                    ]
            elif efi_img and os.path.exists(efi_img):
                efi_rel = os.path.relpath(efi_img, iso_rw)
                cmd += [
                    "-eltorito-boot", efi_rel,
                    "-no-emul-boot",
                    "-isohybrid-gpt-hfsplus",
                ]
            else:
                self.log.emit("[Warning] No boot images found. The ISO will not be bootable.")

            cmd += ["--stdio_sync", "off"]
            cmd.append(iso_rw)

            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                self.error.emit(f"xorriso failed:\n{r.stderr}\n{r.stdout}")
                return

            self.log.emit(f"ISO built: {iso_out}")
            self.progress.emit(95)

            self.log.emit("Cleaning up intermediate files...")
            shutil.rmtree(iso_rw, ignore_errors=True)
            shutil.rmtree(mount_dir, ignore_errors=True)
            if os.path.exists(new_squashfs):
                os.remove(new_squashfs)

            self.progress.emit(100)
            self.finished.emit(iso_out)

        except Exception as e:
            self.error.emit(str(e))


class FinishPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window = parent
        self._output_iso  = None
        self._thread      = None
        self._worker      = None
        self._is_building = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 40)
        layout.setSpacing(20)

        self.title = QLabel("Building ISO")
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(
            "Repacking the rootfs and rebuilding the bootable ISO. "
            "This may take several minutes."
        )
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

        self.progress = QProgressBar()
        self.progress.setObjectName("downloadProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(22)
        layout.addWidget(self.progress)

        log_label = QLabel("Build log:")
        log_label.setObjectName("logHeader")
        layout.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        layout.addWidget(self.log_view, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save ISO to...")
        self.btn_save.setObjectName("btnPrimary")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_iso)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

    def on_enter(self):
        if self._is_building:
            return

        self._is_building = True
        self.progress.setValue(0)
        self.log_view.clear()
        self.title.setText("Building ISO")
        self.subtitle.setText(
            "Repacking the rootfs and rebuilding the bootable ISO. "
            "This may take several minutes."
        )
        self.btn_save.setEnabled(False)
        self.btn_save.setText("Save ISO to...")

        mw     = self._main_window
        mw.btn_next.setVisible(False)
        rootfs = mw.state.get("squashfs_dir")
        iso    = mw.state.get("iso_path")
        work   = mw.state.get("work_dir")
        name   = mw.state.get("osrelease", {}).get("NAME", "void-custom")

        if not all([rootfs, iso, work]):
            self.log_view.appendPlainText("[Error] Missing state - cannot build.")
            self._is_building = False
            return

        self._thread = QThread()
        self._worker = BuildWorker(rootfs, iso, work, name)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self.log_view.appendPlainText)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_finished(self, path):
        self._is_building = False
        self._output_iso = path
        self._main_window.state["output_iso"] = path
        self.title.setText("ISO Ready!")
        self.subtitle.setText(
            f"Your custom ISO has been built successfully.\n{path}"
        )
        self.btn_save.setEnabled(True)

    def _on_error(self, msg):
        self._is_building = False
        self.log_view.appendPlainText(f"\n[ERROR] {msg}")
        self.subtitle.setText("Build failed. See log above.")

    def _save_iso(self):
        if not self._output_iso:
            return

        default_dir = os.path.expanduser("~")
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            sudo_user = os.environ.get("SUDO_USER")
            if sudo_user:
                default_dir = os.path.expanduser(f"~{sudo_user}")
            default_dir = os.path.join(default_dir, "Downloads")
            os.makedirs(default_dir, exist_ok=True)

        dest, _ = QFileDialog.getSaveFileName(
            self, "Save ISO", default_dir, "ISO Images (*.iso)"
        )
        if dest:
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Copying...")
            QApplication.processEvents()
            try:
                shutil.copy2(self._output_iso, dest)
                self.log_view.appendPlainText(f"Saved to: {dest}")
                self.btn_save.setText("Saved!")
            except Exception as e:
                self.log_view.appendPlainText(f"[Error] Could not save: {e}")
                self.btn_save.setText("Save ISO to...")
                self.btn_save.setEnabled(True)
