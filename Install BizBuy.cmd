@echo off
rem Double-click this file to install (or update) BizBuy.
rem It runs install.ps1, which must be in the same folder.
title Installing BizBuy
if not exist "%~dp0install.ps1" (
  echo install.ps1 was not found next to this file.
  echo Download the whole BizBuy folder ^(GitHub: Code ^> Download ZIP^), unzip it, and run this again.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Launch
echo.
pause
