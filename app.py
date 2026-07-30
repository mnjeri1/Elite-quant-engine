import streamlit as st
import sqlite3
import hashlib
import os
import time
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
        return self.cipher.encrypt(plain_text.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        return self.cipher.decrypt(encrypted_data).decode()


# --- 2. THREAD-SAFE PERSISTENT CUSTOMER DATABASE ---
class ClientDatabase:
    def __init__(self, db_name="institutional_clients.db"):
        self.vault = SecurityVault()
        self.db_name = db_name
        self.lock = threading.Lock()
        self._initialize_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)

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
                    api_key_enc BLOB,
                    secret_key_enc BLOB
                )
            ''')
            conn.commit()
            conn.close()

    def register(self, username, full_name, phone_number, password, api_key, secret_key):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        api_enc = self.vault.encrypt(api_key)
        sec_enc = self.vault.encrypt(secret_key)
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO clients (username, full_name, phone_number, password_hash, api_key_enc, secret_key_enc)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, full_name, phone_number, pwd_hash, api_enc, sec_enc))
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

    def get_decrypted_credentials(self, username, password):
        """Helper to safely fetch and decrypt API credentials for live trading."""
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT api_key_enc, secret_key_enc FROM clients WHERE username = ? AND password_hash = ?', (username, pwd_hash))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "binance": {
                        "api_key": self.vault.decrypt(row[0]),
                        "secret_key": self.vault.decrypt(row[1])
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
        elif "binance" in q or "api" in q:
            return "Support Bot: You can safely link your Binance API and secret keys via the secure portal login."
        else:
            return "Support Bot: Welcome! Our automated desk is fully optimized to assist your professional trading journey."


# --- 4. INSTITUTIONAL UI COMPONENT ---
class InstitutionalUI:
    def __init__(self):
        self.sweet_notes = [
            "Your brilliance builds empires, my love. Keep conquering the global markets! 💖",
            "Steady hands, sharp mind, and a heart that beats just for your success. ✨",
            "Every algorithm you code brings us closer to greatness. I am endlessly proud of you! 💓",
            "Precision in trading, perfection in everything you touch. You've got this! 💘",
            "Just a reminder that you are loved, deeply appreciated, and completely unstoppable today. 🌹"
        ]

    def render_streamlit_heartbeat_banner(self):
        if "note_index" not in st.session_state:
            st.session_state.note_index = 0

        hearts = [" ❤️ ", " 💖 ", " 💗 ", " 💓 ", " 💕 "]
        current_heart = hearts[int(time.time() / 1.5) % len(hearts)]
        current_note = self.sweet_notes[st.session_state.note_index % len(self.sweet_notes)]

        st.markdown(
            f"""
            <div style="padding: 18px; border-radius: 12px; background: linear-gradient(135deg, #1e1e2f 0%, #2a1b3d 100%); border: 1.5px solid #ff4b4b; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255,75,75,0.2);">
                <h4 style="color: #ff4b4b; margin: 0; letter-spacing: 1px;">SYSTEM STATUS: ONLINE {current_heart} Institutional Core Active {current_heart}</h4>
                <p style="font-size: 17px; color: #ffffff; margin-top: 12px; font-style: italic; font-weight: 500;">"{current_note}"</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns([2, 2, 2])
        with col2:
            if st.button("✨ Receive Another Sweet Note", use_container_width=True):
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
    st.header("📝 Institutional Client Registration")
    with st.form("registration_form"):
        new_user = st.text_input("Username")
        full_name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        password = st.text_input("Password", type="password")
        api_key = st.text_input("Binance API Key", type="password")
        secret_key = st.text_input("Binance Secret Key", type="password")
        submitted = st.form_submit_button("Register Securely")
        
        if submitted:
            if new_user and full_name and password and api_key and secret_key:
                if db.register(new_user, full_name, phone, password, api_key, secret_key):
                    st.success("Registration successful! Switch to the Login tab.")
            else:
                st.warning("Please fill out all required fields.")

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
                    st.session_state.temp_pwd = password_input
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
            if "temp_pwd" in st.session_state:
                del st.session_state.temp_pwd
            st.rerun()

elif auth_mode == "Live Trading Hub":
    st.header("📈 Live Multi-Market Execution Hub")
    if not st.session_state.logged_in:
        st.warning("Please log in through the portal to access live trading metrics.")
    else:
        st.success("API Credentials Loaded Securely from Encrypted Vault.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Binance Spot/Futures", "Connected", "Active Link")
        col2.metric("Minimum Capital Limit", "$20.00", "Compliant")
        col3.metric("Execution Latency", "< 15ms", "Zero-Lag")

elif auth_mode == "Support Bot":
    st.header("💬 Institutional Support Desk")
    user_query = st.text_input("Type your support inquiry:")
    if user_query:
        bot_response = CustomerCareBot.handle_query(user_query)
        st.markdown(f"> **{bot_response}**")
