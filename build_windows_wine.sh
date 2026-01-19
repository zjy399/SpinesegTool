#!/bin/bash
# Build Windows .exe on Linux using Wine and PyInstaller
# 
# Prerequisites:
#   1. Install Wine: sudo apt-get install wine
#   2. Download and install Python for Windows in Wine:
#      wget https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe
#      wine python-3.11.0-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
#   3. Install pip in Wine: wine python -m pip install --upgrade pip

set -e

echo "Building Windows .exe on Linux using Wine..."
echo ""

# Check if Wine is installed
if ! command -v wine &> /dev/null; then
    echo "Error: Wine is not installed!"
    echo "Please install Wine first:"
    echo "  sudo apt-get install wine"
    exit 1
fi

# Check if Python is available in Wine
if ! wine python --version &> /dev/null; then
    echo "Error: Python is not installed in Wine!"
    echo "Please install Python for Windows in Wine first."
    echo ""
    echo "Steps:"
    echo "  1. Download Python for Windows:"
    echo "     wget https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe"
    echo "  2. Install in Wine:"
    echo "     wine python-3.11.0-amd64.exe /quiet InstallAllUsers=1 PrependPath=1"
    echo "  3. Install pip:"
    echo "     wine python -m pip install --upgrade pip"
    exit 1
fi

# Get Wine prefix (usually ~/.wine)
WINEPREFIX=${WINEPREFIX:-$HOME/.wine}
echo "Using Wine prefix: $WINEPREFIX"

# Install/upgrade pip if needed
echo "Checking pip..."
wine python -m pip install --upgrade pip

# Install PyInstaller
echo "Installing PyInstaller..."
wine python -m pip install pyinstaller

# Install Python dependencies
echo "Installing dependencies..."
wine python -m pip install PySide6 numpy nibabel

# Note: PyTorch and SAM might need to be installed separately
# For CPU version:
# wine python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo ""
echo "Building Windows executable..."

# Convert paths for Wine
# Get absolute path of current directory
CURRENT_DIR=$(pwd)
WIN_DIR=$(winepath -w "$CURRENT_DIR" | tr -d '\r')

# Build using PyInstaller
wine python -m PyInstaller \
    --name=segtool \
    --windowed \
    --onefile \
    --add-data "logo.png;." \
    --hidden-import=PySide6.QtCore \
    --hidden-import=PySide6.QtGui \
    --hidden-import=PySide6.QtWidgets \
    --hidden-import=nibabel \
    --hidden-import=nibabel.nifti1 \
    --clean \
    app.py

echo ""
echo "Build complete!"
echo "Windows executable should be in: dist/segtool.exe"
echo ""
echo "Note: The .exe file will have Windows line endings and paths."
echo "You may need to test it on an actual Windows system."
