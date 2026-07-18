from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RECIPES_CSV = DATA_DIR / "recipes.csv"
INGREDIENTS_CSV = DATA_DIR / "recipe_ingredients.csv"
MEAL_PLAN_CSV = DATA_DIR / "meal_plan.csv"
INVENTORY_CSV = DATA_DIR / "inventory.csv"
SHOPPING_CSV = DATA_DIR / "shopping.csv"
SETTINGS_CSV = DATA_DIR / "settings.csv"

RECIPE_COLUMNS = [
    "recipe_id", "recipe_name", "category", "cook_time",
    "ingredients", "seasonings", "instructions",
]
INGREDIENT_COLUMNS = ["recipe_id", "ingredient_name", "amount", "unit"]
MEAL_PLAN_COLUMNS = ["date", "category", "recipe_id", "recipe_name"]
INVENTORY_COLUMNS = ["inventory_id", "ingredient_name", "amount", "unit", "expiry_date"]
SHOPPING_COLUMNS = ["ingredient_name", "amount", "unit", "checked"]
SETTING_COLUMNS = ["key", "value"]

DEFAULT_SETTINGS = {
    "wife_name": "望実",
    "husband_name": "佳明",
    "due_date": "2027-03-20",
    "people": "2",
    "shopping_cycle_days": "3",
    "rice_wife_g": "300",
    "rice_husband_g": "300",
}


def _migrate_legacy_files() -> None:
    """旧版でプロジェクト直下にあったCSVをdataフォルダへ自動移動する。"""
    for filename in [
        "recipes.csv",
        "recipe_ingredients.csv",
        "meal_plan.csv",
        "inventory.csv",
        "shopping.csv",
        "settings.csv",
    ]:
        old_path = BASE_DIR / filename
        new_path = DATA_DIR / filename
        if old_path.exists() and not new_path.exists():
            shutil.copy2(old_path, new_path)


def _ensure_csv(path: Path, columns: list[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


def initialize_data() -> None:
    _migrate_legacy_files()
    _ensure_csv(RECIPES_CSV, RECIPE_COLUMNS)
    _ensure_csv(INGREDIENTS_CSV, INGREDIENT_COLUMNS)
    _ensure_csv(MEAL_PLAN_CSV, MEAL_PLAN_COLUMNS)
    _ensure_csv(INVENTORY_CSV, INVENTORY_COLUMNS)
    _ensure_csv(SHOPPING_CSV, SHOPPING_COLUMNS)
    _ensure_csv(SETTINGS_CSV, SETTING_COLUMNS)

    settings = load_csv(SETTINGS_CSV, SETTING_COLUMNS)
    existing = set(settings["key"].astype(str)) if not settings.empty else set()
    missing = [{"key": k, "value": v} for k, v in DEFAULT_SETTINGS.items() if k not in existing]
    if missing:
        settings = pd.concat([settings, pd.DataFrame(missing)], ignore_index=True)
        save_csv(settings, SETTINGS_CSV)


def load_csv(path: Path, columns: list[str], dtype: object | None = None) -> pd.DataFrame:
    initialize_missing_only(path, columns)
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=dtype)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


def initialize_missing_only(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_csv(path, columns)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_settings() -> dict[str, str]:
    initialize_data()
    df = load_csv(SETTINGS_CSV, SETTING_COLUMNS, dtype=str).fillna("")
    result = DEFAULT_SETTINGS.copy()
    for _, row in df.iterrows():
        result[str(row["key"])] = str(row["value"])
    return result


def save_settings(values: dict[str, str]) -> None:
    rows = [{"key": key, "value": str(value)} for key, value in values.items()]
    save_csv(pd.DataFrame(rows, columns=SETTING_COLUMNS), SETTINGS_CSV)
