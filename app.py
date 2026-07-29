# app.py
import os
import sqlite3
import asyncio
import ccxt.async_support as ccxt
# Inasoma msimbo wa quant_engine kiotomatiki
import elite_quant_engine

def initialize_database():
    """
    Inatengeneza faili la SQLite kwenye disk na kuandaa meza (table)
    ya kuhifadhi kumbukumbu za biashara za multi-asset kiotomatiki kama haipo.
    """
    db_name = 'elite_quant_engine.db'
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT,
            regime TEXT,
            price REAL,
            strategy TEXT,
            action TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"🔒 [DATABASE STATUS]: Local SQLite Storage verified and active on disk.")

def get_authenticated_exchange(exchange_id='binance'):
    """
    Inasoma API Keys zako kwa siri kutoka kwenye Environment Variables za mfumo wako.
    Hii inalinda akaunti yako isidukuliwe na inaruhusu muunganisho wa kasi (Non-blocking async).
    """
    exchange_class = getattr(ccxt, exchange_id)
    
    api_key = os.getenv('BINANCE_FUTURES_KEY', 'placeholder_key')
    api_secret = os.getenv('BINANCE_FUTURES_SECRET', 'placeholder_secret')
    
    if api_key == 'placeholder_key' or api_secret == 'placeholder_secret':
        print("⚠️ [SECURITY WARNING]: Running on baseline keys. Live multi-asset orders will reject.")

    # Kuunganisha akaunti kwa mfumo wa asynchronous na kusimamia kikomo cha kasi kiotomatiki
    exchange_session = exchange_class({
        'enableRateLimit': True,
        'apiKey': api_key,
        'secret': api_secret,
        'options': {
            'defaultType': 'future'  # Huruhusu biashara za Futures (Crypto, Forex, na Tokenized Stocks) kufanyika kwa pamoja
        }
    })
    
    return exchange_session

if __name__ == "__main__":
    # 🛑 THE SAFETY SWITCH (SWICHI KUU YA USALAMA YA MULTI-ASSET ENGINE)
    # Weka 'True' kama unataka ianze kununua/kuuza kweli (Live Trading).
    # Weka 'False' ili ifanye simulation ya majaribio bila kugusa pesa zako (Paper Trading).
    LIVE_EXECUTION = False   
    
    # Hatua ya 1: Kuandaa hifadhi ya kanzidata kwenye disk
    initialize_database()
    
    # Hatua ya 2: Kuanzisha mawasiliano salama na yaliyoidhinishwa na soko
    exchange = get_authenticated_exchange(exchange_id='binance')
    
    print(f"🚀 [MULTI-ASSET PORTAL ACTIVE] | Production Live Flag: {LIVE_EXECUTION}")
    print("🤖 Launching background crypto, forex, and stock scanning parameters...\n")
    
    # Hatua ya 3: Kukabidhi bendera ya usalama moja kwa moja kwenye multi-asset engine kwa kasi ya juu
    # WEKA HII MPYA BADALA YAKE
if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(elite_quant_engine.master_trading_engine(live_override=LIVE_EXECUTION))
    except RuntimeError:
        # Hii inazuia mgongano wa loop kama Streamlit imekwishaianzisha
        asyncio.create_task(elite_quant_engine.master_trading_engine(live_override=LIVE_EXECUTION))

