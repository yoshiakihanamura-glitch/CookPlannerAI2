from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ai_chef import show_ai_chef_page
from cooking import cook_today_meal, today_is_cooked
from inventory import load_inventory
from planner import load_meal_plan
from recipes import get_recipe_ingredients, load_recipes
from shopping import load_shopping


CATEGORIES = ["主菜", "副菜", "汁物"]


def _expiry_days(expiry_date: object) -> int | None:
    """期限までの日数を返す。"""
    parsed = pd.to_datetime(expiry_date, errors="coerce")

    if pd.isna(parsed):
        return None

    return (parsed.date() - date.today()).days


def _expiry_message(expiry_date: object) -> str:
    """期限を見やすい日本語に変換する。"""
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


def _get_day_plan(target_date: date) -> pd.DataFrame:
    """指定日の献立を取得する。"""
    meal_plan = load_meal_plan()

    if meal_plan.empty:
        return pd.DataFrame()

    return meal_plan[
        meal_plan["date"].astype(str) == target_date.isoformat()
    ].copy()


def _recipe_detail(recipe_id: object) -> dict[str, object] | None:
    """料理IDからレシピと材料を取得する。"""
    try:
        recipe_id_number = int(float(recipe_id))
    except (TypeError, ValueError):
        return None

    recipes = load_recipes()

    if recipes.empty:
        return None

    recipe_ids = pd.to_numeric(
        recipes["recipe_id"],
        errors="coerce",
    )

    matched = recipes[recipe_ids == recipe_id_number]

    if matched.empty:
        return None

    recipe = matched.iloc[0]
    ingredients = get_recipe_ingredients(recipe_id_number)

    return {
        "recipe": recipe,
        "ingredients": ingredients,
    }


def _show_recipe_content(meal: pd.Series) -> None:
    """材料・調味料・作り方を表示する。"""
    detail = _recipe_detail(meal.get("recipe_id"))

    if detail is None:
        st.caption("詳しいレシピは登録されていません。")
        return

    recipe = detail["recipe"]
    ingredients = detail["ingredients"]

    st.markdown("**材料**")

    if ingredients.empty:
        st.caption("材料は登録されていません。")
    else:
        for _, ingredient in ingredients.iterrows():
            name = str(ingredient.get("ingredient_name", "")).strip()
            amount = str(ingredient.get("amount", "")).strip()
            unit = str(ingredient.get("unit", "")).strip()

            if name:
                st.write(f"・{name}：{amount}{unit}")

    st.markdown("**調味料**")
    seasonings = str(recipe.get("seasonings", "")).strip()
    st.write(seasonings or "記載なし")

    st.markdown("**作り方**")
    instructions = str(recipe.get("instructions", "")).strip()

    if instructions:
        st.write(instructions)
    else:
        st.caption("作り方は登録されていません。")


def _show_day_meal(
    target_date: date,
    title: str,
    show_recipe_details: bool,
) -> pd.DataFrame:
    """今日・明日の献立を、料理名を省略せず表示する。"""
    day_plan = _get_day_plan(target_date)

    st.markdown(f"## {title}")

    if day_plan.empty:
        st.info(f"{title}の献立はまだ登録されていません。")
        return day_plan

    for category in CATEGORIES:
        category_meal = day_plan[
            day_plan["category"].astype(str) == category
        ]

        if category_meal.empty:
            recipe_name = "未登録"
            meal = None
        else:
            meal = category_meal.iloc[0]
            recipe_name = str(meal.get("recipe_name", "未登録")).strip()

        # metricを使わず、長い料理名も折り返して全文表示する
        st.markdown(
            f"""
            <div style="
                padding: 0.8rem 1rem;
                margin-bottom: 0.65rem;
                border: 1px solid rgba(128, 128, 128, 0.25);
                border-radius: 0.7rem;
            ">
                <div style="
                    font-size: 0.85rem;
                    opacity: 0.7;
                    margin-bottom: 0.2rem;
                ">
                    {category}
                </div>
                <div style="
                    font-size: 1.05rem;
                    font-weight: 700;
                    line-height: 1.55;
                    overflow-wrap: anywhere;
                    white-space: normal;
                ">
                    {recipe_name}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if (
            show_recipe_details
            and meal is not None
            and recipe_name != "未登録"
        ):
            with st.expander(f"作り方を見る｜{recipe_name}"):
                _show_recipe_content(meal)

    return day_plan


def _show_cook_button(today_plan: pd.DataFrame) -> None:
    """今日の献立を調理済みにして在庫を更新する。"""
    if today_plan.empty:
        return

    if today_is_cooked():
        st.success(
            "今日の献立は調理済みです。"
            "冷蔵庫の残量も更新されています。"
        )
        return

    if st.button(
        "🍳 今日の献立を作った！",
        type="primary",
        use_container_width=True,
        key="home_cook_today",
    ):
        result = cook_today_meal()
        status = result.get("status")

        if status == "success":
            st.success(
                str(result.get("message", "更新しました。"))
            )

            shortages = result.get("shortages", [])

            if shortages:
                shortage_text = "、".join(
                    f"{item['ingredient_name']} "
                    f"{item['amount']}{item['unit']}"
                    for item in shortages
                )

                st.warning(
                    "冷蔵庫で不足していた材料："
                    + shortage_text
                )

            st.rerun()
        else:
            st.warning(
                str(result.get("message", "更新できませんでした。"))
            )


def _show_shopping_summary() -> None:
    """ホームに買い物リストを簡潔に表示する。"""
    st.markdown("## 🛒 買い物リスト")

    shopping = load_shopping()

    if shopping.empty:
        st.caption(
            "買い物リストはありません。"
            "AIシェフの回答を読み込むと自動で追加されます。"
        )
        return

    checked = shopping["checked"].astype(bool)
    pending = shopping[~checked].copy()

    if pending.empty:
        st.success("現在、買うものはありません。")
        return

    for _, item in pending.iterrows():
        name = str(item.get("ingredient_name", "")).strip()
        amount = str(item.get("amount", "")).strip()
        unit = str(item.get("unit", "")).strip()

        st.write(f"□ {name}　{amount}{unit}")


def _show_inventory_summary() -> None:
    """期限が近い食材をホームに表示する。"""
    st.markdown("## 🥦 冷蔵庫")

    inventory = load_inventory()

    if inventory.empty:
        st.caption("冷蔵庫に食材が登録されていません。")
        return

    work = inventory.copy()
    work["_expiry"] = pd.to_datetime(
        work["expiry_date"],
        errors="coerce",
    )
    work["_days"] = work["expiry_date"].apply(_expiry_days)

    expired = work[
        work["_days"].apply(
            lambda value: value is not None and value < 0
        )
    ]

    if not expired.empty:
        st.error(
            f"期限切れの食材が{len(expired)}件あります。"
        )

    urgent = work[
        work["_days"].apply(
            lambda value: (
                value is not None
                and value <= 4
            )
        )
    ].sort_values(
        "_expiry",
        na_position="last",
    )

    if urgent.empty:
        st.success("期限が近い食材はありません。")
        return

    st.caption("優先して使いたい食材")

    for _, item in urgent.head(5).iterrows():
        name = str(item.get("ingredient_name", "")).strip()
        amount = str(item.get("amount", "")).strip()
        unit = str(item.get("unit", "")).strip()
        expiry = _expiry_message(item.get("expiry_date"))

        st.write(
            f"・{name}　{amount}{unit}　{expiry}"
        )


def _show_seven_day_plan() -> None:
    """今日から7日間の献立一覧を表示する。"""
    st.markdown("## 📅 今後7日")

    meal_plan = load_meal_plan()

    if meal_plan.empty:
        st.caption("献立はまだありません。")
        return

    work = meal_plan.copy()
    work["_date"] = pd.to_datetime(
        work["date"],
        errors="coerce",
    )
    work = work.dropna(subset=["_date"])

    start_date = date.today()
    end_date = start_date + timedelta(days=6)

    work = work[
        (work["_date"].dt.date >= start_date)
        & (work["_date"].dt.date <= end_date)
    ]

    if work.empty:
        st.caption("今後7日間の献立は登録されていません。")
        return

    table = work.pivot_table(
        index="date",
        columns="category",
        values="recipe_name",
        aggfunc="first",
    ).reset_index()

    for category in CATEGORIES:
        if category not in table.columns:
            table[category] = "未登録"

    table = table[
        ["date", "主菜", "副菜", "汁物"]
    ].copy()

    table["date"] = pd.to_datetime(
        table["date"],
        errors="coerce",
    ).dt.strftime("%m/%d")

    table.columns = [
        "日付",
        "主菜",
        "副菜",
        "汁物",
    ]

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )


def show_home() -> None:
    """CookPlanner AIのホーム画面。"""
    today_plan = _show_day_meal(
        target_date=date.today(),
        title="🍳 今日の献立",
        show_recipe_details=True,
    )

    _show_cook_button(today_plan)

    st.divider()

    _show_day_meal(
        target_date=date.today() + timedelta(days=1),
        title="🌙 明日の献立",
        show_recipe_details=False,
    )

    st.divider()

    # 既存の無料AIシェフ機能をホーム内にそのまま表示
    show_ai_chef_page()

    st.divider()

    _show_shopping_summary()

    st.divider()

    _show_inventory_summary()

    st.divider()

    _show_seven_day_plan()