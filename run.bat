@echo off
title FOGO Bot - Running
cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ❌ Virtual environment not found! Run setup_fogo_bot.bat first
    pause
    exit /b 1
)
echo Virtual environment activated
echo Starting FOGO Bot...
echo.
python main.py
echo.
echo Bot finished
pause
