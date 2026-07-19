from __future__ import annotations

import json
import re
from typing import Any

from ingredient_rules import canonical_name

AI_CATEGORIES = ["主菜", "副菜", "汁物"]


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
    """ChatGPTのJSON回答をアプリ用の形へ整える。"""
    try:
        raw = json.loads(_clean_json_text(text))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "回答を読み取れませんでした。ChatGPTの回答を最初の「{」から最後の「}」まで丸ごと貼ってください。"
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
            instructions = [
                line.strip()
                for line in instructions_raw.splitlines()
                if line.strip()
            ]
        else:
            instructions = [
                str(line).strip()
                for line in instructions_raw
                if str(line).strip()
            ]

        normalized_menu.append(
            {
                "category": category,
                "recipe_name": recipe_name,
                "cook_time": max(1, cook_time),
                "ingredients": ingredients,
                "seasonings": str(item.get("seasonings", "")).strip(),
                "instructions": instructions,
            }
        )
        seen.add(category)

    if seen != set(AI_CATEGORIES):
        raise ValueError("主菜・副菜・汁物を1品ずつ読み取れませんでした。")

    normalized_menu.sort(
        key=lambda row: AI_CATEGORIES.index(row["category"])
    )

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
    if isinstance(parallel_raw, str):
        parallel_steps = [
            line.strip()
            for line in parallel_raw.splitlines()
            if line.strip()
        ]
    else:
        parallel_steps = [
            str(line).strip()
            for line in parallel_raw
            if str(line).strip()
        ]

    return {
        "summary": str(raw.get("summary", "")).strip(),
        "safety": str(raw.get("safety", "")).strip(),
        "parallel_steps": parallel_steps,
        "menu": normalized_menu,
        "shopping": shopping,
        "inventory_after": inventory_after,
    }