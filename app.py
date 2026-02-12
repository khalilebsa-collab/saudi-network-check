import streamlit as st
import speedtest

st.set_page_config(page_title="نظام الشبكات السيادي", page_icon="🛡️")
st.title("🛡️ نظام مراقبة الشبكات المحمي")

password = st.text_input("أدخل كلمة المرور", type="password")

if password == "Khalil@99": 
    st.success("✅ تم التحقق")
    if st.button("🚀 ابدأ القياس الحقيقي"):
        with st.spinner('جاري الفحص...'):
            try:
                st_test = speedtest.Speedtest()
                st_test.get_best_server()
                down = st_test.download() / 1_000_000
                st.metric("سرعة التحميل", f"{down:.2f} Mbps")
                st.balloons()
            except:
                st.error("❌ الخادم مشغول، كرر المحاولة")
