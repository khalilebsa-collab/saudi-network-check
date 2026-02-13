import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
import io

st.set_page_config(page_title="نظام مراقبة الشبكات", page_icon="🛡️", layout="centered")

DB_PATH = "results.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
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

    cur.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username,password) VALUES (?,?)",
                    ("admin", "admin123"))
        conn.commit()

    conn.close()

init_db()

# ------------------ تسجيل دخول ------------------

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
    st.title("🔐 تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")

    if st.button("دخول"):
        if login(username, password):
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")

    st.stop()

# ------------------ واجهة النظام ------------------

st.title("🛡️ نظام مراقبة الشبكات")

now = datetime.now(ZoneInfo("Asia/Riyadh"))
st.write(f"📅 {now.strftime('%Y-%m-%d')} | ⏰ {now.strftime('%H:%M:%S')}")

# ------------------ فحص الاتصال ------------------

def check_connection():
    urls = [
        "https://www.google.com",
        "https://1.1.1.1"
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return "UP"
        except:
            continue

    return "DOWN"

if st.button("📡 فحص الاتصال الآن"):
    status = check_connection()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO checks (status, timestamp) VALUES (?,?)",
                (status, now.isoformat()))
    conn.commit()
    conn.close()

    if status == "DOWN":
        st.error("🚨 الإنترنت متوقف الآن")
    else:
        st.success("✅ الاتصال يعمل")

# ------------------ تحليل البيانات ------------------

conn = get_conn()
df = pd.read_sql_query("SELECT status, timestamp FROM checks ORDER BY timestamp ASC", conn)
conn.close()

st.markdown("---")
st.subheader("📊 تحليل الاستقرار")

if not df.empty:

    total = len(df)
    up_count = len(df[df["status"]=="UP"])
    uptime = (up_count / total) * 100

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    downtime_minutes = 0
    outage_count = 0
    longest_outage = 0
    down_start = None

    for i, row in df.iterrows():
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
    col1.metric("Uptime %", f"{uptime:.2f}%")
    col2.metric("عدد مرات الانقطاع", outage_count)
    col3.metric("إجمالي دقائق الانقطاع", f"{downtime_minutes:.2f}")

    # -------- تقرير PDF --------

    if st.button("📄 تحميل التقرير PDF"):

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer)
        elements = []

        style = ParagraphStyle(name='NormalStyle', fontSize=14)

        elements.append(Paragraph("Network Monthly Report", style))
        elements.append(Spacer(1, 0.3 * inch))

        data = [
            ["Uptime %", f"{uptime:.2f}%"],
            ["Outage Count", outage_count],
            ["Total Downtime (min)", f"{downtime_minutes:.2f}"],
            ["Longest Outage (min)", f"{longest_outage:.2f}"],
        ]

        elements.append(Table(data))
        doc.build(elements)

        buffer.seek(0)
        st.download_button(
            label="تحميل التقرير",
            data=buffer,
            file_name="network_report.pdf",
            mime="application/pdf"
        )

else:
    st.info("لا توجد بيانات بعد — اضغط فحص الاتصال")
