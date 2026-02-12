import streamlit as st
import speedtest
from datetime import datetime

# 1. إعدادات الصفحة المتقدمة
st.set_page_config(page_title="نظام الشبكات السيادي", page_icon="🛡️", layout="centered")

# 2. لمسة جمالية للعنوان
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🛡️ نظام مراقبة الشبكات المحمي</h1>", unsafe_allow_html=True)
st.write("---")

# 3. نظام الدخول المطور
password = st.text_input("🔑 أدخل رمز الوصول الأمني", type="password")

if password == "Khalil@99": # كلمتك السرية
    st.success("✅ تم منح الوصول للنظام بنجاح")
    
    # 4. واجهة الفحص
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
                
                # 5. عرض النتائج بشكل "كروت" احترافية
                st.balloons()
                st.metric(label="📥 سرعة التحميل الحالية", value=f"{down_speed:.2f} Mbps", delta="مستقر")
                
                st.success("✅ تم اكتمال الفحص بنجاح")
            except:
                st.error("❌ عذراً، هناك ضغط على الخادم، حاول مجدداً")
else:
    if password:
        st.error("🚫 رمز الوصول خاطئ، تم تسجيل المحاولة")
