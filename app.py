-import streamlit as st
-import requests
-from datetime import datetime
-from zoneinfo import ZoneInfo
-import sqlite3
-import pandas as pd
-import hashlib
-import time
-
-st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="centered")
-
-DB_PATH = "results.db"
-
-# ------------------ أدوات مساعدة ------------------
-
-def hash_password(password):
-    return hashlib.sha256(password.encode()).hexdigest()
-
-def get_now():
-    return datetime.now(ZoneInfo("Asia/Riyadh"))
-
-# ------------------ قاعدة البيانات ------------------
-
-def get_conn():
-    try:
-        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
-        return conn
-    except Exception as e:
-        st.error(f"Database connection error: {e}")
-        return None
-
-def init_db():
-    conn = get_conn()
-    if conn is None:
-        return
-    cur = conn.cursor()
-
-    cur.execute("""
-        CREATE TABLE IF NOT EXISTS users (
-            id INTEGER PRIMARY KEY AUTOINCREMENT,
-            username TEXT UNIQUE,
-            password TEXT
-        )
-    """)
-
-    cur.execute("""
-        CREATE TABLE IF NOT EXISTS checks (
-            id INTEGER PRIMARY KEY AUTOINCREMENT,
-            status TEXT,
-            timestamp TEXT
-        )
-    """)
-
-    conn.commit()
-
-    # إنشاء أدمن أول مرة
-    cur.execute("SELECT id FROM users WHERE username=?", ("admin",))
-    if not cur.fetchone():
-        cur.execute("INSERT INTO users (username,password) VALUES (?,?)",
-                    ("admin", hash_password("Khalil@99")))
-        conn.commit()
-
-    conn.close()
-
-init_db()
-
-# ------------------ تسجيل الدخول ------------------
-
-if "logged_in" not in st.session_state:
-    st.session_state.logged_in = False
-
-def login(username, password):
-    conn = get_conn()
-    if conn is None:
-        return False
-    cur = conn.cursor()
-    cur.execute("SELECT id FROM users WHERE username=? AND password=?",
-                (username, hash_password(password)))
-    user = cur.fetchone()
-    conn.close()
-    return user
-
-if not st.session_state.logged_in:
-    st.title("🔐 Login")
-
-    username = st.text_input("Username")
-    password = st.text_input("Password", type="password")
-
-    if st.button("Login"):
-        if login(username, password):
-            st.session_state.logged_in = True
-        else:
-            st.error("Wrong credentials")
-
-    st.stop()
-
-# ------------------ واجهة النظام ------------------
-
-st.title("🛡️ Network Monitoring System")
-now = get_now()
-st.write(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")
-st.write("Site is working!")  # تحقق من عمل الصفحة بشكل صحيح
-
-# ------------------ فحص الاتصال ------------------
-
-targets = [
-    "https://www.google.com",
-    "https://1.1.1.1",
-    "https://www.cloudflare.com",
-    "https://n-pns.com"
-]
-
-def check_connection():
-    for url in targets:
-        try:
-            r = requests.get(url, timeout=3)
-            if r.status_code == 200:
-                return "UP"
-        except:
-            continue
-    return "DOWN"
-
-# فحص تلقائي كل دقيقة باستخدام time.sleep()
-while True:
-    status = check_connection()
-
-    conn = get_conn()
-    if conn is not None:
-        cur = conn.cursor()
-        cur.execute("INSERT INTO checks (status, timestamp) VALUES (?,?)",
-                    (status, now.isoformat()))
-        conn.commit()
-        conn.close()
-
-    if status == "DOWN":
-        st.error("🚨 Internet is DOWN")
-    else:
-        st.success("✅ Internet is UP")
-
-    # تأخير الفحص لمدة دقيقة
-    time.sleep(60)
-    
-    break  # لإنهاء الحلقة بعد الفحص الأول
+import hashlib
+import os
+import sqlite3
+from datetime import datetime
+from zoneinfo import ZoneInfo
+
+import pandas as pd
+import requests
+import streamlit as st
+
+st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="centered")
+
+DB_PATH = "results.db"
+DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
+DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
+APP_RELEASE_TAG = os.getenv("APP_RELEASE_TAG", "release-speed-check-1")
+
+
+# ------------------ أدوات مساعدة ------------------
+def hash_password(password: str) -> str:
+    return hashlib.sha256(password.encode()).hexdigest()
+
+
+def get_now() -> datetime:
+    return datetime.now(ZoneInfo("Asia/Riyadh"))
+
+
+# ------------------ قاعدة البيانات ------------------
+def get_conn():
+    try:
+        return sqlite3.connect(DB_PATH, check_same_thread=False)
+    except Exception as e:
+        st.error(f"Database connection error: {e}")
+        return None
+
+
+def init_db() -> None:
+    conn = get_conn()
+    if conn is None:
+        return
+
+    with conn:
+        cur = conn.cursor()
+        cur.execute(
+            """
+            CREATE TABLE IF NOT EXISTS users (
+                id INTEGER PRIMARY KEY AUTOINCREMENT,
+                username TEXT UNIQUE,
+                password TEXT
+            )
+            """
+        )
+
+        cur.execute(
+            """
+            CREATE TABLE IF NOT EXISTS checks (
+                id INTEGER PRIMARY KEY AUTOINCREMENT,
+                status TEXT,
+                timestamp TEXT
+            )
+            """
+        )
+
+        cur.execute("SELECT id FROM users WHERE username=?", (DEFAULT_ADMIN_USERNAME,))
+        if not cur.fetchone():
+            cur.execute(
+                "INSERT INTO users (username,password) VALUES (?,?)",
+                (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD)),
+            )
+
+    conn.close()
+
+
+def login(username: str, password: str):
+    conn = get_conn()
+    if conn is None:
+        return False
+
+    cur = conn.cursor()
+    cur.execute(
+        "SELECT id FROM users WHERE username=? AND password=?",
+        (username, hash_password(password)),
+    )
+    user = cur.fetchone()
+    conn.close()
+    return user
+
+
+def check_connection(targets: list[str]) -> str:
+    for url in targets:
+        try:
+            response = requests.get(url, timeout=3)
+            if response.status_code == 200:
+                return "UP"
+        except requests.RequestException:
+            continue
+    return "DOWN"
+
+
+def save_check(status: str) -> None:
+    conn = get_conn()
+    if conn is None:
+        return
+
+    timestamp = get_now().isoformat()
+    with conn:
+        cur = conn.cursor()
+        cur.execute(
+            "INSERT INTO checks (status, timestamp) VALUES (?,?)",
+            (status, timestamp),
+        )
+    conn.close()
+
+
+def get_recent_checks(limit: int = 20) -> pd.DataFrame:
+    conn = get_conn()
+    if conn is None:
+        return pd.DataFrame(columns=["status", "timestamp"])
+
+    query = "SELECT status, timestamp FROM checks ORDER BY id DESC LIMIT ?"
+    df = pd.read_sql_query(query, conn, params=(limit,))
+    conn.close()
+    return df
+
+
+init_db()
+
+if "logged_in" not in st.session_state:
+    st.session_state.logged_in = False
+
+if "last_status" not in st.session_state:
+    st.session_state.last_status = None
+
+
+# ------------------ تسجيل الدخول ------------------
+if not st.session_state.logged_in:
+    st.title("🔐 Login")
+    st.caption("Use your configured credentials to continue.")
+
+    username = st.text_input("Username")
+    password = st.text_input("Password", type="password")
+
+    if st.button("Login", type="primary"):
+        if login(username, password):
+            st.session_state.logged_in = True
+            st.rerun()
+        else:
+            st.error("Wrong credentials")
+
+    st.info("Tip: You can set ADMIN_USERNAME and ADMIN_PASSWORD as environment variables.")
+    st.stop()
+
+
+# ------------------ واجهة النظام ------------------
+st.title("🛡️ Network Monitoring System")
+now = get_now()
+st.write(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")
+st.caption(f"Build tag: {APP_RELEASE_TAG}")
+
+st.subheader("Connectivity Check")
+targets = [
+    "https://www.google.com",
+    "https://1.1.1.1",
+    "https://www.cloudflare.com",
+    "https://n-pns.com",
+]
+
+st.caption("Targets: " + ", ".join(targets))
+
+if st.button("Run check now", type="primary"):
+    st.session_state.last_status = check_connection(targets)
+    save_check(st.session_state.last_status)
+
+if st.session_state.last_status == "DOWN":
+    st.error("🚨 Internet is DOWN")
+elif st.session_state.last_status == "UP":
+    st.success("✅ Internet is UP")
+else:
+    st.warning("No checks have been run yet in this session.")
+
+st.subheader("Recent checks")
+recent_checks = get_recent_checks()
+if recent_checks.empty:
+    st.write("No stored checks yet.")
+else:
+    st.dataframe(recent_checks, use_container_width=True)

