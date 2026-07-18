from __future__ import annotations

import pandas as pd
import streamlit as st

from data_store import (
    INGREDIENTS_CSV,
    INGREDIENT_COLUMNS,
    RECIPES_CSV,
    RECIPE_COLUMNS,
    load_csv,
    save_csv,
)

CATEGORIES = ["主菜", "副菜", "汁物", "その他"]
UNITS = ["", "g", "kg", "ml", "L", "個", "本", "枚", "パック", "袋", "束", "片", "大さじ", "小さじ", "カップ", "適量", "少々"]
MAX_INGREDIENTS = 10


def clean_text(value) -> str:
    return "" if pd.isna(value) else str(value)


def load_recipes() -> pd.DataFrame:
    return load_csv(RECIPES_CSV, RECIPE_COLUMNS)


def load_ingredients() -> pd.DataFrame:
    return load_csv(INGREDIENTS_CSV, INGREDIENT_COLUMNS, dtype=str).fillna("")


def get_recipe_ingredients(recipe_id: int) -> pd.DataFrame:
    df = load_ingredients()
    ids = pd.to_numeric(df["recipe_id"], errors="coerce")
    return df[ids == recipe_id].reset_index(drop=True)


def _next_id(df: pd.DataFrame, column: str) -> int:
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return 1 if values.empty else int(values.max()) + 1


def _summary(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        name = row["ingredient_name"].strip()
        if not name:
            continue
        amount = row["amount"].strip()
        unit = row["unit"].strip()
        lines.append(f"{name} {amount}{unit}".strip())
    return "\n".join(lines)


def save_recipe(recipe_id: int | None, name: str, category: str, cook_time: int, rows: list[dict], seasonings: str, instructions: str) -> int:
    recipes = load_recipes()
    ingredients = load_ingredients()
    if recipe_id is None:
        recipe_id = _next_id(recipes, "recipe_id")
        recipes = pd.concat([recipes, pd.DataFrame([{
            "recipe_id": recipe_id,
            "recipe_name": name,
            "category": category,
            "cook_time": cook_time,
            "ingredients": _summary(rows),
            "seasonings": seasonings,
            "instructions": instructions,
        }])], ignore_index=True)
    else:
        target = pd.to_numeric(recipes["recipe_id"], errors="coerce") == recipe_id
        recipes.loc[target, ["recipe_name", "category", "cook_time", "ingredients", "seasonings", "instructions"]] = [
            name, category, cook_time, _summary(rows), seasonings, instructions
        ]
        ingredient_ids = pd.to_numeric(ingredients["recipe_id"], errors="coerce")
        ingredients = ingredients[ingredient_ids != recipe_id]

    new_rows = [{
        "recipe_id": recipe_id,
        "ingredient_name": row["ingredient_name"].strip(),
        "amount": row["amount"].strip(),
        "unit": row["unit"].strip(),
    } for row in rows if row["ingredient_name"].strip()]
    if new_rows:
        ingredients = pd.concat([ingredients, pd.DataFrame(new_rows)], ignore_index=True)
    save_csv(recipes, RECIPES_CSV)
    save_csv(ingredients, INGREDIENTS_CSV)
    return recipe_id


def delete_recipe(recipe_id: int) -> None:
    recipes = load_recipes()
    ingredients = load_ingredients()
    recipes = recipes[pd.to_numeric(recipes["recipe_id"], errors="coerce") != recipe_id]
    ingredients = ingredients[pd.to_numeric(ingredients["recipe_id"], errors="coerce") != recipe_id]
    save_csv(recipes, RECIPES_CSV)
    save_csv(ingredients, INGREDIENTS_CSV)


def ingredient_inputs(prefix: str, existing: list[dict] | None = None) -> list[dict]:
    existing = existing or []
    rows: list[dict] = []
    st.markdown("#### 材料・分量")
    h1, h2, h3 = st.columns([3, 1.2, 1.2])
    h1.markdown("**食材名**")
    h2.markdown("**分量**")
    h3.markdown("**単位**")
    for i in range(MAX_INGREDIENTS):
        current = existing[i] if i < len(existing) else {"ingredient_name": "", "amount": "", "unit": ""}
        c1, c2, c3 = st.columns([3, 1.2, 1.2])
        with c1:
            name = st.text_input(f"食材名{i+1}", value=clean_text(current.get("ingredient_name")), key=f"{prefix}_name_{i}", label_visibility="collapsed", placeholder="例：鶏むね肉")
        with c2:
            amount = st.text_input(f"分量{i+1}", value=clean_text(current.get("amount")), key=f"{prefix}_amount_{i}", label_visibility="collapsed", placeholder="例：300")
        unit_value = clean_text(current.get("unit"))
        with c3:
            unit = st.selectbox(f"単位{i+1}", UNITS, index=UNITS.index(unit_value) if unit_value in UNITS else 0, key=f"{prefix}_unit_{i}", label_visibility="collapsed")
        rows.append({"ingredient_name": name, "amount": amount, "unit": unit})
    return rows


def show_recipe_page() -> None:
    tab_add, tab_list = st.tabs(["レシピ登録", "登録済みレシピ"])
    with tab_add:
        st.subheader("新しいレシピを登録")
        with st.form("new_recipe", clear_on_submit=True):
            name = st.text_input("料理名")
            c1, c2 = st.columns(2)
            category = c1.selectbox("カテゴリ", CATEGORIES)
            cook_time = c2.number_input("調理時間（分）", 1, 180, 30)
            rows = ingredient_inputs("new")
            seasonings = st.text_area("調味料")
            instructions = st.text_area("作り方", height=180)
            submit = st.form_submit_button("🍳 レシピを登録する", use_container_width=True)
        if submit:
            if not name.strip():
                st.error("料理名を入力してください。")
            elif not any(r["ingredient_name"].strip() for r in rows):
                st.error("材料を1つ以上入力してください。")
            elif not instructions.strip():
                st.error("作り方を入力してください。")
            else:
                save_recipe(None, name.strip(), category, int(cook_time), rows, seasonings.strip(), instructions.strip())
                st.success(f"「{name}」を登録しました！")

    with tab_list:
        st.subheader("登録済みレシピ")
        recipes = load_recipes()
        if recipes.empty:
            st.info("まだレシピは登録されていません。")
            return
        c1, c2 = st.columns(2)
        keyword = c1.text_input("料理名・材料で検索")
        category_filter = c2.selectbox("カテゴリで絞り込み", ["すべて"] + CATEGORIES)
        filtered = recipes.copy()
        if keyword.strip():
            mask = filtered["recipe_name"].astype(str).str.contains(keyword, case=False, na=False) | filtered["ingredients"].astype(str).str.contains(keyword, case=False, na=False)
            filtered = filtered[mask]
        if category_filter != "すべて":
            filtered = filtered[filtered["category"] == category_filter]
        st.write(f"表示件数：{len(filtered)}件")
        for _, recipe in filtered.iloc[::-1].iterrows():
            recipe_id = int(float(recipe["recipe_id"]))
            name = clean_text(recipe["recipe_name"])
            category = clean_text(recipe["category"])
            cook_time = int(float(recipe["cook_time"]))
            ingredient_df = get_recipe_ingredients(recipe_id)
            existing = ingredient_df[["ingredient_name", "amount", "unit"]].to_dict("records")
            with st.expander(f"{name}｜{category}｜{cook_time}分"):
                for item in existing:
                    st.write(f"・{item['ingredient_name']}：{item['amount']}{item['unit']}")
                st.markdown("**調味料**")
                st.text(clean_text(recipe["seasonings"]) or "未登録")
                st.markdown("**作り方**")
                st.text(clean_text(recipe["instructions"]) or "未登録")
                with st.form(f"edit_{recipe_id}"):
                    st.markdown("### 編集")
                    edited_name = st.text_input("料理名", value=name)
                    ec1, ec2 = st.columns(2)
                    edited_category = ec1.selectbox("カテゴリ", CATEGORIES, index=CATEGORIES.index(category) if category in CATEGORIES else 0)
                    edited_time = ec2.number_input("調理時間（分）", 1, 180, cook_time)
                    edited_rows = ingredient_inputs(f"edit_{recipe_id}", existing)
                    edited_seasonings = st.text_area("調味料", value=clean_text(recipe["seasonings"]))
                    edited_instructions = st.text_area("作り方", value=clean_text(recipe["instructions"]), height=180)
                    update = st.form_submit_button("変更を保存する", use_container_width=True)
                if update:
                    save_recipe(recipe_id, edited_name.strip(), edited_category, int(edited_time), edited_rows, edited_seasonings.strip(), edited_instructions.strip())
                    st.success("更新しました！")
                    st.rerun()
                if st.button("このレシピを削除する", key=f"delete_{recipe_id}"):
                    delete_recipe(recipe_id)
                    st.rerun()
