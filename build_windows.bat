@echo off
REM Build script for Windows .exe using PyInstaller

echo Building segtool Windows executable...
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Upgrade pip and install requirements
echo Installing/updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Build the executable
echo.
echo Building executable with PyInstaller...
pyinstaller build_windows.spec --clean

echo.
echo Build complete! The .exe file should be in the 'dist' directory.
echo You can run: dist\segtool.exe
pause
