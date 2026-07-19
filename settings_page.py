from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from data_store import DATA_DIR, load_settings, save_settings

DATA_FILES = [
    "recipes.csv",
    "recipe_ingredients.csv",
    "meal_plan.csv",
    "inventory.csv",
    "shopping.csv",
    "cook_log.csv",
    "settings.csv",
    "ai_responses.csv",
]


def _make_backup_zip() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for filename in DATA_FILES:
            path = Path(DATA_DIR) / filename
            if path.exists():
                archive.write(path, arcname=f"data/{filename}")
    buffer.seek(0)
    return buffer.getvalue()


def _restore_backup(uploaded_file) -> int:
    content = BytesIO(uploaded_file.getvalue())
    restored = 0
    with ZipFile(content) as archive:
        names = set(archive.namelist())
        for filename in DATA_FILES:
            candidates = (f"data/{filename}", filename)
            source_name = next((name for name in candidates if name in names), None)
            if source_name is None:
                continue
            target = Path(DATA_DIR) / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(source_name))
            restored += 1
    return restored


def show_settings_page() -> None:
    st.subheader("⚙️ 設定・バックアップ")
    current = load_settings()
    try:
        due_default = datetime.strptime(
            current.get("due_date", "2027-03-20"), "%Y-%m-%d"
        ).date()
    except ValueError:
        due_default = datetime.strptime("2027-03-20", "%Y-%m-%d").date()

    with st.form("settings_form"):
        c1, c2 = st.columns(2)
        wife = c1.text_input("妻の名前", value=current.get("wife_name", "望実"))
        husband = c2.text_input("夫の名前", value=current.get("husband_name", "佳明"))
        due = st.date_input("出産予定日", value=due_default)
        people = st.number_input("人数", 1, 10, int(current.get("people", "2")))
        cycle = st.number_input(
            "買い物周期（日）", 1, 14, int(current.get("shopping_cycle_days", "3"))
        )
        r1, r2 = st.columns(2)
        rice_wife = r1.number_input(
            "望実さんのご飯量（g）", 0, 1000, int(current.get("rice_wife_g", "300"))
        )
        rice_husband = r2.number_input(
            "佳明さんのご飯量（g）", 0, 1000, int(current.get("rice_husband_g", "300"))
        )
        submitted = st.form_submit_button("設定を保存", use_container_width=True)

    if submitted:
        save_settings(
            {
                "wife_name": wife,
                "husband_name": husband,
                "due_date": due.isoformat(),
                "people": str(people),
                "shopping_cycle_days": str(cycle),
                "rice_wife_g": str(rice_wife),
                "rice_husband_g": str(rice_husband),
            }
        )
        st.success("設定を保存しました！")

    st.divider()
    st.markdown("### ☁️ データのバックアップ")
    st.warning(
        "Streamlit Community Cloudでは、アプリの再起動や再デプロイでCSVの変更が消える場合があります。"
        "大切な更新後はバックアップを保存してください。"
    )

    backup_name = f"CookPlannerAI_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    st.download_button(
        "⬇️ 現在のデータをバックアップ",
        data=_make_backup_zip(),
        file_name=backup_name,
        mime="application/zip",
        use_container_width=True,
    )

    uploaded = st.file_uploader(
        "バックアップZIPから復元",
        type=["zip"],
        help="この画面から作成したバックアップZIPを選択してください。",
    )
    confirm = st.checkbox("現在のデータをバックアップ内容で置き換える")
    if st.button(
        "⬆️ バックアップを復元",
        disabled=uploaded is None or not confirm,
        use_container_width=True,
    ):
        try:
            restored = _restore_backup(uploaded)
            if restored == 0:
                st.error("復元できるデータファイルが見つかりませんでした。")
            else:
                st.success(f"{restored}個のデータファイルを復元しました。")
                st.rerun()
        except Exception as exc:
            st.error(f"復元に失敗しました：{exc}")
