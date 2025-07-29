"""
Функции для получения airdrop токенов FOGO
"""

import asyncio
import logging
import random
from typing import Optional
import aiohttp
from solders.pubkey import Pubkey as PublicKey

from config import (
    FOGO_RPC_URL, USER_AGENTS, HTTP_TIMEOUT, 
    AIRDROP_CONFIRMATION_DELAY
)
from utils import create_ssl_context, truncate_address

logger = logging.getLogger(__name__)


async def request_airdrop(session: aiohttp.ClientSession, pubkey: PublicKey, proxy: Optional[str] = None) -> bool:
    """Запрашивает airdrop тестовых токенов через различные методы"""
    try:
        proxy_kwargs = {}
        if proxy:
            proxy_kwargs = {"proxy": proxy}
            
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        ssl_context = create_ssl_context()
        
        # Попытка 1: Официальный FOGO RPC airdrop
        if await _try_official_fogo_airdrop(session, pubkey, headers, ssl_context, proxy_kwargs):
            return True
        
        # Попытка 2: Альтернативные faucet endpoints
        if await _try_alternative_faucets(session, pubkey, headers, ssl_context, proxy_kwargs):
            return True
        
        # Попытка 3: Solana devnet fallback
        if await _try_devnet_fallback(session, pubkey, headers, proxy_kwargs):
            return True
                
        logger.warning(f"❌ All airdrop methods failed for {truncate_address(str(pubkey))}")
        return False
        
    except Exception as e:
        logger.error(f"Airdrop request failed for {pubkey}: {e}")
        return False


async def _try_official_fogo_airdrop(session, pubkey, headers, ssl_context, proxy_kwargs) -> bool:
    """Попытка получить airdrop через официальный FOGO RPC"""
    try:
        logger.debug(f"Trying official FOGO RPC airdrop for {truncate_address(str(pubkey))}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "requestAirdrop",
            "params": [str(pubkey), 2000000000]  # 2 FOGO
        }
        
        async with session.post(
            FOGO_RPC_URL,
            json=payload,
            headers=headers,
            ssl=ssl_context,
            **proxy_kwargs,
            timeout=HTTP_TIMEOUT
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result and result['result']:
                    logger.info(f"✅ Official FOGO airdrop successful for {truncate_address(str(pubkey))} TX: {result['result']}")
                    return True
                elif 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                    logger.debug(f"FOGO RPC airdrop error: {error_msg}")
                    
                    # Если ошибка о лимите, это нормально
                    if any(keyword in error_msg.lower() for keyword in ['limit', 'already', 'funded', 'recent']):
                        logger.info(f"✅ FOGO airdrop limit reached for {truncate_address(str(pubkey))} (already funded recently)")
                        return True
            else:
                logger.debug(f"FOGO RPC returned status {resp.status}")
                        
    except Exception as e:
        logger.debug(f"Official FOGO RPC airdrop failed: {e}")
    
    return False


async def _try_alternative_faucets(session, pubkey, headers, ssl_context, proxy_kwargs) -> bool:
    """Попытка получить airdrop через альтернативные faucets"""
    faucet_endpoints = [
        {
            "url": "https://faucet.fogo.io/api/airdrop",
            "data": {"address": str(pubkey), "amount": 2000000000}
        },
        {
            "url": "https://testnet.fogo.io/api/faucet",
            "data": {"wallet": str(pubkey), "network": "testnet"}
        }
    ]
    
    for endpoint in faucet_endpoints:
        try:
            logger.debug(f"Trying faucet: {endpoint['url']}")
            
            async with session.post(
                endpoint["url"], 
                json=endpoint["data"], 
                headers=headers,
                ssl=ssl_context,
                **proxy_kwargs, 
                timeout=HTTP_TIMEOUT
            ) as resp:
                response_text = await resp.text()
                if resp.status in [200, 201]:
                    logger.info(f"✅ Alternative faucet successful for {truncate_address(str(pubkey))} Response: {response_text[:100]}")
                    return True
                else:
                    logger.debug(f"Faucet {endpoint['url']} returned status {resp.status}: {response_text[:200]}")
                    
        except Exception as e:
            logger.debug(f"Faucet {endpoint['url']} failed: {e}")
            continue
    
    return False


async def _try_devnet_fallback(session, pubkey, headers, proxy_kwargs) -> bool:
    """Попытка получить airdrop через Solana devnet как fallback"""
    try:
        logger.debug(f"Trying Solana devnet fallback for {truncate_address(str(pubkey))}")
        
        devnet_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "requestAirdrop",
            "params": [str(pubkey), 2000000000]  # 2 FOGO
        }
        
        devnet_url = "https://api.devnet.solana.com"
        
        async with session.post(
            devnet_url,
            json=devnet_payload,
            headers=headers,
            **proxy_kwargs,
            timeout=20
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if 'result' in result and result['result']:
                    logger.info(f"✅ Devnet fallback airdrop for {truncate_address(str(pubkey))}")
                    return True
    except Exception as e:
        logger.debug(f"Devnet fallback failed: {e}")
    
    return False


async def request_multiple_airdrops(session: aiohttp.ClientSession, keypairs, proxies) -> int:
    """Запрашивает airdrop для множества кошельков"""
    logger.info("🚰 Requesting airdrops for all wallets...")
    
    airdrop_tasks = []
    for keypair in keypairs:
        proxy = random.choice(proxies) if proxies else None
        airdrop_tasks.append(request_airdrop(session, keypair.pubkey(), proxy))
    
    results = await asyncio.gather(*airdrop_tasks, return_exceptions=True)
    successful_airdrops = sum(1 for r in results if r is True)
    
    logger.info(f"🚰 Airdrop requests completed: {successful_airdrops}/{len(keypairs)} successful")
    
    if successful_airdrops > 0:
        logger.info(f"⏳ Waiting {AIRDROP_CONFIRMATION_DELAY} seconds for airdrop confirmations...")
        await asyncio.sleep(AIRDROP_CONFIRMATION_DELAY)
    
    return successful_airdrops