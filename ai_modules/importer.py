from __future__ import annotations

from datetime import date
from fractions import Fraction
from typing import Any

import pandas as pd

from data_store import (
    MEAL_PLAN_COLUMNS,
    MEAL_PLAN_CSV,
    SHOPPING_COLUMNS,
    SHOPPING_CSV,
    save_csv,
)
from ingredient_rules import canonical_name
from planner import load_meal_plan
from recipes import load_recipes, save_recipe
from shopping import load_shopping


def _find_existing_recipe_id(
    recipe_name: str,
    category: str,
) -> int | None:
    recipes = load_recipes()
    if recipes.empty:
        return None

    target = recipes[
        (recipes["recipe_name"].astype(str).str.strip() == recipe_name.strip())
        & (recipes["category"].astype(str).str.strip() == category.strip())
    ]
    if target.empty:
        return None

    try:
        return int(float(target.iloc[0]["recipe_id"]))
    except (TypeError, ValueError):
        return None


def _amount_number(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        try:
            return float(Fraction(text))
        except (ValueError, ZeroDivisionError):
            return None


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _merge_shopping_items(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0

    shopping = load_shopping()
    rows = shopping.to_dict("records") if not shopping.empty else []

    for item in items:
        name = canonical_name(item["name"])
        unit = str(item.get("unit", "")).strip()
        amount = str(item.get("amount", "")).strip()

        match_index = next(
            (
                index
                for index, row in enumerate(rows)
                if canonical_name(row.get("ingredient_name", "")) == name
                and str(row.get("unit", "")).strip() == unit
            ),
            None,
        )

        if match_index is None:
            rows.append(
                {
                    "ingredient_name": name,
                    "amount": amount,
                    "unit": unit,
                    "checked": True,
                }
            )
            continue

        old_amount = str(rows[match_index].get("amount", "")).strip()
        old_number = _amount_number(old_amount)
        new_number = _amount_number(amount)

        if old_number is not None and new_number is not None:
            rows[match_index]["amount"] = _format_number(
                old_number + new_number
            )
        elif amount and amount not in old_amount:
            rows[match_index]["amount"] = " + ".join(
                part for part in [old_amount, amount] if part
            )

        rows[match_index]["checked"] = True

    dataframe = pd.DataFrame(rows, columns=SHOPPING_COLUMNS)
    save_csv(dataframe, SHOPPING_CSV)
    return len(items)


def adopt_parsed_menu(
    parsed: dict[str, Any],
    target_date: date,
) -> dict[str, int]:
    """解析済み献立をレシピ・献立・買い物へ登録する。"""
    plan = load_meal_plan()
    target_text = target_date.isoformat()
    plan = plan[plan["date"].astype(str) != target_text].copy()

    plan_rows: list[dict[str, Any]] = []
    new_recipe_count = 0

    for item in parsed["menu"]:
        recipe_id = _find_existing_recipe_id(
            item["recipe_name"],
            item["category"],
        )

        ingredient_rows = [
            {
                "ingredient_name": ingredient["name"],
                "amount": ingredient["amount"],
                "unit": ingredient["unit"],
            }
            for ingredient in item["ingredients"]
        ]
        instructions = "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(
                item["instructions"],
                start=1,
            )
        )

        if recipe_id is None:
            recipe_id = save_recipe(
                None,
                item["recipe_name"],
                item["category"],
                item["cook_time"],
                ingredient_rows,
                item["seasonings"],
                instructions,
            )
            new_recipe_count += 1

        plan_rows.append(
            {
                "date": target_text,
                "category": item["category"],
                "recipe_id": recipe_id,
                "recipe_name": item["recipe_name"],
            }
        )

    plan = pd.concat(
        [plan, pd.DataFrame(plan_rows)],
        ignore_index=True,
    )
    plan["_date"] = pd.to_datetime(plan["date"], errors="coerce")
    plan["_order"] = plan["category"].map(
        {"主菜": 0, "副菜": 1, "汁物": 2}
    ).fillna(9)
    plan = plan.sort_values(["_date", "_order"]).drop(
        columns=["_date", "_order"]
    )
    save_csv(plan[MEAL_PLAN_COLUMNS], MEAL_PLAN_CSV)

    shopping_count = _merge_shopping_items(
        parsed.get("shopping", [])
    )

    return {
        "recipes": new_recipe_count,
        "shopping": shopping_count,
        "meals": 3,
    }