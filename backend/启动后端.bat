@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto nopython

".venv\Scripts\python.exe" run.py
echo.
echo   ------------------------------------------------
echo   Server stopped. Press any key to close this window.
echo   ------------------------------------------------
pause >nul
exit /b

:nopython
echo.
echo   [ERROR] Cannot find .venv\Scripts\python.exe
echo           Please make sure this file is inside the "backend" folder.
echo.
pause