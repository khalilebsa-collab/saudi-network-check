import streamlit as st
from ping3 import ping
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io

# ------------------ إعدادات ------------------
st.set_page_config(page_title="نظام مراقبة الشبكات", page_icon="🛡️", layout="centered")

DB_PATH = "results.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ------------------ تهيئة قاعدة البيانات ------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            company_id INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            status TEXT,
            response_time REAL,
            timestamp TEXT
        )
    """)

    conn.commit()

    cur.execute("SELECT id FROM companies WHERE name=?", ("Main Company",))
    if not cur.fetchone():
        cur.execute("INSERT INTO companies (name) VALUES (?)", ("Main Company",))
        company_id = cur.lastrowid
        cur.execute("INSERT INTO users (username,password,role,company_id) VALUES (?,?,?,?)",
                    ("admin", "admin123", "admin", company_id))
        conn.commit()

    conn.close()

init_db()

# ------------------ تسجيل الدخول ------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, company_id FROM users WHERE username=? AND password=?",
                (username, password))
    user = cur.fetchone()
    conn.close()
    return user

if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")

    if st.button("دخول"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.company_id = user[1]
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")

    st.stop()

# ------------------ واجهة النظام ------------------
st.title("🛡️ نظام مراقبة الشبكات")
now = datetime.now(ZoneInfo("Asia/Riyadh"))
st.write(f"📅 {now.strftime('%Y-%m-%d')} | ⏰ {now.strftime('%H:%M:%S')}")

# ------------------ زر فحص Ping ------------------
if st.button("📡 فحص الاتصال الآن"):
    response = ping("8.8.8.8", timeout=1)
    status = "UP" if response else "DOWN"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pings (company_id, status, response_time, timestamp)
        VALUES (?,?,?,?)
    """, (
        st.session_state.company_id,
        status,
        response if response else 0,
        now.isoformat()
    ))
    conn.commit()
    conn.close()

    if status == "DOWN":
        st.error("🚨 الإنترنت متوقف الآن")
    else:
        st.success("✅ الاتصال يعمل")

# ------------------ تحليل البيانات ------------------
conn = get_conn()
df = pd.read_sql_query("""
    SELECT status, timestamp
    FROM pings
    WHERE company_id=?
    ORDER BY timestamp ASC
""", conn, params=(st.session_state.company_id,))
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

    # ------------------ تقرير PDF ------------------
    if st.button("📄 تحميل التقرير الشهري PDF"):

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer)
        elements = []

        style = ParagraphStyle(name='NormalStyle', fontSize=14)

        elements.append(Paragraph("Monthly Network Report", style))
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
    st.info("لا توجد بيانات بعد — اضغط فحص الاتصال أولاً")
