import aiosqlite
from cryptography.fernet import Fernet
import os

KEY_FILE = "secret.key"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "wb") as f:
        f.write(Fernet.generate_key())

with open(KEY_FILE, "rb") as f:
    cipher = Fernet(f.read())

DB_NAME = "elite_quant.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                balance REAL NOT NULL,
                enc_api_key TEXT NOT NULL,
                enc_secret_key TEXT NOT NULL,
                enc_oanda_token TEXT,
                enc_oanda_account TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def register_user(username: str, balance: float, api_key: str, secret_key: str, oanda_token: str = "", oanda_account: str = ""):
    await init_db()
    enc_api = cipher.encrypt(api_key.encode()).decode()
    enc_sec = cipher.encrypt(secret_key.encode()).decode()
    enc_o_token = cipher.encrypt(oanda_token.encode()).decode() if oanda_token else ""
    enc_o_acc = cipher.encrypt(oanda_account.encode()).decode() if oanda_account else ""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO users (username, balance, enc_api_key, enc_secret_key, enc_oanda_token, enc_oanda_account) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, balance, enc_api, enc_sec, enc_o_token, enc_o_acc))
            await db.commit()
        return True
    except Exception:
        return False

async def get_user_profile(username: str):
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT username, balance, enc_api_key, enc_secret_key, enc_oanda_token, enc_oanda_account 
            FROM users WHERE username = ?
        """, (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "username": row[0],
                    "balance": row[1],
                    "api_key": cipher.decrypt(row[2].encode()).decode(),
                    "secret_key": cipher.decrypt(row[3].encode()).decode(),
                    "oanda_token": cipher.decrypt(row[4].encode()).decode() if row[4] else "",
                    "oanda_account": cipher.decrypt(row[5].encode()).decode() if row[5] else ""
                }
    return None

async def update_user_balance(username: str, new_balance: float):
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
        await db.commit()
