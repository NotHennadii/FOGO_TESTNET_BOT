#!/usr/bin/env python3
"""
FOGO Network Bot - Основной файл запуска

Модульная архитектура для автоматизации swap операций в сети FOGO
"""

import asyncio
import sys
import platform
import logging
import os
import aiohttp
from colorama import init, Fore, Style

# Отключаем расширения aiohttp для совместимости с Windows
os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'

# Инициализируем colorama
init(autoreset=True)

# Исправляем проблему с EventLoop на Windows
if platform.system() == "Windows":
    # Устанавливаем SelectorEventLoop для Windows (требуется для aiodns)
    if sys.version_info >= (3, 8):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            # Fallback для старых версий
            pass
    
    # Дополнительные настройки для Windows
    os.environ['PYTHONASYNCIODEBUG'] = '0'

# Импорты модулей
from config import VERSION
from utils import (
    load_keypairs_from_file, load_proxies, validate_input_params, 
    print_banner, get_platform_connector_settings, create_safe_connector
)
from network import verify_fogo_connection, check_wallets_balance
from airdrop import request_multiple_airdrops
from worker import run_multiple_workers, print_final_statistics
from transaction import get_transaction_type

# Настройка логирования
logging.basicConfig(
    format='[%(levelname)s] %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_user_configuration():
    """Получает конфигурацию от пользователя"""
    print(f"{Fore.CYAN}=== FOGO BOT CONFIGURATION ==={Style.RESET_ALL}")
    
    # Основные опции
    use_proxies = input("Use proxies? (y/n): ").strip().lower() == 'y'
    check_balances = input("Check wallet balances first? (y/n): ").strip().lower() == 'y'
    request_airdrops = input("Request airdrops for empty wallets? (y/n): ").strip().lower() == 'y'
    
    print(f"\n{Fore.YELLOW}=== SWAP CONFIGURATION ==={Style.RESET_ALL}")
    try:
        num_swaps = int(input("Enter number of swaps per wallet: "))
        min_delay = float(input("Enter min delay between swaps (seconds): "))
        max_delay = float(input("Enter max delay between swaps (seconds): "))
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return None
    
    # Валидация
    if not validate_input_params(num_swaps, min_delay, max_delay):
        return None
    
    return {
        'use_proxies': use_proxies,
        'check_balances': check_balances,
        'request_airdrops': request_airdrops,
        'num_swaps': num_swaps,
        'min_delay': min_delay,
        'max_delay': max_delay
    }


async def setup_network_connection():
    """Настраивает и проверяет подключение к сети"""
    logger.info(f"{Fore.CYAN}🔗 Verifying FOGO testnet connection...{Style.RESET_ALL}")
    
    # Пробуем создать коннектор безопасным способом
    connector = None
    
    # Способ 1: Безопасный коннектор
    try:
        connector = create_safe_connector()
        logger.debug("Created safe connector successfully")
    except Exception as e:
        logger.warning(f"Safe connector failed: {e}")
    
    # Способ 2: Базовый коннектор без дополнительных настроек
    if connector is None:
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            logger.debug("Created basic connector")
        except Exception as e:
            logger.warning(f"Basic connector failed: {e}")
    
    # Способ 3: Самый простой коннектор
    if connector is None:
        try:
            # Отключаем все расширения aiohttp
            import os
            os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'
            connector = aiohttp.TCPConnector()
            logger.debug("Created minimal connector")
        except Exception as e:
            logger.error(f"All connector methods failed: {e}")
            return None, None
    
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            connection_ok = await verify_fogo_connection(session)
            if not connection_ok:
                logger.error("❌ Failed to verify FOGO testnet connection. Check your internet connection.")
                return None, None
            return session, connector
    except Exception as e:
        logger.error(f"Failed to establish session: {e}")
        return None, None


async def load_configuration(config):
    """Загружает файлы конфигурации (кошельки и прокси)"""
    # Загружаем кошельки
    keypairs = load_keypairs_from_file("private_key.txt")
    if not keypairs:
        logger.error("No keypairs loaded. Please check private_key.txt file.")
        return None, None
        
    logger.info(f"✅ Loaded {len(keypairs)} keypairs")

    # Загружаем прокси
    proxies = load_proxies("proxy.txt") if config['use_proxies'] else []
    if config['use_proxies']:
        logger.info(f"✅ Loaded {len(proxies)} proxies")
    else:
        logger.info("ℹ️  Running without proxies")
    
    return keypairs, proxies


async def pre_execution_checks(config, keypairs, proxies):
    """Выполняет проверки перед началом работы"""
    connector_settings = get_platform_connector_settings()
    connector = aiohttp.TCPConnector(**connector_settings)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Проверяем балансы если нужно
        if config['check_balances']:
            await check_wallets_balance(keypairs, session)

        # Запрашиваем airdrop если нужно
        if config['request_airdrops']:
            successful_airdrops = await request_multiple_airdrops(session, keypairs, proxies)
            if successful_airdrops > 0:
                logger.info("⏳ Waiting for airdrop confirmations...")

        # Финальная проверка балансов
        if config['check_balances'] or config['request_airdrops']:
            await check_wallets_balance(keypairs, session)


def print_execution_summary(config, keypairs):
    """Выводит сводку перед началом выполнения"""
    print(f"\n{Fore.GREEN}🚀 Starting execution...{Style.RESET_ALL}")
    print(f"📊 Configuration: {config['num_swaps']} swaps per wallet, {config['min_delay']}-{config['max_delay']}s delays")
    print(f"👥 Workers: {len(keypairs)} wallet(s)")
    print(f"🔗 Proxies: {'Enabled' if config['use_proxies'] else 'Disabled'}")
    print(f"💰 Airdrops: {'Requested' if config['request_airdrops'] else 'Skipped'}")
    print(f"═══════════════════════════════════════════════════════")


async def main():
    """Основная функция"""
    try:
        # Выводим баннер
        print_banner(get_transaction_type())
        
        # Получаем конфигурацию от пользователя
        config = get_user_configuration()
        if not config:
            return
        
        # Проверяем подключение к сети
        session, connector = await setup_network_connection()
        if not session:
            return
        
        # Загружаем конфигурацию
        keypairs, proxies = await load_configuration(config)
        if not keypairs:
            return
        
        # Выполняем предварительные проверки
        await pre_execution_checks(config, keypairs, proxies)
        
        # Выводим сводку перед началом
        print_execution_summary(config, keypairs)
        
        # Запускаем воркеров
        stats = await run_multiple_workers(
            keypairs, 
            config['num_swaps'], 
            config['min_delay'], 
            config['max_delay'], 
            proxies
        )
        
        # Выводим финальную статистику
        print_final_statistics(stats)
        
        # Показываем финальный баланс если нужно
        if config['check_balances'] or config['request_airdrops']:
            print(f"\n{Fore.CYAN}📊 Final wallet status:{Style.RESET_ALL}")
            connector_settings = get_platform_connector_settings()
            connector = aiohttp.TCPConnector(**connector_settings)
            async with aiohttp.ClientSession(connector=connector) as session:
                await check_wallets_balance(keypairs, session)

    except KeyboardInterrupt:
        logger.info(f"\n{Fore.RED}⚠️  Script interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()


def setup_windows_event_loop():
    """Дополнительная настройка для Windows"""
    if platform.system() == "Windows":
        try:
            # Для Windows используем SelectorEventLoop (требуется для aiodns)
            loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(loop)
            logger.debug("Set SelectorEventLoop for Windows")
        except Exception as e:
            logger.debug(f"Failed to set SelectorEventLoop: {e}")
            # Fallback: пробуем ProactorEventLoop
            try:
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
                logger.debug("Fallback to ProactorEventLoop")
            except Exception as e2:
                logger.debug(f"Failed to set ProactorEventLoop: {e2}")


if __name__ == "__main__":
    print(f"{Fore.GREEN}Starting FOGO Network Bot {VERSION}...{Style.RESET_ALL}")
    
    # Настройка для Windows
    setup_windows_event_loop()
    
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")