# <img src=assets/logo.svg height="30" valign="middle"> VoidBox ISO Customizer

![Repo](https://img.shields.io/badge/github-repo-green?logo=github)
![Licence](https://img.shields.io/badge/Licence:-MIT-green)
![Version](https://img.shields.io/badge/Latest%20Supported%20Void%20Linux%20Version:-2025__02__02-green)
![Toolkit](https://img.shields.io/badge/Toolkit:-PySide6-green)
![Languagues](https://img.shields.io/badge/Languages:-C,%20Python-green)

> **Disclaimer!!** Using VoidBox's chroot feature on any Debian-based distribution or any non-Void distro can cause severe conflicts with the AppArmor security module, and the only way to fix it is to force-restart. **Use at your own risk!!**


## What is VoidBox?

**VoidBox** is a free and open source graphical Void Linux ISO customizer. Select a work directory, drop into an interactive chroot, install packages, configure your system, and build a bootable ISO. All from a clean, simple interface.

Think of it as Cubic, but for Void Linux.

## Features

- **Work directory:** resume existing projects or start fresh, ISOs and rootfs are detected automatically
- **ISO selection:** download the latest Void Linux base ISO automatically (glibc, musl, aarch64) or load your own
- **Interactive chroot:** full terminal session inside the Void rootfs via xterm
- **Repository setup:** network and local ISO repos configured automatically inside the chroot
- **ISO build:** repack the rootfs into a bootable ISO using the same xz compression as official Void ISOs
- **BIOS + UEFI:** hybrid boot support via xorriso
- **Native C extensions:** PTY, mount/umount and SHA-256 via Python C extensions for performance

## How does it work?

VoidBox downloads a Void Linux live ISO, extracts its squashfs rootfs, sets up bind mounts and repository configuration, then drops you into a chroot terminal. When you are done customizing, it repacks the rootfs with mksquashfs and rebuilds a bootable ISO with xorriso, preserving the original boot structure.

## Requirements

- **Python 3.10+**
- **PySide6**
- **unsquashfs** · **mksquashfs** (squashfs-tools)
- **xorriso**
- **wget**
- **xterm**
- **python3-dev** · **libssl-dev** (for building native extensions)

## Installation

Clone the repository and install dependencies:

```bash
# Void Linux
xbps-install python3 python3-pip squashfs-tools xorriso wget xterm python3-devel openssl-devel

# Debian / Ubuntu
sudo apt install python3 python3-pip squashfs-tools xorriso wget xterm python3-dev libssl-dev

pip install PySide6
```

Build the native C extensions:

```bash
git clone https://github.com/Just-Alex22/VoidBox-ISO-Customizer.git
cd VoidBox
python3 setup.py build_ext --inplace
```

Run:

```bash
python3 main.py
```

The app will prompt for root privileges via pkexec automatically.

## Usage

1. **Work Directory:** Select a folder for your project. If it already contains a rootfs or ISO, VoidBox will resume from there automatically.
2. **Select ISO:** Choose a Void Linux variant or load a local ISO. Skipped if the work directory already has one.
3. **Download:** The ISO is downloaded from the official Void Linux mirrors. Skipped if already present.
4. **Customize:** An xterm window opens with a full chroot session. Install packages with `xbps-install`, edit `/etc/os-release`, and configure anything you need. Close the terminal when done.
5. **Build:** VoidBox repacks the rootfs and builds a bootable ISO ready to burn or boot.

## Contributing

If you want to collaborate with the development of **VoidBox**, follow us on GitHub and send your **Pull Requests** and **Issues** through the repository.

## License

This program comes with the MIT license; consult https://www.mit.edu/~amini/LICENSE.md for more information.

---

> **Development:** [Just_Alex](https://github.com/Just-Alex22) 
> **Repository:** [VoidBox](https://github.com/Just-Alex22/VoidBox-ISO-Customizer)
