import aiosqlite
import os
import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken


DB_NAME = "elite_quant.db"

PASSWORD_ITERATIONS = 600_000
PASSWORD_HASH_NAME = "sha256"
PASSWORD_SALT_BYTES = 32


# ============================================================
# ENCRYPTION
# ============================================================

def get_encryption_key():
    """
    IMPORTANT:
    During migration this continues using the existing
    secret.key so existing encrypted broker credentials
    remain decryptable.

    Later we will move this key into Streamlit secrets.
    """

    env_key = os.getenv("ELITE_ENCRYPTION_KEY")

    if env_key:
        return env_key.encode("utf-8")

    key_file = "secret.key"

    if not os.path.exists(key_file):
        key = Fernet.generate_key()

        with open(key_file, "wb") as f:
            f.write(key)

        print(
            "WARNING: A new development encryption key "
            "was generated."
        )

    with open(key_file, "rb") as f:
        return f.read().strip()


cipher = Fernet(get_encryption_key())


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password: str) -> str:
    """
    Passwords are hashed, not encrypted.
    """

    if not password:
        raise ValueError("Password cannot be empty.")

    if len(password) < 10:
        raise ValueError(
            "Password must contain at least 10 characters."
        )

    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)

    password_hash = hashlib.pbkdf2_hmac(
        PASSWORD_HASH_NAME,
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS
    )

    salt_encoded = base64.urlsafe_b64encode(
        salt
    ).decode("utf-8")

    hash_encoded = base64.urlsafe_b64encode(
        password_hash
    ).decode("utf-8")

    return (
        f"pbkdf2_{PASSWORD_HASH_NAME}"
        f"${PASSWORD_ITERATIONS}"
        f"${salt_encoded}"
        f"${hash_encoded}"
    )


def verify_password(
    password: str,
    stored_hash: str
) -> bool:

    try:

        algorithm, iterations, salt_encoded, hash_encoded = (
            stored_hash.split("$")
        )

        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.urlsafe_b64decode(
            salt_encoded
        )

        expected_hash = base64.urlsafe_b64decode(
            hash_encoded
        )

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations)
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except Exception:
        return False


# ============================================================
# DATABASE INITIALIZATION / MIGRATION
# ============================================================

async def init_db():

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT UNIQUE NOT NULL,

                password_hash TEXT,

                balance REAL NOT NULL DEFAULT 0,

                enc_api_key TEXT NOT NULL,
                enc_secret_key TEXT NOT NULL,

                enc_alpaca_key TEXT,
                enc_alpaca_sec TEXT,

                enc_oanda_token TEXT,
                enc_oanda_account TEXT,

                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                last_login TIMESTAMP
            )
        """)

        # ----------------------------------------------------
        # Migrate existing database
        # ----------------------------------------------------

        cursor = await db.execute(
            "PRAGMA table_info(users)"
        )

        columns = await cursor.fetchall()

        column_names = {
            column[1]
            for column in columns
        }

        if "password_hash" not in column_names:

            await db.execute("""
                ALTER TABLE users
                ADD COLUMN password_hash TEXT
            """)

        if "last_login" not in column_names:

            await db.execute("""
                ALTER TABLE users
                ADD COLUMN last_login TIMESTAMP
            """)

        await db.commit()


# ============================================================
# REGISTER USER
# ============================================================

async def register_user(
    username: str,
    password: str,
    balance: float,
    api_key: str = "",
    secret_key: str = "",
    alpaca_key: str = "",
    alpaca_sec: str = "",
    oanda_token: str = "",
    oanda_account: str = ""
):

    username = username.strip()

    if len(username) < 3:
        return False

    if len(password) < 10:
        return False

    if balance < 0:
        return False

    try:

        password_hash = hash_password(password)

        # Encrypt broker credentials

        enc_api = cipher.encrypt(
            api_key.encode("utf-8")
        ).decode("utf-8")

        enc_sec = cipher.encrypt(
            secret_key.encode("utf-8")
        ).decode("utf-8")

        enc_alpaca_key = (
            cipher.encrypt(
                alpaca_key.encode("utf-8")
            ).decode("utf-8")
            if alpaca_key
            else ""
        )

        enc_alpaca_sec = (
            cipher.encrypt(
                alpaca_sec.encode("utf-8")
            ).decode("utf-8")
            if alpaca_sec
            else ""
        )

        enc_oanda_token = (
            cipher.encrypt(
                oanda_token.encode("utf-8")
            ).decode("utf-8")
            if oanda_token
            else ""
        )

        enc_oanda_account = (
            cipher.encrypt(
                oanda_account.encode("utf-8")
            ).decode("utf-8")
            if oanda_account
            else ""
        )

        await init_db()

        async with aiosqlite.connect(DB_NAME) as db:

            await db.execute("""
                INSERT INTO users (
                    username,
                    password_hash,
                    balance,
                    enc_api_key,
                    enc_secret_key,
                    enc_alpaca_key,
                    enc_alpaca_sec,
                    enc_oanda_token,
                    enc_oanda_account
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                password_hash,
                balance,
                enc_api,
                enc_sec,
                enc_alpaca_key,
                enc_alpaca_sec,
                enc_oanda_token,
                enc_oanda_account
            ))

            await db.commit()

        return True

    except aiosqlite.IntegrityError:

        return False

    except Exception as e:

        print(
            f"Registration error: {e}"
        )

        return False


# ============================================================
# AUTHENTICATE USER
# ============================================================

async def authenticate_user(
    username: str,
    password: str
):

    username = username.strip()

    if not username or not password:
        return None

    await init_db()

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute("""
            SELECT
                username,
                password_hash,
                balance,
                enc_api_key,
                enc_secret_key,
                enc_alpaca_key,
                enc_alpaca_sec,
                enc_oanda_token,
                enc_oanda_account
            FROM users
            WHERE username = ?
        """, (username,)) as cursor:

            row = await cursor.fetchone()

            if not row:
                return None

            stored_password_hash = row[1]

            # Existing accounts created before this
            # security upgrade do not have passwords.
            if not stored_password_hash:

                return {
                    "migration_required": True,
                    "username": row[0]
                }

            if not verify_password(
                password,
                stored_password_hash
            ):

                return None

            # Update last login

            await db.execute("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
            """, (username,))

            await db.commit()

            try:

                return {
                    "migration_required": False,

                    "username": row[0],

                    "balance": row[2],

                    "api_key": cipher.decrypt(
                        row[3].encode()
                    ).decode(),

                    "secret_key": cipher.decrypt(
                        row[4].encode()
                    ).decode(),

                    "alpaca_key": (
                        cipher.decrypt(
                            row[5].encode()
                        ).decode()
                        if row[5]
                        else ""
                    ),

                    "alpaca_sec": (
                        cipher.decrypt(
                            row[6].encode()
                        ).decode()
                        if row[6]
                        else ""
                    ),

                    "oanda_token": (
                        cipher.decrypt(
                            row[7].encode()
                        ).decode()
                        if row[7]
                        else ""
                    ),

                    "oanda_account": (
                        cipher.decrypt(
                            row[8].encode()
                        ).decode()
                        if row[8]
                        else ""
                    )
                }

            except InvalidToken:

                print(
                    "Credential decryption failed. "
                    "The encryption key may be incorrect."
                )

                return None

            except Exception as e:

                print(
                    f"Credential decryption error: {e}"
                )

                return None


# ============================================================
# SET PASSWORD FOR EXISTING USER
# ============================================================

async def set_initial_password(
    username: str,
    new_password: str
):

    if len(new_password) < 10:
        return False

    await init_db()

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute("""
            SELECT password_hash
            FROM users
            WHERE username = ?
        """, (username,)) as cursor:

            row = await cursor.fetchone()

            if not row:
                return False

            # Only permit this for accounts that
            # haven't been migrated yet.

            if row[0]:
                return False

        password_hash = hash_password(
            new_password
        )

        await db.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE username = ?
        """, (
            password_hash,
            username
        ))

        await db.commit()

        return True


# ============================================================
# CHANGE PASSWORD
# ============================================================

async def change_password(
    username: str,
    current_password: str,
    new_password: str
):

    if len(new_password) < 10:
        return False

    await init_db()

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute("""
            SELECT password_hash
            FROM users
            WHERE username = ?
        """, (username,)) as cursor:

            row = await cursor.fetchone()

            if not row:
                return False

            if not row[0]:
                return False

            if not verify_password(
                current_password,
                row[0]
            ):
                return False

        new_hash = hash_password(
            new_password
        )

        await db.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE username = ?
        """, (
            new_hash,
            username
        ))

        await db.commit()

        return True


# ============================================================
# BALANCE
# ============================================================

async def update_user_balance(
    username: str,
    new_balance: float
):

    new_balance = max(
        0.0,
        float(new_balance)
    )

    await init_db()

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE users
            SET balance = ?
            WHERE username = ?
        """, (
            new_balance,
            username
        ))

        await db.commit()
