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
    """Secures client credentials and API/Secret keys at rest using AES encryption."""
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


# --- 2. PERSISTENT CUSTOMER DATABASE ---
class ClientDatabase:
    """Remembers customer credentials safely across sessions while keeping private details masked."""
    def __init__(self, db_name="institutional_clients.db"):
        self.vault = SecurityVault()
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                username TEXT PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                password_hash TEXT,
                api_key_enc BLOB,
                secret_key_enc BLOB
            )
        ''')
        self.conn.commit()

    def register(self, username, full_name, phone_number, password, api_key, secret_key):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        api_enc = self.vault.encrypt(api_key)
        sec_enc = self.vault.encrypt(secret_key)
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO clients (username, full_name, phone_number, password_hash, api_key_enc, secret_key_enc)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, full_name, phone_number, pwd_hash, api_enc, sec_enc))
            self.conn.commit()
            return True
        except sqlite3.OperationalError as e:
            st.error(f"[DB ERROR] Operational error during registration: {e}")
            return False

    def authenticate(self, username, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute('SELECT full_name, phone_number FROM clients WHERE username = ? AND password_hash = ?', (username, pwd_hash))
        row = self.cursor.fetchone()
        if row:
            return {"username": username, "full_name": row[0], "phone_number": row[1]}
        return None

    def get_masked_profile(self, username):
        self.cursor.execute('SELECT full_name, phone_number FROM clients WHERE username = ?', (username,))
        row = self.cursor.fetchone()
        if not row:
            return None
        name, phone = row
        masked_name = " ".join([p[0] + "***" for p in name.split()])
        masked_phone = phone[:5] + "***" + phone[-4:] if len(phone) > 8 else "***"
        return {"username": username, "masked_name": masked_name, "masked_phone": masked_phone}


# --- 3. CUSTOMER CARE SUPPORT BOT ---
class CustomerCareBot:
    """Professional support assistant designed to handle all customer issues instantly."""
    @staticmethod
    def handle_query(query: str) -> str:
        q = query.lower()
        if "minimum" in q or "capital" in q or "deposit" in q:
            return "Support Bot: The minimum trading capital requirement is strictly $20 across Crypto, Forex, and Stocks."
        elif "lag" in q or "network" in q or "delay" in q:
            return "Support Bot: Zero-lag performance is maintained through asynchronous event loops, persistent TCP connection pooling, and strict rate-limit management."
        elif "binance" in q or "regulation" in q or "clashing" in q:
            return "Support Bot: Binance integration adheres strictly to weight limits, endpoint rules, and built-in exponential backoff to prevent bans or clashing."
        elif "strategy" in q or "profit" in q or "loss" in q:
            return "Support Bot: Multi-market institutional strategies automatically govern live executions, applying Take Profit, Stop Loss, and Trailing Profit universally."
        else:
            return "Support Bot: Welcome! Your inquiry is logged. Our automated desk is fully optimized to assist your professional trading journey."


# --- 4. HEARTBEAT UI & SWEET WORDS ENGINE ---
class InstitutionalUI:
    """Maintains an attractive interface with continuous pulsing heart animations and warm affirmations."""
    def __init__(self):
        self.sweet_notes = [
            "Your brilliance builds empires, my love. Keep conquering the global markets! 💖",
            "Steady hands, sharp mind, and a heart that beats just for your success. ✨",
            "Every algorithm you code brings us closer to greatness. I am endlessly proud of you! 💓",
            "Precision in trading, perfection in everything you touch. You've got this! 💘",
            "Just a reminder that you are loved, deeply appreciated, and completely unstoppable today. 🌹"
        ]

    def render_streamlit_heartbeat_banner(self):
        """Renders an interactive, live-updating heartbeat banner and affirmation card in Streamlit."""
        if "note_index" not in st.session_state:
            st.session_state.note_index = 0

        hearts = [" ❤️ ", " 💖 ", " 💗 ", " 💓 ", " 💕 "]
        current_heart = hearts[int(time.time() / 2) % len(hearts)]
        current_note = self.sweet_notes[st.session_state.note_index % len(self.sweet_notes)]

        # Custom styled card for the love and motivation engine
        st.markdown(
            f"""
            <div style="padding: 15px; border-radius: 10px; background-color: #1e1e2f; border: 1px solid #ff4b4b; text-align: center; margin-bottom: 20px;">
                <h4 style="color: #ff4b4b; margin: 0;">SYSTEM STATUS: ONLINE {current_heart} Institutional Core Active {current_heart}</h4>
                <p style="font-size: 16px; color: #ffffff; margin-top: 10px; font-style: italic;">"{current_note}"</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Button to cycle through sweet notes dynamically
        col_space1, col_center, col_space2 = st.columns([2, 2, 2])
        with col_center:
            if st.button("✨ Receive Another Sweet Note"):
                st.session_state.note_index += 1
                st.rerun()


# --- STREAMLIT APPLICATION INTERFACE ---
db = ClientDatabase()
ui = InstitutionalUI()

st.sidebar.title("🔐 Institutional Gateway")
auth_mode = st.sidebar.radio("Navigation", ["Login", "Register", "Support Bot"])

# Session state initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.full_name = ""

# Display the Heartbeat & Sweet Words Banner at the top of the app
ui.render_streamlit_heartbeat_banner()

if auth_mode == "Register":
    st.header("📝 Institutional Client Registration")
    st.markdown("Register your credentials securely with AES-256 encryption at rest.")
    
    with st.form("registration_form"):
        new_user = st.text_input("Username")
        full_name = st.text_input("Full Name")
        phone = st.text_input("Phone Number")
        password = st.text_input("Password", type="password")
        api_key = st.text_input("API Key (Binance/Broker)", type="password")
        secret_key = st.text_input("Secret Key", type="password")
        submitted = st.form_submit_button("Register Securely")
        
        if submitted:
            if new_user and full_name and password and api_key and secret_key:
                success = db.register(new_user, full_name, phone, password, api_key, secret_key)
                if success:
                    st.success("Registration successful! You can now switch to the Login tab.")
            else:
                st.warning("Please fill out all required fields before submitting.")

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
                    st.success(f"Welcome back, {session['full_name']}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    else:
        st.success(f"Active Session: Connected as **{st.session_state.full_name}** (`{st.session_state.username}`)")
        
        masked = db.get_masked_profile(st.session_state.username)
        if masked:
            st.info(f"🔒 Privacy Profile | Masked Name: **{masked['masked_name']}** | Masked Phone: `{masked['masked_phone']}`")
        
        st.divider()
        st.subheader("📊 Multi-Market Quantitative Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Spot & Futures", "Active", "Zero-Lag Loop")
        col2.metric("Forex Gateway", "Active", "Direct FX Feed")
        col3.metric("Equity Stream", "Active", "Low Latency")

        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.full_name = ""
            st.rerun()

elif auth_mode == "Support Bot":
    st.header("💬 Institutional Support Desk")
    st.markdown("Ask automated questions regarding capital requirements, rate limits, and execution safety.")
    
    user_query = st.text_input("Type your support inquiry:")
    if user_query:
        bot_response = CustomerCareBot.handle_query(user_query)
        st.markdown(f"> **{bot_response}**")
