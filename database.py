import sqlite3
from cryptography.fernet import Fernet
import os

KEY_FILE = "secret.key"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "wb") as f:
        f.write(Fernet.generate_key())

with open(KEY_FILE, "rb") as f:
    cipher = Fernet(f.read())

def init_db():
    conn = sqlite3.connect("elite_quant.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            balance REAL NOT NULL,
            enc_api_key TEXT NOT NULL,
            enc_secret_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def register_user(username: str, balance: float, api_key: str, secret_key: str):
    init_db()
    conn = sqlite3.connect("elite_quant.db")
    cursor = conn.cursor()
    
    enc_api = cipher.encrypt(api_key.encode()).decode()
    enc_sec = cipher.encrypt(secret_key.encode()).decode()
    
    try:
        cursor.execute("INSERT INTO users (username, balance, enc_api_key, enc_secret_key) VALUES (?, ?, ?, ?)",
                       (username, balance, enc_api, enc_sec))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def get_user_profile(username: str):
    init_db()
    conn = sqlite3.connect("elite_quant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance, enc_api_key, enc_secret_key FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "username": row[0],
            "balance": row[1],
            "api_key": cipher.decrypt(row[2].encode()).decode(),
            "secret_key": cipher.decrypt(row[3].encode()).decode()
        }
    return None
