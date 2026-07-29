import streamlit as st
import os
import sqlite3
import asyncio
import ccxt.async_support as ccxt
import nest_asyncio

# Weka jina rasmi la ukurasa wa mbele
st.set_page_config(page_title="Elite Quad Engine", page_icon="📈", layout="centered")

st.title("📈 Elite Quad Engine")
st.markdown("Karibu kwenye mfumo wa kisasa wa biashara ya kiotomatiki.")

# Utaratibu wa Usajili na Kuingia (Sign Up & Login) kwenye Sidebar
st.sidebar.header("👤 Akaunti ya Mtumiaji")

auth_mode = st.sidebar.radio("Chagua", ["Ingia (Login)", "Jisajili (Sign Up)"])

# Hakikisha database ya wateja ipo
def init_user_db():
    conn = sqlite3.connect("elite_users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_user_db()

if auth_mode == "Jisajili (Sign Up)":
    st.sidebar.subheader("Jisajili Hapa")
    reg_name = st.sidebar.text_input("Jina Lako Kamili")
    reg_phone = st.sidebar.text_input("Nambari ya Simu")
    
    if st.sidebar.button("Wasilisha Usajili"):
        if reg_name and reg_phone:
            try:
                conn = sqlite3.connect("elite_users.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (phone, name) VALUES (?, ?)", (reg_phone, reg_name))
                conn.commit()
                conn.close()
                st.sidebar.success("Usajili umekamilika! Sasa unaweza kuingia.")
            except sqlite3.IntegrityError:
                st.sidebar.error("Nambari hii ya simu imekwisha sajiliwa.")
        else:
            st.sidebar.warning("Tafadhali jaza jina na nambari ya simu.")

else:
    st.sidebar.subheader("Ingia Kwenye Akaunti")
    login_phone = st.sidebar.text_input("Weka Nambari Yako ya Simu ya Kuingia")
    
    if st.sidebar.button("Ingia"):
        if login_phone:
            conn = sqlite3.connect("elite_users.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE phone = ?", (login_phone,))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                st.session_state['logged_in_user'] = user[0]
                st.sidebar.success(f"Karibu tena, {user[0]}!")
            else:
                st.sidebar.error("Nambari ya simu haijatambuliwa. Jisajili kwanza.")
        else:
            st.sidebar.warning("Tafadhali weka nambari ya simu.")

# Sehemu ya Udhibiti wa Injini (Inafanya kazi tu ikiwa mtumiaji ameingia)
if 'logged_in_user' in st.session_state:
    st.markdown("---")
    st.subheader(f"🚀 Udhibiti wa Injini ya Biashara - Imekaribishwa: {st.session_state['logged_in_user']}")

    if st.button("Anzisha Master Trading Engine"):
        with st.spinner("Inaanzisha mfumo wa biashara..."):
            try:
                nest_asyncio.apply()
                st.success("Mfumo umezinduliwa kikamilifu!")
            except Exception as e:
                st.error(f"Hitilafu imetokea: {e}")
    else:
        st.info("Bonyeza kitufe hapo juu kuwasha injini ya biashara.")
else:
    st.warning("⚠️ Tafadhali jisajili au ingia kwa kutumia namba yako ya simu kwenye upande wa kushoto (Sidebar) ili kuona na kuendesha mfumo.")
