"""
Утилиты и вспомогательные функции для FOGO Bot
"""

import os
import base58
import logging
import platform
import ssl
from typing import List
from solders.keypair import Keypair
from config import NATIVE_TOKEN_SYMBOL, LAMPORTS_PER_FOGO

logger = logging.getLogger(__name__)


def format_token_amount(lamports: int, symbol: str = NATIVE_TOKEN_SYMBOL) -> str:
    """Форматирует количество токенов для отображения"""
    amount = lamports / LAMPORTS_PER_FOGO
    return f"{amount:.6f} {symbol}"


def format_small_amount(lamports: int, symbol: str = NATIVE_TOKEN_SYMBOL) -> str:
    """Форматирует малые количества токенов"""
    amount = lamports / LAMPORTS_PER_FOGO
    if amount < 0.001:
        return f"{amount:.8f} {symbol}"
    else:
        return f"{amount:.6f} {symbol}"


def load_keypairs_from_file(filename: str) -> List[Keypair]:
    """Загружает приватные ключи из файла"""
    keypairs = []
    if not os.path.exists(filename):
        logger.error(f"Keypair file '{filename}' not found.")
        return keypairs
    
    with open(filename, "r", encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                secret_key_bytes = base58.b58decode(line)
                if len(secret_key_bytes) != 64:
                    logger.error(f"Invalid secret key length for line {line_num}: expected 64 bytes, got {len(secret_key_bytes)}")
                    continue
                keypair = Keypair.from_bytes(secret_key_bytes)
                keypairs.append(keypair)
                logger.debug(f"Loaded keypair {line_num}: {str(keypair.pubkey())[:6]}...")
            except Exception as e:
                logger.error(f"Failed to load keypair from line {line_num}: {e}")
    
    return keypairs


def load_proxies(filename: str) -> List[str]:
    """Загружает прокси из файла"""
    proxies = []
    if not os.path.exists(filename):
        logger.warning(f"Proxy file {filename} not found, running without proxies")
        return proxies
    
    with open(filename, "r", encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            proxy = line.strip()
            if proxy and not proxy.startswith('#'):
                # Проверяем формат прокси
                if "://" not in proxy:
                    proxy = f"http://{proxy}"
                proxies.append(proxy)
                logger.debug(f"Loaded proxy {line_num}: {proxy}")
    
    return proxies


def create_ssl_context(verify: bool = False) -> ssl.SSLContext:
    """Создает SSL контекст с настройками для FOGO"""
    ssl_context = ssl.create_default_context()
    if not verify:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def create_safe_connector():
    """Создает безопасный коннектор для проблемных систем"""
    import socket
    
    try:
        if platform.system() == "Windows":
            # Пробуем разные варианты для Windows
            try:
                # Вариант 1: Без DNS кэша и с отключенным resolver
                connector = aiohttp.TCPConnector(
                    ssl=False,
                    use_dns_cache=False,
                    family=socket.AF_UNSPEC,
                    limit=10,
                    limit_per_host=5
                )
                return connector
            except:
                # Вариант 2: Совсем базовый коннектор
                return aiohttp.TCPConnector(ssl=False)
        else:
            # Для Linux/Mac стандартные настройки
            return aiohttp.TCPConnector(ssl=False, limit=10, limit_per_host=5)
            
    except Exception as e:
        logger.warning(f"Failed to create custom connector: {e}")
        # Последний fallback
        return aiohttp.TCPConnector()


def get_platform_connector_settings():
    """Возвращает настройки коннектора для текущей платформы"""
    if platform.system() == "Windows":
        return {
            "ssl": False,
            "limit": 10,
            "limit_per_host": 5,
            "use_dns_cache": False,
            "resolver": None,  # Отключаем resolver для Windows
            "family": 0,  # Используем любой тип сокета
            "enable_cleanup_closed": True
        }
    else:
        return {
            "ssl": False,
            "limit": 10,
            "limit_per_host": 5
        }


def truncate_address(address: str, length: int = 6) -> str:
    """Сокращает адрес для отображения"""
    return f"{str(address)[:length]}..."


def calculate_adaptive_delay(base_min: float, base_max: float, failure_rate: float) -> float:
    """Вычисляет адаптивную задержку на основе процента неудач"""
    import random
    
    if failure_rate > 0.5:  # Больше 50% неудач
        multiplier = 2.0
    elif failure_rate > 0.3:  # Больше 30% неудач
        multiplier = 1.5
    else:
        multiplier = 1.0
    
    base_delay = random.uniform(base_min, base_max)
    return base_delay * multiplier


def validate_input_params(num_swaps: int, min_delay: float, max_delay: float) -> bool:
    """Валидирует входные параметры"""
    if num_swaps <= 0:
        logger.error("Number of swaps must be positive")
        return False
    
    if min_delay < 0 or max_delay < 0:
        logger.error("Delays must be non-negative")
        return False
        
    if min_delay > max_delay:
        logger.error("Min delay cannot be greater than max delay")
        return False
    
    return True


def print_banner(transaction_type: str):
    """Выводит баннер приложения"""
    from colorama import Fore, Style
    from config import VERSION, NATIVE_TOKEN_SYMBOL
    
    banner = f"""
{Fore.RED}{Style.BRIGHT}
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%#*+==##@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#=-----*@@%#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@=---::--#@@@-:%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@%@@@@*----::-+%@@@-:#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%%%@@@@@%:--:::+%@@+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@=-*@*--#@@@@@+-::::-#@@@@@@@@@@#*@@@@@%=@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@%--+-----%@@@%:-::::-*@@@@@@@@@@@@#*%@%=-%@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@#+#*----------:-:::----#@@@@-@@@@@@@@@*---#@%@@@@@@@@@@@@@
@@@@@@@@@@@@@%@%@*--::-::---::-:::-----=**--#@@@@@@#=---:@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@#:-:::---::::-:::::-----:  --==+==---:--*@+%@@@@@@@@@@@@@
@@@@@@@@@@@#@@@#--::::--::::::::::::::::::----------::-=@@%@@@@@@@@@@@@@@
@@@@@@@@@@@*-==::::::::::::::::::::::::::::::::::--:::-%@@@@@@@@@@@@@@@@@
@@@@@@@@@@@#----:::::::::::::::::..::::::::::::::-::::#@@@@%%@@@@@@@@@@@@
@@@@@@@@@@@@----::::::::-:::::::......:-=:::::.:::::::%@@@*=%@@@%%@@@@@@@
@@@@@@@@##@@-----:::::::::............-=:.::....::::-:+%@@@@@%%%@@@@@@@@@
@@@@@@@@@@@@---:-:::.:::.:............:-:......:::::---:-=-----*@@@@@@@@@
@@@@%#@*#@@@+---:-:::..::..............::.......:=-:::----------*##@@@@@@
@@@@@@%+-==-------:--::::.......................:==:::::--------+@@@@@@@@
@@@@%*#=---------::-=::.........................:=-.::::=--:----+*=#@@@@@
@@@@@@%=-::---:::::-=+=:.......................:-:..:::=--------+%*+@@@@@
@@@@@@%=-:::::::..::::-:...........................::::-=:::----+%@@@@@@@
@@@@@@%=--::::::...::................................:-==:::----+%@@@@@@@
@@@@@@%=---::***########################################**+:----+%@@@@@@@
@@@@@@%+---:=*@@@@@@@@+.....:@@@@@@@@@@@@@@@@@@%-.....*@@%#:----+%%@@@@@@
@@@@@@@+---:=*@@@@@#::.=****%@@@@@@@@@@@@@@@@+:.:+****%@@@#====-+%%@@@@@@
@@@@@@@*-=-:=*@@@@@=..-%@@@@@@@@@@@@@@@@@@@@@. .=@@@@@@@@%%=====#@@@@@@@@
@@@@@@@#===--#%@@@%--:-+++@@@@@@@%#+*#%@@@@@%-::-++#@@@@@%%=-==+%@@@@@@@@
@@@@@@@@+===-*#@@@@@@+  .+@@@@@@%*=..=#%@@@@@@%. .:#@@@@@#+:-==+#=#@@@@@@
@@@@@%%#+====#%@@@@#:.=%@@@@@@%*=....+#%@@@@@#..+@@@@@@%#::==+%*+@@@@@@@@
@@@@@@%%*====+#%@@@+-#@@@@@@@%#+......+#%@@@@:=%@@@@@@%#=:-==#@%@@@@@@@@@
@@@@@@%*%*=====*#%%#%%%%%%%##*=........+*#%%%*%%%%%%%#* :-==#@@@@@@@@@@@@
@@@@@@@@@@@*====-::::------:....:::::::::::::-----:::::::===%@@@@@@@@@@@@
@@@@@@@@@@@%=====--:::::::::::::::::::::::-=:::::::-==++==@@%@@@@@@@@@@@@
@@@@@@@@@@@@@#=======-::::::::-===+=--==+++++=-::-=++++=%@*=@@@@@@@@@@@@@
@@@@@@@@@@@@@@@%============++++++++++++++++++++++++==%@@#%@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@%+=---==+=++++++++++++++++++++==-::--#@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@*--::::::::::::----:::::::::::::-+%@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@%+-::::::::--:::::::-----::::-=#@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@%*----------::---#%+---+#@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@%%##+==*=:-=*%@@%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

                        FOGO NETWORK BOT {VERSION}
                  Enhanced for FOGO Native Token Trading
                      Transaction Type: {transaction_type}
                          Native Token: {NATIVE_TOKEN_SYMBOL}
{Style.RESET_ALL}
"""
    print(banner)