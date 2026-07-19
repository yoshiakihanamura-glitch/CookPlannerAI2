from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from data_store import load_settings
from inventory import load_inventory
from planner import load_meal_plan


AI_CATEGORIES = ["主菜", "副菜", "汁物"]


def pregnancy_week(due_date_text: str) -> str:
    """出産予定日から現在の妊娠週数を計算する。"""
    try:
        due_date = datetime.strptime(
            due_date_text,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return "不明"

    pregnancy_start = due_date - timedelta(days=280)
    elapsed_days = (date.today() - pregnancy_start).days

    if elapsed_days < 0:
        return "妊娠前"

    return f"{elapsed_days // 7}週{elapsed_days % 7}日"


def inventory_text() -> str:
    """現在の冷蔵庫をAIへ渡す文章に変換する。"""
    inventory = load_inventory()

    if inventory.empty:
        return "- 冷蔵庫に登録された食材はありません"

    work = inventory.copy()
    work["_expiry"] = pd.to_datetime(
        work["expiry_date"],
        errors="coerce",
    )
    work = work.sort_values(
        "_expiry",
        na_position="last",
    )

    lines: list[str] = []

    for _, row in work.iterrows():
        name = str(row.get("ingredient_name", "")).strip()
        amount = str(row.get("amount", "")).strip()
        unit = str(row.get("unit", "")).strip()
        expiry = str(row.get("expiry_date", "")).strip() or "未設定"
        storage = (
            str(row.get("storage_location", "")).strip()
            or "未設定"
        )
        note = str(row.get("note", "")).strip()

        line = (
            f"- {name}：{amount}{unit}"
            f"（保存場所：{storage}、消費目安：{expiry}）"
        )

        if note:
            line += f"／メモ：{note}"

        lines.append(line)

    return "\n".join(lines)


def urgent_inventory_text() -> str:
    """期限が3日以内の食材をAIへ渡す文章に変換する。"""
    inventory = load_inventory()

    if inventory.empty:
        return "- なし"

    work = inventory.copy()
    work["_expiry"] = pd.to_datetime(
        work["expiry_date"],
        errors="coerce",
    )
    work["_days"] = (
        work["_expiry"] - pd.Timestamp(date.today())
    ).dt.days

    urgent = work[
        work["_days"].notna()
        & (work["_days"] <= 3)
    ].sort_values("_days")

    if urgent.empty:
        return "- なし"

    lines: list[str] = []

    for _, row in urgent.iterrows():
        days = int(row["_days"])

        if days < 0:
            label = "期限切れ"
        elif days == 0:
            label = "今日まで"
        else:
            label = f"あと{days}日"

        lines.append(
            f"- {row['ingredient_name']}："
            f"{row['amount']}{row['unit']}（{label}）"
        )

    return "\n".join(lines)


def recent_meals_text(days: int = 14) -> str:
    """直近の献立履歴をAIへ渡す文章に変換する。"""
    plan = load_meal_plan()

    if plan.empty:
        return "- 履歴なし"

    work = plan.copy()
    work["_date"] = pd.to_datetime(
        work["date"],
        errors="coerce",
    )
    work = work.dropna(
        subset=["_date"],
    ).sort_values(
        "_date",
        ascending=False,
    )

    recent_dates = (
        work["date"]
        .drop_duplicates()
        .head(days)
    )
    work = work[
        work["date"].isin(recent_dates)
    ]

    if work.empty:
        return "- 履歴なし"

    lines: list[str] = []

    for meal_date, group in work.groupby(
        "date",
        sort=False,
    ):
        meals: list[str] = []

        for category in AI_CATEGORIES:
            row = group[
                group["category"] == category
            ]

            if not row.empty:
                meals.append(
                    f"{category}："
                    f"{row.iloc[0]['recipe_name']}"
                )

        lines.append(
            f"- {meal_date}｜"
            + "／".join(meals)
        )

    return "\n".join(lines)


def build_prompt(
    cuisine: list[str],
    taste: list[str],
    max_minutes: int,
    max_extra_items: int,
    budget: int,
    extra_request: str,
) -> str:
    """ChatGPTへ貼り付ける献立作成プロンプトを生成する。"""
    settings = load_settings()

    people = settings.get("people", "2")
    due_date = settings.get("due_date", "未設定")
    shopping_cycle = settings.get(
        "shopping_cycle_days",
        "3",
    )
    rice_wife = settings.get(
        "rice_wife_g",
        "300",
    )
    rice_husband = settings.get(
        "rice_husband_g",
        "300",
    )

    cuisine_text = (
        "・".join(cuisine)
        if cuisine
        else "指定なし。食材に最も合うもの"
    )
    taste_text = (
        "・".join(taste)
        if taste
        else "指定なし。献立全体のバランスを優先"
    )

    return f"""あなたは日本の家庭料理に詳しい料理研究家兼、妊娠中の食事を安全面から補助する献立アシスタントです。
冷蔵庫の現実の在庫を最優先し、料理名だけを機械的に合成せず、一般的に成立して本当においしい夕食を考えてください。

【家族】
- {people}人分
- 出産予定日：{due_date}
- 現在：妊娠{pregnancy_week(due_date)}
- 妻の白米：{rice_wife}g
- 夫の白米：{rice_husband}g

【妊娠中の安全条件】
- レバー、ハツ、鶏モツは使わない
- 生肉、生魚、生卵、生ハムなど非加熱食品は避ける
- 肉・魚・卵は中心まで十分に加熱する
- アルコールを使う場合は十分に加熱して飛ばす
- 不確かな食材は、より安全な代替案を選ぶ

【現在の冷蔵庫】
{inventory_text()}

【優先して使い切りたい食材】
{urgent_inventory_text()}

【直近14日間の献立】
{recent_meals_text(14)}

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
返答には説明文やMarkdownを付けず、下記のJSONだけを返してください。
JSONのキー名は絶対に変えないでください。
材料のamountは数量だけ、unitは単位だけに分けてください。
数量が曖昧な場合も「1/2」「適量」のように文字列で記載してください。

{{
  "summary": "献立全体のねらい",
  "safety": "妊娠中の安全確認",
  "parallel_steps": [
    "同時進行手順1",
    "同時進行手順2",
    "同時進行手順3"
  ],
  "menu": [
    {{
      "category": "主菜",
      "recipe_name": "料理名",
      "cook_time": 20,
      "ingredients": [
        {{
          "name": "食材名",
          "amount": "300",
          "unit": "g",
          "from_inventory": true
        }}
      ],
      "seasonings": "調味料をまとめて記載",
      "instructions": [
        "手順1",
        "手順2",
        "十分加熱する手順"
      ]
    }},
    {{
      "category": "副菜",
      "recipe_name": "料理名",
      "cook_time": 10,
      "ingredients": [],
      "seasonings": "",
      "instructions": []
    }},
    {{
      "category": "汁物",
      "recipe_name": "料理名",
      "cook_time": 10,
      "ingredients": [],
      "seasonings": "",
      "instructions": []
    }}
  ],
  "shopping": [
    {{
      "name": "買い足す食材名",
      "amount": "1",
      "unit": "袋"
    }}
  ],
  "inventory_after": [
    {{
      "name": "食材名",
      "amount": "残る数量",
      "unit": "g"
    }}
  ]
}}

最後に、提案した料理名と材料の組み合わせが一般的な料理として自然に成立するか自分で再確認してください。
肉を使わない料理に「生姜焼き」と名付けるような不自然な料理は禁止です。"""