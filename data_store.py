from __future__ import annotations

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
COOK_LOG_CSV = DATA_DIR / "cook_log.csv"
SETTINGS_CSV = DATA_DIR / "settings.csv"

RECIPE_COLUMNS = [
    "recipe_id", "recipe_name", "category", "cook_time",
    "ingredients", "seasonings", "instructions",
]
INGREDIENT_COLUMNS = ["recipe_id", "ingredient_name", "amount", "unit"]
MEAL_PLAN_COLUMNS = ["date", "category", "recipe_id", "recipe_name"]
INVENTORY_COLUMNS = [
    "inventory_id",
    "ingredient_name",
    "amount",
    "unit",
    "expiry_date",
    "purchase_date",
    "storage_location",
    "note",
]
SHOPPING_COLUMNS = ["ingredient_name", "amount", "unit", "checked"]
COOK_LOG_COLUMNS = ["date", "recipe_id", "category", "recipe_name", "cooked_at"]
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


SEED_DIR = BASE_DIR / "seed"
SEED_RECIPES_CSV = SEED_DIR / "recipes.csv"
SEED_INGREDIENTS_CSV = SEED_DIR / "recipe_ingredients.csv"


def _merge_seed_recipes() -> None:
    """同梱された300レシピを既存データへ重複なしで追加する。"""
    if not SEED_RECIPES_CSV.exists() or not SEED_INGREDIENTS_CSV.exists():
        return

    current_recipes = load_csv(RECIPES_CSV, RECIPE_COLUMNS).fillna("")
    current_ingredients = load_csv(
        INGREDIENTS_CSV,
        INGREDIENT_COLUMNS,
        dtype=str,
    ).fillna("")
    seed_recipes = pd.read_csv(SEED_RECIPES_CSV, encoding="utf-8-sig").fillna("")
    seed_ingredients = pd.read_csv(
        SEED_INGREDIENTS_CSV,
        encoding="utf-8-sig",
        dtype=str,
    ).fillna("")

    existing_keys = {
        (str(row["recipe_name"]).strip(), str(row["category"]).strip())
        for _, row in current_recipes.iterrows()
    }
    current_ids = pd.to_numeric(
        current_recipes["recipe_id"],
        errors="coerce",
    ).dropna()
    next_id = 1 if current_ids.empty else int(current_ids.max()) + 1

    new_recipe_rows = []
    new_ingredient_rows = []
    seed_to_new_id: dict[int, int] = {}

    for _, recipe in seed_recipes.iterrows():
        key = (
            str(recipe["recipe_name"]).strip(),
            str(recipe["category"]).strip(),
        )
        if key in existing_keys:
            continue

        old_id = int(float(recipe["recipe_id"]))
        new_id = next_id
        next_id += 1
        seed_to_new_id[old_id] = new_id

        row = {column: recipe.get(column, "") for column in RECIPE_COLUMNS}
        row["recipe_id"] = new_id
        new_recipe_rows.append(row)
        existing_keys.add(key)

    for _, item in seed_ingredients.iterrows():
        old_id = int(float(item["recipe_id"]))
        if old_id not in seed_to_new_id:
            continue
        new_ingredient_rows.append(
            {
                "recipe_id": seed_to_new_id[old_id],
                "ingredient_name": str(item["ingredient_name"]).strip(),
                "amount": str(item["amount"]).strip(),
                "unit": str(item["unit"]).strip(),
            }
        )

    if new_recipe_rows:
        current_recipes = pd.concat(
            [current_recipes, pd.DataFrame(new_recipe_rows)],
            ignore_index=True,
        )
        save_csv(current_recipes[RECIPE_COLUMNS], RECIPES_CSV)

    if new_ingredient_rows:
        current_ingredients = pd.concat(
            [current_ingredients, pd.DataFrame(new_ingredient_rows)],
            ignore_index=True,
        )
        save_csv(current_ingredients[INGREDIENT_COLUMNS], INGREDIENTS_CSV)


def _migrate_legacy_files() -> None:
    """旧版でプロジェクト直下にあったCSVをdataフォルダへ自動コピーする。"""
    for filename in [
        "recipes.csv",
        "recipe_ingredients.csv",
        "meal_plan.csv",
        "inventory.csv",
        "shopping.csv",
        "cook_log.csv",
        "settings.csv",
    ]:
        old_path = BASE_DIR / filename
        new_path = DATA_DIR / filename
        if old_path.exists() and not new_path.exists():
            shutil.copy2(old_path, new_path)


def _ensure_csv(path: Path, columns: list[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )


def initialize_missing_only(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_csv(path, columns)


def load_csv(
    path: Path,
    columns: list[str],
    dtype: object | None = None,
) -> pd.DataFrame:
    initialize_missing_only(path, columns)

    try:
        dataframe = pd.read_csv(
            path,
            encoding="utf-8-sig",
            dtype=dtype,
        )
    except (pd.errors.EmptyDataError, FileNotFoundError):
        dataframe = pd.DataFrame(columns=columns)

    # 旧バージョンのCSVにも新しい列を自動追加する。
    for column in columns:
        if column not in dataframe.columns:
            dataframe[column] = ""

    return dataframe[columns]


def save_csv(dataframe: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


def initialize_data() -> None:
    _migrate_legacy_files()
    _ensure_csv(RECIPES_CSV, RECIPE_COLUMNS)
    _ensure_csv(INGREDIENTS_CSV, INGREDIENT_COLUMNS)
    _ensure_csv(MEAL_PLAN_CSV, MEAL_PLAN_COLUMNS)
    _ensure_csv(INVENTORY_CSV, INVENTORY_COLUMNS)
    _ensure_csv(SHOPPING_CSV, SHOPPING_COLUMNS)
    _ensure_csv(COOK_LOG_CSV, COOK_LOG_COLUMNS)
    _ensure_csv(SETTINGS_CSV, SETTING_COLUMNS)
    _merge_seed_recipes()

    settings = load_csv(
        SETTINGS_CSV,
        SETTING_COLUMNS,
        dtype=str,
    ).fillna("")

    existing = (
        set(settings["key"].astype(str))
        if not settings.empty
        else set()
    )

    missing = [
        {"key": key, "value": value}
        for key, value in DEFAULT_SETTINGS.items()
        if key not in existing
    ]

    if missing:
        settings = pd.concat(
            [settings, pd.DataFrame(missing)],
            ignore_index=True,
        )
        save_csv(settings, SETTINGS_CSV)


def load_settings() -> dict[str, str]:
    initialize_data()
    dataframe = load_csv(
        SETTINGS_CSV,
        SETTING_COLUMNS,
        dtype=str,
    ).fillna("")

    result = DEFAULT_SETTINGS.copy()

    for _, row in dataframe.iterrows():
        result[str(row["key"])] = str(row["value"])

    return result


def save_settings(values: dict[str, str]) -> None:
    rows = [
        {"key": key, "value": str(value)}
        for key, value in values.items()
    ]
    save_csv(
        pd.DataFrame(rows, columns=SETTING_COLUMNS),
        SETTINGS_CSV,
    )
