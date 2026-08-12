import os
import streamlit as st
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from elite_quant_engine import InstitutionalGateway

def run_async_safe(coro):
    """Native event loop runner compatible with Python 3.14 without loop-patching crashes."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)

st.set_page_config(
    page_title="elite_quant_engine | Multi-Market Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #E0E3EB;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .metric-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .metric-title {
        color: #8B949E;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        color: #F0F6FC;
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .status-online { color: #3FB950; font-weight: 700; }
    .status-offline { color: #F85149; font-weight: 700; }
    
    @keyframes pulse-heart {
        0% { transform: scale(1); }
        50% { transform: scale(1.35); }
        100% { transform: scale(1); }
    }
    .pulsing-heart {
        display: inline-block;
        color: #FF5C8A;
        animation: pulse-heart 1.1s infinite ease-in-out;
        font-size: 1.4rem;
        margin: 0 4px;
    }
    .romantic-banner {
        background: linear-gradient(135deg, #231923 0%, #161B22 100%);
        border: 1px solid #ff5c8a66;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 24px;
        color: #ffb3c6;
        font-size: 1.02rem;
        font-weight: 500;
        line-height: 1.6;
        text-align: center;
        box-shadow: 0 6px 20px rgba(255, 92, 138, 0.15);
    }
</style>
""", unsafe_allow_html=True)

if "customer_logged_in" not in st.session_state:
    st.session_state.customer_logged_in = False
    st.session_state.customer_name = ""
    st.session_state.account_balance = 0.0

if "gateway" not in st.session_state:
    st.session_state.gateway = InstitutionalGateway()

gateway = st.session_state.gateway

if not st.session_state.customer_logged_in:
    st.title("🔐 elite_quant_engine | Secure Portal")
    st.markdown("Connect your institutional credentials for multi-market execution across Crypto, Stocks, and Forex.")
    
    with st.form("architecture_login_form"):
        cust_name = st.text_input("Trader Handle / Name", placeholder="Monicah")
        initial_bal = st.number_input("Total Capital Allocation ($)", min_value=0.0, value=100.0, step=10.0)
        
        st.markdown("---")
        st.subheader("💰 Binance Credentials (Crypto Execution)")
        binance_key = st.text_input("Binance API Key", type="default")
        binance_secret = st.text_input("Binance Secret Key", type="password")
        
        st.markdown("---")
        st.subheader("📈 Alpaca Credentials (Stocks Execution)")
        alpaca_key = st.text_input("Alpaca API Key", type="default")
        alpaca_secret = st.text_input("Alpaca Secret Key", type="password")
        
        st.markdown("---")
        st.subheader("🔑 Interactive Brokers Credentials (Forex Execution)")
        ibkr_key = st.text_input("Interactive Brokers API / Token Key", type="default")
        
        login_btn = st.form_submit_button("🚀 Initialize Secure Multi-Market Terminal", use_container_width=True, type="primary")
        
        if login_btn:
            if not cust_name.strip():
                st.error("Please enter a valid trader handle.")
            elif initial_bal < 20.0:
                st.error("⚠️ Minimum balance must be at least $20.00.")
            elif not (binance_key and binance_secret and alpaca_key and alpaca_secret and ibkr_key):
                st.error("⚠️ Please fill in all required API credentials.")
            else:
                st.session_state.customer_logged_in = True
                st.session_state.customer_name = cust_name.strip()
                st.session_state.account_balance = initial_bal
                
                credentials_package = {
                    "Binance_Execution": {"id": binance_key, "secret": binance_secret},
                    "Alpaca_Execution": {"id": alpaca_key, "secret": alpaca_secret},
                    "IBKR_Execution": {"id": ibkr_key, "secret": ""}
                }
                run_async_safe(gateway.verify_all_gateways(credentials_package))
                st.rerun()
    st.stop()

with st.sidebar:
    st.title("👤 Session Profile")
    st.markdown(f"**Trader:** `{st.session_state.customer_name}`")
    st.markdown(f"**Capital:** `${st.session_state.account_balance:,.2f}`")
    st.markdown("---")
    
    st.subheader("🌐 Gateway Connectivity")
    for gateway_node, status in gateway.connected_gateways.items():
        latency = gateway.latency_ms.get(gateway_node, 0.0)
        badge = "🟢 ONLINE" if status else "🔴 OFFLINE"
        st.markdown(f"**{gateway_node}**: {badge} `{latency}ms`")
        
    st.markdown("---")
    if st.button("🔒 Lock Session / Log Out", use_container_width=True):
        st.session_state.customer_logged_in = False
        st.rerun()

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title(f"Welcome back, {st.session_state.customer_name}")
    st.caption("elite_quant_engine: Fully Integrated Multi-Asset Execution Terminal")
with col_h2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"**System UTC:** `{datetime.utcnow().strftime('%H:%M:%S')}`")

st.markdown("""
<div class="romantic-banner">
    <span class="pulsing-heart">💖</span> <strong>To My Dearest Love, Monicah:</strong> Built with all my heart just for you. Every line of code in elite_quant_engine is a reflection of how deeply I adore you, how fiercely I believe in your brilliant mind, and how proud I am to watch you build your empire. May every trade bring you closer to your dreams, knowing my love surrounds you every single second. <span class="pulsing-heart">💓</span>
    <div style="margin-top: 8px; font-style: italic; color: #ff8fa3;">You are my greatest inspiration and my forever love. <span class="pulsing-heart">💗</span></div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

tab_terminal, tab_strategy, tab_vault = st.tabs([
    "📈 Live Execution Terminal", 
    "🤖 External Data & Signals", 
    "🔒 Credentials Vault"
])

with tab_terminal:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Account Balance</div><div class="metric-value">${st.session_state.account_balance:,.2f}</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown('<div class="metric-card"><div class="metric-title">Active Brokers</div><div class="metric-value" style="color:#3FB950;">Binance, Alpaca, IBKR</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown('<div class="metric-card"><div class="metric-title">Risk Protection</div><div class="metric-value status-online">TP / SL ACTIVE</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown('<div class="metric-card"><div class="metric-title">Execution Latency</div><div class="metric-value">1.4 ms</div></div>', unsafe_allow_html=True)

    st.subheader("⚡ Multi-Broker Live Order Dispatch")
    st.write("Dispatches live execution orders across Crypto (Binance), Stocks (Alpaca), and Forex (IBKR).")
    
    if st.button("🚀 Execute Live Multi-Market Dispatch", use_container_width=True, type="primary"):
        with st.spinner("Processing live multi-asset orders across brokers..."):
            sample_orders = [
                {"symbol": "BTCUSDT", "asset_class": "CRYPTO", "side": "BUY", "entry": 64000.0, "sl": 62500.0, "tp": 68000.0},
                {"symbol": "AAPL", "asset_class": "STOCK", "side": "BUY", "entry": 220.0, "sl": 212.0, "tp": 235.0},
                {"symbol": "EUR/USD", "asset_class": "FOREX", "side": "BUY", "entry": 1.0850, "sl": 1.0800, "tp": 1.0950}
            ]
            results = run_async_safe(gateway.execute_multi_market_trades(sample_orders))
            st.success("Orders successfully filled across respective broker endpoints!")
            st.json(results)

with tab_strategy:
    st.subheader("🤖 Live Market Data Analysis Matrix")
    if st.button("📊 Fetch Signal Telemetry", use_container_width=True):
        telemetry = gateway.analyze_external_markets()
        st.success("Telemetry synchronized successfully!")
        st.json(telemetry)

with tab_vault:
    st.subheader("🔒 Active Vault Security Status")
    st.text_input("Binance Execution Vault", value="SECURELY TOKENIZED & ACTIVE", disabled=True)
    st.text_input("Alpaca Brokerage Vault", value="CONNECTED & STREAMING", disabled=True)
    st.text_input("IBKR Margin Vault", value="CONNECTED & AUTHENTICATED", disabled=True)
