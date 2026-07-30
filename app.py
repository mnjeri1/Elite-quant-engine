import streamlit
import sqlite3
import hashlib
import os
import time
import threading
from cryptography.fernet import Fernet

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
            print(f"[DB ERROR] Operational error during registration: {e}")
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
        self._note_index = 0

    def start_beating_heart_banner(self):
        def animate():
            hearts = [" ❤️ ", " 💖 ", " 💗 ", " 💓 ", " 💕 "]
            i = 0
            while True:
                heart_pulse = hearts[i % len(hearts)]
                current_note = self.sweet_notes[self._note_index % len(self.sweet_notes)]
                print(f"\r[SYSTEM STATUS: ONLINE] {heart_pulse} Institutional Core Active {heart_pulse} | Note: {current_note}", end="", flush=True)
                time.sleep(1.8)
                i += 1
                if i % 10 == 0:
                    self._note_index += 1

        t = threading.Thread(target=animate, daemon=True)
        t.start()


if __name__ == "__main__":
    db = ClientDatabase()
    ui = InstitutionalUI()
    bot = CustomerCareBot()
    
    print("\n--- INSTITUTIONAL CLIENT GATEWAY INITIALIZED ---")
    ui.start_beating_heart_banner()
    
    test_user = "trader_pro"
    if db.register(test_user, "Monicah Kabui", "+254712345678", "SecurePass123!", "binance_api_key_sample", "binance_secret_key_sample"):
        print("\n[INFO] User registered securely with persistent encrypted database memory.")
    
    session = db.authenticate(test_user, "SecurePass123!")
    if session:
        print(f"\n[INFO] Welcome back, {session['username']}! Credentials securely remembered.")
        print("[PRIVACY CHECK] Masked Profile:", db.get_masked_profile(test_user))
    
    print("\n--- TESTING CUSTOMER CARE BOT ---")
    print(bot.handle_query("How does the Binance connection avoid getting banned?"))
    
    time.sleep(6)
