from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from data_store import INVENTORY_COLUMNS, INVENTORY_CSV, load_csv, save_csv
from recipes import UNITS


def load_inventory() -> pd.DataFrame:
    return load_csv(INVENTORY_CSV, INVENTORY_COLUMNS, dtype=str).fillna("")


def show_inventory_page() -> None:
    st.subheader("冷蔵庫")
    df = load_inventory()
    with st.form("inventory_add", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1.5])
        name = c1.text_input("食材名")
        amount = c2.text_input("数量")
        unit = c3.selectbox("単位", UNITS)
        expiry = c4.date_input("賞味期限", value=date.today())
        submitted = st.form_submit_button("冷蔵庫に追加", use_container_width=True)
    if submitted:
        if not name.strip():
            st.error("食材名を入力してください。")
        else:
            ids = pd.to_numeric(df["inventory_id"], errors="coerce").dropna()
            next_id = 1 if ids.empty else int(ids.max()) + 1
            row = {"inventory_id": next_id, "ingredient_name": name.strip(), "amount": amount.strip(), "unit": unit, "expiry_date": expiry.isoformat()}
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            save_csv(df, INVENTORY_CSV)
            st.rerun()
    if df.empty:
        st.info("冷蔵庫は空です。")
        return
    display = df.copy()
    display.columns = ["ID", "食材", "数量", "単位", "賞味期限"]
    st.dataframe(display, use_container_width=True, hide_index=True)
    options = {f"{row['ingredient_name']}（{row['amount']}{row['unit']}）": row["inventory_id"] for _, row in df.iterrows()}
    selected = st.selectbox("削除する食材", ["選択してください"] + list(options.keys()))
    if selected != "選択してください" and st.button("選択した食材を削除"):
        target = int(float(options[selected]))
        df = df[pd.to_numeric(df["inventory_id"], errors="coerce") != target]
        save_csv(df, INVENTORY_CSV)
        st.rerun()
