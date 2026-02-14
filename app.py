import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import pandas as pd
import hashlib
import time

st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="centered")

DB_PATH = "results.db"

# ------------------ أدوات مساعدة ------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_now():
    return datetime.now(ZoneInfo("Asia/Riyadh"))

# ------------------ قاعدة البيانات ------------------

def get_conn():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

def init_db():
    conn = get_conn()
    if conn is None:
        return
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()

    # إنشاء أدمن أول مرة
    cur.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username,password) VALUES (?,?)",
                    ("admin", hash_password("admin123")))
        conn.commit()

    conn.close()

init_db()

# ------------------ تسجيل الدخول ------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login(username, password):
    conn = get_conn()
    if conn is None:
        return False
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=? AND password=?",
                (username, hash_password(password)))
    user = cur.fetchone()
    conn.close()
    return user

if not st.session_state.logged_in:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if login(username, password):
            st.session_state.logged_in = True
        else:
            st.error("Wrong credentials")

    st.stop()

# ------------------ واجهة النظام ------------------

st.title("🛡️ Network Monitoring System")
now = get_now(_
