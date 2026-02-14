import hashlib
import os
import sqlite3
import time
from datetime import datetime
from statistics import mean
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Network Monitor", page_icon="🛡️", layout="centered")

DB_PATH = "results.db"
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
APP_RELEASE_TAG = os.getenv("APP_RELEASE_TAG", "speed-monitor-v3")
SPEED_DROP_THRESHOLD_MBPS = float(os.getenv("SPEED_DROP_THRESHOLD_MBPS", "20"))
QUICK_TEST_INTERVAL_SECONDS = int(os.getenv("QUICK_TEST_INTERVAL_SECONDS", "300"))
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


# ------------------ أدوات مساعدة ------------------
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


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def send_telegram_alert(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=8,
        )
        return True
    except requests.RequestException:
        return False


# ------------------ قاعدة البيانات ------------------
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
                duration_seconds REAL,
                start_reason TEXT,
                end_reason TEXT
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


def check_connection(targets: list[str]) -> str:
    for url in targets:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return "UP"
        except requests.RequestException:
            continue
    return "DOWN"


def get_last_status() -> str | None:
    conn = get_conn()
    if conn is None:
        return None
    row = conn.execute("SELECT status FROM checks ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else None


def save_check(status: str) -> None:
    conn = get_conn()
    if conn is None:
        return

    with conn:
        conn.execute(
            "INSERT INTO checks (status, timestamp) VALUES (?,?)",
            (status, get_now().isoformat()),
        )
    conn.close()


def get_recent_checks(limit: int = 20) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["status", "timestamp"])

    query = "SELECT status, timestamp FROM checks ORDER BY id DESC LIMIT ?"
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df


def track_incident_transition(new_status: str) -> tuple[bool, bool]:
    conn = get_conn()
    if conn is None:
        return False, False

    down_started = False
    down_recovered = False
    with conn:
        last_status_row = conn.execute("SELECT status FROM checks ORDER BY id DESC LIMIT 1").fetchone()
        last_status = last_status_row[0] if last_status_row else None

        open_incident = conn.execute(
            "SELECT id, started_at FROM incidents WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if new_status == "DOWN" and (last_status is None or last_status == "UP") and open_incident is None:
            conn.execute(
                "INSERT INTO incidents (started_at, start_reason) VALUES (?, ?)",
                (get_now().isoformat(), "Connectivity check failed"),
            )
            down_started = True

        if new_status == "UP" and open_incident is not None:
            incident_id, started_at = open_incident
            started = datetime.fromisoformat(started_at)
            ended = get_now()
            duration = (ended - started).total_seconds()
            conn.execute(
                """
                UPDATE incidents
                SET ended_at=?, duration_seconds=?, end_reason=?
                WHERE id=?
                """,
                (ended.isoformat(), duration, "Connectivity restored", incident_id),
            )
            down_recovered = True

    conn.close()
    return down_started, down_recovered


def get_incidents(limit: int = 20) -> pd.DataFrame:
    conn = get_conn()
    if conn is None:
        return pd.DataFrame(columns=["started_at", "ended_at", "duration", "start_reason", "end_reason"])

    query = """
    SELECT started_at, ended_at, duration_seconds, start_reason, end_reason
    FROM incidents
    ORDER BY id DESC
    LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()

    if not df.empty:
        df["duration"] = df["duration_seconds"].apply(format_duration)
        df.drop(columns=["duration_seconds"], inplace=True)
    return df


def compute_sla(hours: int = 24) -> dict:
    conn = get_conn()
    if conn is None:
        return {"uptime_pct": None, "checks_count": 0, "outages": 0, "avg_speed": None}

    since = (get_now().timestamp() - hours * 3600)
    since_iso = datetime.fromtimestamp(since, tz=ZoneInfo("Asia/Riyadh")).isoformat()

    checks_df = pd.read_sql_query(
        "SELECT status FROM checks WHERE timestamp >= ?", conn, params=(since_iso,)
    )
    speed_df = pd.read_sql_query(
        "SELECT download_mbps FROM speed_checks WHERE timestamp >= ?", conn, params=(since_iso,)
    )
    outages = conn.execute(
        "SELECT COUNT(*) FROM incidents WHERE started_at >= ?", (since_iso,)
    ).fetchone()[0]
    conn.close()

    checks_count = len(checks_df)
    uptime_pct = None
    if checks_count > 0:
        uptime_pct = round((checks_df["status"].eq("UP").sum() / checks_count) * 100, 2)

    avg_speed = None
    if not speed_df.empty:
        speed_vals = speed_df["download_mbps"].dropna()
        if not speed_vals.empty:
            avg_speed = round(float(speed_vals.mean()), 2)

    return {
        "uptime_pct": uptime_pct,
        "checks_count": checks_count,
        "outages": outages,
        "avg_speed": avg_speed,
    }


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

    download_mbps = mean(samples) if samples else None
    latency_ms = _measure_latency_ms("https://www.google.com/generate_204")

    return {
        "mode": mode,
        "download_mbps": download_mbps,
        "latency_ms": latency_ms,
    }


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
    SELECT mode, ROUND(download_mbps, 2) AS download_mbps,
           ROUND(latency_ms, 1) AS latency_ms,
           drop_detected, timestamp
    FROM speed_checks
    ORDER BY id DESC
    LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df


def _seconds_since_last_speed_test() -> float | None:
    conn = get_conn()
    if conn is None:
        return None

    row = conn.execute("SELECT timestamp FROM speed_checks ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None

    then = datetime.fromisoformat(row[0])
    return (get_now() - then).total_seconds()


init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "last_status" not in st.session_state:
    st.session_state.last_status = None
if "latest_speed" not in st.session_state:
    st.session_state.latest_speed = None
if "speed_alert" not in st.session_state:
    st.session_state.speed_alert = None
if "event_message" not in st.session_state:
    st.session_state.event_message = None


# ------------------ تسجيل الدخول ------------------
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

    st.info("Tip: You can set ADMIN_USERNAME and ADMIN_PASSWORD as environment variables.")
    st.stop()


# ------------------ واجهة النظام ------------------
st.title("🛡️ Network Monitoring System")
now = get_now()
st.write(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")
st.caption(f"Build tag: {APP_RELEASE_TAG}")

st.subheader("SLA Snapshot (Last 24h)")
sla = compute_sla(24)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Uptime", f"{sla['uptime_pct']}%" if sla["uptime_pct"] is not None else "-")
k2.metric("Checks", str(sla["checks_count"]))
k3.metric("Outages", str(sla["outages"]))
k4.metric("Avg speed", f"{sla['avg_speed']} Mbps" if sla["avg_speed"] is not None else "-")

st.subheader("Connectivity Check")
st.caption("Targets: " + ", ".join(TARGETS))

col_run, col_auto = st.columns([1, 2])
with col_run:
    run_connectivity = st.button("Run check now", type="primary")
with col_auto:
    auto_quick_test = st.checkbox("Auto quick speed test when internet check runs", value=True)

if run_connectivity:
    current_status = check_connection(TARGETS)
    down_started, down_recovered = track_incident_transition(current_status)
    save_check(current_status)
    st.session_state.last_status = current_status

    if down_started:
        msg = f"🚨 Incident started at {get_now().strftime('%Y-%m-%d %H:%M:%S')} (internet DOWN)"
        send_telegram_alert(msg)
        st.session_state.event_message = msg
    elif down_recovered:
        msg = f"✅ Incident recovered at {get_now().strftime('%Y-%m-%d %H:%M:%S')} (internet UP)"
        send_telegram_alert(msg)
        st.session_state.event_message = msg

if st.session_state.last_status == "DOWN":
    st.error("🚨 Internet is DOWN")
elif st.session_state.last_status == "UP":
    st.success("✅ Internet is UP")
else:
    st.warning("No checks have been run yet in this session.")

if st.session_state.event_message:
    st.info(st.session_state.event_message)


st.subheader("Speed Monitoring (Download + Latency)")
st.caption(
    f"Threshold: {SPEED_DROP_THRESHOLD_MBPS:.1f} Mbps | "
    f"Auto quick-test interval: {QUICK_TEST_INTERVAL_SECONDS}s"
)

c1, c2 = st.columns(2)
full_clicked = c1.button("Run full speed test")
quick_clicked = c2.button("Run quick speed test")

if full_clicked or quick_clicked:
    mode = "full" if full_clicked else "quick"
    with st.spinner(f"Running {mode} speed test..."):
        result = run_speed_test(mode)

    speed_value = result["download_mbps"]
    drop_detected = speed_value is not None and speed_value < SPEED_DROP_THRESHOLD_MBPS
    save_speed_check(result, drop_detected)
    st.session_state.latest_speed = result

    if drop_detected:
        st.session_state.speed_alert = (
            f"⚠️ Speed dropped to {speed_value:.2f} Mbps (< {SPEED_DROP_THRESHOLD_MBPS:.1f} Mbps). "
            "Running automatic quick verification now..."
        )
        send_telegram_alert(st.session_state.speed_alert)
        with st.spinner("Running automatic quick verification..."):
            quick_result = run_speed_test("quick")
        quick_drop = (
            quick_result["download_mbps"] is not None
            and quick_result["download_mbps"] < SPEED_DROP_THRESHOLD_MBPS
        )
        save_speed_check(quick_result, quick_drop)
        st.session_state.latest_speed = quick_result


if auto_quick_test and st.session_state.last_status == "UP" and run_connectivity:
    seconds_since_last = _seconds_since_last_speed_test()
    if seconds_since_last is None or seconds_since_last >= QUICK_TEST_INTERVAL_SECONDS:
        with st.spinner("Auto-running quick speed test..."):
            quick_result = run_speed_test("quick")
        quick_drop = (
            quick_result["download_mbps"] is not None
            and quick_result["download_mbps"] < SPEED_DROP_THRESHOLD_MBPS
        )
        save_speed_check(quick_result, quick_drop)
        st.session_state.latest_speed = quick_result
        if quick_drop:
            st.session_state.speed_alert = (
                f"🚨 Low speed detected automatically: {quick_result['download_mbps']:.2f} Mbps"
            )
            send_telegram_alert(st.session_state.speed_alert)

if st.session_state.speed_alert:
    st.error(st.session_state.speed_alert)

latest = st.session_state.latest_speed
if latest:
    dl = latest["download_mbps"]
    lat = latest["latency_ms"]
    dl_text = f"{dl:.2f} Mbps" if dl is not None else "unavailable"
    st.info(f"Latest speed result → Mode: {latest['mode']} | Download: {dl_text}")
    if lat is not None:
        st.caption(f"Latency: {lat:.1f} ms")

st.subheader("Recent checks")
recent_checks = get_recent_checks()
if recent_checks.empty:
    st.write("No stored checks yet.")
else:
    st.dataframe(recent_checks, width="stretch")

st.subheader("Recent speed checks")
recent_speed = get_recent_speed_checks()
if recent_speed.empty:
    st.write("No speed checks yet.")
else:
    st.dataframe(recent_speed, width="stretch")

st.subheader("Incident timeline")
incident_df = get_incidents()
if incident_df.empty:
    st.write("No incidents yet.")
else:
    st.dataframe(incident_df, width="stretch")

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    st.caption("Telegram alerts are enabled.")
else:
    st.caption("Telegram alerts are disabled. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable.")
