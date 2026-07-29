# elite_quant_engine_production.py
import asyncio
import math
import auth_manager

# INSTITUTIONAL PORTFOLIO CONSTRAINTS
MAX_TOTAL_RISK_CAP = 0.20  # Maximum cumulative wallet allocation (20%)
LOOKBACK_CANDLES = 30      # Evaluation lookback depth window
MIN_NOTIONAL_USDT = 11.0   # Binance safety margin threshold limit

def calculate_rsi(closes, period=14):
    """Vectorized calculation of the Relative Strength Index."""
    if len(closes) <= period: return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0: return 100.0
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0: return 100.0
    return 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))

def calculate_covariance_modifier(symbol, correlations):
    """Reduces allocation size if asset is highly correlated with Bitcoin."""
    btc_link = correlations.get(f"{symbol}_BTC/USDT:USDT", 0.0)
    if btc_link > 0.80 and 'BTC' not in symbol:
        return 0.50  # Cut concentration risk by half
    return 1.0

def calculate_kelly_fraction(win_rate=0.54, reward_to_risk=2.0):
    """Conservative Quarter-Kelly compound capital growth allocator."""
    loss_rate = 1.0 - win_rate
    if reward_to_risk <= 0: return 0.0
    raw_kelly = win_rate - (loss_rate / reward_to_risk)
    return max(0.0, min(raw_kelly * 0.25, MAX_TOTAL_RISK_CAP))

async def fetch_watchlist_returns(exchange, watchlist):
    """Concurrently fetches OHLCV datasets to prevent I/O blocking loops."""
    async def fetch_single(item):
        try:
            ohlcv = await exchange.fetch_ohlcv(item['symbol'], timeframe='1h', limit=LOOKBACK_CANDLES)
            if not ohlcv or len(ohlcv) < 24: return item['symbol'], None
            closes = [candle[4] for candle in ohlcv]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            return item['symbol'], returns
        except Exception:
            return item['symbol'], None

    results = await asyncio.gather(*(fetch_single(item) for item in watchlist))
    return {sym: rets for sym, rets in results if rets is not None}

async def execute_strategy_and_trade(exchange, item, correlations, free_usdt, live_execution=True):
    """Executes dual-market strategy analysis with high-speed precision logic."""
    symbol = item['symbol']
    market_type = item['type']  # 'spot' or 'futures'

    try:
        # Step 1: Rapid Data Pipeline Fetch
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=LOOKBACK_CANDLES)
        if not ohlcv or len(ohlcv) < 24: raise ValueError("Insufficient candle history.")
            
        closes = [candle[4] for candle in ohlcv]
        current_price = closes[-1]
        start_price = closes[-24]
        price_change_pct = ((current_price - start_price) / start_price) * 100
        rsi = calculate_rsi(closes)
        
        # Step 2: Dynamic Strategy Regime Selection
        side, reward_risk = None, 2.0
        if price_change_pct > 1.5 and rsi < 68:
            regime, strategy, side = "🚀 Strong Uptrend", "[MOMENTUM LONG]", "buy"
            tp_pct, sl_pct = 1.04, 0.985  
            reward_risk = 2.66
        elif price_change_pct < -1.5 and rsi > 32:
            if market_type == 'spot':
                return symbol, "💤 Spot Neutralized", current_price, "[SPOT SHORT BYPASSED]", "Spot ignores shorting."
            regime, strategy, side = "⚠️ Strong Downtrend", "[HEDGE SHORT]", "sell"
            tp_pct, sl_pct = 0.97, 1.015  
            reward_risk = 2.00
        elif rsi < 30:
            regime, strategy, side = "⚖️ Oversold Exhaustion", "[MEAN REVERSION LONG]", "buy"
            tp_pct, sl_pct = 1.02, 0.99   
            reward_risk = 2.00
        else:
            return symbol, "💤 Ranging Consolidation", current_price, "[STANDBY]", "Price inside neutral zone bounds."

        # Step 3: Position Sizing & Notional Safety Valuation Check
        kelly_frac = calculate_kelly_fraction(win_rate=0.54, reward_to_risk=reward_risk)
        cov_modifier = calculate_covariance_modifier(symbol, correlations)
        allocated_capital = free_usdt * (kelly_frac * cov_modifier)
        
        raw_size = allocated_capital / current_price
        precision_amount = float(exchange.amount_to_precision(symbol, raw_size))
        
        final_notional = precision_amount * current_price
        if final_notional < MIN_NOTIONAL_USDT:
            return symbol, regime, current_price, strategy, f"Risk Blocked: Notional value (${final_notional:.2f}) below threshold limit."

        action = f"Signal Verified | Size: {precision_amount} | Market: {market_type.upper()}"

        # Step 4: Low-Latency Branching Execution Layer
        if live_execution and side:
            try:
                if market_type == 'futures':
                    try: await exchange.set_margin_mode('isolated', symbol)
                    except Exception: pass
                    try: await exchange.set_leverage(5, symbol)
                    except Exception: pass
                    
                    entry_order = await exchange.create_order(symbol, 'market', side, precision_amount)
                    exec_price = entry_order.get('price', current_price) or current_price
                    
                    tp_price = float(exchange.price_to_precision(symbol, exec_price * tp_pct))
                    sl_price = float(exchange.price_to_precision(symbol, exec_price * sl_pct))
                    exit_side = 'sell' if side == 'buy' else 'buy'
                    
                    # Precise futures bracket orders with profit retention & stop protection
                    await exchange.create_order(symbol, 'limit', exit_side, precision_amount, tp_price, params={'reduceOnly': True})
                    stop_params = {'stopPrice': sl_price, 'triggerPrice': sl_price, 'reduceOnly': True}
                    await exchange.create_order(symbol, 'stop_market', exit_side, precision_amount, price=None, params=stop_params)
                    
                    action += f" -> [FUTURES ID: {entry_order.get('id')} | TP: {tp_price} | SL: {sl_price}]"

                elif market_type == 'spot':
                    if side == 'buy':
                        entry_order = await exchange.create_order(symbol, 'market', 'buy', precision_amount)
                        exec_price = entry_order.get('price', current_price) or current_price
                        
                        tp_price = float(exchange.price_to_precision(symbol, exec_price * tp_pct))
                        sl_price = float(exchange.price_to_precision(symbol, exec_price * sl_pct))
                        
                        # Spot profit targets and stop-loss safeguard orders
                        await exchange.create_order(symbol, 'limit', 'sell', precision_amount, tp_price)
                        stop_params = {'stopPrice': sl_price, 'triggerPrice': sl_price}
                        await exchange.create_order(symbol, 'stop_market', 'sell', precision_amount, price=None, params=stop_params)
                        
                        action += f" -> [SPOT BUY ID: {entry_order.get('id')} | TP: {tp_price} | SL: {sl_price}]"
            
            except Exception as trade_err:
                action += f" -> [API Rejection: {trade_err}]"

        return symbol, regime, current_price, strategy, action

    except Exception as e:
        return symbol, "Execution Paused", 0.0, "[SHIELD ACTIVE]", f"Feed Protected: {str(e)}"

async def master_trading_engine():
    """Asynchronous orchestration core managed for zero-lag pipeline execution."""
    LIVE_EXECUTION = True   
    
    auth_manager.initialize_database()
    exchange = auth_manager.get_authenticated_exchange(exchange_id='binance')
    
    watchlist = [
        {'symbol': 'BTC/USDT', 'type': 'spot'},
        {'symbol': 'ETH/USDT:USDT', 'type': 'futures'},
        {'symbol': 'SOL/USDT:USDT', 'type': 'futures'}
    ]
    
    print(f"✨ ELITE QUANT ENGINE ACTIVE | Dual Spot/Futures Production Flag: {LIVE_EXECUTION}")
    
    try:
        await exchange.load_markets()
        returns_dict = await fetch_watchlist_returns(exchange, watchlist)

        correlations = {}
        for sym_a in returns_dict:
            mean_a = sum(returns_dict[sym_a]) / len(returns_dict[sym_a])
            var_a = sum((x - mean_a) ** 2 for x in returns_dict[sym_a])
            for sym_b in returns_dict:
                mean_b = sum(returns_dict[sym_b]) / len(returns_dict[sym_b])
                var_b = sum((x - mean_b) ** 2 for x in returns_dict[sym_b])
                cov = sum((returns_dict[sym_a][k] - mean_a) * (returns_dict[sym_b][k] - mean_b) for k in range(min(len(returns_dict[sym_a]), len(returns_dict[sym_b]))))
                correlations[f"{sym_a}_{sym_b}"] = cov / math.sqrt(var_a * var_b) if var_a > 0 and var_b > 0 else 1.0

        free_usdt = 0.0
        if LIVE_EXECUTION:
            try:
                balance = await exchange.fetch_balance()
                free_usdt = balance.get('USDT', {}).get('free', 0.0)
                if free_usdt <= 0:
                    print("❌ Critical Risk Error: USDT balance unparseable or zero. Aborting execution.")
                    return
            except Exception as b_err:
                print(f"❌ Balance Fetch Failed. Halting engine. Error: {b_err}")
                return

        tasks = [execute_strategy_and_trade(exchange, item, correlations, free_usdt, live_execution=LIVE_EXECUTION) for item in watchlist]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, tuple) and len(res) == 5:
                symbol, regime, price, strategy, action = res
                price_str = f"${price:,.2f}" if price > 10 else f"${price:,.4f}"
                print(f"◆ {symbol:<15} | Price: {price_str:<10} | Matrix: {regime}")
                print(f"  ↳ {strategy} -> {action}\n")
                auth_manager.log_trade_to_db(symbol, regime, price, strategy, action)
            else:
                print(f"❌ Worker Exception Encountered: {res}\n")

    except Exception as e:
        print(f"❌ Master System Quantitative Panic: {e}")
    finally:
        await exchange.close()
        print("🔒 Secure API and Database connection channels cleanly disengaged.")

if __name__ == "__main__":
    asyncio.run(master_trading_engine())
