@echo off
rem Finds a usable Python 3 and leaves it in %PY%.
rem Called by the other .bat files - not meant to be run on its own.
set "PY="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY exit /b 0

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY exit /b 0

echo.
echo    Python 3 does not seem to be installed on this PC.
echo.
echo    Get it from   https://www.python.org/downloads/windows/
echo    and leave the "Add python.exe to PATH" box ticked while
echo    installing. Then run this file again.
echo.
choice /c YN /n /m "   Open the download page now? [Y/N] "
if not errorlevel 2 start "" https://www.python.org/downloads/windows/
echo.
exit /b 1
