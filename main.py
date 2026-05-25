#!/usr/bin/env python3

import sys
import os
import subprocess

SCRIPT_DIR   = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
APPARMOR_PROFILE = os.path.join(SCRIPT_DIR, "voidbox.apparmor")
APPARMOR_NAME    = "voidbox"


_aa_was_enforcing = False


def setup_apparmor():
    """
    Put the flatpak AppArmor profile in complain mode so it stops
    denying DBus signals during VoidBox operations.
    Restores enforce mode on exit.
    """
    global _aa_was_enforcing
    _aa_was_enforcing = False
    try:
        profile = "/etc/apparmor.d/flatpak"
        if not os.path.exists(profile):
            return
        if not os.path.exists("/sys/kernel/security/apparmor"):
            return
        # Check if profile is in enforce mode
        r = subprocess.run(["aa-status", "--json"],
                           capture_output=True, text=True)
        if r.returncode == 0 and "flatpak" in r.stdout:
            import json
            status = json.loads(r.stdout)
            enforced = status.get("profiles", {})
            if enforced.get("flatpak") == "enforce":
                subprocess.run(["aa-complain", profile], capture_output=True)
                _aa_was_enforcing = True
                print("[VoidBox] AppArmor flatpak profile set to complain mode.", flush=True)
    except Exception:
        pass


def teardown_apparmor():
    """Restore flatpak AppArmor profile to enforce mode if we changed it."""
    try:
        if _aa_was_enforcing:
            profile = "/etc/apparmor.d/flatpak"
            subprocess.run(["aa-enforce", profile], capture_output=True)
            print("[VoidBox] AppArmor flatpak profile restored to enforce mode.", flush=True)
    except Exception:
        pass


def check_root():
    if os.geteuid() != 0:
        import subprocess, shutil
        script = os.path.join(SCRIPT_DIR, "main.py")
        print("[VoidBox] Not root - relaunching via pkexec...", flush=True)
        print(f"[VoidBox] Script: {script}", flush=True)
        try:
            display      = os.environ.get("DISPLAY", ":0")
            xauth_src    = os.environ.get("XAUTHORITY", "")
            wayland_disp = os.environ.get("WAYLAND_DISPLAY", "")
            xdg_runtime  = os.environ.get("XDG_RUNTIME_DIR", "")

            # Grant root access to X11 display before switching user
            subprocess.run(["xhost", "+SI:localuser:root"], capture_output=True)

            # Copy Xauthority to a root-readable path
            xauth_dst = "/tmp/.voidbox_xauth"
            if xauth_src and os.path.exists(xauth_src):
                shutil.copy2(xauth_src, xauth_dst)
                os.chmod(xauth_dst, 0o644)
            else:
                xauth_dst = xauth_src

            # Copy Wayland socket to a root-accessible path if possible
            wayland_dst = ""
            if wayland_disp and xdg_runtime:
                wayland_src = os.path.join(xdg_runtime, wayland_disp)
                if os.path.exists(wayland_src):
                    # Create /tmp/voidbox-wayland-0 symlink accessible to root
                    wayland_dst = f"/tmp/voidbox-{wayland_disp}"
                    try:
                        if os.path.exists(wayland_dst):
                            os.remove(wayland_dst)
                        os.symlink(wayland_src, wayland_dst)
                    except Exception:
                        wayland_dst = ""

            env_args = [
                f"DISPLAY={display}",
                f"XAUTHORITY={xauth_dst}",
                "HOME=/root",
                "XDG_CONFIG_HOME=/root/.config",
                "XDG_CACHE_HOME=/root/.cache",
                "XDG_DATA_HOME=/root/.local/share",
            ]

            # Pass Wayland env but let Qt fall back to xcb if permission denied
            if wayland_disp and xdg_runtime:
                env_args += [
                    f"WAYLAND_DISPLAY={wayland_disp}",
                    f"XDG_RUNTIME_DIR={xdg_runtime}",
                ]
            # Tell Qt to try wayland first, then xcb as fallback
            env_args.append("QT_QPA_PLATFORM=wayland;xcb")

            dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
            if dbus:
                env_args.append(f"DBUS_SESSION_BUS_ADDRESS={dbus}")

            print(f"[VoidBox] env: DISPLAY={display} WAYLAND={wayland_disp} XAUTH={xauth_dst}", flush=True)
            os.execvp("pkexec", ["pkexec", "env"] + env_args + [sys.executable, script] + sys.argv[1:])
        except Exception as e:
            print(f"[VoidBox] pkexec failed: {e}", flush=True)
            sys.exit(1)
        sys.exit(0)


def check_dependencies():
    import shutil
    missing = [d for d in ["unsquashfs", "mksquashfs", "xorriso", "wget"] if not shutil.which(d)]
    if missing:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Missing dependencies",
            "The following tools are required but not found:\n\n"
            + "\n".join(f"  • {d}" for d in missing)
            + "\n\nPlease install them and try again.")
        sys.exit(1)


def apply_dark_palette(app):
    from PySide6.QtGui import QPalette, QColor

    dark = QPalette()
    dark.setColor(QPalette.Window,          QColor("#1e1e1e"))
    dark.setColor(QPalette.WindowText,      QColor("#e0e0e0"))
    dark.setColor(QPalette.Base,            QColor("#252525"))
    dark.setColor(QPalette.AlternateBase,   QColor("#2a2a2a"))
    dark.setColor(QPalette.Text,            QColor("#e0e0e0"))
    dark.setColor(QPalette.BrightText,      QColor("#ffffff"))
    dark.setColor(QPalette.Button,          QColor("#2d2d2d"))
    dark.setColor(QPalette.ButtonText,      QColor("#e0e0e0"))
    dark.setColor(QPalette.Highlight,       QColor("#2980b9"))
    dark.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    dark.setColor(QPalette.ToolTipBase,     QColor("#252525"))
    dark.setColor(QPalette.ToolTipText,     QColor("#e0e0e0"))
    dark.setColor(QPalette.Mid,             QColor("#3a3a3a"))
    dark.setColor(QPalette.Dark,            QColor("#141414"))
    dark.setColor(QPalette.Shadow,          QColor("#111111"))
    dark.setColor(QPalette.Link,            QColor("#5dade2"))
    dark.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#555555"))
    dark.setColor(QPalette.Disabled, QPalette.Text,       QColor("#555555"))
    dark.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#555555"))
    dark.setColor(QPalette.Disabled, QPalette.Button,     QColor("#2a2a2a"))
    dark.setColor(QPalette.Disabled, QPalette.Highlight,  QColor("#444444"))
    app.setPalette(dark)


def main():
    check_root()
    setup_apparmor()

    import atexit
    atexit.register(teardown_apparmor)

    # --- SAFETY NET ---
    # Even if pkexec somehow leaves the wrong HOME variable, force it here
    # before Qt initializes so it NEVER writes to the user's home directory.
    if os.geteuid() == 0:
        os.environ["HOME"] = "/root"
        os.environ["XDG_CONFIG_HOME"] = "/root/.config"
        os.environ["XDG_CACHE_HOME"] = "/root/.cache"
        os.environ["XDG_DATA_HOME"] = "/root/.local/share"
    # ------------------

    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    os.chdir(SCRIPT_DIR)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("VoidBox")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("VoidBox Project")
    app.setStyle("Fusion")

    apply_dark_palette(app)

    qss_path = os.path.join(SCRIPT_DIR, "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            app.setStyleSheet(f.read())

    logo_path = os.path.join(SCRIPT_DIR, "assets", "logo.svg")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))

    check_dependencies()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
