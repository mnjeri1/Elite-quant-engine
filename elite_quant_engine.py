import ccxt.async_support as ccxt
import aiohttp
import asyncio
import logging
import math
from datetime import datetime, time
import pytz
from dataclasses import dataclass, field
from typing import List, Optional

# Optional real SDK imports for equities (Alpaca Trading & Historical Data)
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, 
        TakeProfitRequest, 
        StopLossRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest
    ALPACA_SDK_AVAILABLE = True
except ImportError:
    ALPACA_SDK_AVAILABLE = False

# Optional real SDK imports for Interactive Brokers (IBKR) via ib_insync
try:
    from ib_insync import IB, Stock, Forex, MarketOrder, LimitOrder, StopOrder
    IBKR_SDK_AVAILABLE = True
except ImportError:
    IBKR_SDK_AVAILABLE = False

# Institutional Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (LiveEngine): %(message)s")
logger = logging.getLogger("UniversalInstitutionalEngine")

@dataclass
class LiveTradeOrder:
    symbol: str
    asset_class: str  # 'CRYPTO_SPOT', 'CRYPTO_FUTURE', 'FOREX', or 'STOCKS'
    side: str         # 'BUY' or 'SELL'
    entry_price: float
    volume: float
    stop_loss: float
    take_profit: float
    trailing_delta: float = 0.0
    highest_price: float = field(init=False)
    is_active: bool = True

    def __post_init__(self):
        self.highest_price = self.entry_price


class UniversalMultiBrokerGateway:
    """
    Seamlessly routes live trades and native bracket risk management across 
    Binance Spot/Futures, Alpaca Equities, and Interactive Brokers (IBKR) for Forex via persistent session pooling.
    Configured strictly for LIVE production environments (paper=False).
    """
    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.exchanges = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.stock_data_client = None
        self.ibkr_client = None

    async def initialize_exchanges(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

        stocks_creds = self.credentials.get("stocks", {})
        binance_creds = self.credentials.get("binance", {})
        ibkr_creds = self.credentials.get("ibkr", {})

        # 1. Initialize Crypto Spot (Binance Live)
        if binance_creds.get("api_key") and binance_creds.get("secret_key"):
            if "CRYPTO_SPOT" not in self.exchanges:
                self.exchanges["CRYPTO_SPOT"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                logger.info("[CCXT] Binance Spot LIVE connection initialized.")

            # 2. Initialize Crypto Futures (Binance USD-M Live)
            if "CRYPTO_FUTURE" not in self.exchanges:
                self.exchanges["CRYPTO_FUTURE"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })
                logger.info("[CCXT] Binance Futures LIVE connection initialized.")

        # 3. Initialize Stocks (Alpaca Live Trading & Historical Data Clients)
        if stocks_creds.get("api_key") and stocks_creds.get("secret_key") and ALPACA_SDK_AVAILABLE:
            if "STOCKS" not in self.exchanges:
                self.exchanges["STOCKS"] = TradingClient(
                    stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"],
                    paper=False  # STRICTLY LIVE TRADING ENDPOINT
                )
                self.stock_data_client = StockHistoricalDataClient(
                    api_key=stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"]
                )
                logger.info("[ALPACA] Equities LIVE trading and data feeds initialized.")

        # 4. Initialize Interactive Brokers (IBKR) for Forex Live Gateway (Port 7496 for Live TWS)
        if ibkr_creds.get("host") and ibkr_creds.get("port") and IBKR_SDK_AVAILABLE:
            if "IBKR" not in self.exchanges:
                self.ibkr_client = IB()
                try:
                    await self.ibkr_client.connectAsync(
                        host=ibkr_creds.get("host", "127.0.0.1"),
                        port=int(ibkr_creds.get("port", 7496)), # Port 7496 is Live TWS/Gateway
                        clientId=int(ibkr_creds.get("client_id", 1))
                    )
                    self.exchanges["IBKR"] = self.ibkr_client
                    logger.info("[IBKR] Interactive Brokers LIVE gateway connection initialized.")
                except Exception as e:
                    logger.error(f"[IBKR ERROR] Failed to connect to IBKR LIVE socket: {e}")

    async def close_exchanges(self):
        for key in ["CRYPTO_SPOT", "CRYPTO_FUTURE"]:
            if key in self.exchanges:
                await self.exchanges[key].close()
                self.exchanges.pop(key, None)
        
        if self.ibkr_client and self.ibkr_client.isConnected():
            self.ibkr_client.disconnect()
            logger.info("[IBKR] Disconnected from Interactive Brokers live gateway.")

        if self.session and not self.session.closed:
            await self.session.close()

    def _submit_alpaca_sync(self, client, market_order_data):
        return client.submit_order(order_data=market_order_data)

    async def execute_order(self, order: LiveTradeOrder) -> bool:
        try:
            # --- CRYPTO FUTURES ---
            if order.asset_class == "CRYPTO_FUTURE" and "CRYPTO_FUTURE" in self.exchanges:
                exchange = self.exchanges["CRYPTO_FUTURE"]
                params = {'stopLossPrice': order.stop_loss, 'takeProfitPrice': order.take_profit}
                await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume, params=params)
                return True

            # --- CRYPTO SPOT ---
            elif order.asset_class == "CRYPTO_SPOT" and "CRYPTO_SPOT" in self.exchanges:
                exchange = self.exchanges["CRYPTO_SPOT"]
                await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume)
                inverted_side = 'sell' if order.side.upper() == 'BUY' else 'buy'
                await exchange.create_order(order.symbol, 'STOP_MARKET', inverted_side, order.volume, None, {'stopPrice': order.stop_loss})
                await exchange.create_order(order.symbol, 'TAKE_PROFIT_MARKET', inverted_side, order.volume, None, {'stopPrice': order.take_profit})
                return True

            # --- STOCKS (Alpaca Live) ---
            elif order.asset_class == "STOCKS" and "STOCKS" in self.exchanges:
                client = self.exchanges["STOCKS"]
                side_enum = OrderSide.BUY if order.side.upper() == "BUY" else OrderSide.SELL
                market_order_data = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.volume,
                    side=side_enum,
                    time_in_force=TimeInForce.DAY,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=order.take_profit),
                    stop_loss=StopLossRequest(stop_price=order.stop_loss)
                )
                await asyncio.to_thread(self._submit_alpaca_sync, client, market_order_data)
                return True

            # --- FOREX (IBKR Live) ---
            elif order.asset_class == "FOREX" and "IBKR" in self.exchanges:
                if not IBKR_SDK_AVAILABLE or not self.ibkr_client or not self.ibkr_client.isConnected():
                    logger.error("[FOREX ERROR] IBKR live client is not connected.")
                    return False

                contract = Forex(order.symbol)
                await self.ibkr_client.qualifyContractsAsync(contract)
                
                action = "BUY" if order.side.upper() == "BUY" else "SELL"
                parent_order = MarketOrder(action, order.volume)
                parent_order.transmit = False
                
                tp_action = "SELL" if action == "BUY" else "BUY"
                sl_action = "SELL" if action == "BUY" else "BUY"
                
                tp_order = LimitOrder(tp_action, order.volume, order.take_profit)
                tp_order.parentId = parent_order.orderId
                tp_order.transmit = False
                
                sl_order = StopOrder(sl_action, order.volume, order.stop_loss)
                sl_order.parentId = parent_order.orderId
                sl_order.transmit = True
                
                for o in [parent_order, tp_order, sl_order]:
                    self.ibkr_client.placeOrder(contract, o)
                return True

        except Exception as e:
            logger.error(f"[EXECUTION ERROR] {e}")
            return False
        return False


class ZeroLagMultiMarketEngine:
    def __init__(self, symbols_config: List[dict], min_capital: float = 20.0, credentials: dict = None):
        self.symbols_config = symbols_config
        self.min_capital = min_capital
        self.active_orders: List[LiveTradeOrder] = []
        self.gateway = UniversalMultiBrokerGateway(credentials or {})

    def verify_capital(self, account_balance: float) -> bool:
        return account_balance >= self.min_capital

    def is_market_open(self, asset_class: str) -> bool:
        if asset_class in ["CRYPTO_SPOT", "CRYPTO_FUTURE"]:
            return True

        ny_tz = pytz.timezone("America/New_York")
        now_ny = datetime.now(ny_tz)
        current_time = now_ny.time()
        current_weekday = now_ny.weekday()

        if asset_class == "STOCKS":
            if current_weekday >= 5:
                return False
            return time(9, 30) <= current_time <= time(16, 0)

        elif asset_class == "FOREX":
            if current_weekday == 5:
                return False
            if current_weekday == 6 and current_time < time(17, 0):
                return False
            if current_weekday == 4 and current_time >= time(17, 0):
                return False
            return True

        return True

    def calculate_effective_position_size(self, account_balance: float, risk_percentage: float, entry_price: float, stop_loss: float) -> float:
        if entry_price == stop_loss or account_balance < self.min_capital:
            return 0.0
        risk_amount = account_balance * risk_percentage
        risk_per_unit = abs(entry_price - stop_loss)
        return round(risk_amount / risk_per_unit, 4)

    async def deploy_trade(self, order: LiveTradeOrder, account_balance: float) -> bool:
        if not self.verify_capital(account_balance):
            logger.warning("[CAPITAL WARNING] Insufficient balance to deploy live trade.")
            return False
        if not self.is_market_open(order.asset_class):
            logger.info(f"[SESSION FILTER] Market for {order.symbol} ({order.asset_class}) is currently closed. Bypassing loop.")
            return False
            
        await self.gateway.initialize_exchanges()
        return await self.gateway.execute_order(order)

    async def run_zero_lag_execution_loop(self, current_balance: float):
        await self.gateway.initialize_exchanges()
        logger.info("Zero-lag live multi-market execution engine active for PRODUCTION.")

        try:
            while True:
                if not self.verify_capital(current_balance):
                    logger.error("[CRITICAL CAPITAL ERROR] Balance dropped below threshold. Halting live engine.")
                    break

                tasks = []
                for item in self.symbols_config:
                    symbol = item["symbol"]
                    asset_type = item["asset_class"]
                    
                    if not self.is_market_open(asset_type):
                        continue

                    tasks.append(self._process_symbol_loop(symbol, asset_type, current_balance))

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(0.1)
        finally:
            await self.gateway.close_exchanges()

    async def _process_symbol_loop(self, symbol: str, asset_type: str, balance: float):
        pass
