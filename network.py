"""
Сетевые операции и проверки для FOGO Bot
"""

import asyncio
import logging
import aiohttp
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.async_api import AsyncClient

from config import (
    FOGO_RPC_URL, FOGO_GENESIS_HASH, USER_AGENTS, 
    HTTP_TIMEOUT, NETWORK_CHECK_DELAY
)
from utils import create_ssl_context, truncate_address, format_token_amount

logger = logging.getLogger(__name__)


async def verify_fogo_connection(session: aiohttp.ClientSession) -> bool:
    """Проверяет подключение к FOGO testnet и валидирует параметры сети"""
    try:
        ssl_context = create_ssl_context()
        logger.info("🔍 Verifying FOGO testnet connection...")
        
        # Проверяем genesis hash
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getGenesisHash"
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result:
                    genesis_hash = result['result']
                    if genesis_hash == FOGO_GENESIS_HASH:
                        logger.info(f"✅ FOGO Genesis hash verified: {genesis_hash}")
                    else:
                        logger.warning(f"⚠️  Genesis hash mismatch! Expected: {FOGO_GENESIS_HASH}, Got: {genesis_hash}")
                        return False
                else:
                    logger.error(f"❌ Invalid genesis response: {result}")
                    return False
            else:
                logger.error(f"❌ Failed to get genesis hash, status: {resp.status}")
                return False
        
        # Проверяем версию сети
        await _check_network_version(session, ssl_context)
        
        # Проверяем активность сети
        network_active = await _check_network_activity(session, ssl_context)
        if network_active:
            logger.info("✅ FOGO testnet connection verified successfully!")
            return True
        else:
            logger.warning("⚠️  Network might be inactive")
            return False
        
    except Exception as e:
        logger.error(f"❌ FOGO connection verification failed: {e}")
        return False


async def _check_network_version(session: aiohttp.ClientSession, ssl_context):
    """Проверяет версию сети"""
    try:
        version_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getVersion"
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=version_payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result:
                    version_info = result['result']
                    logger.info(f"✅ FOGO Network version: {version_info.get('solana-core', 'Unknown')}")
                    
                    if 'feature-set' in version_info:
                        logger.info(f"✅ Feature set: {version_info['feature-set']}")
    except Exception as e:
        logger.debug(f"Failed to get network version: {e}")


async def _check_network_activity(session: aiohttp.ClientSession, ssl_context) -> bool:
    """Проверяет активность сети (прогресс слотов)"""
    try:
        slot_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSlot"
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=slot_payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result:
                    current_slot = result['result']
                    logger.info(f"✅ Current slot: {current_slot}")
                    
                    # Ждем и проверяем прогресс
                    await asyncio.sleep(NETWORK_CHECK_DELAY)
                    
                    async with session.post(
                        FOGO_RPC_URL,
                        json=slot_payload,
                        headers={'Content-Type': 'application/json'},
                        ssl=ssl_context,
                        timeout=HTTP_TIMEOUT
                    ) as resp2:
                        if resp2.status == 200:
                            result2 = await resp2.json()
                            if 'result' in result2:
                                new_slot = result2['result']
                                if new_slot > current_slot:
                                    logger.info(f"✅ Network is active (slot progressed from {current_slot} to {new_slot})")
                                    return True
                                else:
                                    logger.warning(f"⚠️  Network might be stalled (slot unchanged: {current_slot})")
                                    return False
        return False
    except Exception as e:
        logger.debug(f"Failed to check network activity: {e}")
        return False


async def get_balance_rpc(session: aiohttp.ClientSession, pubkey: PublicKey) -> int:
    """Получает баланс через прямой RPC вызов"""
    try:
        ssl_context = create_ssl_context()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [str(pubkey)]
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if 'result' in data and 'value' in data['result']:
                    return data['result']['value']
        return 0
    except Exception as e:
        logger.debug(f"RPC balance check failed for {truncate_address(str(pubkey))}: {e}")
        return 0


async def get_balance_client(client: AsyncClient, pubkey: PublicKey) -> int:
    """Получает баланс через Solana клиент"""
    try:
        resp = await client.get_balance(pubkey)
        if resp.value is not None:
            return resp.value
        return 0
    except Exception as e:
        logger.debug(f"Client balance check failed for {truncate_address(str(pubkey))}: {e}")
        return 0


async def check_wallets_balance(keypairs, session: aiohttp.ClientSession = None):
    """Проверяет балансы всех кошельков"""
    logger.info("Checking wallet balances...")
    
    if session:
        # Используем RPC через сессию
        for i, keypair in enumerate(keypairs, 1):
            balance = await get_balance_rpc(session, keypair.pubkey())
            status = "✅ Ready" if balance > 1000000 else "❌ Needs funding"
            logger.info(f"Wallet {i}: {truncate_address(str(keypair.pubkey()), 8)} | Balance: {format_token_amount(balance)} | {status}")
    else:
        # Используем стандартный клиент
        try:
            async with AsyncClient(FOGO_RPC_URL) as client:
                for i, keypair in enumerate(keypairs, 1):
                    balance = await get_balance_client(client, keypair.pubkey())
                    status = "✅ Ready" if balance > 1000000 else "❌ Needs funding"
                    logger.info(f"Wallet {i}: {truncate_address(str(keypair.pubkey()), 8)} | Balance: {format_token_amount(balance)} | {status}")
        except Exception as e:
            logger.error(f"Error checking balances: {e}")


async def send_rpc_request(session: aiohttp.ClientSession, method: str, params: list, timeout: int = HTTP_TIMEOUT):
    """Отправляет RPC запрос к FOGO сети"""
    try:
        ssl_context = create_ssl_context()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            ssl=ssl_context,
            timeout=timeout
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"RPC request failed with status {resp.status}")
                return None
    except Exception as e:
        logger.debug(f"RPC request failed: {e}")
        return None