import os
import random
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


# ==================================================
# 基本設定
# ==================================================

RECIPES_CSV = "recipes.csv"
INGREDIENTS_CSV = "recipe_ingredients.csv"
MEAL_PLAN_CSV = "meal_plan.csv"

RECIPE_COLUMNS = [
    "recipe_id",
    "recipe_name",
    "category",
    "cook_time",
    "ingredients",
    "seasonings",
    "instructions",
]

INGREDIENT_COLUMNS = [
    "recipe_id",
    "ingredient_name",
    "amount",
    "unit",
]

MEAL_PLAN_COLUMNS = [
    "date",
    "category",
    "recipe_id",
    "recipe_name",
]

CATEGORIES = ["主菜", "副菜", "汁物", "その他"]

PLAN_CATEGORIES = ["主菜", "副菜", "汁物"]

UNITS = [
    "",
    "g",
    "kg",
    "ml",
    "L",
    "個",
    "本",
    "枚",
    "パック",
    "袋",
    "束",
    "片",
    "大さじ",
    "小さじ",
    "カップ",
    "適量",
    "少々",
]

MAX_INGREDIENTS = 10
SAME_RECIPE_INTERVAL_DAYS = 14


# ==================================================
# CSV初期化・読み込み
# ==================================================

def initialize_csv_files() -> None:
    if not os.path.exists(RECIPES_CSV):
        pd.DataFrame(columns=RECIPE_COLUMNS).to_csv(
            RECIPES_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    if not os.path.exists(INGREDIENTS_CSV):
        pd.DataFrame(columns=INGREDIENT_COLUMNS).to_csv(
            INGREDIENTS_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    if not os.path.exists(MEAL_PLAN_CSV):
        pd.DataFrame(columns=MEAL_PLAN_COLUMNS).to_csv(
            MEAL_PLAN_CSV,
            index=False,
            encoding="utf-8-sig",
        )


def load_csv(path: str, columns: list[str]) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(
            path,
            encoding="utf-8-sig",
        )
    except (pd.errors.EmptyDataError, FileNotFoundError):
        dataframe = pd.DataFrame(columns=columns)

    for column in columns:
        if column not in dataframe.columns:
            dataframe[column] = ""

    return dataframe[columns]


def load_recipes() -> pd.DataFrame:
    initialize_csv_files()
    return load_csv(RECIPES_CSV, RECIPE_COLUMNS)


def load_ingredients() -> pd.DataFrame:
    initialize_csv_files()

    dataframe = load_csv(
        INGREDIENTS_CSV,
        INGREDIENT_COLUMNS,
    )

    return dataframe.fillna("")


def load_meal_plan() -> pd.DataFrame:
    initialize_csv_files()
    return load_csv(MEAL_PLAN_CSV, MEAL_PLAN_COLUMNS)


def save_recipes(dataframe: pd.DataFrame) -> None:
    dataframe.to_csv(
        RECIPES_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def save_ingredients(dataframe: pd.DataFrame) -> None:
    dataframe.to_csv(
        INGREDIENTS_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def save_meal_plan(dataframe: pd.DataFrame) -> None:
    dataframe.to_csv(
        MEAL_PLAN_CSV,
        index=False,
        encoding="utf-8-sig",
    )


# ==================================================
# 共通処理
# ==================================================

def clean_text(value) -> str:
    if pd.isna(value):
        return ""

    return str(value)


def get_next_recipe_id(recipes: pd.DataFrame) -> int:
    if recipes.empty:
        return 1

    recipe_ids = pd.to_numeric(
        recipes["recipe_id"],
        errors="coerce",
    ).dropna()

    if recipe_ids.empty:
        return 1

    return int(recipe_ids.max()) + 1


def create_ingredient_summary(
    ingredient_rows: list[dict],
) -> str:
    lines = []

    for item in ingredient_rows:
        name = item["ingredient_name"].strip()
        amount = item["amount"].strip()
        unit = item["unit"].strip()

        if not name:
            continue

        quantity = f"{amount}{unit}".strip()

        if quantity:
            lines.append(f"{name} {quantity}")
        else:
            lines.append(name)

    return "\n".join(lines)


def get_recipe_ingredients(
    recipe_id: int,
) -> pd.DataFrame:
    ingredients = load_ingredients()

    recipe_ids = pd.to_numeric(
        ingredients["recipe_id"],
        errors="coerce",
    )

    return ingredients[
        recipe_ids == recipe_id
    ].reset_index(drop=True)


# ==================================================
# レシピ登録・更新・削除
# ==================================================

def add_recipe(
    recipe_name: str,
    category: str,
    cook_time: int,
    ingredient_rows: list[dict],
    seasonings: str,
    instructions: str,
) -> None:
    recipes = load_recipes()
    ingredients = load_ingredients()

    recipe_id = get_next_recipe_id(recipes)

    new_recipe = {
        "recipe_id": recipe_id,
        "recipe_name": recipe_name,
        "category": category,
        "cook_time": cook_time,
        "ingredients": create_ingredient_summary(
            ingredient_rows
        ),
        "seasonings": seasonings,
        "instructions": instructions,
    }

    recipes = pd.concat(
        [
            recipes,
            pd.DataFrame([new_recipe]),
        ],
        ignore_index=True,
    )

    new_ingredients = []

    for item in ingredient_rows:
        ingredient_name = (
            item["ingredient_name"].strip()
        )

        if not ingredient_name:
            continue

        new_ingredients.append(
            {
                "recipe_id": recipe_id,
                "ingredient_name": ingredient_name,
                "amount": item["amount"].strip(),
                "unit": item["unit"].strip(),
            }
        )

    if new_ingredients:
        ingredients = pd.concat(
            [
                ingredients,
                pd.DataFrame(new_ingredients),
            ],
            ignore_index=True,
        )

    save_recipes(recipes)
    save_ingredients(ingredients)


def update_recipe(
    recipe_id: int,
    recipe_name: str,
    category: str,
    cook_time: int,
    ingredient_rows: list[dict],
    seasonings: str,
    instructions: str,
) -> None:
    recipes = load_recipes()
    ingredients = load_ingredients()

    recipe_ids = pd.to_numeric(
        recipes["recipe_id"],
        errors="coerce",
    )

    target = recipe_ids == recipe_id

    recipes.loc[target, "recipe_name"] = recipe_name
    recipes.loc[target, "category"] = category
    recipes.loc[target, "cook_time"] = cook_time
    recipes.loc[target, "ingredients"] = (
        create_ingredient_summary(ingredient_rows)
    )
    recipes.loc[target, "seasonings"] = seasonings
    recipes.loc[target, "instructions"] = instructions

    ingredient_recipe_ids = pd.to_numeric(
        ingredients["recipe_id"],
        errors="coerce",
    )

    ingredients = ingredients[
        ingredient_recipe_ids != recipe_id
    ]

    new_ingredients = []

    for item in ingredient_rows:
        ingredient_name = (
            item["ingredient_name"].strip()
        )

        if not ingredient_name:
            continue

        new_ingredients.append(
            {
                "recipe_id": recipe_id,
                "ingredient_name": ingredient_name,
                "amount": item["amount"].strip(),
                "unit": item["unit"].strip(),
            }
        )

    if new_ingredients:
        ingredients = pd.concat(
            [
                ingredients,
                pd.DataFrame(new_ingredients),
            ],
            ignore_index=True,
        )

    save_recipes(recipes)
    save_ingredients(ingredients)


def delete_recipe(recipe_id: int) -> None:
    recipes = load_recipes()
    ingredients = load_ingredients()
    meal_plan = load_meal_plan()

    recipe_ids = pd.to_numeric(
        recipes["recipe_id"],
        errors="coerce",
    )

    ingredient_recipe_ids = pd.to_numeric(
        ingredients["recipe_id"],
        errors="coerce",
    )

    plan_recipe_ids = pd.to_numeric(
        meal_plan["recipe_id"],
        errors="coerce",
    )

    recipes = recipes[recipe_ids != recipe_id]

    ingredients = ingredients[
        ingredient_recipe_ids != recipe_id
    ]

    meal_plan = meal_plan[
        plan_recipe_ids != recipe_id
    ]

    save_recipes(recipes)
    save_ingredients(ingredients)
    save_meal_plan(meal_plan)


# ==================================================
# 材料入力画面
# ==================================================

def show_ingredient_inputs(
    prefix: str,
    existing_rows: list[dict] | None = None,
) -> None:
    existing_rows = existing_rows or []

    st.markdown("#### 材料・分量")

    header_name, header_amount, header_unit = (
        st.columns([3, 1.3, 1.3])
    )

    header_name.markdown("**食材名**")
    header_amount.markdown("**分量**")
    header_unit.markdown("**単位**")

    for index in range(MAX_INGREDIENTS):
        if index < len(existing_rows):
            current = existing_rows[index]
        else:
            current = {
                "ingredient_name": "",
                "amount": "",
                "unit": "",
            }

        name_value = clean_text(
            current.get("ingredient_name", "")
        )

        amount_value = clean_text(
            current.get("amount", "")
        )

        unit_value = clean_text(
            current.get("unit", "")
        )

        unit_index = (
            UNITS.index(unit_value)
            if unit_value in UNITS
            else 0
        )

        col_name, col_amount, col_unit = st.columns(
            [3, 1.3, 1.3]
        )

        with col_name:
            st.text_input(
                f"食材名{index + 1}",
                value=name_value,
                placeholder="例：鶏むね肉",
                key=f"{prefix}_name_{index}",
                label_visibility="collapsed",
            )

        with col_amount:
            st.text_input(
                f"分量{index + 1}",
                value=amount_value,
                placeholder="例：300",
                key=f"{prefix}_amount_{index}",
                label_visibility="collapsed",
            )

        with col_unit:
            st.selectbox(
                f"単位{index + 1}",
                UNITS,
                index=unit_index,
                key=f"{prefix}_unit_{index}",
                label_visibility="collapsed",
            )


def collect_ingredient_rows(
    prefix: str,
) -> list[dict]:
    rows = []

    for index in range(MAX_INGREDIENTS):
        rows.append(
            {
                "ingredient_name":
                    st.session_state.get(
                        f"{prefix}_name_{index}",
                        "",
                    ),
                "amount":
                    st.session_state.get(
                        f"{prefix}_amount_{index}",
                        "",
                    ),
                "unit":
                    st.session_state.get(
                        f"{prefix}_unit_{index}",
                        "",
                    ),
            }
        )

    return rows


# ==================================================
# 30日献立生成
# ==================================================

def choose_recipe(
    category_recipes: pd.DataFrame,
    current_day: int,
    history: dict[int, list[int]],
    use_counts: dict[int, int],
) -> dict | None:
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

    for _, recipe in candidates.iterrows():
        recipe_id = int(recipe["recipe_id"])
        used_days = history.get(recipe_id, [])

        recently_used = any(
            current_day - used_day
            < SAME_RECIPE_INTERVAL_DAYS
            for used_day in used_days
        )

        if not recently_used:
            allowed_rows.append(recipe)

    if allowed_rows:
        candidates = pd.DataFrame(allowed_rows)

    fast_recipes = candidates[
        candidates["cook_time"] <= 30
    ]

    if not fast_recipes.empty:
        candidates = fast_recipes

    minimum_use_count = min(
        use_counts.get(
            int(recipe_id),
            0,
        )
        for recipe_id in candidates["recipe_id"]
    )

    candidates = candidates[
        candidates["recipe_id"].apply(
            lambda recipe_id:
                use_counts.get(
                    int(recipe_id),
                    0,
                )
                == minimum_use_count
        )
    ]

    selected_index = random.choice(
        candidates.index.tolist()
    )

    return candidates.loc[selected_index].to_dict()


def generate_meal_plan(
    start_date: date,
    number_of_days: int = 30,
) -> pd.DataFrame:
    recipes = load_recipes()

    history: dict[int, list[int]] = {}
    use_counts: dict[int, int] = {}
    plan_rows = []

    for day_number in range(number_of_days):
        plan_date = start_date + timedelta(
            days=day_number
        )

        for category in PLAN_CATEGORIES:
            category_recipes = recipes[
                recipes["category"] == category
            ]

            selected = choose_recipe(
                category_recipes=category_recipes,
                current_day=day_number,
                history=history,
                use_counts=use_counts,
            )

            if selected is None:
                plan_rows.append(
                    {
                        "date": plan_date.isoformat(),
                        "category": category,
                        "recipe_id": "",
                        "recipe_name": "未登録",
                    }
                )
                continue

            recipe_id = int(selected["recipe_id"])

            plan_rows.append(
                {
                    "date": plan_date.isoformat(),
                    "category": category,
                    "recipe_id": recipe_id,
                    "recipe_name":
                        clean_text(
                            selected["recipe_name"]
                        ),
                }
            )

            history.setdefault(
                recipe_id,
                [],
            ).append(day_number)

            use_counts[recipe_id] = (
                use_counts.get(recipe_id, 0) + 1
            )

    return pd.DataFrame(
        plan_rows,
        columns=MEAL_PLAN_COLUMNS,
    )


def create_plan_table(
    meal_plan: pd.DataFrame,
) -> pd.DataFrame:
    if meal_plan.empty:
        return pd.DataFrame()

    table = meal_plan.pivot(
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


# ==================================================
# 画面
# ==================================================

st.set_page_config(
    page_title="CookPlanner AI",
    page_icon="🍳",
    layout="wide",
)

initialize_csv_files()

st.title("🍳 CookPlanner AI")
st.caption("レシピ登録・30日献立作成アプリ")

tab_register, tab_list, tab_plan = st.tabs(
    [
        "レシピ登録",
        "登録済みレシピ",
        "30日献立",
    ]
)


# ==================================================
# レシピ登録タブ
# ==================================================

with tab_register:
    st.subheader("新しいレシピを登録")

    with st.form(
        "recipe_form",
        clear_on_submit=True,
    ):
        recipe_name = st.text_input("料理名")

        col_category, col_time = st.columns(2)

        with col_category:
            category = st.selectbox(
                "カテゴリ",
                CATEGORIES,
            )

        with col_time:
            cook_time = st.number_input(
                "調理時間（分）",
                min_value=1,
                max_value=180,
                value=30,
                step=1,
            )

        show_ingredient_inputs("register")

        seasonings = st.text_area(
            "調味料",
        )

        instructions = st.text_area(
            "作り方",
            height=180,
        )

        submitted = st.form_submit_button(
            "🍳 レシピを登録する",
            use_container_width=True,
        )

    if submitted:
        ingredient_rows = collect_ingredient_rows(
            "register"
        )

        valid_ingredients = [
            item
            for item in ingredient_rows
            if item["ingredient_name"].strip()
        ]

        if not recipe_name.strip():
            st.error("料理名を入力してください。")

        elif not valid_ingredients:
            st.error(
                "材料を1つ以上入力してください。"
            )

        elif not instructions.strip():
            st.error(
                "作り方を入力してください。"
            )

        else:
            add_recipe(
                recipe_name=recipe_name.strip(),
                category=category,
                cook_time=int(cook_time),
                ingredient_rows=ingredient_rows,
                seasonings=seasonings.strip(),
                instructions=instructions.strip(),
            )

            st.success(
                f"「{recipe_name}」を登録しました！"
            )


# ==================================================
# 登録済みレシピタブ
# ==================================================

with tab_list:
    st.subheader("登録済みレシピ")

    recipes = load_recipes()

    if recipes.empty:
        st.info(
            "まだレシピは登録されていません。"
        )

    else:
        col_search, col_category = st.columns(2)

        with col_search:
            search_text = st.text_input(
                "料理名・材料で検索",
                placeholder="例：鶏、鮭、豆腐",
            )

        with col_category:
            category_filter = st.selectbox(
                "カテゴリで絞り込み",
                ["すべて"] + CATEGORIES,
            )

        filtered_recipes = recipes.copy()

        if search_text.strip():
            keyword = search_text.strip()

            name_match = (
                filtered_recipes["recipe_name"]
                .astype(str)
                .str.contains(
                    keyword,
                    case=False,
                    na=False,
                )
            )

            ingredient_match = (
                filtered_recipes["ingredients"]
                .astype(str)
                .str.contains(
                    keyword,
                    case=False,
                    na=False,
                )
            )

            filtered_recipes = filtered_recipes[
                name_match | ingredient_match
            ]

        if category_filter != "すべて":
            filtered_recipes = filtered_recipes[
                filtered_recipes["category"]
                == category_filter
            ]

        st.write(
            f"表示件数：{len(filtered_recipes)}件"
        )

        for _, recipe in (
            filtered_recipes.iloc[::-1].iterrows()
        ):
            recipe_id = int(
                float(recipe["recipe_id"])
            )

            recipe_name_value = clean_text(
                recipe["recipe_name"]
            )

            category_value = clean_text(
                recipe["category"]
            )

            cook_time_value = int(
                float(recipe["cook_time"])
            )

            seasonings_value = clean_text(
                recipe["seasonings"]
            )

            instructions_value = clean_text(
                recipe["instructions"]
            )

            recipe_ingredients = (
                get_recipe_ingredients(recipe_id)
            )

            title = (
                f"{recipe_name_value}｜"
                f"{category_value}｜"
                f"{cook_time_value}分"
            )

            with st.expander(title):
                st.markdown("### 材料・分量")

                existing_rows = []

                for _, item in (
                    recipe_ingredients.iterrows()
                ):
                    ingredient_name = clean_text(
                        item["ingredient_name"]
                    )
                    amount = clean_text(
                        item["amount"]
                    )
                    unit = clean_text(
                        item["unit"]
                    )

                    existing_rows.append(
                        {
                            "ingredient_name":
                                ingredient_name,
                            "amount": amount,
                            "unit": unit,
                        }
                    )

                    st.write(
                        f"・{ingredient_name}："
                        f"{amount}{unit}"
                    )

                st.markdown("### 調味料")
                st.text(
                    seasonings_value or "未登録"
                )

                st.markdown("### 作り方")
                st.text(
                    instructions_value or "未登録"
                )

                st.divider()
                st.markdown("### レシピを編集")

                with st.form(
                    f"edit_form_{recipe_id}"
                ):
                    edited_name = st.text_input(
                        "料理名",
                        value=recipe_name_value,
                        key=f"edit_name_{recipe_id}",
                    )

                    col_edit_category, col_edit_time = (
                        st.columns(2)
                    )

                    category_index = (
                        CATEGORIES.index(
                            category_value
                        )
                        if category_value
                        in CATEGORIES
                        else 0
                    )

                    with col_edit_category:
                        edited_category = st.selectbox(
                            "カテゴリ",
                            CATEGORIES,
                            index=category_index,
                            key=(
                                f"edit_category_"
                                f"{recipe_id}"
                            ),
                        )

                    with col_edit_time:
                        edited_cook_time = (
                            st.number_input(
                                "調理時間（分）",
                                min_value=1,
                                max_value=180,
                                value=cook_time_value,
                                step=1,
                                key=(
                                    f"edit_time_"
                                    f"{recipe_id}"
                                ),
                            )
                        )

                    show_ingredient_inputs(
                        prefix=f"edit_{recipe_id}",
                        existing_rows=existing_rows,
                    )

                    edited_seasonings = st.text_area(
                        "調味料",
                        value=seasonings_value,
                        key=(
                            f"edit_seasonings_"
                            f"{recipe_id}"
                        ),
                    )

                    edited_instructions = st.text_area(
                        "作り方",
                        value=instructions_value,
                        height=180,
                        key=(
                            f"edit_instructions_"
                            f"{recipe_id}"
                        ),
                    )

                    update_clicked = (
                        st.form_submit_button(
                            "変更を保存する",
                            use_container_width=True,
                        )
                    )

                if update_clicked:
                    edited_ingredients = (
                        collect_ingredient_rows(
                            f"edit_{recipe_id}"
                        )
                    )

                    valid_ingredients = [
                        item
                        for item in edited_ingredients
                        if item[
                            "ingredient_name"
                        ].strip()
                    ]

                    if not edited_name.strip():
                        st.error(
                            "料理名を入力してください。"
                        )

                    elif not valid_ingredients:
                        st.error(
                            "材料を1つ以上"
                            "入力してください。"
                        )

                    elif not (
                        edited_instructions.strip()
                    ):
                        st.error(
                            "作り方を入力してください。"
                        )

                    else:
                        update_recipe(
                            recipe_id=recipe_id,
                            recipe_name=(
                                edited_name.strip()
                            ),
                            category=edited_category,
                            cook_time=int(
                                edited_cook_time
                            ),
                            ingredient_rows=(
                                edited_ingredients
                            ),
                            seasonings=(
                                edited_seasonings.strip()
                            ),
                            instructions=(
                                edited_instructions.strip()
                            ),
                        )

                        st.success(
                            "レシピを更新しました！"
                        )
                        st.rerun()

                st.divider()

                delete_clicked = st.button(
                    "このレシピを削除する",
                    key=f"delete_{recipe_id}",
                )

                if delete_clicked:
                    delete_recipe(recipe_id)

                    st.success(
                        f"「{recipe_name_value}」"
                        "を削除しました。"
                    )

                    st.rerun()


# ==================================================
# 30日献立タブ
# ==================================================

with tab_plan:
    st.subheader("30日分の献立を作成")

    recipes = load_recipes()

    category_counts = (
        recipes["category"]
        .value_counts()
        .to_dict()
    )

    col_main, col_side, col_soup = st.columns(3)

    col_main.metric(
        "主菜",
        f"{category_counts.get('主菜', 0)}件",
    )

    col_side.metric(
        "副菜",
        f"{category_counts.get('副菜', 0)}件",
    )

    col_soup.metric(
        "汁物",
        f"{category_counts.get('汁物', 0)}件",
    )

    missing_categories = [
        category
        for category in PLAN_CATEGORIES
        if category_counts.get(category, 0) == 0
    ]

    if missing_categories:
        st.warning(
            "次のカテゴリにレシピがありません："
            + "、".join(missing_categories)
            + "。該当部分は「未登録」になります。"
        )

    start_date = st.date_input(
        "献立の開始日",
        value=date.today(),
    )

    generate_clicked = st.button(
        "📅 30日分の献立を生成する",
        type="primary",
        use_container_width=True,
    )

    if generate_clicked:
        new_plan = generate_meal_plan(
            start_date=start_date,
            number_of_days=30,
        )

        save_meal_plan(new_plan)

        st.success(
            "30日分の献立を作成しました！"
        )

        st.rerun()

    meal_plan = load_meal_plan()

    if meal_plan.empty:
        st.info(
            "まだ献立がありません。"
            "上のボタンから生成してください。"
        )

    else:
        plan_table = create_plan_table(
            meal_plan
        )

        st.markdown("### 作成済みの献立")
        st.dataframe(
            plan_table,
            use_container_width=True,
            hide_index=True,
        )