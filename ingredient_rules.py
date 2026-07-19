from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class IngredientRule:
    storage_location: str
    shelf_life_days: int
    category: str


DEFAULT_RULE = IngredientRule(
    storage_location="冷蔵",
    shelf_life_days=3,
    category="その他",
)


def normalize_name(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip()


# 「賞味期限」ではなく、アプリ内で使う安全寄りの「消費目安」。
# 実物パッケージに期限表示がある場合は、そちらを優先して手動修正する。
RULES: dict[str, IngredientRule] = {
    "卵": IngredientRule("冷蔵", 14, "卵・乳製品"),
    "牛乳": IngredientRule("冷蔵", 5, "卵・乳製品"),
    "ヨーグルト": IngredientRule("冷蔵", 7, "卵・乳製品"),
    "木綿豆腐": IngredientRule("冷蔵", 3, "大豆製品"),
    "豆腐": IngredientRule("冷蔵", 3, "大豆製品"),
    "厚揚げ": IngredientRule("冷蔵", 3, "大豆製品"),
    "油揚げ": IngredientRule("冷蔵", 5, "大豆製品"),
    "鶏むね肉": IngredientRule("冷蔵", 2, "肉"),
    "鶏もも肉": IngredientRule("冷蔵", 2, "肉"),
    "豚こま切れ肉": IngredientRule("冷蔵", 2, "肉"),
    "豚ロース肉": IngredientRule("冷蔵", 2, "肉"),
    "牛こま切れ肉": IngredientRule("冷蔵", 2, "肉"),
    "生鮭": IngredientRule("冷蔵", 2, "魚介"),
    "さば": IngredientRule("冷蔵", 2, "魚介"),
    "たら": IngredientRule("冷蔵", 2, "魚介"),
    "むきえび": IngredientRule("冷蔵", 2, "魚介"),
    "もやし": IngredientRule("冷蔵", 2, "野菜"),
    "ほうれん草": IngredientRule("野菜室", 3, "野菜"),
    "小松菜": IngredientRule("野菜室", 3, "野菜"),
    "にら": IngredientRule("野菜室", 3, "野菜"),
    "ブロッコリー": IngredientRule("野菜室", 4, "野菜"),
    "きゅうり": IngredientRule("野菜室", 5, "野菜"),
    "トマト": IngredientRule("野菜室", 5, "野菜"),
    "なす": IngredientRule("野菜室", 5, "野菜"),
    "ピーマン": IngredientRule("野菜室", 7, "野菜"),
    "オクラ": IngredientRule("野菜室", 4, "野菜"),
    "ズッキーニ": IngredientRule("野菜室", 5, "野菜"),
    "キャベツ": IngredientRule("野菜室", 10, "野菜"),
    "白菜": IngredientRule("野菜室", 7, "野菜"),
    "大根": IngredientRule("野菜室", 10, "野菜"),
    "かぶ": IngredientRule("野菜室", 5, "野菜"),
    "にんじん": IngredientRule("野菜室", 14, "野菜"),
    "玉ねぎ": IngredientRule("常温", 21, "野菜"),
    "長ねぎ": IngredientRule("野菜室", 7, "野菜"),
    "じゃがいも": IngredientRule("常温", 21, "野菜"),
    "さつまいも": IngredientRule("常温", 14, "野菜"),
    "里いも": IngredientRule("常温", 10, "野菜"),
    "かぼちゃ": IngredientRule("野菜室", 7, "野菜"),
    "ごぼう": IngredientRule("野菜室", 7, "野菜"),
    "れんこん": IngredientRule("野菜室", 5, "野菜"),
    "セロリ": IngredientRule("野菜室", 7, "野菜"),
    "しめじ": IngredientRule("冷蔵", 5, "きのこ"),
    "きのこミックス": IngredientRule("冷蔵", 5, "きのこ"),
    "カットトマト": IngredientRule("常温", 365, "加工食品"),
    "コーン": IngredientRule("常温", 365, "加工食品"),
    "ひじき": IngredientRule("常温", 180, "乾物"),
    "切り干し大根": IngredientRule("常温", 180, "乾物"),
    "春雨": IngredientRule("常温", 180, "乾物"),
    "わかめ": IngredientRule("常温", 180, "乾物"),
}


ALIASES: dict[str, str] = {
    "鶏モモ肉": "鶏もも肉",
    "鶏肉": "鶏もも肉",
    "鮭": "生鮭",
    "サバ": "さば",
    "タラ": "たら",
    "玉葱": "玉ねぎ",
    "人参": "にんじん",
}


def canonical_name(value: object) -> str:
    normalized = normalize_name(value)
    return ALIASES.get(normalized, normalized)


def get_rule(value: object) -> IngredientRule:
    return RULES.get(canonical_name(value), DEFAULT_RULE)
