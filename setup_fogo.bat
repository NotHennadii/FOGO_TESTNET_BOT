@echo off
chcp 65001 >nul
title FOGO Bot - Setup and Installation
color 0A

echo.
echo ████████╗ ██████╗  ██████╗  ██████╗     ██████╗  ██████╗ ████████╗
echo ██╔══   ██╔═══██╗██╔════╝ ██╔═══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
echo ██████  ██║   ██║██║  ███╗██║   ██║    ██████╔╝██║   ██║   ██║   
echo ██╔══   ██║   ██║██║   ██║██║   ██║    ██╔══██╗██║   ██║   ██║   
echo ██║     ╚██████╔╝╚██████╔╝╚██████╔╝    ██████╔╝╚██████╔╝   ██║   
echo ╚═╝      ╚═════╝  ╚═════╝  ╚═════╝     ╚═════╝  ╚═════╝    ╚═╝   
echo.
echo                    SETUP AND INSTALLATION SCRIPT
echo                         Version 1.1 - Windows
echo ===============================================================================
echo.

:: Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Проверяем Python
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.8+ from https://python.org
    echo    Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% found

:: Проверяем pip
echo.
echo [2/7] Checking pip installation...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip not found! Installing pip...
    python -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo ❌ Failed to install pip
        pause
        exit /b 1
    )
)
echo ✅ pip is available

:: Обновляем pip
echo.
echo [3/7] Upgrading pip to latest version...
python -m pip install --upgrade pip >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ pip upgraded successfully
) else (
    echo ⚠️  pip upgrade failed, but continuing...
)

:: Проверяем и создаем виртуальную среду
echo.
echo [4/7] Setting up virtual environment...
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

:: Активируем виртуальную среду
echo.
echo [5/7] Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo ✅ Virtual environment activated
) else (
    echo ❌ Virtual environment activation script not found
    pause
    exit /b 1
)

:: Создаем requirements.txt если его нет
echo.
echo [6/7] Preparing dependencies...
if not exist "requirements.txt" (
    echo 📝 Creating requirements.txt...
    (
        echo # FOGO Bot Dependencies
        echo # Core Solana libraries
        echo solana==0.30.2
        echo solders==0.20.1
        echo # HTTP client
        echo aiohttp==3.9.1
        echo # Encoding
        echo base58==2.1.1
        echo # Terminal colors
        echo colorama==0.4.6
        echo # Optional speedups
        echo aiofiles==23.2.0
    ) > requirements.txt
    echo ✅ requirements.txt created
) else (
    echo ✅ requirements.txt already exists
)

:: Устанавливаем зависимости
echo.
echo [7/7] Installing dependencies...
echo 📦 This may take a few minutes...

:: Устанавливаем зависимости по одной для лучшего контроля
echo Installing solana...
python -m pip install solana==0.30.2 --no-cache-dir
if %errorlevel% neq 0 (
    echo ⚠️  Failed to install solana, trying alternative...
    python -m pip install solana --no-cache-dir
)

echo Installing solders...
python -m pip install solders==0.20.1 --no-cache-dir
if %errorlevel% neq 0 (
    echo ⚠️  Failed to install solders, trying alternative...
    python -m pip install solders --no-cache-dir
)

echo Installing aiohttp...
python -m pip install "aiohttp>=3.8.0,<4.0.0" --no-cache-dir
if %errorlevel% neq 0 (
    echo ❌ Failed to install aiohttp
    pause
    exit /b 1
)

echo Installing additional dependencies...
python -m pip install base58 colorama aiofiles --no-cache-dir

:: Проверяем установку
echo.
echo 🔍 Verifying installation...
python -c "import solana; import solders; import aiohttp; import base58; import colorama; print('✅ All dependencies imported successfully')" 2>nul
if %errorlevel% equ 0 (
    echo ✅ All dependencies verified successfully
) else (
    echo ⚠️  Some dependencies may have issues, but continuing...
)

:: Создаем файлы конфигурации если их нет
echo.
echo 📁 Setting up configuration files...

if not exist "private_key.txt" (
    echo 📝 Creating private_key.txt template...
    (
        echo # Add your private keys here (one per line, base58 encoded)
        echo # Example:
        echo # 5K7qF2B3xM8nR9pL6wE4vQ1tN8hJ9kF2xS7dY3cA6bZ9mP4rT1uV2wX8yG5hL3nK
        echo # 3M7pF4B2xL9nR8pK6wD3vP1tM8hI9jE2xQ7cX3bY9lO4qS1uT2vW8xF5gH3mJ2nL
    ) > private_key.txt
    echo ✅ private_key.txt template created
)

if not exist "proxy.txt" (
    echo 📝 Creating proxy.txt template...
    (
        echo # Add your proxies here (one per line)
        echo # Supported formats:
        echo # http://username:password@ip:port
        echo # socks5://username:password@ip:port
        echo # http://ip:port
        echo # Example:
        echo # http://user:pass@123.456.789.123:8080
        echo # socks5://user:pass@123.456.789.123:1080
    ) > proxy.txt
    echo ✅ proxy.txt template created
)

:: Создаем run.bat для удобного запуска
echo.
echo 🚀 Creating run script...
(
    echo @echo off
    echo title FOGO Bot - Running
    echo cd /d "%%~dp0"
    echo if exist "venv\Scripts\activate.bat" ^(
    echo     call venv\Scripts\activate.bat
    echo ^) else ^(
    echo     echo ❌ Virtual environment not found! Run setup_fogo_bot.bat first
    echo     pause
    echo     exit /b 1
    echo ^)
    echo echo ✅ Virtual environment activated
    echo echo 🚀 Starting FOGO Bot...
    echo echo.
    echo python main.py
    echo echo.
    echo echo 🏁 Bot finished
    echo pause
) > run.bat
echo ✅ run.bat created

:: Создаем update.bat для обновления зависимостей
(
    echo @echo off
    echo title FOGO Bot - Update Dependencies
    echo cd /d "%%~dp0"
    echo if exist "venv\Scripts\activate.bat" ^(
    echo     call venv\Scripts\activate.bat
    echo ^) else ^(
    echo     echo ❌ Virtual environment not found! Run setup_fogo_bot.bat first
    echo     pause
    echo     exit /b 1
    echo ^)
    echo echo 🔄 Updating dependencies...
    echo python -m pip install --upgrade pip
    echo python -m pip install -r requirements.txt --upgrade
    echo echo ✅ Dependencies updated
    echo pause
) > update.bat
echo ✅ update.bat created

:: Финальные инструкции
echo.
echo ===============================================================================
echo.
echo 🎉 SETUP COMPLETED SUCCESSFULLY!
echo.
echo 📋 NEXT STEPS:
echo    1. Edit 'private_key.txt' and add your wallet private keys
echo    2. Edit 'proxy.txt' and add your proxies (optional)
echo    3. Make sure 'main.py' is in this folder
echo    4. Run 'run.bat' to start the bot
echo.
echo 📁 FILES CREATED:
echo    ✅ venv/               - Virtual environment
echo    ✅ requirements.txt    - Python dependencies
echo    ✅ private_key.txt     - Wallet keys template
echo    ✅ proxy.txt          - Proxy list template  
echo    ✅ run.bat            - Start bot script
echo    ✅ update.bat         - Update dependencies script
echo.
echo 🔧 USEFUL COMMANDS:
echo    • run.bat             - Start the bot
echo    • update.bat          - Update dependencies
echo    • setup_fogo_bot.bat  - Re-run this setup
echo.
echo ⚠️  IMPORTANT:
echo    - Add your REAL private keys to private_key.txt (remove example lines)
echo    - Keep your private keys safe and never share them
echo    - Test with small amounts first
echo.
echo ===============================================================================
echo.
echo Press any key to exit...
pause >nul