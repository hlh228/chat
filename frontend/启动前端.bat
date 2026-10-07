@echo off
cd /d "%~dp0"

if not exist "..\backend\.venv\Scripts\python.exe" goto nopython

"..\backend\.venv\Scripts\python.exe" run.py
echo.
echo   ------------------------------------------------
echo   Server stopped. Press any key to close this window.
echo   ------------------------------------------------
pause >nul
exit /b

:nopython
echo.
echo   [ERROR] Cannot find ..\backend\.venv\Scripts\python.exe
echo           Please keep this file inside the "chat\frontend" folder.
echo.
pause
