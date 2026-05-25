"""
setup.py - Build VoidBox native C extensions.

Usage:
    python3 setup.py build_ext --inplace

Produces:
    vb_chroot.cpython-3XX-linux-gnu.so
    vb_mount.cpython-3XX-linux-gnu.so
    vb_sha256.cpython-3XX-linux-gnu.so

Requirements:
    apt install python3-dev libssl-dev
"""

from setuptools import setup, Extension
import subprocess
import sys

py_include = subprocess.check_output(
    [sys.executable, "-c", "import sysconfig; print(sysconfig.get_path('include'))"],
    text=True
).strip()

vb_chroot = Extension(
    "vb_chroot",
    sources=["src/vb_chroot.c"],
    include_dirs=[py_include],
    libraries=["util"],
    extra_compile_args=["-O2", "-Wall", "-Wextra", "-std=c11"],
)

vb_mount = Extension(
    "vb_mount",
    sources=["src/vb_mount.c"],
    include_dirs=[py_include],
    extra_compile_args=["-O2", "-Wall", "-Wextra", "-std=c11"],
)

vb_sha256 = Extension(
    "vb_sha256",
    sources=["src/vb_sha256.c"],
    include_dirs=[py_include],
    libraries=["ssl", "crypto"],
    extra_compile_args=["-O2", "-Wall", "-Wextra", "-std=c11"],
)

setup(
    name="voidbox-native",
    version="0.1.0",
    description="VoidBox native C extensions",
    ext_modules=[vb_chroot, vb_mount, vb_sha256],
)
