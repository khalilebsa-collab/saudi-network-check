import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import pandas as pd

st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="centered")

DB_PATH = "results.db"

# ------------------ قاعدة البيانات ------------------

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
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
                    ("admin", "admin123"))
        conn.commit()

    conn.close()

init_db()

# ------------------ تسجيل الدخول ------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=? AND password=?",
                (username, password))
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
            st.rerun()
        else:
            st.error("Wrong credentials")

    st.stop()

# ------------------ واجهة النظام ------------------

st.title("🛡️ Network Monitoring System")

now = datetime.now(ZoneInfo("Asia/Riyadh"))
st.write(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")

# ------------------ فحص الاتصال ------------------

def check_connection():
    try:
        r = requests.get("https://www.google.com", timeout=3)
        if r.status_code == 200:
            return "UP"
    except:
        pass
    return "DOWN"

if st.button("📡 Check Connection Now"):
    status = check_connection()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO checks (status, timestamp) VALUES (?,?)",
                (status, now.isoformat()))
    conn.commit()
    conn.close()

    if status == "DOWN":
        st.error("🚨 Internet is DOWN")
    else:
        st.success("✅ Internet is UP")

# ------------------ التحليل ------------------

conn = get_conn()
df = pd.read_sql_query("SELECT status, timestamp FROM checks ORDER BY timestamp ASC", conn)
conn.close()

st.markdown("---")
st.subheader("📊 Stability Analysis")

if not df.empty:
    total = len(df)
    up_count = len(df[df["status"] == "UP"])
    uptime = (up_count / total) * 100

    st.metric("Uptime %", f"{uptime:.2f}%")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    downtime_minutes = 0
    outage_count = 0
    longest_outage = 0
    down_start = None

    for _, row in df.iterrows():
        if row["status"] == "DOWN":
            if down_start is None:
                down_start = row["timestamp"]
        else:
            if down_start is not None:
                duration = (row["timestamp"] - down_start).total_seconds() / 60
                downtime_minutes += duration
                longest_outage = max(longest_outage, duration)
                outage_count += 1
                down_start = None

    col1, col2, col3 = st.columns(3)
    col1.metric("Outage Count", outage_count)
    col2.metric("Total Downtime (min)", f"{downtime_minutes:.2f}")
    col3.metric("Longest Outage (min)", f"{longest_outage:.2f}")

else:
    st.info("No data yet. Click check connection.")
