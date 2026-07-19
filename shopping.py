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
from ingredient_rules import canonical_name, get_rule
from inventory import load_inventory
from planner import load_meal_plan
from recipes import UNITS, get_recipe_ingredients


def load_shopping() -> pd.DataFrame:
    dataframe = load_csv(
        SHOPPING_CSV,
        SHOPPING_COLUMNS,
        dtype=str,
    ).fillna("")
    dataframe["checked"] = dataframe["checked"].apply(_to_bool)
    return dataframe


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _normalize_name(value: object) -> str:
    return canonical_name(value)


def _parse_amount(value: object) -> float | None:
    text = unicodedata.normalize("NFKC", str(value)).strip()
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
        unicodedata.normalize("NFKC", str(unit)).strip(),
    )


def _upcoming_plan(days: int) -> pd.DataFrame:
    plan = load_meal_plan()
    if plan.empty:
        return plan
    plan = plan.copy()
    plan["parsed_date"] = pd.to_datetime(plan["date"], errors="coerce")
    plan = plan.dropna(subset=["parsed_date"])
    upcoming = plan[plan["parsed_date"] >= pd.Timestamp(date.today())]
    if upcoming.empty:
        upcoming = plan
    upcoming = upcoming.sort_values("parsed_date")
    selected_dates = upcoming["date"].drop_duplicates().head(days)
    return upcoming[upcoming["date"].isin(selected_dates)]


def _aggregate_required_ingredients(
    plan: pd.DataFrame,
) -> dict[tuple[str, str], dict[str, object]]:
    aggregated: dict[tuple[str, str], dict[str, object]] = {}
    recipe_ids = pd.to_numeric(
        plan["recipe_id"], errors="coerce"
    ).dropna().astype(int)

    for recipe_id in recipe_ids:
        ingredients = get_recipe_ingredients(int(recipe_id))
        for _, item in ingredients.iterrows():
            name = _normalize_name(item["ingredient_name"])
            unit = str(item["unit"]).strip()
            if not name:
                continue
            key = _shopping_key(name, unit)
            amount_text = str(item["amount"]).strip()
            numeric_amount = _parse_amount(amount_text)
            if key not in aggregated:
                aggregated[key] = {
                    "ingredient_name": name,
                    "unit": unit,
                    "numeric_amount": 0.0,
                    "text_amounts": [],
                }
            if numeric_amount is None:
                if amount_text:
                    aggregated[key]["text_amounts"].append(amount_text)
            else:
                aggregated[key]["numeric_amount"] += numeric_amount
    return aggregated


def _aggregate_inventory() -> dict[tuple[str, str], float]:
    inventory = load_inventory()
    result: dict[tuple[str, str], float] = {}
    if inventory.empty:
        return result
    for _, item in inventory.iterrows():
        name = _normalize_name(item["ingredient_name"])
        unit = str(item["unit"]).strip()
        amount = _parse_amount(item["amount"])
        if not name or amount is None:
            continue
        key = _shopping_key(name, unit)
        result[key] = result.get(key, 0.0) + amount
    return result


def build_shopping_list(days: int = 3) -> pd.DataFrame:
    plan = _upcoming_plan(days)
    if plan.empty:
        return pd.DataFrame(columns=SHOPPING_COLUMNS)

    required = _aggregate_required_ingredients(plan)
    inventory = _aggregate_inventory()
    rows: list[dict[str, object]] = []

    for key, item in required.items():
        required_number = float(item["numeric_amount"])
        available_number = inventory.get(key, 0.0)
        shortage = max(required_number - available_number, 0.0)
        amount_parts: list[str] = []
        if shortage > 0:
            amount_parts.append(_format_amount(shortage))
        amount_parts.extend(list(item["text_amounts"]))
        if not amount_parts:
            continue
        rows.append(
            {
                "ingredient_name": item["ingredient_name"],
                "amount": " + ".join(amount_parts),
                "unit": item["unit"],
                "checked": True,
            }
        )

    return pd.DataFrame(rows, columns=SHOPPING_COLUMNS)


def _next_inventory_id(inventory: pd.DataFrame) -> int:
    ids = pd.to_numeric(inventory["inventory_id"], errors="coerce").dropna()
    return 1 if ids.empty else int(ids.max()) + 1


def _add_checked_items_to_inventory(shopping: pd.DataFrame) -> tuple[int, int]:
    checked = shopping[shopping["checked"].apply(_to_bool)].copy()
    if checked.empty:
        return (0, 0)

    inventory = load_inventory()
    added_count = 0
    skipped_count = 0

    for _, item in checked.iterrows():
        amount = _parse_amount(item["amount"])
        if amount is None:
            skipped_count += 1
            continue

        name = _normalize_name(item["ingredient_name"])
        unit = str(item["unit"]).strip()
        rule = get_rule(name)
        new_row = {
            "inventory_id": _next_inventory_id(inventory),
            "ingredient_name": name,
            "amount": _format_amount(amount),
            "unit": unit,
            "expiry_date": (
                date.today() + timedelta(days=rule.shelf_life_days)
            ).isoformat(),
            "purchase_date": date.today().isoformat(),
            "storage_location": rule.storage_location,
            "note": "買い物リストから自動追加（消費目安）",
        }
        # 期限管理を正しくするため、既存在庫へ合算せず購入ロットごとに追加する。
        inventory = pd.concat(
            [inventory, pd.DataFrame([new_row])], ignore_index=True
        )
        added_count += 1

    save_csv(inventory[INVENTORY_COLUMNS], INVENTORY_CSV)
    return (added_count, skipped_count)


def _save_shopping_editor(edited: pd.DataFrame) -> pd.DataFrame:
    """画面上の買い物リストを内部形式へ戻して保存する。"""
    updated = edited.rename(
        columns={
            "食材": "ingredient_name",
            "数量": "amount",
            "単位": "unit",
            "購入済み": "checked",
            "冷蔵庫へ入れる": "checked",
            "購入対象": "checked",
        }
    ).copy()

    # 旧版CSVや表示名の違いが残っていても落ちないように補完する。
    for column in SHOPPING_COLUMNS:
        if column not in updated.columns:
            updated[column] = False if column == "checked" else ""

    updated["checked"] = updated["checked"].apply(_to_bool)
    updated = updated[SHOPPING_COLUMNS].copy()
    save_csv(updated, SHOPPING_CSV)
    return updated


def show_shopping_page() -> None:
    st.subheader("🛒 買い物リスト")
    st.caption("献立に必要な材料をまとめ、冷蔵庫にある分を差し引きます。")

    days = st.number_input(
        "何日分をまとめる？", min_value=1, max_value=7, value=3, step=1
    )
    if st.button(
        "🛒 不足分の買い物リストを作る",
        type="primary",
        use_container_width=True,
    ):
        generated = build_shopping_list(int(days))
        save_csv(generated, SHOPPING_CSV)
        st.success(f"{len(generated)}件の不足食材を反映しました。")
        st.rerun()

    dataframe = load_shopping()
    if dataframe.empty:
        st.info("買い物リストはまだありません。献立作成後に生成してください。")
        return

    checked_count = int(dataframe["checked"].apply(_to_bool).sum())
    metrics = st.columns(3)
    metrics[0].metric("買うもの", f"{len(dataframe)}件")
    metrics[1].metric("対象外", f"{len(dataframe) - checked_count}件")
    metrics[2].metric("冷蔵庫へ入れる", f"{checked_count}件")

    editable = dataframe.rename(
        columns={
            "ingredient_name": "食材",
            "amount": "数量",
            "unit": "単位",
            "checked": "冷蔵庫へ入れる",
        }
    )
    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "食材": st.column_config.TextColumn(required=True),
            "数量": st.column_config.TextColumn(),
            "単位": st.column_config.SelectboxColumn(options=UNITS),
            "冷蔵庫へ入れる": st.column_config.CheckboxColumn(
                help="生成時はすべて選択済みです。買わなかった物だけ外してください。"
            ),
        },
        key="shopping_editor",
    )

    if st.button("変更を保存", use_container_width=True):
        _save_shopping_editor(edited)
        st.success("買い物リストを保存しました。")
        st.rerun()

    st.markdown("### 買ったものをまとめて冷蔵庫へ")
    st.caption(
        "生成時は全商品が自動で選択済みです。買わなかった物だけチェックを外してください。購入日・保存場所・消費目安日は自動です。"
    )
    if st.button(
        "🧊 チェック中の商品を冷蔵庫へ一括追加",
        type="primary",
        use_container_width=True,
    ):
        updated = _save_shopping_editor(edited)
        added_count, skipped_count = _add_checked_items_to_inventory(updated)
        if added_count == 0:
            st.warning("冷蔵庫へ追加する商品がありません。数量を数字で入力してください。")
        else:
            remaining = updated[~updated["checked"].apply(_to_bool)]
            save_csv(remaining[SHOPPING_COLUMNS], SHOPPING_CSV)
            message = f"{added_count}件を冷蔵庫へ追加しました。"
            if skipped_count:
                message += f" 数量を読めない{skipped_count}件は残しました。"
            st.success(message)
            st.rerun()

    st.info(
        "運用ルール：冷蔵庫はまっさらな状態から開始し、以後はこの買い物画面から購入品を登録します。"
    )
    st.caption(
        "※ 日付は実物の期限ではなく消費目安です。パッケージ表示がある場合は冷蔵庫画面で上書きしてください。"
    )
