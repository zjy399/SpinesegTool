#!/bin/bash
# Build script for Linux executable using PyInstaller

set -e

echo "Building segtool Linux executable..."
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip and install requirements
echo "Installing/updating dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install PyInstaller if not already installed
pip install pyinstaller

# Build the executable
echo ""
echo "Building executable with PyInstaller..."

# Create spec file for Linux if it doesn't exist
if [ ! -f "build_linux.spec" ]; then
    echo "Creating build_linux.spec..."
    pyinstaller --name=segtool \
        --windowed \
        --onefile \
        --add-data "logo.png:." \
        --hidden-import=PySide6.QtCore \
        --hidden-import=PySide6.QtGui \
        --hidden-import=PySide6.QtWidgets \
        --hidden-import=nibabel \
        --hidden-import=nibabel.nifti1 \
        --collect-all PySide6 \
        app.py --clean
else
    pyinstaller build_linux.spec --clean
fi

echo ""
echo "Build complete! The executable should be in the 'dist' directory."
echo "You can run: ./dist/segtool"
echo ""
echo "Note: For Windows .exe, you need to run build_windows.bat on a Windows system."
