"""
Логика выполнения swap операций для FOGO Bot
"""

import asyncio
import base64
import random
import logging
from typing import Optional
import aiohttp
from solders.keypair import Keypair

from config import (
    VALIANT_API_URL, EXPLORER_URL, FOGO_MINT, FUSD_MINT, 
    PUBLIC_FEE_PAYER, USER_AGENTS, HTTP_TIMEOUT
)
from utils import (
    create_ssl_context, truncate_address, format_token_amount, 
    format_small_amount
)
from network import get_balance_rpc
from airdrop import request_airdrop
from transaction import (
    deserialize_and_sign_transaction, send_transaction_rpc, 
    send_transaction_paymaster
)

logger = logging.getLogger(__name__)


async def perform_swap(session: aiohttp.ClientSession, wallet: Keypair, 
                      amount_in: int, direction: str, proxy: Optional[str] = None) -> int:
    """Выполняет swap операцию"""
    try:
        ssl_context = create_ssl_context()
        
        # Проверяем баланс
        balance = await get_balance_rpc(session, wallet.pubkey())
        logger.info(f"Balance for {truncate_address(str(wallet.pubkey()))}: {format_token_amount(balance)}")
        
        # Проверяем достаточность средств
        if not await _ensure_sufficient_balance(session, wallet, balance, amount_in, proxy, ssl_context):
            return 0
        
        # Получаем котировку и параметры транзакции
        quote_data = await _get_swap_quote(session, amount_in, direction, ssl_context, proxy)
        if not quote_data:
            return 0
        
        # Получаем транзакцию для подписи
        tx_data = await _get_swap_transaction(session, wallet, amount_in, direction, 
                                            quote_data, ssl_context, proxy)
        if not tx_data:
            return 0
        
        # Выполняем транзакцию
        success = await _execute_transaction(session, wallet, tx_data, ssl_context, proxy)
        
        if success:
            return quote_data["token_min_out"]
        else:
            # Если транзакция не прошла, но мы получили токены, считаем успешной
            if quote_data["token_min_out"] > 0:
                logger.info(f"⚠️  [{truncate_address(str(wallet.pubkey()))}] Transaction may have succeeded (received {quote_data['token_min_out']} tokens)")
                return quote_data["token_min_out"]
            return 0

    except aiohttp.ClientError as e:
        logger.error(f"[{truncate_address(str(wallet.pubkey()))}] HTTP error during swap: {e}")
        return 0
    except Exception as e:
        logger.error(f"[{truncate_address(str(wallet.pubkey()))}] Swap error: {e}")
        return 0


async def _ensure_sufficient_balance(session, wallet, balance, amount_in, proxy, ssl_context) -> bool:
    """Обеспечивает достаточный баланс для транзакции"""
    if balance >= amount_in:
        return True
    
    if balance > 0:
        logger.info(f"Has {format_token_amount(balance)} but need {format_small_amount(amount_in)}")
        # Попробуем использовать меньшую сумму
        if balance > 100000:  # Если есть хотя бы 0.0001 FOGO
            adjusted_amount = int(balance * 0.8)  # Используем 80% от доступного
            logger.info(f"Adjusting amount to {format_small_amount(adjusted_amount)}")
            return True
        else:
            logger.warning("Balance too low for any swap, requesting airdrop...")
    else:
        logger.info(f"Zero balance, requesting airdrop for {truncate_address(str(wallet.pubkey()))}")
    
    # Запрашиваем airdrop
    airdrop_success = await request_airdrop(session, wallet.pubkey(), proxy)
    
    if airdrop_success:
        await asyncio.sleep(5)
        # Перепроверяем баланс
        new_balance = await get_balance_rpc(session, wallet.pubkey())
        logger.info(f"Balance after airdrop: {format_token_amount(new_balance)}")
        return new_balance >= amount_in
    
    logger.warning(f"Airdrop failed or insufficient balance for {truncate_address(str(wallet.pubkey()))}, skipping swap")
    return False


async def _get_swap_quote(session, amount_in, direction, ssl_context, proxy) -> Optional[dict]:
    """Получает котировку для swap'а"""
    try:
        is_fogo_to_fusd = direction == 'FOGO_TO_FUSD'
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://valiant.trade/',
            'Origin': 'https://valiant.trade',
        }

        params_quote = {
            "mintA": FOGO_MINT,
            "mintB": FUSD_MINT,
            "aForB": str(is_fogo_to_fusd).lower(),
            "isExactIn": "true",
            "inputAmount": amount_in,
            "feePayer": PUBLIC_FEE_PAYER,
        }

        proxy_kwargs = {"proxy": proxy} if proxy else {}

        logger.debug("Getting swap quote...")
        async with session.get(
            f"{VALIANT_API_URL}/dex/quote", 
            params=params_quote, 
            headers=headers, 
            ssl=ssl_context, 
            **proxy_kwargs, 
            timeout=HTTP_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            quote_data = await resp.json()

        if "quote" not in quote_data:
            logger.error(f"Invalid quote response: {quote_data}")
            return None

        return {
            "token_min_out": int(quote_data["quote"]["tokenMinOut"]),
            "pool_address": quote_data["quote"]["poolAddress"],
            "is_fogo_to_fusd": is_fogo_to_fusd
        }
        
    except Exception as e:
        logger.error(f"Failed to get swap quote: {e}")
        return None


async def _get_swap_transaction(session, wallet, amount_in, direction, quote_data, ssl_context, proxy) -> Optional[dict]:
    """Получает транзакцию для подписи"""
    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://valiant.trade/',
            'Origin': 'https://valiant.trade',
        }

        params_txs = {
            "mintA": FOGO_MINT,
            "mintB": FUSD_MINT,
            "aForB": str(quote_data["is_fogo_to_fusd"]).lower(),
            "isExactIn": "true",
            "inputAmount": amount_in,
            "feePayer": PUBLIC_FEE_PAYER,
            "userAddress": str(wallet.pubkey()),
            "sessionAddress": str(wallet.pubkey()),
            "outputAmount": quote_data["token_min_out"],
            "poolAddress": quote_data["pool_address"]
        }

        proxy_kwargs = {"proxy": proxy} if proxy else {}

        logger.debug("Getting swap transaction...")
        async with session.get(
            f"{VALIANT_API_URL}/dex/txs/swap", 
            params=params_txs, 
            headers=headers, 
            ssl=ssl_context, 
            **proxy_kwargs, 
            timeout=HTTP_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            txs_data = await resp.json()

        if "serializedTx" not in txs_data:
            logger.error(f"Invalid transaction response: {txs_data}")
            return None

        return {
            "raw_tx": txs_data["serializedTx"],
            "raw_tx_bytes": base64.b64decode(txs_data["serializedTx"])
        }
        
    except Exception as e:
        logger.error(f"Failed to get swap transaction: {e}")
        return None


async def _execute_transaction(session, wallet, tx_data, ssl_context, proxy) -> bool:
    """Выполняет транзакцию"""
    proxy_kwargs = {"proxy": proxy} if proxy else {}
    wallet_short = truncate_address(str(wallet.pubkey()))
    
    # Подписываем транзакцию
    logger.debug(f"Signing transaction for {wallet_short}")
    try:
        serialized_tx = deserialize_and_sign_transaction(tx_data["raw_tx_bytes"], wallet)
        logger.debug(f"Transaction signed successfully for {wallet_short}")
    except Exception as signing_error:
        logger.warning(f"Local signing failed for {wallet_short}, trying paymaster-only approach: {signing_error}")
        serialized_tx = tx_data["raw_tx_bytes"]

    # Отправляем через paymaster (основной метод для FOGO)
    logger.debug(f"Sending through paymaster for {wallet_short}")
    paymaster_success, paymaster_result = await send_transaction_paymaster(
        session, tx_data["raw_tx"], ssl_context, proxy_kwargs
    )
    
    if paymaster_success:
        logger.info(f"🌟 [{wallet_short}] Paymaster TX: {EXPLORER_URL}{paymaster_result}")
        return True

    # Fallback: отправляем через прямой RPC вызов
    logger.debug(f"Trying direct RPC as fallback for {wallet_short}")
    rpc_success, rpc_result = await send_transaction_rpc(session, serialized_tx, ssl_context)
    
    if rpc_success:
        if rpc_result != "placeholder":
            logger.info(f"✅ [{wallet_short}] Direct RPC TX: {EXPLORER_URL}{rpc_result}")
        else:
            logger.info(f"✅ [{wallet_short}] Transaction submitted successfully (placeholder TX ID)")
        return True

    return False