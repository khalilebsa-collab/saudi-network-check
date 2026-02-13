import streamlit as st
import speedtest
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import os

# إعداد الصفحة
st.set_page_config(
    page_title="نظام مراقبة الشبكات المحلي",
    page_icon="🛡️",
    layout="centered"
)

# عنوان الصفحة
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
<h1 style='text-align: center; color: #1E3A8A;'>🛡️ نظام مراقبة الشبكات المحلي</h1>
""", unsafe_allow_html=True)

st.write("---")

# ضبط التوقيت على الرياض
now = datetime.now(ZoneInfo("Asia/Riyadh"))

# عرض التاريخ والوقت
col1, col2 = st.columns(2)

with col1:
    st.info(f"📅 التاريخ: {now.strftime('%Y-%m-%d')}")

with col2:
    st.info(f"⏰ الوقت: {now.strftime('%H:%M:%S')}")

# زر الفحص
if st.button("🚀 بدء فحص السرعة"):

    with st.spinner("⏳ جاري قياس سرعة الاتصال..."):

        try:
            s = speedtest.Speedtest()
            s.get_best_server()
            down_speed = s.download() / 1_000_000

            # حفظ النتائج في CSV
            file_exists = os.path.isfile("results.csv")

            with open("results.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                if not file_exists:
                    writer.writerow(["date", "time", "speed_mbps"])

                writer.writerow([
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S"),
                    round(down_speed, 2)
                ])

            st.success("✅ تم القياس بنجاح")
            st.metric(
                label="⚡ سرعة التحميل",
                value=f"{down_speed:.2f} Mbps"
            )
            st.balloons()

   except Exception:
    st.error("❌ حدث خطأ أثناء قياس السرعة — قد يكون بسبب قيود السيرفر")

# --- لوحة المتابعة ---
st.markdown("---")
st.subheader("📊 لوحة المتابعة")

if os.path.isfile("results.csv"):
    import pandas as pd

    df = pd.read_csv("results.csv")

    st.dataframe(df, use_container_width=True)

    avg_speed = df["speed_mbps"].mean()
    max_speed = df["speed_mbps"].max()
    min_speed = df["speed_mbps"].min()

    col1, col2, col3 = st.columns(3)

    col1.metric("📈 متوسط السرعة", f"{avg_speed:.2f} Mbps")
    col2.metric("🚀 أعلى سرعة", f"{max_speed:.2f} Mbps")
    col3.metric("🐢 أقل سرعة", f"{min_speed:.2f} Mbps")

    st.line_chart(df["speed_mbps"])
else:
    st.info("لا توجد بيانات حتى الآن")

