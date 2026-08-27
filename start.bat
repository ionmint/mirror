@echo off
title Mirror - start
call "%~dp0src\_python.bat"
if not defined PY (
  pause
  exit /b 1
)
%PY% "%~dp0src\setup.py" --start
echo.
pause
