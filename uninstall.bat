@echo off
title Mirror - uninstall
call "%~dp0src\_python.bat"
if not defined PY (
  pause
  exit /b 1
)
echo.
echo    Removing the autostart entry and stopping Mirror.
echo    The folder and your journals stay where they are: delete this
echo    folder by hand to get rid of everything.
echo.
%PY% "%~dp0src\setup.py" --uninstall
%PY% "%~dp0src\setup.py" --stop
echo.
pause
