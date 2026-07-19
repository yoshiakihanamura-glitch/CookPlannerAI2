from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from cooking import cook_today_meal, today_is_cooked
from data_store import load_settings
from inventory import load_inventory
from planner import load_meal_plan
from recipes import load_recipes
from shopping import load_shopping


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


def _expiry_days(expiry_date: object) -> int | None:
    parsed = pd.to_datetime(
        expiry_date,
        errors="coerce",
    )
    if pd.isna(parsed):
        return None
    return (parsed.date() - date.today()).days


def _expiry_message(expiry_date: object) -> str:
    days = _expiry_days(expiry_date)
    if days is None:
        return "期限未設定"
    if days < 0:
        return f"期限切れ（{abs(days)}日前）"
    if days == 0:
        return "今日まで"
    if days == 1:
        return "明日まで"
    return f"あと{days}日"


def _show_today_meal() -> pd.DataFrame:
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
        return today_plan

    columns = st.columns(3)

    for column, category in zip(
        columns,
        ["主菜", "副菜", "汁物"],
    ):
        category_plan = today_plan[
            today_plan["category"] == category
        ]
        recipe_name = (
            "未登録"
            if category_plan.empty
            else str(
                category_plan.iloc[0]["recipe_name"]
            )
        )
        column.metric(category, recipe_name)

    return today_plan


def _show_cook_button(today_plan: pd.DataFrame) -> None:
    if today_plan.empty:
        return

    if today_is_cooked():
        st.success("今日の献立は調理済みです。冷蔵庫の残量も更新されています。")
        return

    if st.button(
        "🍳 今日の献立を作った！",
        type="primary",
        use_container_width=True,
    ):
        result = cook_today_meal()
        status = result.get("status")
        if status == "success":
            st.success(str(result.get("message", "更新しました。")))
            shortages = result.get("shortages", [])
            if shortages:
                shortage_text = "、".join(
                    f"{item['ingredient_name']} {item['amount']}{item['unit']}"
                    for item in shortages
                )
                st.warning(
                    "冷蔵庫で不足していた材料：" + shortage_text
                    + "。買い物リストを更新してください。"
                )
            st.rerun()
        else:
            st.warning(str(result.get("message", "更新できませんでした。")))


def show_home() -> None:
    settings = load_settings()
    inventory = load_inventory()
    shopping = load_shopping()
    recipes = load_recipes()

    husband_name = settings.get(
        "husband_name",
        "佳明",
    )
    st.subheader(f"おはよう、{husband_name}さん")

    shopping_remaining = 0
    if not shopping.empty:
        shopping_remaining = int(
            (~shopping["checked"].astype(bool)).sum()
        )

    urgent_count = 0
    expired_count = 0
    if not inventory.empty:
        expiry_days = inventory[
            "expiry_date"
        ].apply(_expiry_days)
        urgent_count = int(
            expiry_days.apply(
                lambda value: (
                    value is not None
                    and 0 <= value <= 3
                )
            ).sum()
        )
        expired_count = int(
            expiry_days.apply(
                lambda value: (
                    value is not None
                    and value < 0
                )
            ).sum()
        )

    metrics = st.columns(4)
    metrics[0].metric(
        "冷蔵庫",
        f"{len(inventory)}品",
    )
    metrics[1].metric(
        "期限3日以内",
        f"{urgent_count}品",
    )
    metrics[2].metric(
        "買い物残り",
        f"{shopping_remaining}件",
    )
    metrics[3].metric(
        "登録レシピ",
        f"{len(recipes)}件",
    )

    if expired_count:
        st.error(
            f"期限切れの食材が{expired_count}品あります。"
        )

    today_plan = _show_today_meal()
    _show_cook_button(today_plan)

    st.markdown("### 🥦 今日使い切りたい食材")

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

        urgent_items = inventory.sort_values(
            "expiry",
            na_position="last",
        ).head(3)

        for _, item in urgent_items.iterrows():
            st.write(
                f"・{item['ingredient_name']} "
                f"{item['amount']}{item['unit']}　"
                f"{_expiry_message(item['expiry_date'])}"
            )

    st.markdown("### 🛒 買い物")
    if shopping.empty:
        st.caption(
            "買い物リストはまだありません。"
        )
    elif shopping_remaining == 0:
        st.success("買い物はすべて完了しています。")
    else:
        st.write(
            f"未購入の食材が{shopping_remaining}件あります。"
        )
        pending = shopping[
            ~shopping["checked"].astype(bool)
        ].head(5)
        for _, item in pending.iterrows():
            st.write(
                f"・{item['ingredient_name']} "
                f"{item['amount']}{item['unit']}"
            )

    st.markdown("### 🤰 妊娠情報")

    week = pregnancy_week(
        settings.get("due_date", "")
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
