@echo off
title FOGO Bot - Update Dependencies
cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ❌ Virtual environment not found! Run setup_fogo_bot.bat first
    pause
    exit /b 1
)
echo 🔄 Updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --upgrade
echo ✅ Dependencies updated
pause
