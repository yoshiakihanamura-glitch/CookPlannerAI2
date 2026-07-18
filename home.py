from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from data_store import load_settings
from inventory import load_inventory
from planner import load_meal_plan


def pregnancy_week(
    due_date_text: str,
) -> tuple[int, int] | None:
    """出産予定日から現在の妊娠週数を計算する。"""
    try:
        due_date = datetime.strptime(
            due_date_text,
            "%Y-%m-%d",
        ).date()
    except (ValueError, TypeError):
        return None

    pregnancy_start_date = due_date - timedelta(
        days=280
    )

    elapsed_days = (
        date.today() - pregnancy_start_date
    ).days

    if elapsed_days < 0:
        return (0, 0)

    return (
        elapsed_days // 7,
        elapsed_days % 7,
    )


def show_home() -> None:
    """ホーム画面を表示する。"""
    settings = load_settings()

    husband_name = settings.get(
        "husband_name",
        "佳明",
    )

    st.subheader(
        f"おはよう、{husband_name}さん"
    )

    today = date.today().isoformat()
    meal_plan = load_meal_plan()

    if meal_plan.empty:
        today_plan = pd.DataFrame()
    else:
        today_plan = meal_plan[
            meal_plan["date"].astype(str) == today
        ]

    st.markdown("### 🍳 今日の献立")

    if today_plan.empty:
        st.info(
            "今日の献立はまだありません。"
            "献立画面から30日分を生成してください。"
        )
    else:
        columns = st.columns(3)

        for column, category in zip(
            columns,
            ["主菜", "副菜", "汁物"],
        ):
            category_plan = today_plan[
                today_plan["category"] == category
            ]

            if category_plan.empty:
                recipe_name = "未登録"
            else:
                recipe_name = str(
                    category_plan.iloc[0][
                        "recipe_name"
                    ]
                )

            column.metric(
                category,
                recipe_name,
            )

    st.markdown(
        "### 🥦 今日使い切りたい食材"
    )

    inventory = load_inventory()

    if inventory.empty:
        st.caption(
            "冷蔵庫に食材が登録されていません。"
        )
    else:
        inventory = inventory.copy()

        inventory["expiry"] = pd.to_datetime(
            inventory["expiry_date"],
            errors="coerce",
        )

        urgent_items = (
            inventory.sort_values(
                "expiry",
                na_position="last",
            )
            .head(3)
        )

        for _, item in urgent_items.iterrows():
            ingredient_name = str(
                item.get(
                    "ingredient_name",
                    "",
                )
            )

            amount = str(
                item.get(
                    "amount",
                    "",
                )
            )

            unit = str(
                item.get(
                    "unit",
                    "",
                )
            )

            expiry_date = str(
                item.get(
                    "expiry_date",
                    "",
                )
            )

            st.write(
                f"・{ingredient_name} "
                f"{amount}{unit} "
                f"期限：{expiry_date}"
            )

    st.markdown("### 🤰 妊娠情報")

    week = pregnancy_week(
        settings.get(
            "due_date",
            "",
        )
    )

    if week is None:
        st.caption(
            "設定画面で出産予定日を"
            "入力してください。"
        )
    else:
        st.write(
            f"妊娠 {week[0]}週 {week[1]}日"
        )