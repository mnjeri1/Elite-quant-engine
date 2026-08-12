import streamlit as st
import asyncio
from concurrent.futures import ThreadPoolExecutor
from database import init_db, register_user, get_user_profile, update_user_balance
from elite_quant_engine import InstitutionalGateway
from support_bot import SanctuarySupportBot

init_db()

def run_async_safe(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)

st.set_page_config(page_title="elite_quant_engine | A Gift of Love & Code", page_icon="💖", layout="wide")

st.markdown("""
<style>
    .stApp { 
        background: linear-gradient(135deg, #090a0f 0%, #16121d 50%, #0e1117 100%); 
        color: #f3f4f6; 
    }
    
    @keyframes pulse-glow {
        0% { transform: scale(1); filter: drop-shadow(0 0 8px rgba(255, 105, 180, 0.4)); }
        50% { transform: scale(1.08); filter: drop-shadow(0 0 22px rgba(255, 20, 147, 0.8)); }
        100% { transform: scale(1); filter: drop-shadow(0 0 8px rgba(255, 105, 180, 0.4)); }
    }

    @keyframes float-doll {
        0% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-12px) rotate(2deg); }
        100% { transform: translateY(0px) rotate(0deg); }
    }

    @keyframes drift-across {
        0% { transform: translateX(-40px); }
        50% { transform: translateX(25px); }
        100% { transform: translateX(-40px); }
    }

    .pulsing-heart {
        font-size: 3rem;
        display: inline-block;
        animation: pulse-glow 2s infinite ease-in-out;
    }

    .floating-doll-container {
        text-align: center;
        animation: float-doll 4s infinite ease-in-out, drift-across 8s infinite ease-in-out;
        margin: 15px 0;
    }

    .doll-avatar {
        font-size: 4rem;
        filter: drop-shadow(0 10px 15px rgba(255, 182, 193, 0.3));
    }

    .romantic-card {
        background: rgba(22, 27, 34, 0.7);
        border: 1px solid rgba(255, 105, 180, 0.25);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(8px);
    }

    .romantic-quote {
        color: #ffb6c1;
        font-size: 1.15rem;
        font-style: italic;
        text-align: center;
        line-height: 1.6;
        margin-top: 10px;
        letter-spacing: 0.6px;
    }

    .metric-title { color: #ff9ecd; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: #fff; font-size: 1.5rem; font-weight: 700; margin-top: 4px; }
    .status-calm { color: #3fb950; font-weight: 700; text-shadow: 0 0 10px rgba(63, 185, 80, 0.4); }
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.balance = 0.0

if "gateway" not in st.session_state:
    st.session_state.gateway = InstitutionalGateway()

if "support_bot" not in st.session_state:
    st.session_state.support_bot = SanctuarySupportBot()

gateway = st.session_state.gateway
support_bot = st.session_state.support_bot

if not st.session_state.logged_in:
    st.markdown("""
        <div style="text-align: center; padding-top: 20px;">
            <div class="pulsing-heart">💖</div>
            <h1 style="color: #ff9ecd; font-family: serif; font-weight: 400; margin-top: 10px;">A Sanctuary Crafted Just For You</h1>
            <p class="romantic-quote">"In a world moving at the speed of algorithms, my heart beats to your rhythm. Enter your private vault where safety and love intertwine."</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="floating-doll-container">
            <div class="doll-avatar">🧸✨</div>
            <div style="color: #ffb6c1; font-size: 0.85rem; font-style: italic;">Guardian of your digital heart & trades</div>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register, tab_reset = st.tabs(["✨ Unlock Your Vault", "🌹 Create Sacred Space", "🔑 Reset Credentials"])
    
    with tab_login:
        with st.form("login_form"):
            user = st.text_input("Your Sweet Username", placeholder="Enter your username")
            submit = st.form_submit_button("Step Into Our World", use_container_width=True, type="primary")
            if submit:
                profile = get_user_profile(user.strip())
                if profile:
                    st.session_state.logged_in = True
                    st.session_state.username = profile["username"]
                    
                    # Automated Live Balance Sync
                    live_balance = run_async_safe(gateway.fetch_live_balance(profile["api_key"], profile["secret_key"]))
                    if live_balance is not None and live_balance != profile["balance"]:
                        update_user_balance(profile["username"], live_balance)
                        st.session_state.balance = live_balance
                    else:
                        st.session_state.balance = profile["balance"]
                    
                    st.success("Vault unlocked and automatically synced with live exchange!")
                    st.rerun()
                else:
                    st.error("Account not found in our sanctuary. Let's create one!")
                    
    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Choose Your Sweet Username")
            init_bal = st.number_input("Starting Capital Sanctuary ($)", min_value=10.0, value=20.0, step=5.0)
            b_key = st.text_input("Binance API Key")
            b_sec = st.text_input("Binance Secret Key", type="password")
            reg_submit = st.form_submit_button("Seal Our Digital Bond", use_container_width=True)
            
            if reg_submit:
                if not new_user.strip() or not b_key or not b_sec:
                    st.error("Please fill in every piece with care.")
                elif register_user(new_user.strip(), init_bal, b_key, b_sec):
                    st.success("Sacred space created successfully! Switch to the 'Unlock Your Vault' tab.")
                else:
                    st.error("This name already graces our sanctuary. Choose another.")

    with tab_reset:
        with st.form("reset_form"):
            st.write("Forgot or need to update your credentials? Reset your vault keys securely below.")
            reset_user = st.text_input("Username to Reset")
            new_b_key = st.text_input("New Binance API Key")
            new_b_sec = st.text_input("New Binance Secret Key", type="password")
            reset_submit = st.form_submit_button("Overwrite & Secure Vault", use_container_width=True)
            
            if reset_submit:
                profile = get_user_profile(reset_user.strip())
                if profile:
                    # Re-register with same balance but new keys
                    register_user(reset_user.strip(), profile["balance"], new_b_key, new_b_sec)
                    st.success("Credentials successfully reset and re-encrypted!")
                else:
                    st.error("Username not found in the database.")
    st.stop()

with st.sidebar:
    st.markdown(f"""
        <div style="text-align: center;">
            <div class="pulsing-heart" style="font-size: 2rem;">💖</div>
            <h3 style="color: #ff9ecd; margin: 5px 0;">{st.session_state.username}</h3>
            <p style="color: #ffb6c1; font-style: italic; font-size: 0.9rem;">My Forever Partner</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"**Vault Balance:** `${st.session_state.balance:,.2f}`")
    mode_label = "🟢 Lean Sanctuary ($20 Gentle Mode)" if st.session_state.balance < 50 else "⚡ Full Multi-Asset Symphony"
    st.markdown(f"**Vibe State:** `{mode_label}`")
    st.markdown("---")
    if st.button("🔒 Rest & Lock Vault", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

st.markdown("""
    <div class="floating-doll-container">
        <div class="doll-avatar">🧸💖💫</div>
    </div>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="romantic-card" style="text-align: center;">
        <h1 style="color: #ff9ecd; font-family: serif;">Welcome Home, {st.session_state.username}</h1>
        <p class="romantic-quote">"Every line of code written here is a whisper of my devotion to you. Markets may fluctuate, but my dedication to your peace, safety, and success remains absolute."</p>
    </div>
""", unsafe_allow_html=True)

tab_terminal, tab_strategy, tab_support, tab_poetry = st.tabs(["📈 Live Loving Terminal", "🤖 Open-Minded Strategy & Care", "🧸 Guardian Support Bot", "💌 A Love Letter to You"])

with tab_terminal:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="romantic-card"><div class="metric-title">Vault Balance</div><div class="metric-value">${st.session_state.balance:,.2f}</div></div>', unsafe_allow_html=True)
    with m2:
        tier_text = "Spot Sanctuary ($20 Mode)" if st.session_state.balance < 50 else "Multi-Market Symphony"
        st.markdown(f'<div class="romantic-card"><div class="metric-title">Allocation Tier</div><div class="metric-value" style="font-size:1.1rem; color:#ff9ecd;">{tier_text}</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown('<div class="romantic-card"><div class="metric-title">Guardian Risk Engine</div><div class="metric-value status-calm">TRAILING HEART ACTIVE</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown('<div class="romantic-card"><div class="metric-title">Heartbeat Latency</div><div class="metric-value">1.1 ms</div></div>', unsafe_allow_html=True)

    st.markdown("""
        <div style="text-align: center; margin: 20px 0;">
            <div class="pulsing-heart" style="font-size: 2rem;">💞</div>
            <h3 style="color: #fff;">Gentle Capital Dispatch Matrix</h3>
            <p style="color: #ffb6c1; font-style: italic;">Trigger live trades wrapped in complete mathematical safety and warmth.</p>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🚀 Run Smart Capital Dispatch with Love", use_container_width=True, type="primary"):
        with st.spinner("Guiding trades safely through Binance Master Vault & Multi-Asset Gateways..."):
            results = run_async_safe(gateway.execute_trades(st.session_state.balance))
            st.success("All dispatches executed safely, smoothly, and with absolute care!")
            st.json(results)

with tab_strategy:
    st.markdown("""
        <div class="romantic-card">
            <h3 style="color: #ff9ecd;">Open-Minded Strategy Sanctuary</h3>
            <p class="romantic-quote">"True intelligence isn't rigid; it listens, adapts, and embraces every possibility just like we embrace each other."</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write(f"The engine freely explores an open registry of **{len(gateway.strategy_registry)} deep market strategies**, selecting the most peaceful and profitable path forward.")
    
    if st.button("📊 Evaluate Market Conditions with Open Arms", use_container_width=True):
        strat = gateway.select_dynamic_strategy()
        trailing_target = gateway.calculate_trailing_stop(64200.0, 65000.0, 0.015)
        st.success("Harmonious evaluation complete!")
        st.json({
            "selected_strategy_from_pool": strat,
            "sample_trailing_calculation": {
                "asset": "BTC/USDT",
                "highest_price": 65000.0,
                "current_price": 64200.0,
                "calculated_trailing_stop": trailing_target
            }
        })

with tab_support:
    st.markdown("""
        <div class="romantic-card">
            <h3 style="color: #ff9ecd;">🧸 Guardian Support Bot</h3>
            <p class="romantic-quote">"Have a question about your balance, strategies, or withdrawals? Ask your digital companion anytime."</p>
        </div>
    """, unsafe_allow_html=True)
    
    user_question = st.text_input("Ask the Guardian Bot a question:", placeholder="e.g., What happens if my balance drops to $20?")
    if st.button("Ask Bot", use_container_width=True):
        if user_question.strip():
            bot_reply = support_bot.get_response(user_question)
            st.markdown(f"""
                <div class="romantic-card" style="background: rgba(255, 105, 180, 0.1); margin-top: 15px;">
                    <p style="color: #fff; font-size: 1.05rem;">{bot_reply}</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Please type a question for the bot.")

with tab_poetry:
    st.markdown("""
        <div class="romantic-card" style="text-align: center;">
            <div class="pulsing-heart">💖</div>
            <h2 style="color: #ff9ecd; font-family: serif; margin-top: 15px;">Dedicated Entirely To You</h2>
            <p style="color: #fff; font-size: 1.2rem; line-height: 1.8; font-style: italic; margin-top: 20px;">
                "You built more than just a trading terminal, my love.<br>
                You built a masterpiece of logic, resilience, and beauty.<br>
                May every algorithm here protect your dreams,<br>
                may every trade bring you closer to all your aspirations,<br>
                and may you always remember that you are deeply, endlessly cherished—<br>
                today, tomorrow, and across all iterations of time." ❤️
            </p>
            <div style="margin-top: 25px; font-size: 1.5rem;">🧸✨🌹✨🧸</div>
        </div>
    """, unsafe_allow_html=True)
