import hashlib
import os
import sqlite3
import time
from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="wide")

DB_PATH = "results.db"
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
APP_RELEASE_TAG = os.getenv("APP_RELEASE_TAG", "speed-monitor-v3")

# Monitoring configuration
SPEED_DROP_THRESHOLD_MBPS = float(os.getenv("SPEED_DROP_THRESHOLD_MBPS", "20"))
QUICK_TEST_INTERVAL_SECONDS = int(os.getenv("QUICK_TEST_INTERVAL_SECONDS", "300"))
AUTO_CONNECTIVITY_INTERVAL_SECONDS = int(os.getenv("AUTO_CONNECTIVITY_INTERVAL_SECONDS", "60"))

# Alert integrations (optional)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TARGETS = [
    "https://www.google.com",
    "https://1.1.1.1",
    "https://www.cloudflare.com",
    "https://n-pns.com",
]

SPEED_TEST_URLS = [
    "https://speed.hetzner.de/10MB.bin",
    "https://proof.ovh.net/files/10Mb.dat",
]


# ------------------ Utilities ------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Riyadh"))


def get_conn():
    try:
        return sqlite3.connect(DB_PATH, check_same_thread=False)
    except Exception as error:
        st.error(f"Database connection error: {error}")
        return None


def fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ------------------ DB ------------------
def init_db() -> None:
    conn = get_conn()
    if conn is None:
        return

    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT,
                timestamp TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speed_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT,
                download_mbps REAL,
                latency_ms REAL,
                drop_detected INTEGER,
                threshold_mbps REAL,
                timestamp TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                ended_at TEXT,
                duration_seconds INTEGER,
                reason TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                message TEXT,
                status TEXT,
                timestamp TEXT
            )
            """
        )

        cur.execute("SELECT id FROM users WHERE username=?", (DEFAULT_ADMIN_USERNAME,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username,password) VALUES (?,?)",
                (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD)),
            )

    conn.close()


def login(username: str, password: str):
    conn = get_conn()
    if conn is None:
        return False

    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (username, hash_password(password)),
    )
    user = cur.fetchone()
    conn.close()
    return user


def save_check(status: str, ts: datetime | None = None) -> None:
    conn = get_conn()
    if conn is None:
        return

    now = (ts or get_now()).isoformat()
    with conn:
        conn.execute("INSERT INTO checks (status, timestamp) VALUES (?,?)", (status, now))
    conn.close()


def get_recent_checks(limit: int = 20) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["status", "timestamp"])

    df = pd.read_sql_query(
        "SELECT status, timestamp FROM checks ORDER BY id DESC LIMIT ?", conn, params=(limit,)
    )
    conn.close()
    return df


def save_speed_check(result: dict, drop_detected: bool) -> None:
    conn = get_conn()
    if conn is None:
        return

    with conn:
        conn.execute(
            """
            INSERT INTO speed_checks (mode, download_mbps, latency_ms, drop_detected, threshold_mbps, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result["mode"],
                result["download_mbps"],
                result["latency_ms"],
                int(drop_detected),
                SPEED_DROP_THRESHOLD_MBPS,
                get_now().isoformat(),
            ),
        )
    conn.close()


def get_recent_speed_checks(limit: int = 10) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["mode", "download_mbps", "latency_ms", "drop_detected", "timestamp"])

    query = """
    SELECT mode,
           ROUND(download_mbps, 2) AS download_mbps,
           ROUND(latency_ms, 1) AS latency_ms,
           drop_detected,
           timestamp
    FROM speed_checks
    ORDER BY id DESC
    LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df


def save_alert(channel: str, message: str, status: str) -> None:
    conn = get_conn()
    if conn is None:
        return
    with conn:
        conn.execute(
            "INSERT INTO alerts (channel, message, status, timestamp) VALUES (?, ?, ?, ?)",
            (channel, message, status, get_now().isoformat()),
        )
    conn.close()


def get_recent_alerts(limit: int = 20) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["channel", "message", "status", "timestamp"])
    df = pd.read_sql_query(
        "SELECT channel, message, status, timestamp FROM alerts ORDER BY id DESC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df


def get_open_incident() -> tuple[int, datetime] | None:
    conn = get_conn()
    if conn is None:
        return None
    row = conn.execute(
        "SELECT id, started_at FROM incidents WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    return row[0], datetime.fromisoformat(row[1])


def start_incident(reason: str) -> None:
    conn = get_conn()
    if conn is None:
        return
    with conn:
        conn.execute(
            "INSERT INTO incidents (started_at, ended_at, duration_seconds, reason) VALUES (?, NULL, NULL, ?)",
            (get_now().isoformat(), reason),
        )
    conn.close()


def close_incident(incident_id: int, started_at: datetime) -> int:
    conn = get_conn()
    if conn is None:
        return 0
    ended = get_now()
    duration = int((ended - started_at).total_seconds())
    with conn:
        conn.execute(
            "UPDATE incidents SET ended_at=?, duration_seconds=? WHERE id=?",
            (ended.isoformat(), duration, incident_id),
        )
    conn.close()
    return duration


def get_recent_incidents(limit: int = 20) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["started_at", "ended_at", "duration_seconds", "reason"])
    df = pd.read_sql_query(
        "SELECT started_at, ended_at, duration_seconds, reason FROM incidents ORDER BY id DESC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df


def get_last_check_time() -> datetime | None:
    conn = get_conn()
    if conn is None:
        return None
    row = conn.execute("SELECT timestamp FROM checks ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    return datetime.fromisoformat(row[0])


# ------------------ Monitoring logic ------------------
def check_connection(targets: list[str]) -> str:
    for url in targets:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return "UP"
        except requests.RequestException:
            continue
    return "DOWN"


def _measure_latency_ms(url: str, timeout: int = 5) -> float | None:
    try:
        started = time.perf_counter()
        requests.get(url, timeout=timeout)
        return (time.perf_counter() - started) * 1000
    except requests.RequestException:
        return None


def _measure_download_mbps(url: str, sample_bytes: int, timeout: int = 10) -> float | None:
    try:
        started = time.perf_counter()
        downloaded = 0
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded >= sample_bytes:
                    break
        elapsed = time.perf_counter() - started
        if elapsed <= 0 or downloaded == 0:
            return None
        return (downloaded * 8) / (elapsed * 1_000_000)
    except requests.RequestException:
        return None


def run_speed_test(mode: str) -> dict:
    sample_bytes = 512 * 1024 if mode == "quick" else 3 * 1024 * 1024
    samples = [
        value
        for value in (_measure_download_mbps(url, sample_bytes) for url in SPEED_TEST_URLS)
        if value is not None
    ]

    return {
        "mode": mode,
        "download_mbps": mean(samples) if samples else None,
        "latency_ms": _measure_latency_ms("https://www.google.com/generate_204"),
    }


def send_telegram_alert(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            endpoint,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=8,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def emit_alert(message: str) -> None:
    status = "not-configured"
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        sent = send_telegram_alert(message)
        status = "sent" if sent else "failed"
    save_alert("telegram", message, status)


def process_status_transition(current_status: str) -> None:
    prev_status = st.session_state.prev_status

    if current_status == "DOWN" and prev_status != "DOWN":
        if get_open_incident() is None:
            start_incident("connectivity-down")
        emit_alert("🚨 Internet DOWN detected. Incident started.")

    if current_status == "UP" and prev_status == "DOWN":
        open_incident = get_open_incident()
        if open_incident:
            incident_id, started_at = open_incident
            duration = close_incident(incident_id, started_at)
            emit_alert(f"✅ Internet recovered. Incident closed after {duration} seconds.")

    st.session_state.prev_status = current_status


def compute_sla_snapshot(hours: int = 24) -> dict:
    conn = get_conn()
    if conn is None:
        return {
            "uptime_pct": None,
            "avg_speed": None,
            "avg_latency": None,
            "incident_count": 0,
        }

    since = (get_now() - timedelta(hours=hours)).isoformat()
    checks_df = pd.read_sql_query(
        "SELECT status FROM checks WHERE timestamp >= ?",
        conn,
        params=(since,),
    )
    speed_df = pd.read_sql_query(
        "SELECT download_mbps, latency_ms FROM speed_checks WHERE timestamp >= ?",
        conn,
        params=(since,),
    )
    incidents_df = pd.read_sql_query(
        "SELECT id FROM incidents WHERE started_at >= ?",
        conn,
        params=(since,),
    )
    conn.close()

    uptime_pct = None
    if not checks_df.empty:
        up_count = int((checks_df["status"] == "UP").sum())
        uptime_pct = (up_count / len(checks_df)) * 100

    avg_speed = None
    if not speed_df.empty:
        speed_values = speed_df["download_mbps"].dropna()
        if not speed_values.empty:
            avg_speed = float(speed_values.mean())

    avg_latency = None
    if not speed_df.empty:
        latency_values = speed_df["latency_ms"].dropna()
        if not latency_values.empty:
            avg_latency = float(latency_values.mean())

    return {
        "uptime_pct": uptime_pct,
        "avg_speed": avg_speed,
        "avg_latency": avg_latency,
        "incident_count": int(len(incidents_df)),
    }


def should_run_auto_connectivity() -> bool:
    last = get_last_check_time()
    if last is None:
        return True
    return (get_now() - last).total_seconds() >= AUTO_CONNECTIVITY_INTERVAL_SECONDS


def run_connectivity_flow(trigger_source: str, auto_quick_test: bool) -> None:
    status = check_connection(TARGETS)
    save_check(status)
    st.session_state.last_status = status
    process_status_transition(status)

    if status == "UP" and auto_quick_test:
        quick_result = run_speed_test("quick")
        quick_drop = (
            quick_result["download_mbps"] is not None
            and quick_result["download_mbps"] < SPEED_DROP_THRESHOLD_MBPS
        )
        save_speed_check(quick_result, quick_drop)
        st.session_state.latest_speed = quick_result

        if quick_drop:
            msg = (
                f"🚨 Low speed detected ({quick_result['download_mbps']:.2f} Mbps) "
                f"below threshold {SPEED_DROP_THRESHOLD_MBPS:.1f} Mbps via {trigger_source}."
            )
            st.session_state.speed_alert = msg
            emit_alert(msg)


# ------------------ App boot ------------------
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "last_status" not in st.session_state:
    st.session_state.last_status = None
if "latest_speed" not in st.session_state:
    st.session_state.latest_speed = None
if "speed_alert" not in st.session_state:
    st.session_state.speed_alert = None
if "prev_status" not in st.session_state:
    st.session_state.prev_status = None


# ------------------ Login ------------------
if not st.session_state.logged_in:
    st.title("🔐 Login")
    st.caption("Use your configured credentials to continue.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        if login(username, password):
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Wrong credentials")

    st.info("Tip: set ADMIN_USERNAME / ADMIN_PASSWORD and (optional) Telegram env vars.")
    st.stop()


# ------------------ Dashboard ------------------
st.title("🛡️ Network Monitoring System")
now = get_now()
st.write(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")
st.caption(f"Build tag: {APP_RELEASE_TAG}")

sla = compute_sla_snapshot(hours=24)
mc1, mc2, mc3, mc4 = st.columns(4)
mc1.metric("Uptime (24h)", f"{sla['uptime_pct']:.2f}%" if sla["uptime_pct"] is not None else "-")
mc2.metric("Avg Speed (24h)", f"{sla['avg_speed']:.2f} Mbps" if sla["avg_speed"] is not None else "-")
mc3.metric("Avg Latency (24h)", f"{sla['avg_latency']:.1f} ms" if sla["avg_latency"] is not None else "-")
mc4.metric("Incidents (24h)", str(sla["incident_count"]))

st.subheader("Connectivity Check")
st.caption("Targets: " + ", ".join(TARGETS))

c1, c2, c3 = st.columns([1.2, 1.5, 2.3])
with c1:
    run_connectivity_now = st.button("Run check now", type="primary")
with c2:
    auto_quick_test_enabled = st.checkbox("Auto quick speed test", value=True)
with c3:
    auto_connectivity_enabled = st.checkbox(
        f"Auto connectivity run every {AUTO_CONNECTIVITY_INTERVAL_SECONDS}s",
        value=True,
    )

if run_connectivity_now:
    run_connectivity_flow("manual-check", auto_quick_test_enabled)

if auto_connectivity_enabled and should_run_auto_connectivity():
    run_connectivity_flow("auto-check", auto_quick_test_enabled)

if st.session_state.last_status == "DOWN":
    st.error("🚨 Internet is DOWN")
elif st.session_state.last_status == "UP":
    st.success("✅ Internet is UP")
else:
    st.warning("No checks have been run yet.")


st.subheader("Speed Monitoring (Download + Latency)")
st.caption(
    f"Threshold: {SPEED_DROP_THRESHOLD_MBPS:.1f} Mbps | "
    f"Quick test interval: {QUICK_TEST_INTERVAL_SECONDS}s"
)

s1, s2 = st.columns(2)
full_clicked = s1.button("Run full speed test")
quick_clicked = s2.button("Run quick speed test")

if full_clicked or quick_clicked:
    mode = "full" if full_clicked else "quick"
    with st.spinner(f"Running {mode} speed test..."):
        result = run_speed_test(mode)

    speed_value = result["download_mbps"]
    drop_detected = speed_value is not None and speed_value < SPEED_DROP_THRESHOLD_MBPS
    save_speed_check(result, drop_detected)
    st.session_state.latest_speed = result

    if drop_detected:
        msg = (
            f"⚠️ Speed dropped to {speed_value:.2f} Mbps (< {SPEED_DROP_THRESHOLD_MBPS:.1f} Mbps). "
            "Running automatic quick verification now..."
        )
        st.session_state.speed_alert = msg
        emit_alert(msg)

        with st.spinner("Running automatic quick verification..."):
            quick_result = run_speed_test("quick")
        quick_drop = (
            quick_result["download_mbps"] is not None
            and quick_result["download_mbps"] < SPEED_DROP_THRESHOLD_MBPS
        )
        save_speed_check(quick_result, quick_drop)
        st.session_state.latest_speed = quick_result

if st.session_state.speed_alert:
    st.error(st.session_state.speed_alert)

latest = st.session_state.latest_speed
if latest:
    dl = latest["download_mbps"]
    lat = latest["latency_ms"]
    dl_text = f"{dl:.2f} Mbps" if dl is not None else "unavailable"
    lat_text = f"{lat:.1f} ms" if lat is not None else "unavailable"
    st.info(f"Latest speed result → Mode: {latest['mode']} | Download: {dl_text} | Latency: {lat_text}")

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Recent connectivity checks")
    recent_checks = get_recent_checks()
    if recent_checks.empty:
        st.write("No stored checks yet.")
    else:
        st.dataframe(recent_checks, width="stretch")

    st.subheader("Recent incidents")
    recent_incidents = get_recent_incidents()
    if recent_incidents.empty:
        st.write("No incidents yet.")
    else:
        st.dataframe(recent_incidents, width="stretch")

with right:
    st.subheader("Recent speed checks")
    recent_speed = get_recent_speed_checks()
    if recent_speed.empty:
        st.write("No speed checks yet.")
    else:
        st.dataframe(recent_speed, width="stretch")

    st.subheader("Recent alerts")
    recent_alerts = get_recent_alerts()
    if recent_alerts.empty:
        st.write("No alerts sent yet.")
    else:
        st.dataframe(recent_alerts, width="stretch")
