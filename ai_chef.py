from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from data_store import (
    BASE_DIR,
    MEAL_PLAN_COLUMNS,
    MEAL_PLAN_CSV,
    SHOPPING_COLUMNS,
    SHOPPING_CSV,
    load_csv,
    load_settings,
    save_csv,
)
from ingredient_rules import canonical_name
from inventory import load_inventory
from planner import load_meal_plan
from recipes import load_recipes, save_recipe
from shopping import load_shopping

AI_RESPONSES_CSV = Path(BASE_DIR) / "data" / "ai_responses.csv"
AI_RESPONSE_COLUMNS = ["saved_at", "target_date", "prompt", "response"]
AI_CATEGORIES = ["主菜", "副菜", "汁物"]
KNOWN_UNITS = [
    "大さじ", "小さじ", "カップ", "パック", "適量", "少々",
    "kg", "ml", "g", "L", "個", "本", "枚", "袋", "束", "片", "丁",
]


def _pregnancy_week(due_date_text: str) -> str:
    try:
        due_date = datetime.strptime(due_date_text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "不明"
    start = due_date - timedelta(days=280)
    elapsed = (date.today() - start).days
    if elapsed < 0:
        return "妊娠前"
    return f"{elapsed // 7}週{elapsed % 7}日"


def _inventory_text() -> str:
    inventory = load_inventory()
    if inventory.empty:
        return "- 冷蔵庫に登録された食材はありません"
    work = inventory.copy()
    work["_expiry"] = pd.to_datetime(work["expiry_date"], errors="coerce")
    work = work.sort_values("_expiry", na_position="last")
    lines: list[str] = []
    for _, row in work.iterrows():
        expiry = str(row.get("expiry_date", "")).strip() or "未設定"
        storage = str(row.get("storage_location", "")).strip() or "未設定"
        note = str(row.get("note", "")).strip()
        line = (
            f"- {row['ingredient_name']}：{row['amount']}{row['unit']}"
            f"（保存場所：{storage}、消費目安：{expiry}）"
        )
        if note:
            line += f"／メモ：{note}"
        lines.append(line)
    return "\n".join(lines)


def _urgent_inventory_text() -> str:
    inventory = load_inventory()
    if inventory.empty:
        return "- なし"
    work = inventory.copy()
    work["_expiry"] = pd.to_datetime(work["expiry_date"], errors="coerce")
    work["_days"] = (work["_expiry"] - pd.Timestamp(date.today())).dt.days
    urgent = work[work["_days"].notna() & (work["_days"] <= 3)].sort_values("_days")
    if urgent.empty:
        return "- なし"
    lines: list[str] = []
    for _, row in urgent.iterrows():
        days = int(row["_days"])
        label = "期限切れ" if days < 0 else ("今日まで" if days == 0 else f"あと{days}日")
        lines.append(f"- {row['ingredient_name']}：{row['amount']}{row['unit']}（{label}）")
    return "\n".join(lines)


def _recent_meals_text(days: int = 14) -> str:
    plan = load_meal_plan()
    if plan.empty:
        return "- 履歴なし"
    work = plan.copy()
    work["_date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["_date"]).sort_values("_date", ascending=False)
    recent_dates = work["date"].drop_duplicates().head(days)
    work = work[work["date"].isin(recent_dates)]
    if work.empty:
        return "- 履歴なし"
    lines: list[str] = []
    for meal_date, group in work.groupby("date", sort=False):
        parts: list[str] = []
        for category in AI_CATEGORIES:
            row = group[group["category"] == category]
            if not row.empty:
                parts.append(f"{category}：{row.iloc[0]['recipe_name']}")
        lines.append(f"- {meal_date}｜" + "／".join(parts))
    return "\n".join(lines)


def build_prompt(
    cuisine: list[str],
    taste: list[str],
    max_minutes: int,
    max_extra_items: int,
    budget: int,
    extra_request: str,
) -> str:
    settings = load_settings()
    people = settings.get("people", "2")
    due_date = settings.get("due_date", "未設定")
    shopping_cycle = settings.get("shopping_cycle_days", "3")
    rice_wife = settings.get("rice_wife_g", "300")
    rice_husband = settings.get("rice_husband_g", "300")
    cuisine_text = "・".join(cuisine) if cuisine else "指定なし。食材に最も合うもの"
    taste_text = "・".join(taste) if taste else "指定なし。献立全体のバランスを優先"

    return f"""あなたは日本の家庭料理に詳しい料理研究家兼、妊娠中の食事を安全面から補助する献立アシスタントです。
冷蔵庫の現実の在庫を最優先し、料理名だけを機械的に合成せず、一般的に成立して本当においしい夕食を考えてください。

【家族】
- {people}人分
- 出産予定日：{due_date}
- 現在：妊娠{_pregnancy_week(due_date)}
- 妻の白米：{rice_wife}g、夫の白米：{rice_husband}g

【妊娠中の安全条件】
- レバー、ハツ、鶏モツは使わない
- 生肉、生魚、生卵、生ハムなど非加熱食品は避ける
- 肉・魚・卵は中心まで十分に加熱する
- アルコールを使う場合は十分に加熱して飛ばす
- 不確かな食材は、より安全な代替案を選ぶ

【現在の冷蔵庫】
{_inventory_text()}

【優先して使い切りたい食材】
{_urgent_inventory_text()}

【直近14日間の献立】
{_recent_meals_text(14)}

【条件】
- 買い物周期：{shopping_cycle}日ごと
- 追加購入予算：目安{budget}円以内
- 夕食全体を{max_minutes}分以内で完成
- 買い足しは最大{max_extra_items}品
- 料理ジャンル：{cuisine_text}
- 味・気分：{taste_text}
- 冷蔵庫の食材と期限を優先する
- 直近14日以内と同じ料理は原則避ける
- 同じ肉・魚・卵料理が続かないようにする
- 主菜1品、副菜1品、汁物1品
- 味付け・食感・調理法を3品で重複させすぎない
- 初心者にも分かる手順にする
- 基本調味料は家庭にある前提でよい
- 追加の希望：{extra_request.strip() or '特になし'}

【重要】
返答は説明文やMarkdownを付けず、下記のJSONだけを返してください。JSONのキー名は絶対に変えないでください。
材料のamountは数量だけ、unitは単位だけに分けてください。数量が曖昧な場合も「1/2」「適量」のように文字列で記載してください。

{{
  "summary": "献立全体のねらい",
  "safety": "妊娠中の安全確認",
  "parallel_steps": ["同時進行手順1", "同時進行手順2", "同時進行手順3"],
  "menu": [
    {{
      "category": "主菜",
      "recipe_name": "料理名",
      "cook_time": 20,
      "ingredients": [
        {{"name": "食材名", "amount": "300", "unit": "g", "from_inventory": true}}
      ],
      "seasonings": "調味料をまとめて記載",
      "instructions": ["手順1", "手順2", "十分加熱する手順"]
    }},
    {{"category": "副菜", "recipe_name": "料理名", "cook_time": 10, "ingredients": [], "seasonings": "", "instructions": []}},
    {{"category": "汁物", "recipe_name": "料理名", "cook_time": 10, "ingredients": [], "seasonings": "", "instructions": []}}
  ],
  "shopping": [
    {{"name": "買い足す食材名", "amount": "1", "unit": "袋"}}
  ],
  "inventory_after": [
    {{"name": "食材名", "amount": "残る数量", "unit": "g"}}
  ]
}}

最後に、提案した料理名と材料の組み合わせが一般的な料理として自然に成立するか自分で再確認してください。肉を使わない料理に「生姜焼き」と名付けるような不自然な料理は禁止です。"""


def _clipboard_button(text: str) -> None:
    escaped = html.escape(text)
    components.html(
        f"""
        <textarea id="copy-source" style="position:absolute;left:-9999px;top:-9999px;">{escaped}</textarea>
        <button onclick="copyPrompt()" style="
            width:100%;padding:0.75rem 1rem;border:0;border-radius:0.5rem;
            background:#ff4b4b;color:white;font-size:1rem;font-weight:700;cursor:pointer;">
            📋 ChatGPT用プロンプトをコピー
        </button>
        <div id="copy-result" style="margin-top:0.45rem;font-family:sans-serif;font-size:0.9rem;"></div>
        <script>
        async function copyPrompt() {{
            const text = document.getElementById('copy-source').value;
            const result = document.getElementById('copy-result');
            try {{
                await navigator.clipboard.writeText(text);
                result.textContent = 'コピーしました。ChatGPTへ貼り付けてください。';
                result.style.color = '#138a36';
            }} catch (error) {{
                const source = document.getElementById('copy-source');
                source.style.position = 'static';
                source.style.width = '100%';
                source.style.height = '120px';
                source.select();
                document.execCommand('copy');
                source.style.position = 'absolute';
                result.textContent = 'コピーしました。';
                result.style.color = '#138a36';
            }}
        }}
        </script>
        """,
        height=90,
    )


def _load_responses() -> pd.DataFrame:
    if not AI_RESPONSES_CSV.exists():
        return pd.DataFrame(columns=AI_RESPONSE_COLUMNS)
    try:
        dataframe = pd.read_csv(AI_RESPONSES_CSV, encoding="utf-8-sig", dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        dataframe = pd.DataFrame(columns=AI_RESPONSE_COLUMNS)
    for column in AI_RESPONSE_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""
    return dataframe[AI_RESPONSE_COLUMNS]


def _save_response(prompt: str, response: str, target_date: date) -> None:
    history = _load_responses()
    row = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "target_date": target_date.isoformat(),
        "prompt": prompt,
        "response": response.strip(),
    }
    history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
    history.to_csv(AI_RESPONSES_CSV, index=False, encoding="utf-8-sig")


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _normalize_ingredient(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    name = canonical_name(str(item.get("name", "")).strip())
    if not name:
        return None
    return {
        "name": name,
        "amount": str(item.get("amount", "")).strip(),
        "unit": str(item.get("unit", "")).strip(),
        "from_inventory": bool(item.get("from_inventory", False)),
    }


def parse_ai_response(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(_clean_json_text(text))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "回答を読み取れませんでした。新しいプロンプトでChatGPTに作り直し、JSONを丸ごと貼ってください。"
        ) from exc
    if not isinstance(raw, dict):
        raise ValueError("回答の形式が正しくありません。")

    menu = raw.get("menu")
    if not isinstance(menu, list):
        raise ValueError("menuが見つかりません。")
    normalized_menu: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in menu:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        if category not in AI_CATEGORIES or category in seen:
            continue
        recipe_name = str(item.get("recipe_name", "")).strip()
        if not recipe_name:
            raise ValueError(f"{category}の料理名がありません。")
        try:
            cook_time = int(float(item.get("cook_time", 30)))
        except (TypeError, ValueError):
            cook_time = 30
        ingredients = [
            normalized
            for value in (item.get("ingredients") or [])
            if (normalized := _normalize_ingredient(value)) is not None
        ]
        instructions_raw = item.get("instructions") or []
        if isinstance(instructions_raw, str):
            instructions = [line.strip() for line in instructions_raw.splitlines() if line.strip()]
        else:
            instructions = [str(line).strip() for line in instructions_raw if str(line).strip()]
        normalized_menu.append({
            "category": category,
            "recipe_name": recipe_name,
            "cook_time": max(1, cook_time),
            "ingredients": ingredients,
            "seasonings": str(item.get("seasonings", "")).strip(),
            "instructions": instructions,
        })
        seen.add(category)
    if seen != set(AI_CATEGORIES):
        raise ValueError("主菜・副菜・汁物を1品ずつ読み取れませんでした。")
    normalized_menu.sort(key=lambda row: AI_CATEGORIES.index(row["category"]))

    shopping = [
        normalized
        for value in (raw.get("shopping") or [])
        if (normalized := _normalize_ingredient(value)) is not None
    ]
    inventory_after = [
        normalized
        for value in (raw.get("inventory_after") or [])
        if (normalized := _normalize_ingredient(value)) is not None
    ]
    parallel_raw = raw.get("parallel_steps") or []
    parallel_steps = (
        [line.strip() for line in parallel_raw.splitlines() if line.strip()]
        if isinstance(parallel_raw, str)
        else [str(line).strip() for line in parallel_raw if str(line).strip()]
    )
    return {
        "summary": str(raw.get("summary", "")).strip(),
        "safety": str(raw.get("safety", "")).strip(),
        "parallel_steps": parallel_steps,
        "menu": normalized_menu,
        "shopping": shopping,
        "inventory_after": inventory_after,
    }


def _find_existing_recipe_id(recipe_name: str, category: str) -> int | None:
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
            rows.append({"ingredient_name": name, "amount": amount, "unit": unit, "checked": True})
            continue
        old_amount = str(rows[match_index].get("amount", "")).strip()
        old_number = _amount_number(old_amount)
        new_number = _amount_number(amount)
        if old_number is not None and new_number is not None:
            rows[match_index]["amount"] = _format_number(old_number + new_number)
        elif amount and amount not in old_amount:
            rows[match_index]["amount"] = " + ".join(part for part in [old_amount, amount] if part)
        rows[match_index]["checked"] = True
    dataframe = pd.DataFrame(rows, columns=SHOPPING_COLUMNS)
    save_csv(dataframe, SHOPPING_CSV)
    return len(items)


def adopt_parsed_menu(parsed: dict[str, Any], target_date: date) -> dict[str, int]:
    plan = load_meal_plan()
    target_text = target_date.isoformat()
    plan = plan[plan["date"].astype(str) != target_text].copy()
    plan_rows: list[dict[str, Any]] = []
    new_recipe_count = 0

    for item in parsed["menu"]:
        recipe_id = _find_existing_recipe_id(item["recipe_name"], item["category"])
        rows = [
            {
                "ingredient_name": ingredient["name"],
                "amount": ingredient["amount"],
                "unit": ingredient["unit"],
            }
            for ingredient in item["ingredients"]
        ]
        instructions = "\n".join(
            f"{index}. {step}" for index, step in enumerate(item["instructions"], start=1)
        )
        if recipe_id is None:
            recipe_id = save_recipe(
                None,
                item["recipe_name"],
                item["category"],
                item["cook_time"],
                rows,
                item["seasonings"],
                instructions,
            )
            new_recipe_count += 1
        plan_rows.append({
            "date": target_text,
            "category": item["category"],
            "recipe_id": recipe_id,
            "recipe_name": item["recipe_name"],
        })

    plan = pd.concat([plan, pd.DataFrame(plan_rows)], ignore_index=True)
    plan["_date"] = pd.to_datetime(plan["date"], errors="coerce")
    plan["_order"] = plan["category"].map({"主菜": 0, "副菜": 1, "汁物": 2}).fillna(9)
    plan = plan.sort_values(["_date", "_order"]).drop(columns=["_date", "_order"])
    save_csv(plan[MEAL_PLAN_COLUMNS], MEAL_PLAN_CSV)
    shopping_count = _merge_shopping_items(parsed.get("shopping", []))
    return {"recipes": new_recipe_count, "shopping": shopping_count, "meals": 3}


def _show_parsed_preview(parsed: dict[str, Any]) -> None:
    st.markdown("### 4. 読み取り結果を確認")
    if parsed.get("summary"):
        st.info(parsed["summary"])
    for item in parsed["menu"]:
        with st.expander(
            f"{item['category']}｜{item['recipe_name']}｜約{item['cook_time']}分",
            expanded=True,
        ):
            st.markdown("**材料**")
            if item["ingredients"]:
                for ingredient in item["ingredients"]:
                    source = "🧊" if ingredient.get("from_inventory") else "🛒"
                    st.write(f"{source} {ingredient['name']}：{ingredient['amount']}{ingredient['unit']}")
            else:
                st.caption("材料なし")
            st.markdown("**調味料**")
            st.write(item["seasonings"] or "記載なし")
            st.markdown("**作り方**")
            for index, step in enumerate(item["instructions"], start=1):
                st.write(f"{index}. {step}")
    if parsed.get("shopping"):
        st.markdown("**買い足すもの**")
        for item in parsed["shopping"]:
            st.write(f"・{item['name']}：{item['amount']}{item['unit']}")
    else:
        st.success("買い足しなし")
    if parsed.get("parallel_steps"):
        with st.expander("30分で作る順番"):
            for index, step in enumerate(parsed["parallel_steps"], start=1):
                st.write(f"{index}. {step}")
    if parsed.get("safety"):
        st.warning(parsed["safety"])
    if parsed.get("inventory_after"):
        with st.expander("調理後の冷蔵庫残量予測（今回は確認用）"):
            for item in parsed["inventory_after"]:
                st.write(f"・{item['name']}：{item['amount']}{item['unit']}")
            st.caption("冷蔵庫の自動更新は次のバージョンで実装します。")


def show_ai_chef_page() -> None:
    st.subheader("🤖 無料AIシェフ")
    st.caption("API・追加料金なし。ChatGPTの回答を貼ると、献立・レシピ・買い物へ自動反映できます。")

    inventory = load_inventory()
    info_columns = st.columns(3)
    info_columns[0].metric("冷蔵庫", f"{len(inventory)}件")
    info_columns[1].metric("直近献立", f"{load_meal_plan()['date'].nunique()}日分")
    info_columns[2].metric("利用料金", "0円")

    st.markdown("### 1. 今日の希望")
    left, right = st.columns(2)
    with left:
        cuisine = st.multiselect(
            "料理ジャンル",
            ["和食", "洋食", "中華", "韓国風", "指定なし"],
            default=["指定なし"],
        )
        max_minutes = st.slider("夕食全体の最大時間", 15, 60, 30, 5)
        budget = st.number_input("追加購入の予算目安（円）", 0, 5000, 1000, 100)
    with right:
        taste = st.multiselect(
            "味・気分",
            ["あっさり", "ガッツリ", "野菜多め", "魚を食べたい", "肉を食べたい", "洗い物少なめ", "指定なし"],
            default=["指定なし"],
        )
        max_extra_items = st.slider("買い足しの最大品数", 0, 10, 3)
        target_date = st.date_input("献立の日付", value=date.today())

    extra_request = st.text_area(
        "追加の希望",
        placeholder="例：今日は暑いのでさっぱり。しめじを必ず使いたい。辛い料理は避けたい。",
    )
    prompt = build_prompt(
        cuisine=[item for item in cuisine if item != "指定なし"],
        taste=[item for item in taste if item != "指定なし"],
        max_minutes=max_minutes,
        max_extra_items=max_extra_items,
        budget=int(budget),
        extra_request=extra_request,
    )
    st.session_state["free_ai_prompt"] = prompt

    st.markdown("### 2. ChatGPTへ渡す")
    _clipboard_button(prompt)
    with st.expander("👀 プロンプトの中身を見る", expanded=False):
        st.text_area("生成されたプロンプト", value=prompt, height=520, disabled=True)
    st.info("コピーしてこのチャットへ送信し、返ってきたJSONを下へ丸ごと貼ってください。")

    st.markdown("### 3. ChatGPTの回答を貼る")
    # Streamlitでは、同じ実行中に表示済みウィジェットの値を
    # session_stateから直接変更できないため、次回実行の先頭で消す。
    if st.session_state.pop("clear_free_ai_response", False):
        st.session_state.pop("free_ai_response", None)

    response = st.text_area(
        "回答をそのまま貼り付け",
        value=st.session_state.get("free_ai_response", ""),
        height=420,
        placeholder='ChatGPTの回答を、最初の「{」から最後の「}」まで丸ごと貼り付けます。',
        key="free_ai_response",
    )

    action_columns = st.columns(2)
    if action_columns[0].button("🔍 回答を読み取る", type="primary", use_container_width=True):
        if not response.strip():
            st.error("ChatGPTの回答を貼り付けてください。")
        else:
            try:
                st.session_state["parsed_ai_menu"] = parse_ai_response(response)
                st.success("主菜・副菜・汁物・買い物を読み取りました。内容を確認してください。")
            except ValueError as exc:
                st.session_state.pop("parsed_ai_menu", None)
                st.error(str(exc))

    if action_columns[1].button("💾 回答だけ保存", use_container_width=True):
        if not response.strip():
            st.error("ChatGPTの回答を貼り付けてください。")
        else:
            _save_response(prompt, response, target_date)
            st.success("回答を履歴へ保存しました。")

    parsed = st.session_state.get("parsed_ai_menu")
    if parsed:
        _show_parsed_preview(parsed)
        if st.button("✅ この内容を献立・レシピ・買い物へ反映", type="primary", use_container_width=True):
            result = adopt_parsed_menu(parsed, target_date)
            _save_response(prompt, response, target_date)
            st.success(
                f"{target_date.isoformat()}の献立3品を登録しました。"
                f" 新しいレシピ{result['recipes']}件、買い物{result['shopping']}件を反映しました。"
            )
            st.session_state.pop("parsed_ai_menu", None)
            st.session_state["clear_free_ai_response"] = True
            st.rerun()

    history = _load_responses()
    if not history.empty:
        with st.expander(f"保存済み回答（{len(history)}件）"):
            latest = history.iloc[::-1].head(10)
            for _, row in latest.iterrows():
                st.markdown(f"**{row['target_date']}｜保存 {row['saved_at']}**")
                st.text_area(
                    "保存内容",
                    value=row["response"],
                    height=180,
                    disabled=True,
                    key=f"saved_{row['saved_at']}_{row['target_date']}",
                    label_visibility="collapsed",
                )
