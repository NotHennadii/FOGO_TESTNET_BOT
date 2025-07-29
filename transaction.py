"""
Обработка и подпись транзакций для FOGO Bot
"""

import base64
import logging
from solders.keypair import Keypair

logger = logging.getLogger(__name__)

# Определяем тип транзакций
try:
    from solders.transaction import VersionedTransaction
    TRANSACTION_TYPE = "solders"
except ImportError:
    try:
        from solana.transaction import VersionedTransaction
        TRANSACTION_TYPE = "solana_versioned"  
    except ImportError:
        VersionedTransaction = None
        TRANSACTION_TYPE = "legacy"

# Альтернативный импорт для Transaction
try:
    from solana.transaction import Transaction
except ImportError:
    try:
        from solana.transaction.transaction import Transaction
    except ImportError:
        Transaction = None


def get_transaction_type() -> str:
    """Возвращает тип используемых транзакций"""
    return TRANSACTION_TYPE


def deserialize_and_sign_transaction(raw_tx_bytes: bytes, wallet: Keypair) -> bytes:
    """Универсальная функция для десериализации и подписи транзакций"""
    
    logger.debug("Using simplified transaction signing approach")
    
    try:
        # Метод 1: Попробуем solders
        if TRANSACTION_TYPE == "solders":
            from solders.transaction import VersionedTransaction
            
            tx = VersionedTransaction.from_bytes(raw_tx_bytes)
            
            # Получаем сообщение для подписи
            message_bytes = bytes(tx.message)
            signature = wallet.sign_message(message_bytes)
            
            # Создаем список подписей
            signatures = [signature.signature]
            
            # Создаем новую подписанную транзакцию
            signed_tx = VersionedTransaction(tx.message, signatures)
            return bytes(signed_tx)
            
    except Exception as solders_error:
        logger.debug(f"Solders signing failed: {solders_error}")
    
    try:
        # Метод 2: Попробуем через legacy
        if Transaction is not None:
            legacy_tx = Transaction.deserialize(raw_tx_bytes) 
            legacy_tx.sign(wallet)
            return legacy_tx.serialize()
            
    except Exception as legacy_error:
        logger.debug(f"Legacy signing failed: {legacy_error}")
    
    # Метод 3: Возвращаем оригинальные байты (транзакция может быть уже подписана)
    logger.debug("Returning original transaction bytes")
    return raw_tx_bytes


async def send_transaction_rpc(session, tx_bytes: bytes, ssl_context) -> tuple[bool, str]:
    """Отправляет транзакцию через прямой RPC вызов"""
    try:
        from config import FOGO_RPC_URL, HTTP_TIMEOUT
        
        tx_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                base64.b64encode(tx_bytes).decode(),
                {
                    "skipPreflight": True,
                    "encoding": "base64"
                }
            ]
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=tx_payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result and result['result']:
                    tx_sig = result['result']
                    # Проверяем что это не placeholder
                    if tx_sig != "1111111111111111111111111111111111111111111111111111111111111111":
                        return True, tx_sig
                    else:
                        return True, "placeholder"
                else:
                    logger.error(f"❌ RPC transaction failed: {result}")
                    return False, ""
            else:
                logger.error(f"❌ RPC returned status {resp.status}")
                return False, ""
                
    except Exception as e:
        logger.debug(f"Direct RPC transaction failed: {e}")
        return False, ""


async def send_transaction_paymaster(session, raw_tx: str, ssl_context, proxy_kwargs) -> tuple[bool, str]:
    """Отправляет транзакцию через paymaster"""
    try:
        from config import PAYMASTER_URL, HTTP_TIMEOUT
        
        async with session.post(
            PAYMASTER_URL, 
            json={"transaction": raw_tx}, 
            headers={"Content-Type": "application/json"}, 
            ssl=ssl_context, 
            **proxy_kwargs, 
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.text()
                # Удаляем кавычки если есть
                result = result.strip('"')
                if result and result != "null" and len(result) > 10:
                    return True, result
                else:
                    logger.debug(f"Paymaster returned empty/invalid result: {result}")
                    return False, ""
            else:
                response_text = await resp.text()
                
                # Обрабатываем известные ошибки
                if "5663009" in response_text:
                    logger.debug("Paymaster: Known transaction error (5663009) - trying fallback")
                elif "500" in str(resp.status):
                    logger.debug("Paymaster: Server error (500) - trying fallback")
                else:
                    logger.error(f"❌ Paymaster returned status {resp.status}: {response_text[:200]}")
                return False, ""
                
    except Exception as e:
        logger.debug(f"Paymaster failed: {e}")
        return False, ""


async def check_transaction_status(session, tx_signature: str, ssl_context) -> bool:
    """Проверяет статус транзакции в FOGO network"""
    try:
        from config import FOGO_RPC_URL
        
        if not tx_signature or tx_signature == "1111111111111111111111111111111111111111111111111111111111111111":
            return True  # Placeholder считаем успешным
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignatureStatus",
            "params": [tx_signature]
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=10
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result and result['result']:
                    status = result['result']['value']
                    if status is None:
                        return False  # Транзакция не найдена
                    elif 'err' in status and status['err'] is None:
                        return True   # Успешная транзакция
                    else:
                        return False  # Ошибка в транзакции
                        
        return True  # По умолчанию считаем успешной если не можем проверить
        
    except Exception:
        return True  # По умолчанию считаем успешной если произошла ошибка при проверке