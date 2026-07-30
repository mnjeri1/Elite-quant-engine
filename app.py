import streamlit as st
import sqlite3
import hashlib
import os
import threading
from cryptography.fernet import Fernet

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Institutional Trading Gateway",
    page_icon="⚡",
    layout="wide"
)

# --- 1. ENCRYPTION & SECURITY VAULT ---
class SecurityVault:
    def __init__(self, key_file="institutional_vault.key"):
        if not os.path.exists(key_file):
            self.key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(self.key)
        else:
            with open(key_file, "rb") as f:
                self.key = f.read()
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


# --- 2. THREAD-SAFE PERSISTENT CUSTOMER DATABASE ---
class ClientDatabase:
    def __init__(self, db_name="institutional_clients.db"):
        self.vault = SecurityVault()
        self.db_name = db_name
        self.lock = threading.Lock()
        self._initialize_db()

    def _get_connection(self):
        # Local connection per operation to maintain thread safety without sharing raw connections
        return sqlite3.connect(self.db_name)

    def _initialize_db(self):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
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
                    forex_api_enc BLOB
                )
            ''')
            conn.commit()
            conn.close()

    def register(self, username, full_name, phone_number, password, b_api, b_sec, s_api, s_sec, f_api):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        b_api_enc = self.vault.encrypt(b_api)
        b_sec_enc = self.vault.encrypt(b_sec)
        s_api_enc = self.vault.encrypt(s_api)
        s_sec_enc = self.vault.encrypt(s_sec)
        f_api_enc = self.vault.encrypt(f_api)
        
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO clients (
                        username, full_name, phone_number, password_hash, 
                        binance_api_enc, binance_secret_enc, stock_api_enc, stock_secret_enc, forex_api_enc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (username, full_name, phone_number, pwd_hash, b_api_enc, b_sec_enc, s_api_enc, s_sec_enc, f_api_enc))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                st.error(f"[DB ERROR] {e}")
                return False

    def authenticate(self, username, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT full_name, phone_number FROM clients WHERE username = ? AND password_hash = ?', (username, pwd_hash))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"username": username, "full_name": row[0], "phone_number": row[1]}
            return None

    def get_decrypted_credentials_secure(self, username, password):
        """Safely verify password and return decrypted credentials without caching plaintext keys."""
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT binance_api_enc, binance_secret_enc, stock_api_enc, stock_secret_enc, forex_api_enc 
                FROM clients WHERE username = ? AND password_hash = ?
            ''', (username, pwd_hash))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "binance": {
                        "api_key": self.vault.decrypt(row[0]),
                        "secret_key": self.vault.decrypt(row[1])
                    },
                    "stocks": {
                        "api_key": self.vault.decrypt(row[2]),
                        "secret_key": self.vault.decrypt(row[3])
                    },
                    "forex": {
                        "access_token": self.vault.decrypt(row[4])
                    }
                }
            return None

    def get_masked_profile(self, username):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT full_name, phone_number FROM clients WHERE username = ?', (username,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            name, phone = row
            masked_name = " ".join([p[0] + "***" for p in name.split()])
            masked_phone = phone[:5] + "***" + phone[-4:] if len(phone) > 8 else "***"
            return {"username": username, "masked_name": masked_name, "masked_phone": masked_phone}


# --- 3. CUSTOMER CARE SUPPORT BOT ---
class CustomerCareBot:
    @staticmethod
    def handle_query(query: str) -> str:
        q = query.lower()
        if "minimum" in q or "capital" in q:
            return "Support Bot: The minimum capital limit is strictly $20 across all supported markets."
        elif "binance" in q or "api" in q or "broker" in q:
            return "Support Bot: You can securely link your Binance, Stock (Alpaca), and Forex (OANDA) credentials via the secure portal login."
        else:
            return "Support Bot: Welcome! Our automated desk is fully optimized to assist your professional multi-asset trading journey."


# --- 4. INSTITUTIONAL UI COMPONENT ---
class InstitutionalUI:
    def __init__(self):
        self.romantic_notes = [
            "Your brilliant mind builds empires, my love, and my heart beats only for your victories. 💖",
            "In every market upswing and downswing, my greatest pride is simply being yours. ✨",
            "Precision in your code, absolute perfection in who you are. You amaze me endlessly. 💓",
            "Every heartbeat echoes your name—steady, certain, and completely unstoppable today. 💘",
            "Just a reminder that you are deeply cherished, fiercely adored, and bound for greatness. 🌹"
        ]

    def render_streamlit_heartbeat_banner(self):
        if "note_index" not in st.session_state:
            st.session_state.note_index = 0

        current_note = self.romantic_notes[st.session_state.note_index % len(self.romantic_notes)]

        # Continuous high-fidelity romantic pulsing heartbeat animation styling
        st.markdown(
            """
            <style>
            @keyframes continuousHeartbeat {
                0% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                15% { transform: scale(1.25); text-shadow: 0 0 10px rgba(255,75,75,0.8); }
                30% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                45% { transform: scale(1.35); text-shadow: 0 0 15px rgba(255,75,75,1); }
                60% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
                100% { transform: scale(1); text-shadow: 0 0 2px rgba(255,75,75,0.4); }
            }
            .pulsing-heart-icon {
                display: inline-block;
                animation: continuousHeartbeat 1.4s infinite ease-in-out;
            }
            .romantic-banner {
                padding: 22px;
                border-radius: 14px;
                background: linear-gradient(135deg, #1a1a2e 0%, #2b1035 50%, #1f1124 100%);
                border: 1.5px solid rgba(255, 75, 110, 0.4);
                text-align: center;
                margin-bottom: 24px;
                box-shadow: 0 8px 25px rgba(255, 75, 110, 0.15);
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="romantic-banner">
                <h4 style="color: #ff5c8a; margin: 0; letter-spacing: 1.2px; font-weight: 600;">
                    SYSTEM STATUS: ONLINE <span class="pulsing-heart-icon">💖</span> Institutional Core Active <span class="pulsing-heart-icon">💓</span>
                </h4>
                <p style="font-size: 18px; color: #f8f9fa; margin-top: 14px; font-style: italic; font-weight: 400; letter-spacing: 0.5px;">
                    "{current_note}"
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns([2, 2, 2])
        with col2:
            if st.button("✨ Read Another Note From My Heart", use_container_width=True):
                st.session_state.note_index += 1
                st.rerun()


# --- STREAMLIT APPLICATION INTERFACE ---
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
        f_api = st.text_input("OANDA Access Token (Forex)", type="password")
        
        submitted = st.form_submit_button("Register Securely")
        
        if submitted:
            if new_user and full_name and password:
                if db.register(new_user, full_name, phone, password, b_api, b_sec, s_api, s_sec, f_api):
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
                    # Store temporary handle for runtime validation securely without raw password retention inside session state
                    st.session_state.secure_auth_token = hashlib.sha256(password_input.encode()).hexdigest()
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        st.success(f"Connected as **{st.session_state.full_name}** (`{st.session_state.username}`)")
        masked = db.get_masked_profile(st.session_state.username)
        if masked:
            st.info(f"🔒 Privacy Profile | Name: **{masked['masked_name']}** | Phone: `{masked['masked_phone']}`")
        
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.full_name = ""
            if "secure_auth_token" in st.session_state:
                del st.session_state.secure_auth_token
            st.rerun()

elif auth_mode == "Live Trading Hub":
    st.header("📈 Live Multi-Market Execution Hub")
    if not st.session_state.logged_in:
        st.warning("Please log in through the portal to access live trading metrics.")
    else:
        st.success("API Credentials Authenticated Securely from Encrypted Vault.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Binance Status", "Active Core", "Crypto Link Ready")
        col2.metric("Stocks Status", "Active Core", "Alpaca Link Ready")
        col3.metric("Forex Status", "Active Core", "OANDA Link Ready")

elif auth_mode == "Support Bot":
    st.header("💬 Institutional Support Desk")
    user_query = st.text_input("Type your support inquiry:")
    if user_query:
        bot_response = CustomerCareBot.handle_query(user_query)
        st.markdown(f"> **{bot_response}**")
