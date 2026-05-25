#!/usr/bin/env python3
import sys
import os
import subprocess
import shutil


def find_squashfs(mount_dir):
    candidates = [
        # Void Linux typically uses this nested structure
        os.path.join(mount_dir, "LiveOS", "squashfs.img"),
        os.path.join(mount_dir, "squashfs.img"),
        os.path.join(mount_dir, "LiveOS", "rootfs.img"),
        os.path.join(mount_dir, "airootfs.sfs"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for root, dirs, files in os.walk(mount_dir):
        for f in files:
            if f.endswith(".squashfs") or f.endswith(".sfs") or f.endswith(".img"):
                return os.path.join(root, f)
    return None

def find_inner_image(staging_dir):
    """Searches the extracted outer image for an inner rootfs."""
    candidates = [
        os.path.join(staging_dir, "LiveOS", "rootfs.img"),
        os.path.join(staging_dir, "rootfs.img"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Fallback search for any image/squashfs
    for root, dirs, files in os.walk(staging_dir):
        for f in files:
            if f.endswith(".img") or f.endswith(".sfs") or f.endswith(".squashfs"):
                return os.path.join(root, f)
    return None


def main():
    if len(sys.argv) < 3:
        print("[Error] Usage: vb_extract.py <iso_path> <work_dir>", flush=True)
        sys.exit(1)

    iso_path    = sys.argv[1]
    work_dir    = sys.argv[2]
    mount_dir   = os.path.join(work_dir, "iso_mount")
    rootfs_dir  = os.path.join(work_dir, "rootfs")
    staging_dir = os.path.join(work_dir, "staging")

    if not os.path.exists(iso_path):
        print(f"[Error] ISO not found: {iso_path}", flush=True)
        sys.exit(1)

    if os.path.exists(rootfs_dir):
        print("Removing old rootfs...", flush=True)
        try:
            shutil.rmtree(rootfs_dir)
        except OSError as e:
            print(f"[Error] Could not remove old rootfs: {e}", flush=True)
            sys.exit(1)

    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)

    # Prevent stale mounts from previous crashed runs
    subprocess.run(["umount", "-l", mount_dir], capture_output=True)
    os.makedirs(mount_dir, exist_ok=True)

    print(f"Mounting ISO: {iso_path}", flush=True)
    r = subprocess.run(
        ["mount", "-o", "loop,ro", iso_path, mount_dir],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"[Error] mount failed: {r.stderr.strip()}", flush=True)
        sys.exit(1)

    try:
        print("Searching for squashfs...", flush=True)
        squashfs = find_squashfs(mount_dir)

        if not squashfs:
            print("[Error] No squashfs found in ISO.", flush=True)
            sys.exit(1)

        print(f"Found: {squashfs}", flush=True)
        print(f"Extracting outer image to: {staging_dir}", flush=True)

        r = subprocess.run(["unsquashfs", "-d", staging_dir, squashfs])

        if r.returncode != 0:
            print("[Error] unsquashfs failed.", flush=True)
            sys.exit(1)

        # Check if the extracted staging dir contains the actual rootfs directly
        if os.path.exists(os.path.join(staging_dir, "usr", "bin")):
            print("Outer image contains rootfs directly. Moving to final location...", flush=True)
            os.rename(staging_dir, rootfs_dir)
        else:
            # It's a nested image (like Void's LiveOS/rootfs.img)
            print("Searching for inner rootfs image...", flush=True)
            inner_img = find_inner_image(staging_dir)

            if not inner_img:
                print("[Error] Inner rootfs image (e.g., rootfs.img) not found.", flush=True)
                sys.exit(1)

            print(f"Found inner image: {inner_img}", flush=True)

            # Handle inner squashfs images (just in case)
            if inner_img.endswith(".squashfs") or inner_img.endswith(".sfs"):
                print("Extracting inner squashfs...", flush=True)
                r = subprocess.run(["unsquashfs", "-d", rootfs_dir, inner_img])
                if r.returncode != 0:
                    print("[Error] Inner unsquashfs failed.", flush=True)
                    sys.exit(1)
            else:
                # Handle inner ext4/xfs images (Standard for Void Linux)
                print("Mounting inner image...", flush=True)
                inner_mount_dir = os.path.join(work_dir, "inner_mount")
                subprocess.run(["umount", "-l", inner_mount_dir], capture_output=True)
                os.makedirs(inner_mount_dir, exist_ok=True)
                os.makedirs(rootfs_dir, exist_ok=True) # cp -a requires dest to exist

                r = subprocess.run(
                    ["mount", "-o", "loop,ro", inner_img, inner_mount_dir],
                    capture_output=True, text=True
                )
                if r.returncode != 0:
                    print(f"[Error] Inner mount failed: {r.stderr.strip()}", flush=True)
                    sys.exit(1)

                try:
                    print(f"Copying rootfs to: {rootfs_dir}", flush=True)
                    print("This may take a few minutes...", flush=True)
                    # cp -a preserves permissions, symlinks, and ownership flawlessly
                    r = subprocess.run(["cp", "-a", inner_mount_dir + "/.", rootfs_dir])
                    if r.returncode != 0:
                        print("[Error] Failed to copy rootfs.", flush=True)
                        sys.exit(1)
                finally:
                    print("Unmounting inner image...", flush=True)
                    subprocess.run(["umount", "-l", inner_mount_dir], capture_output=True)

            # Clean up the outer staging directory to save disk space
            print("Cleaning up staging files...", flush=True)
            try:
                shutil.rmtree(staging_dir)
            except OSError:
                pass

        # Final validation (Void uses a merged /usr layout, so /usr/bin is the real path)
        if not os.path.exists(os.path.join(rootfs_dir, "usr", "bin")):
            print("[Error] Extraction incomplete - /usr/bin missing.", flush=True)
            sys.exit(1)

        print("Extraction complete.", flush=True)

    finally:
        # ALWAYS unmount the ISO, even if interrupted or if steps fail
        print("Unmounting ISO...", flush=True)
        subprocess.run(["umount", "-l", mount_dir], capture_output=True)


if __name__ == "__main__":
    main()
