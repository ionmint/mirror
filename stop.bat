@echo off
title Mirror - stop
call "%~dp0src\_python.bat"
if not defined PY (
  pause
  exit /b 1
)
%PY% "%~dp0src\setup.py" --stop
echo.
pause
