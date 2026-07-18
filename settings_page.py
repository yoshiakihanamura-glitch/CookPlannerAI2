from __future__ import annotations

from datetime import datetime

import streamlit as st

from data_store import load_settings, save_settings


def show_settings_page() -> None:
    st.subheader("設定")
    current = load_settings()
    try:
        due_default = datetime.strptime(current.get("due_date", "2027-03-20"), "%Y-%m-%d").date()
    except ValueError:
        due_default = datetime.strptime("2027-03-20", "%Y-%m-%d").date()
    with st.form("settings_form"):
        c1, c2 = st.columns(2)
        wife = c1.text_input("妻の名前", value=current.get("wife_name", "望実"))
        husband = c2.text_input("夫の名前", value=current.get("husband_name", "佳明"))
        due = st.date_input("出産予定日", value=due_default)
        people = st.number_input("人数", 1, 10, int(current.get("people", "2")))
        cycle = st.number_input("買い物周期（日）", 1, 14, int(current.get("shopping_cycle_days", "3")))
        r1, r2 = st.columns(2)
        rice_wife = r1.number_input("望実さんのご飯量（g）", 0, 1000, int(current.get("rice_wife_g", "300")))
        rice_husband = r2.number_input("佳明さんのご飯量（g）", 0, 1000, int(current.get("rice_husband_g", "300")))
        submitted = st.form_submit_button("設定を保存", use_container_width=True)
    if submitted:
        save_settings({
            "wife_name": wife,
            "husband_name": husband,
            "due_date": due.isoformat(),
            "people": str(people),
            "shopping_cycle_days": str(cycle),
            "rice_wife_g": str(rice_wife),
            "rice_husband_g": str(rice_husband),
        })
        st.success("設定を保存しました！")
