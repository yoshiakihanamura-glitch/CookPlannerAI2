from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from data_store import BASE_DIR, load_settings
from inventory import load_inventory
from planner import load_meal_plan

AI_RESPONSES_CSV = Path(BASE_DIR) / "data" / "ai_responses.csv"
AI_RESPONSE_COLUMNS = ["saved_at", "target_date", "prompt", "response"]


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
    today = pd.Timestamp(date.today())
    work["_days"] = (work["_expiry"] - today).dt.days
    urgent = work[work["_days"].notna() & (work["_days"] <= 3)].sort_values("_days")
    if urgent.empty:
        return "- なし"

    lines = []
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

    lines = []
    for meal_date, group in work.groupby("date", sort=False):
        parts = []
        for category in ["主菜", "副菜", "汁物"]:
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

【1. 家族人数】
- {people}人分

【2. 妊娠情報】
- 出産予定日：{due_date}
- 現在：妊娠{_pregnancy_week(due_date)}

【3. 妊娠中の安全条件】
- レバー、ハツ、鶏モツは使わない
- 生肉、生魚、生卵、生ハムなど非加熱食品は避ける
- 肉・魚・卵は中心まで十分に加熱する
- アルコールを料理に使う場合は十分に加熱して飛ばす
- 妊娠中の食品安全に不確かな食材は、より安全な代替案を選ぶ

【4〜6. 現在の冷蔵庫・残量・消費目安】
{_inventory_text()}

【7. 優先して使い切りたい食材】
{_urgent_inventory_text()}

【8. 買い物周期】
- {shopping_cycle}日ごと

【9. 今回の追加購入予算】
- 目安 {budget}円以内

【10. 調理時間】
- 3品を並行調理し、夕食全体を{max_minutes}分以内で完成

【11. 直近14日間の献立】
{_recent_meals_text(14)}

【12. 料理の重複回避】
- 直近14日以内と同じ料理は原則提案しない

【13. 主食材の偏り防止】
- 同じ肉・魚・卵料理が続かないようにする
- 3品すべてで同じ食材を主役にしない

【14. 料理ジャンルの希望】
- {cuisine_text}

【15. 味・気分の希望】
- {taste_text}

【16. 買い足し条件】
- 冷蔵庫の食材を最大限使い、買い足しは最大{max_extra_items}品
- 調味料は一般家庭にある基本調味料が揃っている前提でよい

【17. 基本調味料の前提】
- 塩、こしょう、砂糖、しょうゆ、みそ、酢、みりん、料理酒、油、だし類は在庫確認不要
- 特殊なソースや香辛料が必要なら買い足しへ記載

【18. 献立構成】
- 白米は別に用意する
- 妻の白米：{rice_wife}g
- 夫の白米：{rice_husband}g
- 主菜1品、副菜1品、汁物1品を提案する
- 味付け、食感、調理法が3品で重複しすぎないようにする

【19. 作りやすさ】
- 料理初心者でも迷わない簡潔な手順
- 材料は2人分の具体的な数量と単位を記載
- 3品を30分以内で作るための同時進行順も記載

【20. 出力形式】
以下の形式を崩さず、日本語で出力してください。

【献立のねらい】
（在庫・期限・栄養・味の組み合わせを踏まえた短い説明）

【主菜】
料理名：
調理時間：
材料（2人分）：
調味料：
作り方：
使用する冷蔵庫食材：

【副菜】
料理名：
調理時間：
材料（2人分）：
調味料：
作り方：
使用する冷蔵庫食材：

【汁物】
料理名：
調理時間：
材料（2人分）：
調味料：
作り方：
使用する冷蔵庫食材：

【30分で作る順番】
1.
2.
3.

【買い足すもの】
- 食材名：必要量
（買い足しがなければ「なし」）

【調理後の冷蔵庫残量予測】
- 食材名：残る量

【妊娠中の安全確認】
- 十分加熱が必要な食材と注意点

【追加の希望】
{extra_request.strip() or '特になし'}

最後に、提案した料理が一般的な料理として自然に成立するかを自分で再確認してください。たとえば肉を使わない料理へ安易に「生姜焼き」と名付けるような、不自然な料理名は禁止です。"""


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


def show_ai_chef_page() -> None:
    st.subheader("🤖 無料AIシェフ")
    st.caption("API・追加料金なし。アプリが家庭情報を整理し、ChatGPTへ貼るプロンプトを作ります。")

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

    st.info("コピー後、このチャットへ貼り付けて送信してください。回答が出たら、下へ丸ごと貼り戻します。")

    st.markdown("### 3. ChatGPTの回答を貼る")
    response = st.text_area(
        "回答をそのまま貼り付け",
        value=st.session_state.get("free_ai_response", ""),
        height=420,
        placeholder="ChatGPTが作った【主菜】【副菜】【汁物】などの回答を、ここへ丸ごと貼り付けます。",
        key="free_ai_response",
    )

    if st.button("💾 この回答を保存", type="primary", use_container_width=True):
        if not response.strip():
            st.error("ChatGPTの回答を貼り付けてください。")
        else:
            _save_response(prompt, response, target_date)
            st.success("回答を保存しました。次のバージョンで献立・買い物・冷蔵庫へ自動反映できるようにします。")

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
