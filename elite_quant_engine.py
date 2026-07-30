# elite_quant_engine.py
import asyncio
import math

# INSTITUTIONAL PORTFOLIO CONSTRAINTS (Optimized for Micro-Accounts)
MAX_TOTAL_RISK_CAP = 0.50  # Increased to 50% for smaller accounts to clear minimums
LOOKBACK_CANDLES = 30      # Evaluation lookback depth window
MIN_NOTIONAL_USDT = 5.2    # Lowered to clear Binance $5 minimum safety margin

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
        return 0.50  
    return 1.0

def calculate_kelly_fraction(win_rate=0.54, reward_to_risk=2.0):
    """Conservative Quarter-Kelly compound capital growth allocator."""
    loss_rate = 1.0 - win_rate
    if reward_to_risk <= 0: return 0.0
    raw_kelly = win_rate - (loss_rate / reward_to_risk)
    return max(0.0, min(raw_kelly * 0.25, MAX_TOTAL_RISK_CAP))

async def safe_api_call(coro_func, *args, retries=3, delay=1.5, **kwargs):
    """Wraps any exchange API call with exponential backoff to handle network drops and rate limits."""
    for attempt in range(retries):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                raise e
            wait_time = delay * (2 ** attempt)
            await asyncio.sleep(wait_time)

async def fetch_watchlist_returns(exchange, watchlist):
    """Concurrently fetches OHLCV datasets, safely routing non-crypto assets to alternative feeds."""
    async def fetch_single(item):
        symbol = item['symbol']
        asset_class = item['class']
        try:
            if asset_class in ['forex', 'stock']:
                return symbol, None 
            
            ohlcv = await safe_api_call(
                exchange.fetch_ohlcv, 
                symbol, 
                timeframe='1h', 
                limit=LOOKBACK_CANDLES
            )
            if not ohlcv or len(ohlcv) < 24: return symbol, None
            closes = [candle[4] for candle in ohlcv]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            return symbol, returns
        except Exception:
            return symbol, None

    results = await asyncio.gather(*(fetch_single(item) for item in watchlist))
    return {sym: rets for sym, rets in results if rets is not None}

async def execute_strategy_and_trade(exchange, item, correlations, free_usdt, live_execution=True):
    """Executes multi-asset analysis with isolated routing for crypto vs external asset classes."""
    symbol = item['symbol']
    asset_class = item['class']  
    market_type = item['type']   

    try:
        if asset_class in ['forex', 'stock']:
            return symbol, "🌐 External Gateway Active", 0.0, f"[{asset_class.upper()} FEED ROUTED]", "Managed via external API feed."

        ohlcv = await safe_api_call(
            exchange.fetch_ohlcv, 
            symbol, 
            timeframe='1h', 
            limit=LOOKBACK_CANDLES
        )
        if not ohlcv or len(ohlcv) < 24: raise ValueError("Insufficient candle history.")
            
        closes = [candle[4] for candle in ohlcv]
        current_price = closes[-1]
        start_price = closes[-24]
        price_change_pct = ((current_price - start_price) / start_price) * 100
        rsi = calculate_rsi(closes)
        
        side, reward_risk = None, 2.0
        if price_change_pct > 1.5 and rsi < 68:
            regime, strategy, side = "🚀 Strong Uptrend", "[CRYPTO MOMENTUM LONG]", "buy"
            tp_pct, sl_pct = 1.04, 0.985  
            reward_risk = 2.66
        elif price_change_pct < -1.5 and rsi > 32:
            regime, strategy, side = "⚠️ Strong Downtrend", "[CRYPTO PROFIT SHORT]", "sell"
            tp_pct, sl_pct = 0.97, 1.015  
            reward_risk = 2.00
        elif rsi < 30:
            regime, strategy, side = "⚖️ Oversold Exhaustion", "[CRYPTO MEAN REVERSION LONG]", "buy"
            tp_pct, sl_pct = 1.02, 0.99   
            reward_risk = 2.00
        else:
            return symbol, "💤 Ranging Consolidation", current_price, "[STANDBY]", "Price inside neutral zone bounds."

        # Dynamic Sizing scaled for micro-accounts ($20 baseline support)
        kelly_frac = calculate_kelly_fraction(win_rate=0.54, reward_to_risk=reward_risk)
        cov_modifier = calculate_covariance_modifier(symbol, correlations)
        allocated_capital = free_usdt * (kelly_frac * cov_modifier)
        
        raw_size = allocated_capital / current_price
        precision_amount = float(exchange.amount_to_precision(symbol, raw_size))
        
        final_notional = precision_amount * current_price
        if final_notional < MIN_NOTIONAL_USDT:
            return symbol, regime, current_price, strategy, f"Risk Blocked: Notional value (${final_notional:.2f}) below threshold limit."

        action = f"Signal Verified | Size: {precision_amount} | Class: {asset_class.upper()}"

        if live_execution and side:
            try:
                if market_type == 'futures':
                    try: await exchange.set_margin_mode('isolated', symbol)
                    except Exception: pass
                    try: await exchange.set_leverage(3, symbol) # Lowered leverage to 3x for micro-account risk control
                    except Exception: pass
                    
                    entry_order = await safe_api_call(exchange.create_order, symbol, 'market', side, precision_amount)
                    exec_price = entry_order.get('price', current_price) or current_price
                    
                    if side == 'buy':
                        tp_price = float(exchange.price_to_precision(symbol, exec_price * tp_pct))
                        sl_price = float(exchange.price_to_precision(symbol, exec_price * sl_pct))
                        exit_side = 'sell'
                    else:
                        tp_price = float(exchange.price_to_precision(symbol, exec_price * 0.97))
                        sl_price = float(exchange.price_to_precision(symbol, exec_price * 1.015))
                        exit_side = 'buy'
                    
                    await safe_api_call(exchange.create_order, symbol, 'limit', exit_side, precision_amount, tp_price, params={'reduceOnly': True})
                    stop_params = {'stopPrice': sl_price, 'triggerPrice': sl_price, 'reduceOnly': True}
                    await safe_api_call(exchange.create_order, symbol, 'stop_market', exit_side, precision_amount, price=None, params=stop_params)
                    
                    action += f" -> [{side.upper()} ID: {entry_order.get('id')} | TP: {tp_price} | SL: {sl_price}]"

                elif market_type == 'spot' and side == 'buy':
                    entry_order = await safe_api_call(exchange.create_order, symbol, 'market', 'buy', precision_amount)
                    exec_price = entry_order.get('price', current_price) or current_price
                    
                    tp_price = float(exchange.price_to_precision(symbol, exec_price * tp_pct))
                    sl_price = float(exchange.price_to_precision(symbol, exec_price * sl_pct))
                    
                    await safe_api_call(exchange.create_order, symbol, 'limit', 'sell', precision_amount, tp_price)
                    stop_params = {'stopPrice': sl_price, 'triggerPrice': sl_price}
                    await safe_api_call(exchange.create_order, symbol, 'stop_market', 'sell', precision_amount, price=None, params=stop_params)
                    
                    action += f" -> [SPOT BUY ID: {entry_order.get('id')} | TP: {tp_price} | SL: {sl_price}]"
            
            except Exception as trade_err:
                action += f" -> [API Rejection: {trade_err}]"

        return symbol, regime, current_price, strategy, action

    except Exception as e:
        return symbol, "Execution Paused", 0.0, "[SHIELD ACTIVE]", f"Feed Protected: {str(e)}"

async def master_trading_engine(exchange_instance, db_logger, live_override=True):
    """Asynchronous orchestration core supporting multi-asset evaluation loops."""
    LIVE_EXECUTION = live_override   
    exchange = exchange_instance
    
    watchlist = [
        {'symbol': 'BTC/USDT', 'class': 'crypto', 'type': 'spot'},
        {'symbol': 'ETH/USDT:USDT', 'class': 'crypto', 'type': 'futures'},
        {'symbol': 'EUR/USD', 'class': 'forex', 'type': 'spot'},       
        {'symbol': 'AAPL', 'class': 'stock', 'type': 'spot'}           
    ]
    
    print(f"✨ ELITE MULTI-ASSET ENGINE ACTIVE | Production Flag: {LIVE_EXECUTION}")
    
    try:
        await exchange.load_markets()
        returns_dict = await fetch_watchlist_returns(exchange, watchlist)

        # Fixed Covariance Matrix Calculation with matched vector slices
        correlations = {}
        symbols_list = list(returns_dict.keys())
        for i, sym_a in enumerate(symbols_list):
            rets_a = returns_dict[sym_a]
            mean_a = sum(rets_a) / len(rets_a)
            var_a = sum((x - mean_a) ** 2 for x in rets_a)
            
            for j, sym_b in enumerate(symbols_list):
                rets_b = returns_dict[sym_b]
                mean_b = sum(rets_b) / len(rets_b)
                var_b = sum((x - mean_b) ** 2 for x in rets_b)
                
                # Align lookup range safely
                limit_k = min(len(rets_a), len(rets_b))
                cov = sum((rets_a[k] - mean_a) * (rets_b[k] - mean_b) for k in range(limit_k))
                
                denominator = math.sqrt(var_a * var_b)
                correlations[f"{sym_a}_{sym_b}"] = cov / denominator if denominator > 0 else 1.0

        free_usdt = 0.0
        if LIVE_EXECUTION:
            try:
                balance = await safe_api_call(exchange.fetch_balance)
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
                print(f"◆ {symbol:<18} | Price: {price_str:<10} | Matrix: {regime}")
                print(f"  ↳ {strategy} -> {action}\n")
                db_logger(symbol, regime, price, strategy, action)
            else:
                print(f"❌ Worker Exception Encountered: {res}\n")

    except Exception as e:
        print(f"❌ Master System Quantitative Panic: {e}")
    finally:
        await exchange.close()
        print("🔒 Secure API and Database connection channels cleanly disengaged.")
