from __future__ import annotations

import html
from datetime import date
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from ai_modules.importer import adopt_parsed_menu
from ai_modules.parser import parse_ai_response
from ai_modules.prompt_builder import build_prompt


def _clipboard_button(text: str) -> None:
    """プロンプトをクリップボードへコピーするボタン。"""
    escaped = html.escape(text)

    components.html(
        f"""
        <textarea
            id="copy-source"
            style="position:absolute;left:-9999px;top:-9999px;"
        >{escaped}</textarea>

        <button
            onclick="copyPrompt()"
            style="
                width:100%;
                padding:0.75rem 1rem;
                border:0;
                border-radius:0.5rem;
                background:#ff4b4b;
                color:white;
                font-size:1rem;
                font-weight:700;
                cursor:pointer;
            "
        >
            📋 ChatGPT用プロンプトをコピー
        </button>

        <div
            id="copy-result"
            style="
                margin-top:0.45rem;
                font-family:sans-serif;
                font-size:0.9rem;
            "
        ></div>

        <script>
        async function copyPrompt() {{
            const text =
                document.getElementById("copy-source").value;

            const result =
                document.getElementById("copy-result");

            try {{
                await navigator.clipboard.writeText(text);

                result.textContent =
                    "コピーしました。ChatGPTへ貼り付けてください。";

                result.style.color = "#138a36";
            }} catch (error) {{
                const source =
                    document.getElementById("copy-source");

                source.style.position = "static";
                source.style.width = "100%";
                source.style.height = "120px";
                source.select();

                document.execCommand("copy");

                source.style.position = "absolute";

                result.textContent = "コピーしました。";
                result.style.color = "#138a36";
            }}
        }}
        </script>
        """,
        height=90,
    )


def _show_parsed_result(
    parsed: dict[str, Any],
) -> None:
    """直前に登録した献立内容を表示する。"""
    if parsed.get("summary"):
        st.info(parsed["summary"])

    for item in parsed["menu"]:
        title = (
            f"{item['category']}｜"
            f"{item['recipe_name']}｜"
            f"約{item['cook_time']}分"
        )

        with st.expander(
            title,
            expanded=False,
        ):
            st.markdown("**材料**")

            if item["ingredients"]:
                for ingredient in item["ingredients"]:
                    source = (
                        "🧊"
                        if ingredient.get("from_inventory")
                        else "🛒"
                    )

                    st.write(
                        f"{source} "
                        f"{ingredient['name']}："
                        f"{ingredient['amount']}"
                        f"{ingredient['unit']}"
                    )
            else:
                st.caption("材料なし")

            st.markdown("**調味料**")
            st.write(
                item["seasonings"]
                or "記載なし"
            )

            st.markdown("**作り方**")

            if item["instructions"]:
                for index, step in enumerate(
                    item["instructions"],
                    start=1,
                ):
                    st.write(
                        f"{index}. {step}"
                    )
            else:
                st.caption(
                    "作り方は登録されていません。"
                )

    if parsed.get("shopping"):
        with st.expander(
            "買い足すもの",
            expanded=False,
        ):
            for item in parsed["shopping"]:
                st.write(
                    f"・{item['name']}："
                    f"{item['amount']}"
                    f"{item['unit']}"
                )

    if parsed.get("parallel_steps"):
        with st.expander(
            "30分で作る順番",
            expanded=False,
        ):
            for index, step in enumerate(
                parsed["parallel_steps"],
                start=1,
            ):
                st.write(
                    f"{index}. {step}"
                )

    if parsed.get("safety"):
        st.warning(
            parsed["safety"]
        )


def show_ai_chef_page() -> None:
    """ホーム画面内で使う無料AIシェフ。"""
    st.markdown("## 🤖 AIシェフ")

    st.caption(
        "希望を選んでプロンプトをコピーし、"
        "ChatGPTの回答を貼ると、"
        "献立・レシピ・買い物へ自動登録します。"
    )

    with st.expander(
        "今日の希望を設定",
        expanded=False,
    ):
        left, right = st.columns(2)

        with left:
            cuisine = st.multiselect(
                "料理ジャンル",
                [
                    "和食",
                    "洋食",
                    "中華",
                    "韓国風",
                    "指定なし",
                ],
                default=["指定なし"],
                key="ai_cuisine",
            )

            max_minutes = st.slider(
                "夕食全体の最大時間",
                min_value=15,
                max_value=60,
                value=30,
                step=5,
                key="ai_max_minutes",
            )

            budget = st.number_input(
                "追加購入の予算目安（円）",
                min_value=0,
                max_value=5000,
                value=1000,
                step=100,
                key="ai_budget",
            )

        with right:
            taste = st.multiselect(
                "味・気分",
                [
                    "あっさり",
                    "ガッツリ",
                    "野菜多め",
                    "魚を食べたい",
                    "肉を食べたい",
                    "洗い物少なめ",
                    "指定なし",
                ],
                default=["指定なし"],
                key="ai_taste",
            )

            max_extra_items = st.slider(
                "買い足しの最大品数",
                min_value=0,
                max_value=10,
                value=3,
                step=1,
                key="ai_max_extra_items",
            )

            target_date = st.date_input(
                "献立の日付",
                value=date.today(),
                key="ai_target_date",
            )

        extra_request = st.text_area(
            "追加の希望",
            placeholder=(
                "例：今日は暑いのでさっぱり。"
                "しめじを必ず使いたい。"
                "辛い料理は避けたい。"
            ),
            key="ai_extra_request",
        )

    prompt = build_prompt(
        cuisine=[
            item
            for item in cuisine
            if item != "指定なし"
        ],
        taste=[
            item
            for item in taste
            if item != "指定なし"
        ],
        max_minutes=max_minutes,
        max_extra_items=max_extra_items,
        budget=int(budget),
        extra_request=extra_request,
    )

    _clipboard_button(prompt)

    with st.expander(
        "プロンプトの中身を見る",
        expanded=False,
    ):
        st.text_area(
            "生成されたプロンプト",
            value=prompt,
            height=420,
            disabled=True,
            key="ai_prompt_preview",
        )

    if st.session_state.pop(
        "clear_free_ai_response",
        False,
    ):
        st.session_state.pop(
            "free_ai_response",
            None,
        )

    response = st.text_area(
        "ChatGPTの回答を貼る",
        height=300,
        placeholder=(
            "ChatGPTの回答を、"
            "最初の「{」から最後の「}」まで"
            "丸ごと貼り付けます。"
        ),
        key="free_ai_response",
    )

    if st.button(
        "✅ 回答を読み取って自動登録",
        type="primary",
        use_container_width=True,
        key="ai_import_response",
    ):
        if not response.strip():
            st.error(
                "ChatGPTの回答を貼り付けてください。"
            )
        else:
            try:
                parsed = parse_ai_response(
                    response
                )

                result = adopt_parsed_menu(
                    parsed,
                    target_date,
                )

                st.session_state[
                    "last_imported_ai_menu"
                ] = parsed

                st.session_state[
                    "clear_free_ai_response"
                ] = True

                st.success(
                    f"{target_date.isoformat()}の"
                    f"献立3品を登録しました。"
                    f" 新しいレシピ"
                    f"{result['recipes']}件、"
                    f"買い物"
                    f"{result['shopping']}件を"
                    f"反映しました。"
                )

                st.rerun()

            except ValueError as exc:
                st.error(
                    str(exc)
                )

            except Exception as exc:
                st.error(
                    "登録中にエラーが発生しました："
                    f"{exc}"
                )

    imported = st.session_state.get(
        "last_imported_ai_menu"
    )

    if imported:
        with st.expander(
            "直前に登録した献立を見る",
            expanded=False,
        ):
            _show_parsed_result(
                imported
            )