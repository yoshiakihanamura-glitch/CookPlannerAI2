from __future__ import annotations

import pandas as pd
import streamlit as st

from data_store import SHOPPING_COLUMNS, SHOPPING_CSV, load_csv, save_csv
from planner import load_meal_plan
from recipes import get_recipe_ingredients


def load_shopping() -> pd.DataFrame:
    return load_csv(SHOPPING_CSV, SHOPPING_COLUMNS, dtype=str).fillna("")


def build_shopping_list(days: int = 3) -> pd.DataFrame:
    plan = load_meal_plan()
    if plan.empty:
        return pd.DataFrame(columns=SHOPPING_COLUMNS)
    plan = plan.sort_values("date")
    selected_dates = plan["date"].drop_duplicates().head(days)
    plan = plan[plan["date"].isin(selected_dates)]
    rows = []
    for recipe_id in pd.to_numeric(plan["recipe_id"], errors="coerce").dropna().astype(int):
        ingredients = get_recipe_ingredients(recipe_id)
        for _, item in ingredients.iterrows():
            rows.append({"ingredient_name": item["ingredient_name"], "amount": item["amount"], "unit": item["unit"], "checked": "False"})
    return pd.DataFrame(rows, columns=SHOPPING_COLUMNS)


def show_shopping_page() -> None:
    st.subheader("買い物リスト")
    days = st.number_input("何日分をまとめる？", 1, 7, 3)
    if st.button("🛒 献立から買い物リストを作る", type="primary", use_container_width=True):
        save_csv(build_shopping_list(int(days)), SHOPPING_CSV)
        st.rerun()
    df = load_shopping()
    if df.empty:
        st.info("買い物リストはまだありません。")
        return
    edited = st.data_editor(
        df.rename(columns={"ingredient_name": "食材", "amount": "数量", "unit": "単位", "checked": "購入済み"}),
        use_container_width=True,
        hide_index=True,
        column_config={"購入済み": st.column_config.CheckboxColumn()},
    )
    if st.button("変更を保存"):
        edited = edited.rename(columns={"食材": "ingredient_name", "数量": "amount", "単位": "unit", "購入済み": "checked"})
        save_csv(edited[SHOPPING_COLUMNS], SHOPPING_CSV)
        st.success("保存しました！")
