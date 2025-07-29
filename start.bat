@echo off
setlocal

:: Проверяем активна ли виртуальная среда (переменная VIRTUAL_ENV)
if defined VIRTUAL_ENV (
    echo Virtual environment detected.
) else (
    echo No virtual environment detected. Creating one...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python is installed and in PATH.
        exit /b 1
    )
    call venv\Scripts\activate.bat
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages...
pip install --upgrade pip
pip install aiohttp pynacl colorama base58 solana requests

echo Starting bot...
python main.py

pause
endlocal
