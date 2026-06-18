import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="نظام قاعدة بيانات الموظفين", page_icon="📁", layout="wide")

DB_PATH = "employees.db"

ADMIN_COLUMNS = [
    "الرقم",
    "الاسم",
    "الرتبة",
    "آخر مهمة",
    "تاريخ آخر مهمة",
    "النخبة",
    "مستهدف",
    "اجتاز الدورة",
    "الرماية",
    "اللياقة",
    "الوزن",
    "نوع التأشيرة",
    "تاريخ انتهاء التأشيرة",
    "ملاحظات",
]

NAMES_COLUMNS = [
    "الرقم",
    "الاسم",
    "NAME",
    "الرتبة",
    "الرقم المدني",
    "DOB",
    "DOE",
    "رقم الجواز",
    "رقم البيان",
    "المهمة",
    "الطائرة",
]


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_form (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number_text TEXT,
                name TEXT,
                rank TEXT,
                last_mission TEXT,
                last_mission_date TEXT,
                elite_flag TEXT,
                target_flag TEXT,
                course_cleared TEXT,
                shooting TEXT,
                fitness TEXT,
                weight_text TEXT,
                visa_number TEXT,
                visa_expiry TEXT,
                notes TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS names_form (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number_text TEXT,
                arabic_name TEXT,
                english_name TEXT,
                rank TEXT,
                civil_id TEXT,
                dob TEXT,
                doe TEXT,
                passport_number TEXT,
                statement_number TEXT,
                mission TEXT,
                aircraft TEXT,
                created_at TEXT
            )
            """
        )


def fetch_df(table: str) -> pd.DataFrame:
    with get_conn() as conn:
        if table == "admin_form":
            return pd.read_sql_query(
                """
                SELECT number_text AS 'الرقم', name AS 'الاسم', rank AS 'الرتبة',
                       last_mission AS 'آخر مهمة', last_mission_date AS 'تاريخ آخر مهمة',
                       elite_flag AS 'النخبة', target_flag AS 'مستهدف',
                       course_cleared AS 'اجتاز الدورة', shooting AS 'الرماية',
                       fitness AS 'اللياقة', weight_text AS 'الوزن', visa_number AS 'نوع التأشيرة',
                       visa_expiry AS 'تاريخ انتهاء التأشيرة', notes AS 'ملاحظات'
                FROM admin_form
                ORDER BY id DESC
                """,
                conn,
            )
        return pd.read_sql_query(
            """
            SELECT number_text AS 'الرقم', arabic_name AS 'الاسم', english_name AS 'NAME',
                   rank AS 'الرتبة', civil_id AS 'الرقم المدني', dob AS 'DOB', doe AS 'DOE',
                   passport_number AS 'رقم الجواز', statement_number AS 'رقم البيان',
                   mission AS 'المهمة', aircraft AS 'الطائرة'
            FROM names_form
            ORDER BY id DESC
            """,
            conn,
        )


def insert_admin(values: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO admin_form (
                number_text, name, rank, last_mission, last_mission_date,
                elite_flag, target_flag, course_cleared, shooting,
                fitness, weight_text, visa_number, visa_expiry, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["الرقم"],
                values["الاسم"],
                values["الرتبة"],
                values["آخر مهمة"],
                values["تاريخ آخر مهمة"],
                values["النخبة"],
                values["مستهدف"],
                values["اجتاز الدورة"],
                values["الرماية"],
                values["اللياقة"],
                values["الوزن"],
                values["نوع التأشيرة"],
                values["تاريخ انتهاء التأشيرة"],
                values["ملاحظات"],
                datetime.now().isoformat(),
            ),
        )


def insert_names(values: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO names_form (
                number_text, arabic_name, english_name, rank, civil_id,
                dob, doe, passport_number, statement_number, mission, aircraft, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["الرقم"],
                values["الاسم"],
                values["NAME"],
                values["الرتبة"],
                values["الرقم المدني"],
                values["DOB"],
                values["DOE"],
                values["رقم الجواز"],
                values["رقم البيان"],
                values["المهمة"],
                values["الطائرة"],
                datetime.now().isoformat(),
            ),
        )


def delete_by_number(table: str, number_text: str) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE number_text = ?",
            (number_text,),
        )
        return cursor.rowcount


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    return cleaned


def parse_uploaded_dataframe(uploaded_file) -> tuple[pd.DataFrame, str | None]:
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith(".csv"):
            return normalize_columns(pd.read_csv(uploaded_file)), None
        if file_name.endswith(".xlsx"):
            return normalize_columns(pd.read_excel(uploaded_file)), None
        return pd.DataFrame(), "صيغة الملف غير مدعومة. استخدم CSV أو XLSX."
    except Exception as error:
        return pd.DataFrame(), f"تعذر قراءة الملف: {error}"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_text_bytes(df: pd.DataFrame, title: str) -> bytes:
    # Fallback export that always works without external dependencies.
    rows = [title, "=" * len(title), ""]
    rows.append(" | ".join(df.columns.tolist()))
    for _, row in df.iterrows():
        rows.append(" | ".join(str(row[col]) for col in df.columns))
    text_content = "\n".join(rows)
    return text_content.encode("utf-8-sig")


init_db()

st.markdown(
    """
    <style>
    .stApp { direction: rtl; }
    h1, h2, h3, p, label, div { text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📁 نظام إدارة بيانات الموظفين")
st.caption("نسخة أولية مطابقة مبدئيًا للنموذجين المرسلين، مع إدخال يدوي + بحث + استيراد/تصدير.")
st.info("تشغيل البرنامج يكون عبر الأمر: streamlit run app.py")

main_tab, admin_tab, names_tab, records_tab, import_export_tab = st.tabs(
    ["لوحة البيانات", "نموذج الإدارة", "بيان الأسماء", "إدارة السجلات", "الاستيراد والتصدير"]
)

with main_tab:
    st.subheader("ملخص سريع")
    admin_df = fetch_df("admin_form")
    names_df = fetch_df("names_form")
    c1, c2 = st.columns(2)
    c1.metric("عدد سجلات نموذج الإدارة", len(admin_df))
    c2.metric("عدد سجلات بيان الأسماء", len(names_df))

    keyword = st.text_input("بحث عام في جميع الجداول", placeholder="اكتب الاسم أو الرقم أو الرتبة...")
    if keyword:
        admin_filtered = admin_df[
            admin_df.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        ]
        names_filtered = names_df[
            names_df.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        ]
    else:
        admin_filtered = admin_df
        names_filtered = names_df

    st.markdown("#### نتائج نموذج الإدارة")
    st.dataframe(admin_filtered, use_container_width=True, hide_index=True)

    st.markdown("#### نتائج بيان الأسماء")
    st.dataframe(names_filtered, use_container_width=True, hide_index=True)

with admin_tab:
    st.subheader("إضافة سجل جديد - نموذج الإدارة")
    with st.form("admin_form_entry", clear_on_submit=True):
        row1 = st.columns(4)
        values = {
            "الرقم": row1[0].text_input("الرقم"),
            "الاسم": row1[1].text_input("الاسم"),
            "الرتبة": row1[2].text_input("الرتبة"),
            "آخر مهمة": row1[3].text_input("آخر مهمة"),
        }
        row2 = st.columns(4)
        values.update(
            {
                "تاريخ آخر مهمة": row2[0].text_input("تاريخ آخر مهمة"),
                "النخبة": row2[1].selectbox("النخبة", ["", "نعم", "لا"]),
                "مستهدف": row2[2].selectbox("مستهدف", ["", "نعم", "لا"]),
                "اجتاز الدورة": row2[3].selectbox("اجتاز الدورة", ["", "نعم", "لا"]),
            }
        )
        row3 = st.columns(4)
        values.update(
            {
                "الرماية": row3[0].text_input("الرماية"),
                "اللياقة": row3[1].text_input("اللياقة"),
                "الوزن": row3[2].text_input("الوزن"),
                "نوع التأشيرة": row3[3].text_input("نوع التأشيرة"),
            }
        )
        values["تاريخ انتهاء التأشيرة"] = st.text_input("تاريخ انتهاء التأشيرة")
        values["ملاحظات"] = st.text_area("ملاحظات")

        submit = st.form_submit_button("حفظ السجل", type="primary")
        if submit:
            if not values["الاسم"]:
                st.error("الاسم مطلوب على الأقل.")
            else:
                insert_admin(values)
                st.success("تم حفظ سجل نموذج الإدارة بنجاح.")

    st.markdown("#### جدول نموذج الإدارة")
    st.dataframe(fetch_df("admin_form"), use_container_width=True, hide_index=True)

with names_tab:
    st.subheader("إضافة سجل جديد - بيان الأسماء")
    with st.form("names_form_entry", clear_on_submit=True):
        r1 = st.columns(4)
        values = {
            "الرقم": r1[0].text_input("الرقم"),
            "الاسم": r1[1].text_input("الاسم"),
            "NAME": r1[2].text_input("NAME"),
            "الرتبة": r1[3].text_input("الرتبة"),
        }
        r2 = st.columns(4)
        values.update(
            {
                "الرقم المدني": r2[0].text_input("الرقم المدني"),
                "DOB": r2[1].text_input("DOB"),
                "DOE": r2[2].text_input("DOE"),
                "رقم الجواز": r2[3].text_input("رقم الجواز"),
            }
        )
        r3 = st.columns(3)
        values.update(
            {
                "رقم البيان": r3[0].text_input("رقم البيان"),
                "المهمة": r3[1].text_input("المهمة"),
                "الطائرة": r3[2].text_input("الطائرة"),
            }
        )

        submit = st.form_submit_button("حفظ السجل", type="primary")
        if submit:
            if not values["الاسم"]:
                st.error("الاسم مطلوب على الأقل.")
            else:
                insert_names(values)
                st.success("تم حفظ سجل بيان الأسماء بنجاح.")

    st.markdown("#### جدول بيان الأسماء")
    st.dataframe(fetch_df("names_form"), use_container_width=True, hide_index=True)

with records_tab:
    st.subheader("إدارة السجلات (حذف حسب الرقم)")
    st.caption("لأمان البيانات: الحذف يتم فقط بعد إدخال رقم السجل بشكل صريح.")
    table_choice = st.selectbox("اختر الجدول", ["admin_form", "names_form"])
    number_to_delete = st.text_input("رقم السجل المراد حذفه")
    if st.button("حذف السجل", type="primary"):
        if not number_to_delete.strip():
            st.error("يرجى إدخال الرقم أولًا.")
        else:
            deleted = delete_by_number(table_choice, number_to_delete.strip())
            if deleted > 0:
                st.success(f"تم حذف {deleted} سجل من {table_choice}.")
            else:
                st.warning("لم يتم العثور على سجل مطابق لهذا الرقم.")

    st.markdown("#### آخر البيانات الحالية")
    st.dataframe(fetch_df(table_choice), use_container_width=True, hide_index=True)

with import_export_tab:
    st.subheader("الاستيراد")
    st.caption("يدعم هذه النسخة التجريبية: CSV و XLSX بشكل مباشر.")
    target_table = st.radio("وجهة الاستيراد", ["admin_form", "names_form"], horizontal=True)
    uploaded = st.file_uploader("ارفع ملف CSV أو XLSX", type=["csv", "xlsx"])
    if uploaded:
        imported_df, upload_error = parse_uploaded_dataframe(uploaded)
        if upload_error:
            st.error(upload_error)
        elif imported_df.empty:
            st.error("الملف فارغ.")
        else:
            st.write("معاينة البيانات:")
            st.dataframe(imported_df.head(20), use_container_width=True)
            if st.button("تنفيذ الاستيراد", type="primary"):
                missing_cols = [
                    col
                    for col in (ADMIN_COLUMNS if target_table == "admin_form" else NAMES_COLUMNS)
                    if col not in imported_df.columns
                ]
                if missing_cols:
                    st.error(f"الأعمدة التالية ناقصة: {', '.join(missing_cols)}")
                else:
                    if target_table == "admin_form":
                        for _, rec in imported_df.iterrows():
                            insert_admin(rec.to_dict())
                    else:
                        for _, rec in imported_df.iterrows():
                            insert_names(rec.to_dict())
                    st.success("تم الاستيراد بنجاح وتوزيع البيانات على الجدول المحدد.")

    st.divider()
    st.subheader("قوالب جاهزة للاستيراد")
    admin_template = pd.DataFrame(columns=ADMIN_COLUMNS)
    names_template = pd.DataFrame(columns=NAMES_COLUMNS)
    st.download_button(
        "تحميل قالب نموذج الإدارة (CSV)",
        data=dataframe_to_csv_bytes(admin_template),
        file_name="admin_form_template.csv",
        mime="text/csv",
    )
    st.download_button(
        "تحميل قالب بيان الأسماء (CSV)",
        data=dataframe_to_csv_bytes(names_template),
        file_name="names_form_template.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("التصدير")
    export_table = st.radio("اختر النموذج", ["admin_form", "names_form"], horizontal=True, key="export")
    export_df = fetch_df(export_table)

    if export_df.empty:
        st.warning("لا توجد بيانات حاليًا للتصدير.")
    else:
        st.download_button(
            "تصدير CSV (Excel)",
            data=dataframe_to_csv_bytes(export_df),
            file_name=f"{export_table}.csv",
            mime="text/csv",
        )
        st.download_button(
            "تصدير نص منسق (بديل PDF مؤقت)",
            data=dataframe_to_text_bytes(export_df, title=f"Export - {export_table}"),
            file_name=f"{export_table}.txt",
            mime="text/plain",
        )

st.info("الخطوة القادمة: إضافة PDF/Word حقيقي مع استخراج تلقائي دقيق حسب كل نموذج.")
