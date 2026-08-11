import asyncio
import logging
from core_engine import InstitutionalGateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def background_market_monitor():
    """Runs continuously in the background to monitor multi-market health and manage active trades."""
    gateway = InstitutionalGateway()
    
    logging.info("Starting Elite Quant Engine background execution loop (run.py)...")
    
    while True:
        try:
            # 1. Periodically check connection health across all exchanges
            mock_keys = {"Binance": "active", "Alpaca": "active", "InteractiveBrokers": "active"}
            health = await gateway.verify_all_gateways(mock_keys)
            logging.info(f"Background Gateway Health Check: {health}")
            
            # 2. Simulate continuous asynchronous market scans and trailing profit management
            await asyncio.sleep(10)
            
        except Exception as e:
            logging.error(f"Error in background execution loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(background_market_monitor())
    except KeyboardInterrupt:
        logging.info("Elite Quant Engine background runner stopped manually.")
