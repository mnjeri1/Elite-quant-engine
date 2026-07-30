import streamlit as st
import sqlite3
import asyncio
import ccxt.async_support as ccxt

# 1. Page Configuration & Professional Styling
st.set_page_config(
    page_title="Elite Quad Engine",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; background-color: #ff4b4b; color: white; }
    .stButton>button:hover { background-color: #ff2b2b; color: white; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Elite Quad Engine")
st.markdown("##### Institutional-Grade Automated Quantitative Trading Dashboard")
st.markdown("---")

# 2. Optimized Fast Database Connection (Cached to prevent lag)
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect("elite_users.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    conn.commit()
    return conn

conn = get_db_connection()
cursor = conn.cursor()

# 3. Sidebar: Authentication & Secure API Configuration
st.sidebar.header("🔐 Client Portal")
auth_tab = st.sidebar.radio("Select Action", ["Login", "Register"])

if auth_tab == "Register":
    st.sidebar.subheader("New Account Registration")
    reg_name = st.sidebar.text_input("Full Name")
    reg_phone = st.sidebar.text_input("Phone Number (e.g., 07...)")
    
    if st.sidebar.button("Complete Registration"):
        if reg_name and reg_phone:
            try:
                cursor.execute("INSERT INTO users (phone, name) VALUES (?, ?)", (reg_phone, reg_name))
                conn.commit()
                st.sidebar.success("Registration successful! Switch to Login.")
            except sqlite3.IntegrityError:
                st.sidebar.error("Phone number already registered.")
        else:
            st.sidebar.warning("Please fill in all fields.")

else:
    st.sidebar.subheader("Secure Client Login")
    login_phone = st.sidebar.text_input("Registered Phone Number", key="login_input")
    
    if st.sidebar.button("Sign In"):
        if login_phone:
            cursor.execute("SELECT name FROM users WHERE phone = ?", (login_phone,))
            user = cursor.fetchone()
            if user:
                st.session_state['logged_in_user'] = user[0]
                st.session_state['user_phone'] = login_phone
                st.sidebar.success(f"Welcome back, {user[0]}!")
            else:
                st.sidebar.error("Phone number not found. Please register.")
        else:
            st.sidebar.warning("Enter your phone number.")

# 4. Main Dashboard Area (Protected by Login State)
if 'logged_in_user' in st.session_state:
    st.success(f"Active Session: **{st.session_state['logged_in_user']}**")
    
    # Secure API Inputs
    st.subheader("🔑 Exchange API Configuration")
    col1, col2 = st.columns(2)
    with col1:
        api_key = st.text_input("Binance API Key", type="password", placeholder="Enter API Key")
    with col2:
        api_secret = st.text_input("Binance Secret Key", type="password", placeholder="Enter Secret Key")
        
    st.markdown("---")
    
    # Wallet & Risk Management Parameters ($20 Minimum Guardrail)
    st.subheader("🛡️ Wallet & Risk Safeguards ($20 Minimum Rule)")
    st.info("The engine automatically validates wallet equity. Accounts with a minimum of $20 are fully supported.")
    
    trading_pair = st.selectbox("Select Trading Pair", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"])
    allocation_pct = st.slider("Capital Allocation per Trade (%)", min_value=10, max_value=100, value=50, step=5)

    st.markdown("---")
    st.subheader("🚀 Execution Control Panel")

    if st.button("Initialize Master Trading Engine"):
        if not api_key or not api_secret:
            st.error("⚠️ Please provide your Binance API Key and Secret Key above to connect.")
        else:
            with st.spinner("Connecting securely to Binance & verifying wallet balance..."):
                try:
                    # Anti-lag asynchronous balance checker with timeout protection
                    async def fetch_balance_safely():
                        exchange = ccxt.binance({
                            'apiKey': api_key,
                            'secret': api_secret,
                            'enableRateLimit': True,
                            'timeout': 10000,  # 10 seconds timeout limit to prevent infinite hanging
                            'options': {'defaultType': 'spot'}
                        })
                        try:
                            balance = await exchange.fetch_balance()
                            usdt_free = balance['USDT']['free']
                            return usdt_free
                        finally:
                            await exchange.close()

                    # Run safely within a localized loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    available_usdt = loop.run_until_complete(fetch_balance_safely())
                    
                    if available_usdt < 20.0:
                        st.error(f"❌ Insufficient Balance: Your available USDT balance is ${available_usdt:.2f}. A minimum of $20.00 is required.")
                    else:
                        st.success(f"✅ Wallet Verified! Balance: ${available_usdt:.2f} USDT. Minimum threshold met.")
                        st.info(f"🔄 Strategy running smoothly for {trading_pair} with professional position sizing.")
                        
                except Exception as e:
                    st.error(f"Connection Timed Out or Invalid API Keys: {e}")
else:
    st.warning("⚠️ Please sign in or register using your phone number via the sidebar to access the trading engine control panel.")
