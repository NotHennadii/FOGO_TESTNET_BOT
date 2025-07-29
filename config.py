"""
Конфигурация и константы для FOGO Bot
"""

# Константы для FOGO Testnet (по официальной документации)
FOGO_RPC_URL = 'https://testnet.fogo.io/'
FOGO_ENTRYPOINT = 'testnet-entrypoint.fogo.io:8001'
FOGO_GENESIS_HASH = '9GGSFo95raqzZxWqKM5tGYvJp5iv4Dm565S4r8h5PEu9'
FOGO_SHRED_VERSION = 298
FOGO_EXPECTED_BANK_HASH = '4bNWYnpUKqMjoZUNUGUc1ZKXpCVGUkZgGCVpc8BQNenn'

# API endpoints
VALIANT_API_URL = "https://api.valiant.trade"
PAYMASTER_URL = "https://sessions-example.fogo.io/paymaster"
EXPLORER_URL = "https://explorer.fogo.io/tx/"
PUBLIC_FEE_PAYER = "8HnaXmgFJbvvJxSdjeNyWwMXZb85E35NM4XNg6rxuw3w"

# Token addresses для FOGO Testnet
FOGO_MINT = "So11111111111111111111111111111111111111112"  # FOGO (нативный токен)
FUSD_MINT = "fUSDNGgHkZfwckbr5RLLvRbvqvRcTLdH9hcHJiq4jry"   # FUSD

# Константы для отображения
NATIVE_TOKEN_SYMBOL = "FOGO"
NATIVE_TOKEN_DECIMALS = 9
LAMPORTS_PER_FOGO = 1_000_000_000

# User agents для HTTP запросов
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
]

# Настройки для swap'ов
SWAP_AMOUNTS = [
    100000,    # 0.0001 FOGO
    200000,    # 0.0002 FOGO  
    500000,    # 0.0005 FOGO
    1000000,   # 0.001 FOGO
    1500000,   # 0.0015 FOGO
]

# Веса для выбора сумм (предпочтение меньшим суммам)
SWAP_WEIGHTS = [0.3, 0.25, 0.2, 0.15, 0.1]

# Настройки тайм-аутов
HTTP_TIMEOUT = 30
RPC_TIMEOUT = 30
AIRDROP_CONFIRMATION_DELAY = 5
NETWORK_CHECK_DELAY = 2

# Минимальная задержка между транзакциями (для FOGO 40ms блоков)
MIN_TRANSACTION_DELAY = 0.1

# Версия бота
VERSION = "v2.1"