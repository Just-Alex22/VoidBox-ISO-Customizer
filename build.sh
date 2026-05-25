#!/bin/bash
# VoidBox — build native C extensions
set -e

echo "[VoidBox] Building native extensions..."
python3 setup.py build_ext --inplace

# Move .so files from build/ to project root if needed
find . -maxdepth 3 -name "vb_*.so" ! -path "./build/*" | head -5

echo "[VoidBox] Done. You can now run: python3 main.py"
