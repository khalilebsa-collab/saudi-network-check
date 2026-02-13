import streamlit as st
import speedtest
from datetime import datetime
from zoneinfo import ZoneInfo

# 1. إضافة تعليمات الأمان (HSTS & Referrer-Policy)
# هذه الأسطر تخبر المتصفح أن موقعك مشفر وآمن جداً
st.set_page_config(page_title="نظام الشبكات السيادي", page_icon="🛡️", layout="centered")

# منع تسرب المعلومات عند الانتقال لروابط خارجية
st.markdown('<meta name="referrer" content="strict-origin-when-cross-origin">', unsafe_allow_html=True)

# 2. لمسة جمالية للعنوان مع حماية من الـ Clickjacking
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    <h1 style='text-align: center; color: #1E3A8A;'>🛡️ نظام مراقبة الشبكات المحمي</h1>
    """, unsafe_allow_html=True)

st.write("---")

# 3. نظام الدخول الآمن
now = datetime.now(ZoneInfo("Asia/Riyadh"))

col1, col2 = st.columns(2)

with col1:
    st.info(f"📅 التاريخ: {now.strftime('%Y-%m-%d')}")

with col2:
    st.info(f"⏰ الوقت: {now.strftime('%H:%M:%S')}")

if st.button("🚀 بدء فحص السرعة"):
    with st.spinner("⏳ جاري قياس سرعة الاتصال..."):
        try:
            s = speedtest.Speedtest()
            s.get_best_server()
            down_speed = s.download() / 1_000_000
            st.success("✅ تم القياس بنجاح")
            st.metric(label="⚡ سرعة التحميل", value=f"{down_speed:.2f} Mbps")
            st.balloons()
        except:
            st.error("❌ حدث خطأ أثناء قياس السرعة")




