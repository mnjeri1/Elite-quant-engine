import ccxt.async_support as ccxt
import aiohttp
import asyncio
import logging
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
    Binance Spot/Futures, Alpaca Equities, and OANDA Forex via persistent session pooling.
    """
    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.exchanges = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.stock_data_client = None

    async def initialize_exchanges(self):
        # Initialize persistent aiohttp session for REST protocols (OANDA / general HTTP hooks)
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

        stocks_creds = self.credentials.get("stocks", {})
        binance_creds = self.credentials.get("binance", {})

        # 1. Initialize Crypto Spot (Binance)
        if binance_creds.get("api_key") and binance_creds.get("secret_key"):
            if "CRYPTO_SPOT" not in self.exchanges:
                self.exchanges["CRYPTO_SPOT"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                logger.info("[CCXT] Binance Spot live connection initialized.")

            # 2. Initialize Crypto Futures (Binance USD-M)
            if "CRYPTO_FUTURE" not in self.exchanges:
                self.exchanges["CRYPTO_FUTURE"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })
                logger.info("[CCXT] Binance Futures live connection initialized.")

        # 3. Initialize Stocks (Alpaca Trading & Historical Data Clients)
        if stocks_creds.get("api_key") and stocks_creds.get("secret_key") and ALPACA_SDK_AVAILABLE:
            if "STOCKS" not in self.exchanges:
                self.exchanges["STOCKS"] = TradingClient(
                    stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"],
                    paper=stocks_creds.get("paper", True) 
                )
                self.stock_data_client = StockHistoricalDataClient(
                    api_key=stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"]
                )
                logger.info("[ALPACA] Equities trading and data feeds initialized.")

    async def close_exchanges(self):
        for key in ["CRYPTO_SPOT", "CRYPTO_FUTURE"]:
            if key in self.exchanges:
                await self.exchanges[key].close()
                self.exchanges.pop(key, None)
        
        if self.session and not self.session.closed:
            await self.session.close()

    async def execute_order(self, order: LiveTradeOrder) -> bool:
        try:
            # --- CRYPTO EXECUTION (Derivatives / Futures via CCXT native brackets) ---
            if order.asset_class == "CRYPTO_FUTURE" and "CRYPTO_FUTURE" in self.exchanges:
                exchange = self.exchanges["CRYPTO_FUTURE"]
                logger.info(f"[CRYPTO_FUTURE LIVE] Dispatching bracket order for {order.symbol}...")
                params = {
                    'stopLossPrice': order.stop_loss,
                    'takeProfitPrice': order.take_profit
                }
                await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume, params=params)
                return True

            # --- CRYPTO EXECUTION (Spot Market Order + Subsequent Safety Triggers) ---
            elif order.asset_class == "CRYPTO_SPOT" and "CRYPTO_SPOT" in self.exchanges:
                exchange = self.exchanges["CRYPTO_SPOT"]
                logger.info(f"[CRYPTO_SPOT LIVE] Executing spot entry & conditional bracket for {order.symbol}...")
                
                # 1. Execute primary market fill
                await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume)
                
                # 2. Submit independent safety triggers for spot portfolios
                inverted_side = 'sell' if order.side.upper() == 'BUY' else 'buy'
                await exchange.create_order(order.symbol, 'STOP_MARKET', inverted_side, order.volume, None, {'stopPrice': order.stop_loss})
                await exchange.create_order(order.symbol, 'TAKE_PROFIT_MARKET', inverted_side, order.volume, None, {'stopPrice': order.take_profit})
                return True

            # --- STOCKS EXECUTION (Alpaca Native Bracket Orders) ---
            elif order.asset_class == "STOCKS" and "STOCKS" in self.exchanges:
                client = self.exchanges["STOCKS"]
                logger.info(f"[ALPACA LIVE] Routing equity bracket order for {order.symbol}...")
                
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
                client.submit_order(order_data=market_order_data)
                return True

            # --- FOREX EXECUTION (OANDA REST v20 with server-side OCO brackets) ---
            elif order.asset_class == "FOREX":
                forex_creds = self.credentials.get("forex", {})
                token = forex_creds.get("access_token")
                account_id = forex_creds.get("account_id", "YOUR_OANDA_ACCOUNT_ID")
                is_practice = forex_creds.get("practice", True)
                
                if not token:
                    logger.error("[FOREX ERROR] OANDA Access Token missing from vault credentials.")
                    return False

                domain = "api-fxpractice.oanda.com" if is_practice else "api-fxtrade.oanda.com"
                url = f"https://{domain}/v3/accounts/{account_id}/orders"
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                units_val = order.volume if order.side.upper() == "BUY" else -order.volume
                
                payload = {
                    "order": {
                        "units": str(units_val),
                        "instrument": order.symbol,
                        "type": "MARKET",
                        "timeInForce": "FOK",
                        "positionFill": "REDUCE_FIRST",  # Cleanly handles reversals or flat entries
                        "takeProfitOnFill": {"price": str(order.take_profit), "timeInForce": "GTC"},
                        "stopLossOnFill": {"price": str(order.stop_loss), "timeInForce": "GTC"}
                    }
                }
                
                if not self.session or self.session.closed:
                    self.session = aiohttp.ClientSession()

                async with self.session.post(url, json=payload, headers=headers) as response:
                    if response.status == 201:
                        logger.info(f"[OANDA SUCCESS] Forex bracket order filled for {order.symbol}")
                        return True
                    else:
                        err_text = await response.text()
                        logger.error(f"[OANDA FAIL] Order rejected: {err_text}")
                        return False

        except Exception as e:
            logger.error(f"[EXECUTION ERROR] Failed to place live order for {order.symbol}: {e}")
            return False
        return False


class StrategyResearchEngine:
    @staticmethod
    def identify_optimal_strategy(volatility: float, trend_strength: float) -> str:
        if volatility > 0.035:
            return "INSTITUTIONAL_VOLATILITY_BREAKOUT"
        elif trend_strength > 0.70:
            return "MOMENTUM_TREND_FOLLOWING_GRID"
        else:
            return "STATISTICAL_MEAN_REVERSION"


class ZeroLagMultiMarketEngine:
    def __init__(self, symbols_config: List[dict], min_capital: float = 20.0, credentials: dict = None):
        self.symbols_config = symbols_config
        self.min_capital = min_capital
        self.active_orders: List[LiveTradeOrder] = []
        self.gateway = UniversalMultiBrokerGateway(credentials or {})

    def verify_capital(self, account_balance: float) -> bool:
        if account_balance < self.min_capital:
            logger.error(f"CAPITAL BLOCK: Balance ${account_balance:.2f} is below minimum limit.")
            return False
        return True

    async def deploy_trade(self, order: LiveTradeOrder, account_balance: float) -> bool:
        if not self.verify_capital(account_balance):
            return False
        
        await self.gateway.initialize_exchanges()
        success = await self.gateway.execute_order(order)
        if success:
            self.active_orders.append(order)
            logger.info(f"LIVE EXECUTION CONFIRMED [{order.asset_class}]: {order.symbol}")
            return True
        return False

    async def fetch_live_market_data(self, symbol: str, asset_class: str) -> Optional[float]:
        """Fetches active, live tick prices across crypto, equities, and live forex endpoints."""
        try:
            if asset_class in ["CRYPTO_SPOT", "CRYPTO_FUTURE"] and asset_class in self.gateway.exchanges:
                ticker = await self.gateway.exchanges[asset_class].fetch_ticker(symbol)
                return float(ticker['last'])
                
            elif asset_class == "STOCKS" and self.gateway.stock_data_client:
                req = StockLatestTradeRequest(symbol_or_symbols=symbol)
                latest_trade = self.gateway.stock_data_client.get_stock_latest_trade(req)
                if symbol in latest_trade:
                    return float(latest_trade[symbol].price)
                
            elif asset_class == "FOREX":
                forex_creds = self.gateway.credentials.get("forex", {})
                token = forex_creds.get("access_token")
                account_id = forex_creds.get("account_id", "YOUR_OANDA_ACCOUNT_ID")
                is_practice = forex_creds.get("practice", True)
                
                if not token:
                    return None
                    
                domain = "api-fxpractice.oanda.com" if is_practice else "api-fxtrade.oanda.com"
                url = f"https://{domain}/v3/accounts/{account_id}/pricing?instruments={symbol}"
                headers = {"Authorization": f"Bearer {token}"}
                
                if not self.gateway.session or self.gateway.session.closed:
                    self.gateway.session = aiohttp.ClientSession()

                async with self.gateway.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = data.get("prices", [])
                        if prices:
                            bids = float(prices[0]["bids"][0]["price"])
                            asks = float(prices[0]["asks"][0]["price"])
                            return (bids + asks) / 2.0
        except Exception as e:
            logger.warning(f"[TICKER WARNING] Failed to fetch live data for {symbol}: {e}")
        return None

    async def run_zero_lag_execution_loop(self, current_balance: float):
        await self.gateway.initialize_exchanges()
        logger.info("Zero-lag multi-market execution engine active with broker-side protection.")

        try:
            while True:
                if not self.verify_capital(current_balance):
                    break

                for item in self.symbols_config:
                    symbol = item["symbol"]
                    asset_type = item["asset_class"]
                    
                    current_price = await self.fetch_live_market_data(symbol, asset_type)
                    if current_price is None:
                        continue

                    StrategyResearchEngine.identify_optimal_strategy(volatility=0.03, trend_strength=0.75)

                    for order in [o for o in self.active_orders if o.symbol == symbol and o.is_active]:
                        if current_price > order.highest_price:
                            order.highest_price = current_price

                await asyncio.sleep(1)
        finally:
            await self.gateway.close_exchanges()
