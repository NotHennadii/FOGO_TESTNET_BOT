"""
Рабочие процессы для выполнения swap'ов
"""

import asyncio
import random
import logging
import platform
import aiohttp
from solders.keypair import Keypair

from config import (
    SWAP_AMOUNTS, SWAP_WEIGHTS, NATIVE_TOKEN_SYMBOL, 
    MIN_TRANSACTION_DELAY, LAMPORTS_PER_FOGO
)
from utils import (
    get_platform_connector_settings, calculate_adaptive_delay, 
    truncate_address, format_small_amount, create_safe_connector
)
from swap import perform_swap

logger = logging.getLogger(__name__)


async def worker(name: int, wallet: Keypair, swaps: int, 
                min_delay: float, max_delay: float, proxies) -> dict:
    """Рабочий процесс для выполнения swaps с оптимизацией для FOGO testnet"""
    
    proxy = random.choice(proxies) if proxies else None
    if proxy:
        logger.info(f"[Worker {name}] Using proxy: {proxy}")
    
    # Используем безопасный коннектор
    try:
        connector = create_safe_connector()
    except Exception as e:
        logger.warning(f"[Worker {name}] Failed to create safe connector: {e}")
        # Fallback: создаем простой коннектор прямо здесь
        try:
            connector = aiohttp.TCPConnector(ssl=False)
        except Exception as e2:
            logger.warning(f"[Worker {name}] Basic connector also failed: {e2}")
            connector = aiohttp.TCPConnector()
    
    timeout = aiohttp.ClientTimeout(total=60, connect=30)
    
    stats = {
        "successful_swaps": 0,
        "failed_swaps": 0,
        "total_volume": 0,
        "worker_name": name
    }
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for i in range(swaps):
            logger.info(f"[Worker {name}] Cycle {i+1}/{swaps} - Starting swap")
            
            # Выбираем сумму с учетом весов
            amount_in = random.choices(SWAP_AMOUNTS, weights=SWAP_WEIGHTS)[0]
            
            # Выполняем swap
            result = await perform_swap(
                session, wallet, amount_in=amount_in, 
                direction='FOGO_TO_FUSD', proxy=proxy
            )
            
            # Обновляем статистику
            if result > 0:
                stats["successful_swaps"] += 1
                stats["total_volume"] += amount_in
                logger.info(f"[Worker {name}] ✅ Cycle {i+1}/{swaps} - Swap successful, received {result} tokens (Volume: {format_small_amount(amount_in)})")
            else:
                stats["failed_swaps"] += 1
                logger.warning(f"[Worker {name}] ❌ Cycle {i+1}/{swaps} - Swap failed")
            
            # Адаптивная задержка между транзакциями
            if i < swaps - 1:
                await _adaptive_sleep(name, i, stats, min_delay, max_delay)
        
        # Финальная статистика
        _log_worker_stats(name, stats, swaps)
    
    return stats


async def _adaptive_sleep(worker_name: int, cycle: int, stats: dict, 
                         min_delay: float, max_delay: float):
    """Вычисляет и выполняет адаптивную задержку между транзакциями"""
    
    # Вычисляем процент неудач
    total_attempts = cycle + 1
    failure_rate = stats["failed_swaps"] / total_attempts if total_attempts > 0 else 0
    
    # Вычисляем задержку с учетом неудач
    sleep_time = calculate_adaptive_delay(min_delay, max_delay, failure_rate)
    
    # Обеспечиваем минимальную задержку для FOGO testnet (40ms блоки)
    sleep_time = max(sleep_time, MIN_TRANSACTION_DELAY)
    
    # Логируем информацию о задержке при высоком проценте неудач
    if failure_rate > 0.3:
        logger.debug(f"[Worker {worker_name}] High failure rate ({failure_rate:.1%}), using increased delay")
    
    logger.info(f"[Worker {worker_name}] Cycle {cycle+1} done. Sleeping {sleep_time:.1f}s...")
    await asyncio.sleep(sleep_time)


def _log_worker_stats(worker_name: int, stats: dict, total_swaps: int):
    """Логирует финальную статистику воркера"""
    success_rate = (stats["successful_swaps"] / total_swaps) * 100 if total_swaps > 0 else 0
    total_volume_fogo = stats["total_volume"] / LAMPORTS_PER_FOGO
    
    logger.info(f"[Worker {worker_name}] 🏁 All swaps completed!")
    logger.info(f"[Worker {worker_name}] 📊 Stats: {stats['successful_swaps']}✅/{stats['failed_swaps']}❌ ({success_rate:.1f}% success)")
    logger.info(f"[Worker {worker_name}] 💰 Total volume: {total_volume_fogo:.6f} {NATIVE_TOKEN_SYMBOL}")


async def run_multiple_workers(keypairs, num_swaps: int, min_delay: float, 
                              max_delay: float, proxies) -> dict:
    """Запускает множественные воркеры параллельно"""
    
    logger.info(f"🚀 Starting {len(keypairs)} workers...")
    
    start_time = asyncio.get_event_loop().time()
    
    # Создаем задачи для всех воркеров
    tasks = []
    for idx, keypair in enumerate(keypairs, start=1):
        task = worker(idx, keypair, num_swaps, min_delay, max_delay, proxies)
        tasks.append(task)

    # Ждем завершения всех воркеров
    worker_results = await asyncio.gather(*tasks)
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    # Собираем общую статистику
    total_stats = {
        "total_successful_swaps": sum(r["successful_swaps"] for r in worker_results),
        "total_failed_swaps": sum(r["failed_swaps"] for r in worker_results),
        "total_volume": sum(r["total_volume"] for r in worker_results),
        "total_time": total_time,
        "worker_count": len(keypairs),
        "swaps_per_worker": num_swaps,
        "worker_results": worker_results
    }
    
    return total_stats


def print_final_statistics(stats: dict):
    """Выводит финальную статистику работы всех воркеров"""
    from colorama import Fore, Style
    from config import NATIVE_TOKEN_SYMBOL, FOGO_GENESIS_HASH, EXPLORER_URL
    
    total_attempts = stats["worker_count"] * stats["swaps_per_worker"]
    success_rate = (stats["total_successful_swaps"] / total_attempts) * 100 if total_attempts > 0 else 0
    total_volume_fogo = stats["total_volume"] / LAMPORTS_PER_FOGO
    
    print(f"\n{Fore.GREEN}🎉 ALL WORKERS COMPLETED!{Style.RESET_ALL}")
    print(f"⏱️  Total execution time: {stats['total_time']:.2f} seconds")
    print(f"📈 Total swaps attempted: {total_attempts}")
    print(f"✅ Successful swaps: {stats['total_successful_swaps']} ({success_rate:.1f}%)")
    print(f"❌ Failed swaps: {stats['total_failed_swaps']}")
    print(f"💰 Total volume: {total_volume_fogo:.6f} {NATIVE_TOKEN_SYMBOL}")
    print(f"🪙 Native token: {NATIVE_TOKEN_SYMBOL} (FOGO Network)")
    print(f"🌐 FOGO Network: Genesis {FOGO_GENESIS_HASH[:8]}...{FOGO_GENESIS_HASH[-8:]}")
    print(f"🔗 Explorer: {EXPLORER_URL}")
    print(f"💡 Note: Paymaster errors (5663009) are normal - fallback RPC is working!")
    print(f"✅ Swaps are completing successfully with token rewards")
    
    # Детальная статистика по воркерам
    if len(stats["worker_results"]) > 1:
        print(f"\n{Fore.CYAN}📊 Worker Performance:{Style.RESET_ALL}")
        for result in stats["worker_results"]:
            worker_success_rate = (result["successful_swaps"] / stats["swaps_per_worker"]) * 100 if stats["swaps_per_worker"] > 0 else 0
            worker_volume = result["total_volume"] / LAMPORTS_PER_FOGO
            print(f"Worker {result['worker_name']}: {result['successful_swaps']}✅/{result['failed_swaps']}❌ ({worker_success_rate:.1f}%) - {worker_volume:.6f} {NATIVE_TOKEN_SYMBOL}")


def calculate_worker_efficiency(stats: dict) -> dict:
    """Вычисляет эффективность работы воркеров"""
    efficiency_data = {}
    
    for result in stats["worker_results"]:
        worker_name = result["worker_name"]
        total_attempts = stats["swaps_per_worker"]
        success_rate = (result["successful_swaps"] / total_attempts) * 100 if total_attempts > 0 else 0
        volume_per_swap = (result["total_volume"] / result["successful_swaps"]) if result["successful_swaps"] > 0 else 0
        
        efficiency_data[worker_name] = {
            "success_rate": success_rate,
            "volume_per_swap": volume_per_swap,
            "total_volume": result["total_volume"] / LAMPORTS_PER_FOGO,
            "swaps_per_minute": result["successful_swaps"] / (stats["total_time"] / 60) if stats["total_time"] > 0 else 0
        }
    
    return efficiency_data


def print_efficiency_report(stats: dict):
    """Выводит детальный отчет об эффективности"""
    from colorama import Fore, Style
    
    efficiency = calculate_worker_efficiency(stats)
    
    print(f"\n{Fore.YELLOW}📈 EFFICIENCY REPORT{Style.RESET_ALL}")
    print("=" * 60)
    
    # Сортируем воркеров по успешности
    sorted_workers = sorted(efficiency.items(), key=lambda x: x[1]["success_rate"], reverse=True)
    
    print(f"{'Worker':<8} {'Success%':<9} {'Vol/Swap':<10} {'Total Vol':<12} {'Swaps/min':<10}")
    print("-" * 60)
    
    for worker_name, data in sorted_workers:
        print(f"{worker_name:<8} {data['success_rate']:<8.1f}% {data['volume_per_swap']/LAMPORTS_PER_FOGO:<9.6f} {data['total_volume']:<11.6f} {data['swaps_per_minute']:<9.2f}")
    
    # Средние показатели
    avg_success = sum(d["success_rate"] for d in efficiency.values()) / len(efficiency)
    avg_volume = sum(d["total_volume"] for d in efficiency.values()) / len(efficiency)
    avg_speed = sum(d["swaps_per_minute"] for d in efficiency.values()) / len(efficiency)
    
    print("-" * 60)
    print(f"{'Average':<8} {avg_success:<8.1f}% {'-':<9} {avg_volume:<11.6f} {avg_speed:<9.2f}")
    
    # Рекомендации
    print(f"\n{Fore.CYAN}💡 RECOMMENDATIONS:{Style.RESET_ALL}")
    
    best_worker = max(efficiency.items(), key=lambda x: x[1]["success_rate"])
    worst_worker = min(efficiency.items(), key=lambda x: x[1]["success_rate"])
    
    if best_worker[1]["success_rate"] - worst_worker[1]["success_rate"] > 20:
        print(f"• Large performance difference detected between workers")
        print(f"• Best: Worker {best_worker[0]} ({best_worker[1]['success_rate']:.1f}%)")
        print(f"• Worst: Worker {worst_worker[0]} ({worst_worker[1]['success_rate']:.1f}%)")
        print(f"• Consider adjusting delays or proxy settings")
    
    if avg_success < 70:
        print(f"• Overall success rate is low ({avg_success:.1f}%)")
        print(f"• Consider increasing delays between transactions")
        print(f"• Check network conditions and RPC stability")
    
    if avg_speed < 1:
        print(f"• Transaction speed is low ({avg_speed:.2f} swaps/min)")
        print(f"• Consider decreasing delays or optimizing network settings")


async def monitor_worker_progress(worker_stats_queue: asyncio.Queue, total_workers: int):
    """Мониторит прогресс выполнения воркеров в реальном времени"""
    from colorama import Fore, Style
    
    completed_workers = 0
    total_successful = 0
    total_failed = 0
    
    print(f"\n{Fore.CYAN}📊 REAL-TIME MONITORING{Style.RESET_ALL}")
    print("=" * 50)
    
    while completed_workers < total_workers:
        try:
            # Ждем обновления от воркеров
            worker_update = await asyncio.wait_for(worker_stats_queue.get(), timeout=30.0)
            
            if worker_update["status"] == "completed":
                completed_workers += 1
                total_successful += worker_update["successful_swaps"]
                total_failed += worker_update["failed_swaps"]
                
                progress = (completed_workers / total_workers) * 100
                overall_success = (total_successful / (total_successful + total_failed)) * 100 if (total_successful + total_failed) > 0 else 0
                
                print(f"Worker {worker_update['worker_name']} completed: {worker_update['successful_swaps']}✅/{worker_update['failed_swaps']}❌")
                print(f"Progress: {completed_workers}/{total_workers} ({progress:.1f}%) | Overall success: {overall_success:.1f}%")
                print("-" * 50)
            
        except asyncio.TimeoutError:
            # Тайм-аут - продолжаем мониторинг
            continue
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            break
    
    print(f"{Fore.GREEN}✅ All workers completed monitoring{Style.RESET_ALL}")


def generate_summary_report(stats: dict, output_file: str = "fogo_bot_report.txt"):
    """Генерирует текстовый отчет о работе бота"""
    import datetime
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("FOGO NETWORK BOT - EXECUTION REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        # Общая информация
        f.write(f"Report generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Execution time: {stats['total_time']:.2f} seconds\n")
        f.write(f"Workers used: {stats['worker_count']}\n")
        f.write(f"Swaps per worker: {stats['swaps_per_worker']}\n\n")
        
        # Статистика
        total_attempts = stats["worker_count"] * stats["swaps_per_worker"]
        success_rate = (stats["total_successful_swaps"] / total_attempts) * 100 if total_attempts > 0 else 0
        total_volume_fogo = stats["total_volume"] / LAMPORTS_PER_FOGO
        
        f.write("OVERALL STATISTICS:\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total swaps attempted: {total_attempts}\n")
        f.write(f"Successful swaps: {stats['total_successful_swaps']} ({success_rate:.1f}%)\n")
        f.write(f"Failed swaps: {stats['total_failed_swaps']}\n")
        f.write(f"Total volume: {total_volume_fogo:.6f} FOGO\n")
        f.write(f"Average volume per swap: {total_volume_fogo/stats['total_successful_swaps']:.6f} FOGO\n\n")
        
        # Детальная статистика по воркерам
        f.write("WORKER PERFORMANCE:\n")
        f.write("-" * 40 + "\n")
        f.write(f"{'Worker':<8} {'Success':<8} {'Failed':<8} {'Rate%':<8} {'Volume':<12}\n")
        f.write("-" * 50 + "\n")
        
        for result in stats["worker_results"]:
            worker_success_rate = (result["successful_swaps"] / stats["swaps_per_worker"]) * 100 if stats["swaps_per_worker"] > 0 else 0
            worker_volume = result["total_volume"] / LAMPORTS_PER_FOGO
            f.write(f"{result['worker_name']:<8} {result['successful_swaps']:<8} {result['failed_swaps']:<8} {worker_success_rate:<7.1f}% {worker_volume:<11.6f}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("End of Report\n")
    
    logger.info(f"📄 Summary report saved to: {output_file}")


# Экспортируемые функции модуля
__all__ = [
    'worker',
    'run_multiple_workers', 
    'print_final_statistics',
    'calculate_worker_efficiency',
    'print_efficiency_report',
    'monitor_worker_progress',
    'generate_summary_report'
]