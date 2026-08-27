@echo off
title Mirror - install
call "%~dp0src\_python.bat"
if not defined PY (
  pause
  exit /b 1
)
%PY% "%~dp0src\setup.py"
pause
