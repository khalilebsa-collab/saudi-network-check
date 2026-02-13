import streamlit as st
import speedtest
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import pandas as pd

conn = sqlite3.connect("results.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS speed_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    time TEXT,
    speed_mbps REAL
)
""")
conn.commit()
# ------------------ إعدادات عامة ------------------
st.set_page_config(
    page_title="نظام مراقبة الشبكات المحلي",
    page_icon="🛡️",
    layout="centered"
)

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
<h1 style='text-align: center; color: #1E3A8A;'>🛡️ نظام مراقبة الشبكات المحلي</h1>
""", unsafe_allow_html=True)

st.write("---")

# ------------------ توقيت الرياض ------------------
now = datetime.now(ZoneInfo("Asia/Riyadh"))

col1, col2 = st.columns(2)
with col1:
    st.info(f"📅 التاريخ: {now.strftime('%Y-%m-%d')}")
with col2:
    st.info(f"⏰ الوقت: {now.strftime('%H:%M:%S')}")

# ------------------ قاعدة البيانات (SQLite) ------------------
DB_PATH = "results.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            speed_mbps REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def insert_measurement(date_str: str, time_str: str, speed_mbps: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO measurements (date, time, speed_mbps, created_at)
        VALUES (?, ?, ?, ?)
    """, (date_str, time_str, speed_mbps, datetime.now(ZoneInfo("Asia/Riyadh")).isoformat()))
    conn.commit()
    conn.close()

def load_measurements() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, date, time, speed_mbps
        FROM measurements
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df

init_db()

# ------------------ زر الفحص ------------------
if st.button("🚀 بدء فحص السرعة"):
    with st.spinner("⏳ جاري قياس سرعة الاتصال..."):
        try:
            s = speedtest.Speedtest()
            s.get_best_server()
            down_speed = s.download() / 1_000_000  # Mbps

            insert_measurement(
                date_str=now.strftime("%Y-%m-%d"),
                time_str=now.strftime("%H:%M:%S"),
                speed_mbps=round(down_speed, 2)
            )

            st.success("✅ تم القياس بنجاح")
            st.metric("⚡ سرعة التحميل", f"{down_speed:.2f} Mbps")
            st.balloons()

        except Exception:
            st.error("❌ حدث خطأ أثناء قياس السرعة — قد يكون بسبب قيود السيرفر")

# ------------------ لوحة المتابعة ------------------
st.markdown("---")
st.subheader("📊 لوحة المتابعة")

df = load_measurements()

if df.empty:
    st.info("لا توجد بيانات حتى الآن")
else:
    st.dataframe(df, use_container_width=True)

    avg_speed = df["speed_mbps"].mean()
    max_speed = df["speed_mbps"].max()
    min_speed = df["speed_mbps"].min()

    m1, m2, m3 = st.columns(3)
    m1.metric("📈 متوسط السرعة", f"{avg_speed:.2f} Mbps")
    m2.metric("🚀 أعلى سرعة", f"{max_speed:.2f} Mbps")
    m3.metric("🐢 أقل سرعة", f"{min_speed:.2f} Mbps")

    # الرسم: نعرض آخر 100 قياس (عشان ما يثقل)
    df_plot = df.head(100).iloc[::-1]  # نعكس عشان يصير القديم يسار والجديد يمين
    st.line_chart(df_plot["speed_mbps"])

