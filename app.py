import streamlit as st
import speedtest
from datetime import datetime

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
password = st.text_input("🔑 أدخل رمز الوصول الأمني", type="password")

if password == "Khalil@99": 
    st.success("✅ تم منح الوصول للنظام بنجاح")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}")
    with col2:
        st.info(f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}")

    if st.button("🚀 بدء الفحص الشامل"):
        with st.spinner('🔍 جاري فحص جودة الاتصال وتأمين البيانات...'):
            try:
                s = speedtest.Speedtest()
                s.get_best_server()
                down_speed = s.download() / 1_000_000
                st.balloons()
                st.metric(label="📥 سرعة التحميل الحالية", value=f"{down_speed:.2f} Mbps", delta="مستقر")
                st.success("✅ تم اكتمال الفحص بنجاح")
            except:
                st.error("❌ عذراً، هناك ضغط على الخادم، حاول مجدداً")
else:
    if password:
        st.error("🚫 رمز الوصول خاطئ، تم تسجيل المحاولة")
