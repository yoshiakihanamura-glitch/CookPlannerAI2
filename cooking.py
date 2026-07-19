from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction
import unicodedata

import pandas as pd

from data_store import (
    COOK_LOG_COLUMNS,
    COOK_LOG_CSV,
    INVENTORY_COLUMNS,
    INVENTORY_CSV,
    load_csv,
    save_csv,
)
from ingredient_rules import canonical_name
from inventory import load_inventory
from planner import load_meal_plan
from recipes import get_recipe_ingredients


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


def load_cook_log() -> pd.DataFrame:
    return load_csv(COOK_LOG_CSV, COOK_LOG_COLUMNS, dtype=str).fillna("")


def today_is_cooked() -> bool:
    log = load_cook_log()
    if log.empty:
        return False
    return bool((log["date"].astype(str) == date.today().isoformat()).any())


def _consume_one_ingredient(
    inventory: pd.DataFrame,
    ingredient_name: str,
    required_amount: float,
    unit: str,
) -> tuple[pd.DataFrame, float]:
    """期限が近いロットから消費し、足りなかった量を返す。"""
    if inventory.empty:
        return inventory, required_amount

    work = inventory.copy()
    work["_canonical"] = work["ingredient_name"].apply(canonical_name)
    work["_amount_number"] = work["amount"].apply(_parse_amount)
    work["_expiry"] = pd.to_datetime(work["expiry_date"], errors="coerce")

    target_indices = work[
        (work["_canonical"] == canonical_name(ingredient_name))
        & (work["unit"].astype(str).str.strip() == str(unit).strip())
        & work["_amount_number"].notna()
        & (work["_amount_number"] > 0)
    ].sort_values(["_expiry", "purchase_date"], na_position="last").index.tolist()

    remaining_need = required_amount
    for index in target_indices:
        available = _parse_amount(work.at[index, "amount"])
        if available is None or available <= 0:
            continue
        used = min(available, remaining_need)
        new_amount = available - used
        work.at[index, "amount"] = _format_amount(new_amount)
        remaining_need -= used
        if remaining_need <= 1e-9:
            remaining_need = 0.0
            break

    work["_amount_number"] = work["amount"].apply(_parse_amount)
    work = work[
        work["_amount_number"].isna() | (work["_amount_number"] > 1e-9)
    ]
    return work[INVENTORY_COLUMNS].copy(), remaining_need


def cook_today_meal() -> dict[str, object]:
    """今日の献立を作った扱いにし、材料を冷蔵庫から自動で減らす。"""
    today = date.today().isoformat()
    plan = load_meal_plan()
    if plan.empty:
        return {"status": "no_plan", "message": "今日の献立がありません。"}

    today_plan = plan[plan["date"].astype(str) == today].copy()
    if today_plan.empty:
        return {"status": "no_plan", "message": "今日の献立がありません。"}

    log = load_cook_log()
    logged_ids = set(
        pd.to_numeric(
            log[log["date"].astype(str) == today]["recipe_id"],
            errors="coerce",
        ).dropna().astype(int)
    )

    today_plan["recipe_id_num"] = pd.to_numeric(
        today_plan["recipe_id"], errors="coerce"
    )
    pending_plan = today_plan[
        today_plan["recipe_id_num"].notna()
        & ~today_plan["recipe_id_num"].astype(int).isin(logged_ids)
    ]

    if pending_plan.empty:
        return {
            "status": "already_cooked",
            "message": "今日の献立はすでに『作った！』へ反映済みです。",
        }

    inventory = load_inventory()
    shortage_rows: list[dict[str, str]] = []
    consumed_rows: list[dict[str, str]] = []
    log_rows: list[dict[str, str]] = []

    for _, meal in pending_plan.iterrows():
        recipe_id = int(meal["recipe_id_num"])
        ingredients = get_recipe_ingredients(recipe_id)

        for _, item in ingredients.iterrows():
            amount = _parse_amount(item["amount"])
            name = canonical_name(item["ingredient_name"])
            unit = str(item["unit"]).strip()
            if not name or amount is None or amount <= 0:
                continue

            inventory, shortage = _consume_one_ingredient(
                inventory,
                ingredient_name=name,
                required_amount=amount,
                unit=unit,
            )
            used = max(amount - shortage, 0.0)
            if used > 0:
                consumed_rows.append(
                    {"ingredient_name": name, "amount": _format_amount(used), "unit": unit}
                )
            if shortage > 0:
                shortage_rows.append(
                    {"ingredient_name": name, "amount": _format_amount(shortage), "unit": unit}
                )

        log_rows.append(
            {
                "date": today,
                "recipe_id": str(recipe_id),
                "category": str(meal["category"]),
                "recipe_name": str(meal["recipe_name"]),
                "cooked_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    save_csv(inventory[INVENTORY_COLUMNS], INVENTORY_CSV)
    if log_rows:
        log = pd.concat([log, pd.DataFrame(log_rows)], ignore_index=True)
        save_csv(log[COOK_LOG_COLUMNS], COOK_LOG_CSV)

    return {
        "status": "success",
        "message": "今日の献立を調理済みにし、冷蔵庫の残量を更新しました。",
        "consumed": consumed_rows,
        "shortages": shortage_rows,
    }
