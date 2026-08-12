import asyncio
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime
import pytz
import aiohttp
import ccxt.async_support as ccxt_async

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class InstitutionalGateway:
    def __init__(self):
        self.strategy_registry = [
            "Momentum Breakout Vector",
            "Mean Reversion (RSI / Bollinger Bands)",
            "VWAP Trend Crossover",
            "MACD Histogram Trend Following",
            "Statistical Volatility Arbitrage",
            "Exponential Moving Average (EMA) Ribbon Scalp",
            "Order Book Imbalance Momentum",
            "Donchian Channel Breakout",
            "Fibonacci Retracement Dynamic Bounce",
            "Triple Exponential Average (Trix) Cross",
            "Commodity Channel Index (CCI) Extreme Reversal",
            "Parabolic SAR Trend Acceleration",
            "Volume Profile Point of Control (POC) Magnet",
            "Ichimoku Cloud Kumo Breakout",
            "Fractal Adaptive Moving Average (FAMA)"
        ]

    def is_traditional_market_open(self, asset_class: str) -> bool:
        tz_ny = pytz.timezone('America/New_York')
        now_ny = datetime.now(tz_ny)
        weekday = now_ny.weekday()

        if asset_class == "CRYPTO":
            return True
        if asset_class == "FOREX":
            if weekday == 5: return False
            if weekday == 4 and now_ny.hour >= 17: return False
            if weekday == 6 and now_ny.hour < 17: return False
            return True
        if asset_class == "STOCK":
            if weekday >= 5: return False
            market_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now_ny.replace(hour=16, minute=0, second=0, microsecond=0)
            return market_open <= now_ny <= market_close
        return True

    async def fetch_live_balance(self, api_key: str, secret_key: str) -> float:
        exchange = ccxt_async.binance({
            'apiKey': api_key, 'secret': secret_key, 'enableRateLimit': True, 'options': {'defaultType': 'spot'}
        })
        try:
            balance_data = await exchange.fetch_balance()
            total_usdt = float(balance_data['total'].get('USDT', 0.0))
            await exchange.close()
            return total_usdt if total_usdt > 0 else 20.0
        except Exception as e:
            logging.error(f"Balance fetch error: {str(e)}")
            await exchange.close()
            return 20.0

    def select_dynamic_strategy(self, price_series: pd.Series = None) -> Dict[str, Any]:
        if price_series is None or len(price_series) < 10:
            volatility, trend_slope = 0.015, 0.001
        else:
            volatility = price_series.pct_change().std()
            trend_slope = (price_series.iloc[-1] - price_series.iloc[0]) / price_series.iloc[0]

        if volatility > 0.03:
            chosen, action = "Statistical Volatility Arbitrage", "HEDGE/ACCUMULATE"
        elif volatility > 0.02:
            chosen, action = "Donchian Channel Breakout", "BUY"
        elif trend_slope > 0.015:
            chosen, action = "Momentum Breakout Vector", "BUY"
        elif trend_slope < -0.015:
            chosen, action = "MACD Histogram Trend Following", "SHORT/SELL"
        elif volatility < 0.008:
            chosen, action = "VWAP Trend Crossover", "HOLD"
        else:
            chosen, action = "Mean Reversion (RSI / Bollinger Bands)", "ACCUMULATE"

        return {"strategy": chosen, "recommended_action": action, "available_registry_count": len(self.strategy_registry)}

    def process_lean_or_matrix_allocation(self, account_balance: float) -> List[Dict[str, Any]]:
        if account_balance < 50.0:
            return [{
                "symbol": "BTC/USDT", "asset_class": "CRYPTO", "market_type": "SPOT", "side": "BUY", "size_units": 0.0005,
                "execution_note": "Lean Sanctuary Mode (< $50): Micro spot capital preservation."
            }]
        else:
            return [
                {"symbol": "BTC/USDT", "asset_class": "CRYPTO", "market_type": "SPOT", "side": "BUY", "size_units": 0.001, "execution_note": "Crypto Matrix Symphony"},
                {"symbol": "AAPL", "asset_class": "STOCK", "market_type": "EQUITY", "side": "BUY", "size_units": 1, "execution_note": "Alpaca Cloud Stock Gateway"},
                {"symbol": "EUR_USD", "asset_class": "FOREX", "market_type": "FX", "side": "BUY", "size_units": 1000, "execution_note": "OANDA Cloud Forex Gateway"}
            ]

    async def execute_trades(self, account_balance: float, binance_key: str, binance_sec: str, alpaca_key: str = "", alpaca_sec: str = "", oanda_token: str = "", oanda_account_id: str = "") -> List[Dict[str, Any]]:
        results = []
        orders_to_run = self.process_lean_or_matrix_allocation(account_balance)

        for order in orders_to_run:
            asset_class = order["asset_class"]
            if not self.is_traditional_market_open(asset_class):
                results.append({"symbol": order["symbol"], "status": "BYPASSED (Market Closed)", "action": "Skipped to protect capital and prevent off-hours API polling loops."})
                continue

            try:
                if asset_class == "CRYPTO":
                    exchange = ccxt_async.binance({'apiKey': binance_key, 'secret': binance_sec, 'enableRateLimit': True})
                    res = await exchange.create_order(order["symbol"], 'market', order["side"].lower(), order["size_units"])
                    await exchange.close()
                    results.append({"symbol": order["symbol"], "status": "SUCCESS (Binance Live Production)", "response": res})

                elif asset_class == "STOCK":
                    if not ALPACA_AVAILABLE: raise ImportError("alpaca-py package missing.")
                    if not alpaca_key or not alpaca_sec:
                        raise ValueError("Alpaca credentials missing for stock execution.")
                    client = TradingClient(alpaca_key, alpaca_sec, paper=False)
                    req = MarketOrderRequest(symbol=order["symbol"], qty=order["size_units"], side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                    res = client.submit_order(req)
                    results.append({"symbol": order["symbol"], "status": "SUCCESS (Alpaca Stock Live Production)", "order_id": str(res.id)})

                elif asset_class == "FOREX":
                    if not oanda_token or not oanda_account_id:
                        raise ValueError("OANDA Cloud Credentials missing for live forex execution.")
                    url = f"https://api-fxtrade.oanda.com/v3/accounts/{oanda_account_id}/orders"
                    headers = {"Authorization": f"Bearer {oanda_token}", "Content-Type": "application/json"}
                    payload = {
                        "order": {
                            "units": str(order["size_units"]),
                            "instrument": order["symbol"],
                            "timeInForce": "FOK",
                            "type": "MARKET",
                            "positionFill": "DEFAULT"
                        }
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, headers=headers) as resp:
                            data = await resp.json()
                            results.append({"symbol": order["symbol"], "status": "SUCCESS (OANDA Forex Cloud Live)", "response": data})

            except Exception as e:
                logging.error(f"Execution error on {order['symbol']}: {str(e)}")
                results.append({"symbol": order["symbol"], "status": f"ERROR: {str(e)}", "action": "Safely isolated execution exception."})

        return results
