from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data_store import (
    INVENTORY_COLUMNS,
    INVENTORY_CSV,
    load_csv,
    save_csv,
)
from recipes import UNITS

STORAGE_LOCATIONS = ["冷蔵", "冷凍", "野菜室", "常温"]


def load_inventory() -> pd.DataFrame:
    return load_csv(
        INVENTORY_CSV,
        INVENTORY_COLUMNS,
        dtype=str,
    ).fillna("")


def _to_number(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _format_amount(value: object) -> str:
    number = _to_number(value)
    if number is None:
        return str(value).strip()
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def _next_inventory_id(dataframe: pd.DataFrame) -> int:
    ids = pd.to_numeric(
        dataframe["inventory_id"],
        errors="coerce",
    ).dropna()
    return 1 if ids.empty else int(ids.max()) + 1


def _days_until_expiry(expiry_date: object) -> int | None:
    parsed = pd.to_datetime(
        expiry_date,
        errors="coerce",
    )
    if pd.isna(parsed):
        return None
    return (parsed.date() - date.today()).days


def _expiry_label(expiry_date: object) -> str:
    days = _days_until_expiry(expiry_date)
    if days is None:
        return "期限未設定"
    if days < 0:
        return f"期限切れ（{abs(days)}日前）"
    if days == 0:
        return "今日まで"
    if days == 1:
        return "明日まで"
    return f"あと{days}日"


def _save_editor_result(edited: pd.DataFrame) -> None:
    updated = edited.rename(
        columns={
            "ID": "inventory_id",
            "食材": "ingredient_name",
            "数量": "amount",
            "単位": "unit",
            "賞味期限": "expiry_date",
            "購入日": "purchase_date",
            "保存場所": "storage_location",
            "メモ": "note",
        }
    )

    updated = updated[INVENTORY_COLUMNS].fillna("")
    save_csv(updated, INVENTORY_CSV)


def show_inventory_page() -> None:
    st.subheader("📦 冷蔵庫")
    st.caption("食材の登録、残量更新、賞味期限管理をまとめて行えます。")

    dataframe = load_inventory()

    today = date.today()
    expiry_days = dataframe["expiry_date"].apply(
        _days_until_expiry
    ) if not dataframe.empty else pd.Series(dtype="object")

    expired_count = int(
        expiry_days.apply(
            lambda value: value is not None and value < 0
        ).sum()
    )
    urgent_count = int(
        expiry_days.apply(
            lambda value: value is not None and 0 <= value <= 3
        ).sum()
    )

    metric_total, metric_urgent, metric_expired = st.columns(3)
    metric_total.metric("登録食材", f"{len(dataframe)}件")
    metric_urgent.metric("3日以内", f"{urgent_count}件")
    metric_expired.metric("期限切れ", f"{expired_count}件")

    st.markdown("### 食材を追加")

    with st.form("inventory_add", clear_on_submit=True):
        first_row = st.columns([2.4, 1.1, 1.1, 1.4])
        ingredient_name = first_row[0].text_input(
            "食材名",
            placeholder="例：鶏むね肉",
        )
        amount = first_row[1].text_input(
            "数量",
            placeholder="例：300",
        )
        unit = first_row[2].selectbox("単位", UNITS)
        storage_location = first_row[3].selectbox(
            "保存場所",
            STORAGE_LOCATIONS,
        )

        second_row = st.columns([1.4, 1.4, 3])
        purchase_date = second_row[0].date_input(
            "購入日",
            value=today,
        )
        expiry_date = second_row[1].date_input(
            "賞味期限",
            value=today + timedelta(days=3),
        )
        note = second_row[2].text_input(
            "メモ",
            placeholder="例：開封済み、半分使用など",
        )

        submitted = st.form_submit_button(
            "冷蔵庫に追加",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not ingredient_name.strip():
            st.error("食材名を入力してください。")
        elif amount.strip() and _to_number(amount) is None:
            st.error("数量は数字で入力してください。")
        else:
            new_row = {
                "inventory_id": _next_inventory_id(dataframe),
                "ingredient_name": ingredient_name.strip(),
                "amount": _format_amount(amount),
                "unit": unit,
                "expiry_date": expiry_date.isoformat(),
                "purchase_date": purchase_date.isoformat(),
                "storage_location": storage_location,
                "note": note.strip(),
            }

            dataframe = pd.concat(
                [dataframe, pd.DataFrame([new_row])],
                ignore_index=True,
            )
            save_csv(dataframe, INVENTORY_CSV)
            st.success(f"「{ingredient_name}」を追加しました。")
            st.rerun()

    if dataframe.empty:
        st.info("冷蔵庫は空です。上のフォームから食材を追加してください。")
        return

    st.markdown("### 食材一覧")

    filter_row = st.columns([1.3, 1.3, 2.4])
    storage_filter = filter_row[0].selectbox(
        "保存場所で絞り込み",
        ["すべて"] + STORAGE_LOCATIONS,
    )
    expiry_filter = filter_row[1].selectbox(
        "期限で絞り込み",
        ["すべて", "3日以内", "期限切れ", "期限未設定"],
    )
    search_text = filter_row[2].text_input(
        "食材を検索",
        placeholder="例：卵、牛乳",
    )

    filtered = dataframe.copy()

    if storage_filter != "すべて":
        filtered = filtered[
            filtered["storage_location"] == storage_filter
        ]

    if search_text.strip():
        filtered = filtered[
            filtered["ingredient_name"].str.contains(
                search_text.strip(),
                case=False,
                na=False,
            )
        ]

    if expiry_filter != "すべて":
        remaining_days = filtered["expiry_date"].apply(
            _days_until_expiry
        )

        if expiry_filter == "3日以内":
            filtered = filtered[
                remaining_days.apply(
                    lambda value: value is not None and 0 <= value <= 3
                )
            ]
        elif expiry_filter == "期限切れ":
            filtered = filtered[
                remaining_days.apply(
                    lambda value: value is not None and value < 0
                )
            ]
        else:
            filtered = filtered[
                remaining_days.apply(lambda value: value is None)
            ]

    if filtered.empty:
        st.warning("条件に合う食材がありません。")
    else:
        for _, item in filtered.sort_values(
            "expiry_date",
            na_position="last",
        ).iterrows():
            amount_text = _format_amount(item["amount"])
            title = (
                f"{item['ingredient_name']}｜"
                f"{amount_text}{item['unit']}｜"
                f"{_expiry_label(item['expiry_date'])}"
            )

            with st.expander(title):
                detail_columns = st.columns(4)
                detail_columns[0].metric(
                    "残量",
                    f"{amount_text}{item['unit']}",
                )
                detail_columns[1].metric(
                    "保存場所",
                    item["storage_location"] or "未設定",
                )
                detail_columns[2].metric(
                    "購入日",
                    item["purchase_date"] or "未設定",
                )
                detail_columns[3].metric(
                    "賞味期限",
                    item["expiry_date"] or "未設定",
                )

                if item["note"]:
                    st.write(f"メモ：{item['note']}")

                inventory_id = int(float(item["inventory_id"]))

                with st.form(f"consume_{inventory_id}"):
                    consume_columns = st.columns([2, 1])
                    consume_amount = consume_columns[0].text_input(
                        "使用した量",
                        placeholder="例：100",
                        key=f"consume_amount_{inventory_id}",
                    )
                    consume_clicked = consume_columns[1].form_submit_button(
                        "使用量を反映",
                        use_container_width=True,
                    )

                if consume_clicked:
                    current_amount = _to_number(item["amount"])
                    used_amount = _to_number(consume_amount)

                    if current_amount is None:
                        st.error("この食材の現在量が数字ではないため、編集画面で数量を直してください。")
                    elif used_amount is None or used_amount <= 0:
                        st.error("使用した量を0より大きい数字で入力してください。")
                    else:
                        remaining = current_amount - used_amount
                        id_values = pd.to_numeric(
                            dataframe["inventory_id"],
                            errors="coerce",
                        )
                        target = id_values == inventory_id

                        if remaining <= 0:
                            dataframe = dataframe[~target]
                            st.success("使い切ったため、冷蔵庫から削除しました。")
                        else:
                            dataframe.loc[target, "amount"] = _format_amount(remaining)
                            st.success(f"残量を{_format_amount(remaining)}{item['unit']}に更新しました。")

                        save_csv(dataframe, INVENTORY_CSV)
                        st.rerun()

                action_columns = st.columns(2)

                if action_columns[0].button(
                    "使い切った",
                    key=f"finish_{inventory_id}",
                    use_container_width=True,
                ):
                    id_values = pd.to_numeric(
                        dataframe["inventory_id"],
                        errors="coerce",
                    )
                    dataframe = dataframe[id_values != inventory_id]
                    save_csv(dataframe, INVENTORY_CSV)
                    st.rerun()

                if action_columns[1].button(
                    "削除",
                    key=f"delete_{inventory_id}",
                    use_container_width=True,
                ):
                    id_values = pd.to_numeric(
                        dataframe["inventory_id"],
                        errors="coerce",
                    )
                    dataframe = dataframe[id_values != inventory_id]
                    save_csv(dataframe, INVENTORY_CSV)
                    st.rerun()

    st.markdown("### 一括編集")
    st.caption("食材名、数量、期限、保存場所、メモを直接修正できます。")

    editable = dataframe.rename(
        columns={
            "inventory_id": "ID",
            "ingredient_name": "食材",
            "amount": "数量",
            "unit": "単位",
            "expiry_date": "賞味期限",
            "purchase_date": "購入日",
            "storage_location": "保存場所",
            "note": "メモ",
        }
    )

    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        disabled=["ID"],
        column_config={
            "単位": st.column_config.SelectboxColumn(
                options=UNITS,
            ),
            "保存場所": st.column_config.SelectboxColumn(
                options=STORAGE_LOCATIONS,
            ),
        },
        key="inventory_editor",
    )

    if st.button(
        "一覧の変更を保存",
        use_container_width=True,
    ):
        _save_editor_result(edited)
        st.success("冷蔵庫の変更を保存しました。")
        st.rerun()
