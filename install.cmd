@echo off
rem Double-click to install the kit's skills on Windows. Runs install.ps1 for this one run without changing
rem your PowerShell settings.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
