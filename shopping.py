from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction
import unicodedata

import pandas as pd
import streamlit as st

from data_store import (
    INVENTORY_COLUMNS,
    INVENTORY_CSV,
    SHOPPING_COLUMNS,
    SHOPPING_CSV,
    load_csv,
    save_csv,
)
from inventory import STORAGE_LOCATIONS, load_inventory
from planner import load_meal_plan
from recipes import UNITS, get_recipe_ingredients


def load_shopping() -> pd.DataFrame:
    dataframe = load_csv(
        SHOPPING_CSV,
        SHOPPING_COLUMNS,
        dtype=str,
    ).fillna("")

    dataframe["checked"] = dataframe["checked"].apply(
        _to_bool
    )
    return dataframe


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def _normalize_name(value: object) -> str:
    return unicodedata.normalize(
        "NFKC",
        str(value),
    ).strip()


def _parse_amount(value: object) -> float | None:
    text = unicodedata.normalize(
        "NFKC",
        str(value),
    ).strip()

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


def _format_amount(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _shopping_key(name: object, unit: object) -> tuple[str, str]:
    return (
        _normalize_name(name),
        unicodedata.normalize(
            "NFKC",
            str(unit),
        ).strip(),
    )


def _upcoming_plan(days: int) -> pd.DataFrame:
    plan = load_meal_plan()
    if plan.empty:
        return plan

    plan = plan.copy()
    plan["parsed_date"] = pd.to_datetime(
        plan["date"],
        errors="coerce",
    )
    plan = plan.dropna(subset=["parsed_date"])

    today_timestamp = pd.Timestamp(date.today())
    upcoming = plan[
        plan["parsed_date"] >= today_timestamp
    ]

    if upcoming.empty:
        upcoming = plan

    upcoming = upcoming.sort_values("parsed_date")
    selected_dates = (
        upcoming["date"]
        .drop_duplicates()
        .head(days)
    )
    return upcoming[
        upcoming["date"].isin(selected_dates)
    ]


def _aggregate_required_ingredients(
    plan: pd.DataFrame,
) -> dict[tuple[str, str], dict[str, object]]:
    aggregated: dict[
        tuple[str, str],
        dict[str, object],
    ] = {}

    recipe_ids = pd.to_numeric(
        plan["recipe_id"],
        errors="coerce",
    ).dropna().astype(int)

    for recipe_id in recipe_ids:
        ingredients = get_recipe_ingredients(
            int(recipe_id)
        )

        for _, item in ingredients.iterrows():
            name = _normalize_name(
                item["ingredient_name"]
            )
            unit = str(item["unit"]).strip()

            if not name:
                continue

            key = _shopping_key(name, unit)
            amount_text = str(item["amount"]).strip()
            numeric_amount = _parse_amount(
                amount_text
            )

            if key not in aggregated:
                aggregated[key] = {
                    "ingredient_name": name,
                    "unit": unit,
                    "numeric_amount": 0.0,
                    "text_amounts": [],
                }

            if numeric_amount is None:
                if amount_text:
                    aggregated[key][
                        "text_amounts"
                    ].append(amount_text)
            else:
                aggregated[key][
                    "numeric_amount"
                ] += numeric_amount

    return aggregated


def _aggregate_inventory() -> dict[tuple[str, str], float]:
    inventory = load_inventory()
    result: dict[tuple[str, str], float] = {}

    if inventory.empty:
        return result

    for _, item in inventory.iterrows():
        name = _normalize_name(
            item["ingredient_name"]
        )
        unit = str(item["unit"]).strip()
        amount = _parse_amount(item["amount"])

        if not name or amount is None:
            continue

        key = _shopping_key(name, unit)
        result[key] = result.get(key, 0.0) + amount

    return result


def build_shopping_list(
    days: int = 3,
) -> pd.DataFrame:
    plan = _upcoming_plan(days)

    if plan.empty:
        return pd.DataFrame(
            columns=SHOPPING_COLUMNS
        )

    required = _aggregate_required_ingredients(
        plan
    )
    inventory = _aggregate_inventory()
    current = load_shopping()

    checked_by_key = {
        _shopping_key(
            row["ingredient_name"],
            row["unit"],
        ): bool(row["checked"])
        for _, row in current.iterrows()
    }

    rows: list[dict[str, object]] = []

    for key, item in required.items():
        required_number = float(
            item["numeric_amount"]
        )
        available_number = inventory.get(
            key,
            0.0,
        )
        shortage = max(
            required_number - available_number,
            0.0,
        )
        text_amounts = list(
            item["text_amounts"]
        )

        amount_parts: list[str] = []
        if shortage > 0:
            amount_parts.append(
                _format_amount(shortage)
            )
        amount_parts.extend(text_amounts)

        if not amount_parts:
            continue

        rows.append(
            {
                "ingredient_name": item[
                    "ingredient_name"
                ],
                "amount": " + ".join(
                    amount_parts
                ),
                "unit": item["unit"],
                "checked": checked_by_key.get(
                    key,
                    False,
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=SHOPPING_COLUMNS,
    )


def _next_inventory_id(
    inventory: pd.DataFrame,
) -> int:
    ids = pd.to_numeric(
        inventory["inventory_id"],
        errors="coerce",
    ).dropna()
    return 1 if ids.empty else int(ids.max()) + 1


def _add_checked_items_to_inventory(
    shopping: pd.DataFrame,
    storage_location: str,
    expiry_days: int,
) -> int:
    checked = shopping[
        shopping["checked"].apply(_to_bool)
    ].copy()

    if checked.empty:
        return 0

    inventory = load_inventory()
    added_count = 0

    for _, item in checked.iterrows():
        amount = _parse_amount(item["amount"])
        if amount is None:
            continue

        name = _normalize_name(
            item["ingredient_name"]
        )
        unit = str(item["unit"]).strip()

        same_name = (
            inventory["ingredient_name"]
            .astype(str)
            .map(_normalize_name)
            == name
        )
        same_unit = (
            inventory["unit"].astype(str) == unit
        )
        same_storage = (
            inventory["storage_location"]
            .astype(str)
            == storage_location
        )
        target = same_name & same_unit & same_storage

        if target.any():
            target_index = inventory[target].index[0]
            current_amount = _parse_amount(
                inventory.at[target_index, "amount"]
            )

            if current_amount is not None:
                inventory.at[
                    target_index,
                    "amount",
                ] = _format_amount(
                    current_amount + amount
                )
                inventory.at[
                    target_index,
                    "purchase_date",
                ] = date.today().isoformat()
                inventory.at[
                    target_index,
                    "expiry_date",
                ] = (
                    date.today()
                    + timedelta(days=expiry_days)
                ).isoformat()
                added_count += 1
                continue

        new_row = {
            "inventory_id": _next_inventory_id(
                inventory
            ),
            "ingredient_name": name,
            "amount": _format_amount(amount),
            "unit": unit,
            "expiry_date": (
                date.today()
                + timedelta(days=expiry_days)
            ).isoformat(),
            "purchase_date": date.today().isoformat(),
            "storage_location": storage_location,
            "note": "買い物リストから追加",
        }
        inventory = pd.concat(
            [inventory, pd.DataFrame([new_row])],
            ignore_index=True,
        )
        added_count += 1

    save_csv(
        inventory[INVENTORY_COLUMNS],
        INVENTORY_CSV,
    )
    return added_count


def _save_shopping_editor(
    edited: pd.DataFrame,
) -> pd.DataFrame:
    updated = edited.rename(
        columns={
            "食材": "ingredient_name",
            "数量": "amount",
            "単位": "unit",
            "購入済み": "checked",
        }
    )
    updated = updated[SHOPPING_COLUMNS].copy()
    updated["checked"] = updated["checked"].apply(
        _to_bool
    )
    save_csv(updated, SHOPPING_CSV)
    return updated


def show_shopping_page() -> None:
    st.subheader("🛒 買い物リスト")
    st.caption(
        "献立に必要な材料をまとめ、"
        "冷蔵庫にある分を差し引きます。"
    )

    days = st.number_input(
        "何日分をまとめる？",
        min_value=1,
        max_value=7,
        value=3,
        step=1,
    )

    if st.button(
        "🛒 不足分の買い物リストを作る",
        type="primary",
        use_container_width=True,
    ):
        generated = build_shopping_list(
            int(days)
        )
        save_csv(generated, SHOPPING_CSV)
        st.success(
            f"{len(generated)}件の不足食材を"
            "買い物リストに反映しました。"
        )
        st.rerun()

    dataframe = load_shopping()

    if dataframe.empty:
        st.info(
            "買い物リストはまだありません。"
            "献立を作成してから、上のボタンを"
            "押してください。"
        )
        return

    checked_count = int(
        dataframe["checked"].apply(_to_bool).sum()
    )
    remaining_count = len(dataframe) - checked_count

    metric_total, metric_remaining, metric_checked = (
        st.columns(3)
    )
    metric_total.metric(
        "買うもの",
        f"{len(dataframe)}件",
    )
    metric_remaining.metric(
        "未購入",
        f"{remaining_count}件",
    )
    metric_checked.metric(
        "購入済み",
        f"{checked_count}件",
    )

    editable = dataframe.rename(
        columns={
            "ingredient_name": "食材",
            "amount": "数量",
            "unit": "単位",
            "checked": "購入済み",
        }
    )

    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "食材": st.column_config.TextColumn(
                required=True,
            ),
            "数量": st.column_config.TextColumn(),
            "単位": st.column_config.SelectboxColumn(
                options=UNITS,
            ),
            "購入済み": st.column_config.CheckboxColumn(),
        },
        key="shopping_editor",
    )

    action_left, action_right = st.columns(2)

    if action_left.button(
        "変更を保存",
        use_container_width=True,
    ):
        _save_shopping_editor(edited)
        st.success("買い物リストを保存しました。")
        st.rerun()

    if action_right.button(
        "購入済みをリストから消す",
        use_container_width=True,
    ):
        updated = _save_shopping_editor(edited)
        remaining = updated[
            ~updated["checked"].apply(_to_bool)
        ]
        save_csv(
            remaining[SHOPPING_COLUMNS],
            SHOPPING_CSV,
        )
        st.rerun()

    st.markdown("### 購入した食材を冷蔵庫へ")
    st.caption(
        "購入済みにチェックした食材のうち、"
        "数量が数字のものを冷蔵庫へ追加します。"
    )

    with st.form("shopping_to_inventory"):
        option_left, option_right = st.columns(2)
        storage_location = option_left.selectbox(
            "保存場所",
            STORAGE_LOCATIONS,
        )
        expiry_days = option_right.number_input(
            "賞味期限までの日数",
            min_value=0,
            max_value=365,
            value=3,
            step=1,
        )
        add_to_inventory = st.form_submit_button(
            "購入済みを冷蔵庫へ追加",
            use_container_width=True,
        )

    if add_to_inventory:
        updated = _save_shopping_editor(edited)
        added_count = _add_checked_items_to_inventory(
            updated,
            storage_location,
            int(expiry_days),
        )

        if added_count == 0:
            st.warning(
                "冷蔵庫へ追加できる購入済み食材が"
                "ありません。数量を数字で入力し、"
                "購入済みにチェックしてください。"
            )
        else:
            remaining = updated[
                ~updated["checked"].apply(_to_bool)
            ]
            save_csv(
                remaining[SHOPPING_COLUMNS],
                SHOPPING_CSV,
            )
            st.success(
                f"{added_count}件を冷蔵庫へ追加しました。"
            )
            st.rerun()

    st.caption(
        "※ 調味料は現在レシピ内で文章管理のため、"
        "自動買い物リストの対象外です。"
    )
