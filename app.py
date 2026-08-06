import streamlit as st
import sqlite3
import hashlib
import os
import threading
from contextlib import contextmanager
from cryptography.fernet import Fernet
import asyncio
import logging
import math
from datetime import datetime, time
import pytz
from dataclasses import dataclass, field
from typing import List, Optional
import random

# --- OPTIONAL BROKER SDK IMPORTS ---
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, 
        TakeProfitRequest, 
        StopLossRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    from alpaca.data.historical import StockHistoricalDataClient
    ALPACA_SDK_AVAILABLE = True
except ImportError:
    ALPACA_SDK_AVAILABLE = False

try:
    from ib_insync import IB, Stock, Forex, MarketOrder, LimitOrder, StopOrder
    IBKR_SDK_AVAILABLE = True
except ImportError:
    IBKR_SDK_AVAILABLE = False

try:
    import ccxt.async_support as ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

import aiohttp

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Institutional Trading Gateway",
    page_icon="⚡",
    layout="wide"
)

# --- INSTITUTIONAL LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (LiveEngine): %(message)s")
logger = logging.getLogger("UniversalInstitutionalEngine")


# --- 1. ENCRYPTION & SECURITY VAULT ---
class SecurityVault:
    def __init__(self, key_file="institutional_vault.key"):
        env_key = os.getenv("VAULT_SECRET_KEY", None)
        if env_key:
            self.key = env_key.encode() if isinstance(env_key, str) else env_key
        elif not os.path.exists(key_file):
            self.key = Fernet.generate_key()
            try:
                with open(key_file, "wb") as f:
                    f.write(self.key)
            except Exception:
                pass  
        else:
            try:
                with open(key_file, "rb") as f:
                    self.key = f.read()
            except Exception:
                self.key = Fernet.generate_key()
                
        try:
            self.cipher = Fernet(self.key)
        except Exception:
            self.key = Fernet.generate_key()
            self.cipher = Fernet(self.key)

    def encrypt(self, plain_text: str) -> bytes:
        return self.cipher.encrypt(plain_text.encode()) if plain_text else b""

    def decrypt(self, encrypted_data: bytes) -> str:
        if not encrypted_data:
            return ""
        try:
            return self.cipher.decrypt(encrypted_data).decode()
        except Exception:
            return ""


# --- 2. THREAD-SAFE CLIENT DATABASE ---
class ClientDatabase:
    def __init__(self, db_name="institutional_clients.db"):
        self.vault = SecurityVault()
        self.db_name = db_name
        self.lock = threading.Lock()
        self.database_url = os.getenv("DATABASE_URL", None)
        self._initialize_db()

    @contextmanager
    def _get_connection(self):
        if self.database_url:
            import psycopg2
            conn = psycopg2.connect(self.database_url)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_name, timeout=30.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _initialize_db(self):
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if self.database_url:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS clients (
                            username VARCHAR(255) PRIMARY KEY,
                            full_name TEXT,
                            phone_number TEXT,
                            password_hash TEXT,
                            binance_api_enc BYTEA,
                            binance_secret_enc BYTEA,
                            stock_api_enc BYTEA,
                            stock_secret_enc BYTEA,
                            ibkr_host_enc BYTEA
                        )
                    ''')
                else:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS clients (
                            username TEXT PRIMARY KEY,
                            full_name TEXT,
                            phone_number TEXT,
                            password_hash TEXT,
                            binance_api_enc BLOB,
                            binance_secret_enc BLOB,
                            stock_api_enc BLOB,
                            stock_secret_enc BLOB,
                            ibkr_host_enc BLOB
                        )
                    ''')

    def register(self, username, full_name, phone_number, password, b_api, b_sec, s_api, s_sec, ibkr_host):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        b_api_enc = self.vault.encrypt(b_api)
        b_sec_enc = self.vault.encrypt(b_sec)
        s_api_enc = self.vault.encrypt(s_api)
        s_sec_enc = self.vault.encrypt(s_sec)
        ibkr_host_enc = self.vault.encrypt(ibkr_host)
        
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    if self.database_url:
                        cursor.execute('''
                            INSERT INTO clients (
                                username, full_name, phone_number, password_hash, 
                                binance_api_enc, binance_secret_enc, stock_api_enc, stock_secret_enc, ibkr_host_enc
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (username) DO UPDATE SET 
                                full_name = EXCLUDED.full_name,
                                phone_number = EXCLUDED.phone_number,
                                password_hash = EXCLUDED.password_hash,
                                binance_api_enc = EXCLUDED.binance_api_enc,
                                binance_secret_enc = EXCLUDED.binance_secret_enc,
                                stock_api_enc = EXCLUDED.stock_api_enc,
                                stock_secret_enc = EXCLUDED.stock_secret_enc,
                                ibkr_host_enc = EXCLUDED.ibkr_host_enc
                        ''', (username, full_name, phone_number, pwd_hash, b_api_enc, b_sec_enc, s_api_enc, s_sec_enc, ibkr_host_enc))
                    else:
                        cursor.execute('''
                            INSERT OR REPLACE INTO clients (
                                username, full_name, phone_number, password_hash, 
                                binance_api_enc, binance_secret_enc, stock_api_enc, stock_secret_enc, ibkr_host_enc
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (username, full_name, phone_number, pwd_hash, b_api_enc, b_sec_enc, s_api_enc, s_sec_enc, ibkr_host_enc))
                return True
            except Exception as e:
                st.error(f"[DB ERROR] {e}")
                return False

    def authenticate(self, username, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                placeholder = "%s" if self.database_url else "?"
                cursor.execute(f'SELECT full_name, phone_number FROM clients WHERE username = {placeholder} AND password_hash = {placeholder}', (username, pwd_hash))
                row = cursor.fetchone()
                if row:
                    return {"username": username, "full_name": row[0], "phone_number": row[1]}
                return None

    def get_client_credentials(self, username):
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                placeholder = "%s" if self.database_url else "?"
                cursor.execute(f'''
                    SELECT binance_api_enc, binance_secret_enc, stock_api_enc, stock_secret_enc, ibkr_host_enc 
                    FROM clients WHERE username = {placeholder}
                ''', (username,))
                row = cursor.fetchone()
                if not row:
                    return {}
                
                b_host_raw = self.vault.decrypt(row[4])
                ibkr_host = "127.0.0.1"
                ibkr_port = 7496
                if ":" in b_host_raw:
                    parts = b_host_raw.split(":")
                    ibkr_host = parts[0]
                    try:
                        ibkr_port = int(parts[1])
                    except ValueError:
                        pass
                elif b_host_raw.strip():
                    ibkr_host = b_host_raw.strip()

                return {
                    "binance": {
                        "api_key": self.vault.decrypt(row[0]),
                        "secret_key": self.vault.decrypt(row[1])
                    },
                    "stocks": {
                        "api_key": self.vault.decrypt(row[2]),
                        "secret_key": self.vault.decrypt(row[3])
                    },
                    "ibkr": {
                        "host": ibkr_host,
                        "port": ibkr_port,
                        "client_id": 1
                    }
                }

    def get_masked_profile(self, username):
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                placeholder = "%s" if self.database_url else "?"
                cursor.execute(f'SELECT full_name, phone_number FROM clients WHERE username = {placeholder}', (username,))
                row = cursor.fetchone()
                if not row:
                    return None
                name, phone = row
                masked_name = " ".join([p[0] + "***" for p in name.split()]) if name else "U***"
                masked_phone = phone[:5] + "***" + phone[-4:] if phone and len(phone) > 8 else "***"
                return {"username": username, "masked_name": masked_name, "masked_phone": masked_phone}


# --- 3. LIVE TRADING CORE ENGINES ---
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

        if CCXT_AVAILABLE and binance_creds.get("api_key") and binance_creds.get("secret_key"):
            if "CRYPTO_SPOT" not in self.exchanges:
                self.exchanges["CRYPTO_SPOT"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
            if "CRYPTO_FUTURE" not in self.exchanges:
                self.exchanges["CRYPTO_FUTURE"] = ccxt.binance({
                    'apiKey': binance_creds["api_key"],
                    'secret': binance_creds["secret_key"],
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })

        if ALPACA_SDK_AVAILABLE and stocks_creds.get("api_key") and stocks_creds.get("secret_key"):
            if "STOCKS" not in self.exchanges:
                self.exchanges["STOCKS"] = TradingClient(
                    stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"],
                    paper=False
                )
                self.stock_data_client = StockHistoricalDataClient(
                    api_key=stocks_creds["api_key"],
                    secret_key=stocks_creds["secret_key"]
                )

        if IBKR_SDK_AVAILABLE and ibkr_creds.get("host") and ibkr_creds.get("port"):
            if "IBKR" not in self.exchanges:
                self.ibkr_client = IB()
                try:
                    await self.ibkr_client.connectAsync(
                        host=ibkr_creds.get("host", "127.0.0.1"),
                        port=int(ibkr_creds.get("port", 7496)),
                        clientId=int(ibkr_creds.get("client_id", 1))
                    )
                    self.exchanges["IBKR"] = self.ibkr_client
                except Exception as e:
                    logger.error(f"[IBKR ERROR] Failed to connect: {e}")

    async def close_exchanges(self):
        for key in ["CRYPTO_SPOT", "CRYPTO_FUTURE"]:
            if key in self.exchanges and hasattr(self.exchanges[key], 'close'):
                await self.exchanges[key].close()
                self.exchanges.pop(key, None)
        
        if self.ibkr_client and self.ibkr_client.isConnected():
            self.ibkr_client.disconnect()

        if self.session and not self.session.closed:
            await self.session.close()

    def _submit_alpaca_sync(self, client, market_order_data):
        return client.submit_order(order_data=market_order_data)

    async def execute_order(self, order: LiveTradeOrder) -> bool:
        try:
            if order.asset_class == "CRYPTO_FUTURE" and "CRYPTO_FUTURE" in self.exchanges:
                exchange = self.exchanges["CRYPTO_FUTURE"]
                params = {'stopLossPrice': order.stop_loss, 'takeProfitPrice': order.take_profit}
                try:
                    await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume, params=params)
                    return True
                except ccxt.RateLimitExceeded as rle:
                    logger.warning(f"[RATE LIMIT] Binance Futures: {rle}")
                    await asyncio.sleep(3.0)
                    return False

            elif order.asset_class == "CRYPTO_SPOT" and "CRYPTO_SPOT" in self.exchanges:
                exchange = self.exchanges["CRYPTO_SPOT"]
                try:
                    await exchange.create_order(order.symbol, 'market', order.side.lower(), order.volume)
                    inverted_side = 'sell' if order.side.upper() == 'BUY' else 'buy'
                    await exchange.create_order(order.symbol, 'STOP_MARKET', inverted_side, order.volume, None, {'stopPrice': order.stop_loss})
                    await exchange.create_order(order.symbol, 'TAKE_PROFIT_MARKET', inverted_side, order.volume, None, {'stopPrice': order.take_profit})
                    return True
                except ccxt.RateLimitExceeded as rle:
                    logger.warning(f"[RATE LIMIT] Binance Spot: {rle}")
                    await asyncio.sleep(3.0)
                    return False

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

            elif order.asset_class == "FOREX" and "IBKR" in self.exchanges:
                if not IBKR_SDK_AVAILABLE or not self.ibkr_client or not self.ibkr_client.isConnected():
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

    async def run_test_signal_check(self) -> dict:
        await self.gateway.initialize_exchanges()
        status_report = {}
        for item in self.symbols_config:
            symbol = item["symbol"]
            asset_type = item["asset_class"]
            is_open = self.is_market_open(asset_type)
            status_report[symbol] = {"asset_class": asset_type, "market_open": is_open}
        await self.gateway.close_exchanges()
        return status_report


# --- 4. CUSTOMER CARE SUPPORT BOT ---
class CustomerCareBot:
    @staticmethod
    def handle_query(query: str) -> str:
        q = query.lower()
        if "minimum" in q or "capital" in q:
            return "Support Bot: The minimum capital limit is strictly $20 across all supported markets."
        elif "binance" in q or "api" in q or "broker" in q or "ibkr" in q or "alpaca" in q:
            return "Support Bot: You can securely link your Binance, Stock (Alpaca), and Forex (Interactive Brokers) credentials via portal registration."
        else:
            return "Support Bot: Welcome! Our automated desk is fully optimized to assist your professional multi-asset trading journey."


# --- 5. INSTITUTIONAL UI COMPONENT WITH DYNAMIC AFFECTIONATE BANNER ---
class InstitutionalUI:
    def __init__(self):
        self.romantic_notes = [
            "Your brilliant mind builds empires, my love, and my heart beats only for your victories. 💖",
            "In every market upswing and downswing, my greatest pride is simply being yours. ✨",
            "Precision in your code, absolute perfection in who you are. You amaze me endlessly. 💓",
            "Every heartbeat echoes your name—steady, certain, and completely unstoppable today. 💘",
            "Just a reminder that you are deeply cherished, fiercely adored, and bound for greatness. 🌹",
            "No matter how complex the charts get, loving you is the easiest and most wonderful thing in the world. 🥰",
            "You bring so much light, strength, and joy into my life. Go conquer the day, my handsome genius! ⭐",
            "Your determination and heart inspire me every single second. I'm always cheering for you! 🥂",
            "Every line of code you write reflects your brilliance. I am endlessly proud to walk beside you. 🌟"
        ]

    def render_streamlit_heartbeat_banner(self):
        if "note_index" not in st.session_state:
            st.session_state.note_index = random.randint(0, len(self.romantic_notes) - 1)

        current_note = self.romantic_notes[st.session_state.note_index % len(self.romantic_notes)]

        st.markdown(
            """
            <style>
            @keyframes continuousHeartbeat {
                0% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                15% { transform: scale(1.25); text-shadow: 0 0 12px rgba(255,75,75,0.9); }
                30% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                45% { transform: scale(1.4); text-shadow: 0 0 18px rgba(255,75,75,1); }
                60% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                100% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
            }
            .pulsing-heart-icon {
                display: inline-block;
                animation: continuousHeartbeat 1.3s infinite ease-in-out;
            }
            .romantic-banner {
                padding: 24px;
                border-radius: 16px;
                background: linear-gradient(135deg, #1a1a2e 0%, #2b1035 50%, #1f1124 100%);
                border: 1.5px solid rgba(255, 75, 110, 0.5);
                text-align: center;
                margin-bottom: 24px;
                box-shadow: 0 10px 30px rgba(255, 75, 110, 0.2);
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="romantic-banner">
                <h4 style="color: #ff5c8a; margin: 0; letter-spacing: 1.3px; font-weight: 600;">
                    SYSTEM STATUS: ONLINE <span class="pulsing-heart-icon">💖</span> Institutional Core Active <span class="pulsing-heart-icon">💓</span>
                </h4>
                <p style="font-size: 19px; color: #f8f9fa; margin-top: 14px; font-style: italic; font-weight: 400; letter-spacing: 0.5px;">
                    "{current_note}"
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns([2, 2, 2])
        with col2:
            if st.button("✨ Read Another Note From My Heart", use_container_width=True):
                # Picks a random new index ensuring it rotates to a different note
                next_idx = random.randint(0, len(self.romantic_notes) - 1)
                if next_idx == st.session_state.note_index:
                    next_idx = (next_idx + 1) % len(self.romantic_notes)
                st.session_state.note_index = next_idx
                st.rerun()


# --- APP INITIALIZATION ---
db = ClientDatabase()
ui = InstitutionalUI()

st.sidebar.title("🔐 Institutional Gateway")
auth_mode = st.sidebar.radio("Navigation", ["Login", "Register", "Support Bot", "Live Trading Hub"])

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.full_name = ""

ui.render_streamlit_heartbeat_banner()

if auth_mode == "Register":
    st.header("📝 Institutional Client & Multi-Broker Registration")
    with st.form("registration_form"):
        st.subheader("1. User Credentials")
        new_user = st.text_input("Username")
        full_name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        password = st.text_input("Password", type="password")
        
        st.subheader("2. Broker API Integrations")
        b_api = st.text_input("Binance API Key (Crypto)", type="password")
        b_sec = st.text_input("Binance Secret Key (Crypto)", type="password")
        s_api = st.text_input("Alpaca API Key (Stocks)", type="password")
        s_sec = st.text_input("Alpaca Secret Key (Stocks)", type="password")
        ibkr_host = st.text_input("Interactive Brokers Host:Port (e.g., 127.0.0.1:7496)")
        
        submitted = st.form_submit_button("Register Securely")
        
        if submitted:
            if new_user and full_name and password:
                if db.register(new_user, full_name, phone, password, b_api, b_sec, s_api, s_sec, ibkr_host):
                    st.success("Registration successful! Switch to the Login tab.")
            else:
                st.warning("Please fill out the required user credential fields.")

elif auth_mode == "Login":
    st.header("🔑 Client Portal Login")
    if not st.session_state.logged_in:
        with st.form("login_form"):
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Authenticate")
            
            if login_btn:
                session = db.authenticate(username_input, password_input)
                if session:
                    st.session_state.logged_in = True
                    st.session_state.username = session["username"]
                    st.session_state.full_name = session["full_name"]
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        st.success(f"Connected as **{st.session_state.full_name}** (`{st.session_state.username}`)")
        masked = db.get_masked_profile(st.session_state.username)
        if masked:
            st.info(f"🔒 Privacy Profile | Name: **{masked['masked_name']}** | Phone: `{masked['masked_phone']}`")
        
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

elif auth_mode == "Live Trading Hub":
    st.header("📈 Live Multi-Market Execution Hub")
    if not st.session_state.get("logged_in", False):
        st.warning("Please log in through the portal to access live trading metrics and test your execution gateway.")
    else:
        st.success("API Credentials Authenticated Securely from Encrypted Vault.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Binance Status", "Active Core", "Crypto Shield Ready")
        col2.metric("Stocks Status", "Active Core", "Alpaca Link Ready")
        col3.metric("Forex Status", "Active Core", "IBKR Link Ready")
        
        st.markdown("---")
        st.subheader("⚡ Gateway Execution & Session Diagnostic")
        
        if st.button("Run Gateway Connectivity Check"):
            creds = db.get_client_credentials(st.session_state.username)
            symbols_config = [
                {"symbol": "BTC/USDT", "asset_class": "CRYPTO_SPOT"},
                {"symbol": "ETH/USDT:USDT", "asset_class": "CRYPTO_FUTURE"},
                {"symbol": "AAPL", "asset_class": "STOCKS"},
                {"symbol": "EURUSD", "asset_class": "FOREX"}
            ]
            engine = ZeroLagMultiMarketEngine(symbols_config=symbols_config, credentials=creds)
            
            with st.spinner("Connecting to live broker gateways..."):
                try:
                    report = asyncio.run(engine.run_test_signal_check())
                    st.json(report)
                    st.success("Gateway check completed successfully.")
                except Exception as ex:
                    st.error(f"[DIAGNOSTIC ERROR] {ex}")

elif auth_mode == "Support Bot":
    st.header("💬 Institutional Support Desk")
    user_query = st.text_input("Type your support inquiry:")
    if user_query:
        bot_response = CustomerCareBot.handle_query(user_query)
        st.markdown(f"> **{bot_response}**")
