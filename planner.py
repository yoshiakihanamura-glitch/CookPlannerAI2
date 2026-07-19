from __future__ import annotations

import random
import unicodedata
from datetime import date, timedelta
from fractions import Fraction

import pandas as pd
import streamlit as st

from data_store import (
    MEAL_PLAN_COLUMNS,
    MEAL_PLAN_CSV,
    load_csv,
    save_csv,
)
from inventory import load_inventory
from recipes import (
    clean_text,
    get_recipe_ingredients,
    load_recipes,
)

PLAN_CATEGORIES = ["主菜", "副菜", "汁物"]
SAME_RECIPE_INTERVAL_DAYS = 14


def load_meal_plan() -> pd.DataFrame:
    return load_csv(
        MEAL_PLAN_CSV,
        MEAL_PLAN_COLUMNS,
    )


def _normalize_text(value: object) -> str:
    return unicodedata.normalize(
        "NFKC",
        str(value),
    ).strip().lower()


def _ingredient_key(
    name: object,
    unit: object,
) -> tuple[str, str]:
    return (
        _normalize_text(name),
        _normalize_text(unit),
    )


def _parse_amount(value: object) -> float | None:
    text = _normalize_text(value)
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        pass

    try:
        return float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return None


def _expiry_days(
    expiry_date: object,
    target_date: date,
) -> int | None:
    parsed = pd.to_datetime(
        expiry_date,
        errors="coerce",
    )
    if pd.isna(parsed):
        return None
    return (parsed.date() - target_date).days


def _inventory_state() -> dict[
    tuple[str, str],
    dict[str, object],
]:
    inventory = load_inventory()
    state: dict[
        tuple[str, str],
        dict[str, object],
    ] = {}

    if inventory.empty:
        return state

    for _, item in inventory.iterrows():
        name = str(item["ingredient_name"]).strip()
        unit = str(item["unit"]).strip()
        if not name:
            continue

        key = _ingredient_key(name, unit)
        amount = _parse_amount(item["amount"])
        expiry = pd.to_datetime(
            item["expiry_date"],
            errors="coerce",
        )

        if key not in state:
            state[key] = {
                "ingredient_name": name,
                "unit": unit,
                "amount": 0.0,
                "has_numeric_amount": False,
                "expiry_dates": [],
            }

        if amount is not None:
            state[key]["amount"] = (
                float(state[key]["amount"]) + amount
            )
            state[key]["has_numeric_amount"] = True

        if not pd.isna(expiry):
            state[key]["expiry_dates"].append(
                expiry.date()
            )

    return state


def _recipe_requirements(
    recipe_id: int,
) -> list[dict[str, object]]:
    ingredients = get_recipe_ingredients(recipe_id)
    requirements: list[dict[str, object]] = []

    for _, item in ingredients.iterrows():
        name = str(item["ingredient_name"]).strip()
        if not name:
            continue

        unit = str(item["unit"]).strip()
        requirements.append(
            {
                "key": _ingredient_key(name, unit),
                "ingredient_name": name,
                "unit": unit,
                "amount": _parse_amount(item["amount"]),
            }
        )

    return requirements


def _inventory_fit(
    recipe_id: int,
    target_date: date,
    inventory_state: dict[
        tuple[str, str],
        dict[str, object],
    ],
) -> tuple[float, list[str], list[str]]:
    requirements = _recipe_requirements(recipe_id)
    if not requirements:
        return (0.0, [], [])

    matched: list[str] = []
    missing: list[str] = []
    coverage_points = 0.0
    urgent_points = 0.0

    for requirement in requirements:
        key = requirement["key"]
        stock = inventory_state.get(key)

        if stock is None:
            missing.append(
                str(requirement["ingredient_name"])
            )
            continue

        required_amount = requirement["amount"]
        stock_amount = float(stock["amount"])
        has_numeric = bool(
            stock["has_numeric_amount"]
        )

        enough = True
        if required_amount is not None and has_numeric:
            enough = stock_amount >= required_amount

        if enough:
            coverage_points += 1.0
            matched.append(
                str(requirement["ingredient_name"])
            )
        elif stock_amount > 0:
            coverage_points += 0.45
            matched.append(
                str(requirement["ingredient_name"])
                + "（一部あり）"
            )
        else:
            missing.append(
                str(requirement["ingredient_name"])
            )

        expiry_dates = list(
            stock["expiry_dates"]
        )
        if expiry_dates:
            nearest = min(expiry_dates)
            days = (nearest - target_date).days
            if days < 0:
                urgent_points += 0.2
            elif days == 0:
                urgent_points += 1.0
            elif days <= 2:
                urgent_points += 0.75
            elif days <= 4:
                urgent_points += 0.35

    coverage_ratio = coverage_points / len(
        requirements
    )
    urgency_ratio = urgent_points / len(
        requirements
    )

    score = coverage_ratio * 70 + urgency_ratio * 30
    return (score, matched, missing)


def _consume_virtual_inventory(
    recipe_id: int,
    inventory_state: dict[
        tuple[str, str],
        dict[str, object],
    ],
) -> None:
    for requirement in _recipe_requirements(recipe_id):
        key = requirement["key"]
        required_amount = requirement["amount"]
        stock = inventory_state.get(key)

        if (
            stock is None
            or required_amount is None
            or not stock["has_numeric_amount"]
        ):
            continue

        stock["amount"] = max(
            float(stock["amount"]) - required_amount,
            0.0,
        )


def choose_recipe(
    category_recipes: pd.DataFrame,
    day_index: int,
    current_date: date,
    history: dict[int, list[int]],
    counts: dict[int, int],
    inventory_state: dict[
        tuple[str, str],
        dict[str, object],
    ],
    use_inventory: bool,
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

    allowed_rows = []
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
            allowed_rows.append(row)

    if allowed_rows:
        candidates = pd.DataFrame(allowed_rows)

    scored: list[tuple[float, int]] = []

    for row_index, row in candidates.iterrows():
        recipe_id = int(row["recipe_id"])
        cook_time = float(row["cook_time"])
        use_count = counts.get(recipe_id, 0)

        score = 0.0

        # 登録回数が少ない料理を優先する。
        score += max(0.0, 30.0 - use_count * 8.0)

        # 30分以内を優先する。
        if cook_time <= 30:
            score += 18.0
        elif cook_time <= 40:
            score += 7.0
        else:
            score -= 5.0

        if use_inventory and inventory_state:
            fit_score, _, _ = _inventory_fit(
                recipe_id,
                current_date,
                inventory_state,
            )

            # 在庫は直近ほど強く優先し、先の日程では
            # 献立の偏りを防ぐため影響を弱める。
            if day_index <= 2:
                inventory_weight = 1.0
            elif day_index <= 6:
                inventory_weight = 0.55
            else:
                inventory_weight = 0.18

            score += fit_score * inventory_weight

        # 同点時に毎回まったく同じ並びにならないための微差。
        score += random.random() * 0.5
        scored.append((score, row_index))

    if not scored:
        return None

    best_score = max(score for score, _ in scored)
    near_best = [
        row_index
        for score, row_index in scored
        if score >= best_score - 0.25
    ]
    selected_index = random.choice(near_best)
    return candidates.loc[selected_index]


def generate_meal_plan(
    start: date,
    days: int = 30,
    use_inventory: bool = True,
) -> pd.DataFrame:
    recipes = load_recipes()
    rows = []
    history: dict[int, list[int]] = {}
    counts: dict[int, int] = {}
    virtual_inventory = _inventory_state()

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
                current,
                history,
                counts,
                virtual_inventory,
                use_inventory,
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

            if use_inventory:
                _consume_virtual_inventory(
                    recipe_id,
                    virtual_inventory,
                )

    return pd.DataFrame(
        rows,
        columns=MEAL_PLAN_COLUMNS,
    )



def rebuild_future_plan(
    start: date | None = None,
    default_days: int = 30,
    use_inventory: bool = True,
) -> pd.DataFrame:
    """今日以降の献立だけを、現在の冷蔵庫在庫で作り直す。

    今日より前の献立はそのまま残す。既存献立が将来まである場合は、
    その最終日までを再生成し、献立がない場合は30日分を生成する。
    """
    start_date = start or date.today()
    current_plan = load_meal_plan()

    if current_plan.empty:
        future_days = default_days
        past_plan = pd.DataFrame(columns=MEAL_PLAN_COLUMNS)
    else:
        parsed_dates = pd.to_datetime(
            current_plan["date"],
            errors="coerce",
        )
        past_plan = current_plan[
            parsed_dates.dt.date < start_date
        ].copy()

        future_dates = parsed_dates[
            parsed_dates.dt.date >= start_date
        ].dropna()

        if future_dates.empty:
            future_days = default_days
        else:
            last_date = future_dates.max().date()
            future_days = max(
                (last_date - start_date).days + 1,
                1,
            )

    rebuilt = generate_meal_plan(
        start=start_date,
        days=future_days,
        use_inventory=use_inventory,
    )

    combined = pd.concat(
        [past_plan, rebuilt],
        ignore_index=True,
    )
    combined = combined[MEAL_PLAN_COLUMNS]
    save_csv(combined, MEAL_PLAN_CSV)
    return combined

def inventory_recipe_ranking(
    limit: int = 5,
) -> pd.DataFrame:
    recipes = load_recipes()
    inventory_state = _inventory_state()

    columns = [
        "料理名",
        "カテゴリ",
        "在庫活用度",
        "使える食材",
        "不足食材",
    ]

    if recipes.empty or not inventory_state:
        return pd.DataFrame(columns=columns)

    rows = []
    for _, recipe in recipes.iterrows():
        try:
            recipe_id = int(float(recipe["recipe_id"]))
        except (TypeError, ValueError):
            continue

        score, matched, missing = _inventory_fit(
            recipe_id,
            date.today(),
            inventory_state,
        )
        rows.append(
            {
                "料理名": clean_text(
                    recipe["recipe_name"]
                ),
                "カテゴリ": clean_text(
                    recipe["category"]
                ),
                "在庫活用度": round(score),
                "使える食材": "、".join(matched)
                or "なし",
                "不足食材": "、".join(missing)
                or "なし",
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    ranking = pd.DataFrame(rows)
    return (
        ranking.sort_values(
            ["在庫活用度", "料理名"],
            ascending=[False, True],
        )
        .head(limit)
        .reset_index(drop=True)
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
    st.caption(
        "冷蔵庫の在庫と賞味期限を考慮して、"
        "直近の献立を優先的に組み立てます。"
    )

    recipes = load_recipes()
    inventory = load_inventory()
    counts = (
        recipes["category"].value_counts().to_dict()
    )

    count_columns = st.columns(4)
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
    count_columns[3].metric(
        "冷蔵庫",
        f"{len(inventory)}品",
    )

    start = st.date_input(
        "開始日",
        value=date.today(),
    )
    use_inventory = st.toggle(
        "冷蔵庫の在庫・賞味期限を優先する",
        value=True,
        help=(
            "直近7日間は、冷蔵庫にある食材や"
            "期限が近い食材を使える料理を優先します。"
        ),
    )

    if use_inventory and inventory.empty:
        st.info(
            "冷蔵庫が空のため、レシピの重複回避と"
            "調理時間を中心に献立を作成します。"
        )

    if st.button(
        "📅 30日分を生成・再生成する",
        type="primary",
        use_container_width=True,
    ):
        save_csv(
            generate_meal_plan(
                start,
                use_inventory=use_inventory,
            ),
            MEAL_PLAN_CSV,
        )
        st.success(
            "30日分の献立を作成しました！"
        )
        st.rerun()

    if use_inventory and not inventory.empty:
        st.markdown("### 🥦 冷蔵庫を活かせる料理")
        ranking = inventory_recipe_ranking()
        if ranking.empty:
            st.caption(
                "材料が登録されたレシピがありません。"
            )
        else:
            st.dataframe(
                ranking,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "在庫活用度": st.column_config.ProgressColumn(
                        min_value=0,
                        max_value=100,
                        format="%d%%",
                    )
                },
            )

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
