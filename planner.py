from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data_store import (
    MEAL_PLAN_COLUMNS,
    MEAL_PLAN_CSV,
    load_csv,
    save_csv,
)
from recipes import clean_text, load_recipes

PLAN_CATEGORIES = ["主菜", "副菜", "汁物"]
SAME_RECIPE_INTERVAL_DAYS = 14


def load_meal_plan() -> pd.DataFrame:
    return load_csv(
        MEAL_PLAN_CSV,
        MEAL_PLAN_COLUMNS,
    )


def choose_recipe(
    category_recipes: pd.DataFrame,
    day_index: int,
    history: dict[int, list[int]],
    counts: dict[int, int],
):
    if category_recipes.empty:
        return None

    candidates = category_recipes.copy()
    candidates["recipe_id"] = pd.to_numeric(
        candidates["recipe_id"],
        errors="coerce",
    )
    candidates["cook_time"] = pd.to_numeric(
        candidates["cook_time"],
        errors="coerce",
    ).fillna(999)
    candidates = candidates.dropna(
        subset=["recipe_id"]
    )
    candidates["recipe_id"] = (
        candidates["recipe_id"].astype(int)
    )

    allowed = []
    for _, row in candidates.iterrows():
        recipe_id = int(row["recipe_id"])
        recently_used = any(
            day_index - used_day
            < SAME_RECIPE_INTERVAL_DAYS
            for used_day in history.get(
                recipe_id,
                [],
            )
        )
        if not recently_used:
            allowed.append(row)

    if allowed:
        candidates = pd.DataFrame(allowed)

    quick = candidates[
        candidates["cook_time"] <= 30
    ]
    if not quick.empty:
        candidates = quick

    minimum_count = min(
        counts.get(int(recipe_id), 0)
        for recipe_id in candidates["recipe_id"]
    )
    candidates = candidates[
        candidates["recipe_id"].apply(
            lambda recipe_id: counts.get(
                int(recipe_id),
                0,
            )
            == minimum_count
        )
    ]

    return candidates.loc[
        random.choice(candidates.index.tolist())
    ]


def generate_meal_plan(
    start: date,
    days: int = 30,
) -> pd.DataFrame:
    recipes = load_recipes()
    rows = []
    history: dict[int, list[int]] = {}
    counts: dict[int, int] = {}

    for day_index in range(days):
        current = start + timedelta(
            days=day_index
        )

        for category in PLAN_CATEGORIES:
            selected = choose_recipe(
                recipes[
                    recipes["category"] == category
                ],
                day_index,
                history,
                counts,
            )

            if selected is None:
                rows.append(
                    {
                        "date": current.isoformat(),
                        "category": category,
                        "recipe_id": "",
                        "recipe_name": "未登録",
                    }
                )
                continue

            recipe_id = int(selected["recipe_id"])
            rows.append(
                {
                    "date": current.isoformat(),
                    "category": category,
                    "recipe_id": recipe_id,
                    "recipe_name": clean_text(
                        selected["recipe_name"]
                    ),
                }
            )
            history.setdefault(
                recipe_id,
                [],
            ).append(day_index)
            counts[recipe_id] = (
                counts.get(recipe_id, 0) + 1
            )

    return pd.DataFrame(
        rows,
        columns=MEAL_PLAN_COLUMNS,
    )


def plan_table(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame()

    table = dataframe.pivot(
        index="date",
        columns="category",
        values="recipe_name",
    ).reset_index()

    for category in PLAN_CATEGORIES:
        if category not in table.columns:
            table[category] = "未登録"

    table = table[
        ["date", "主菜", "副菜", "汁物"]
    ]
    table.columns = [
        "日付",
        "主菜",
        "副菜",
        "汁物",
    ]
    table["日付"] = pd.to_datetime(
        table["日付"]
    ).dt.strftime("%Y/%m/%d")
    return table


def _show_day_plan(
    dataframe: pd.DataFrame,
    target_date: date,
    title: str,
) -> None:
    st.markdown(f"### {title}")
    target = dataframe[
        dataframe["date"].astype(str)
        == target_date.isoformat()
    ]

    if target.empty:
        st.caption("献立はまだありません。")
        return

    columns = st.columns(3)
    for column, category in zip(
        columns,
        PLAN_CATEGORIES,
    ):
        row = target[target["category"] == category]
        recipe_name = (
            "未登録"
            if row.empty
            else str(row.iloc[0]["recipe_name"])
        )
        column.metric(category, recipe_name)


def show_planner_page() -> None:
    st.subheader("📅 30日分の献立")
    recipes = load_recipes()
    counts = (
        recipes["category"].value_counts().to_dict()
    )

    count_columns = st.columns(3)
    count_columns[0].metric(
        "主菜",
        f"{counts.get('主菜', 0)}件",
    )
    count_columns[1].metric(
        "副菜",
        f"{counts.get('副菜', 0)}件",
    )
    count_columns[2].metric(
        "汁物",
        f"{counts.get('汁物', 0)}件",
    )

    start = st.date_input(
        "開始日",
        value=date.today(),
    )

    if st.button(
        "📅 30日分を生成・再生成する",
        type="primary",
        use_container_width=True,
    ):
        save_csv(
            generate_meal_plan(start),
            MEAL_PLAN_CSV,
        )
        st.success(
            "30日分の献立を作成しました！"
        )
        st.rerun()

    dataframe = load_meal_plan()

    if dataframe.empty:
        st.info("まだ献立がありません。")
        return

    today_column, tomorrow_column = st.columns(2)
    with today_column:
        _show_day_plan(
            dataframe,
            date.today(),
            "今日",
        )
    with tomorrow_column:
        _show_day_plan(
            dataframe,
            date.today() + timedelta(days=1),
            "明日",
        )

    st.markdown("### 30日一覧")
    st.dataframe(
        plan_table(dataframe),
        use_container_width=True,
        hide_index=True,
    )
