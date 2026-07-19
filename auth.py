from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st


def _configured_password() -> str:
    """Secrets, environment variable, then local development fallback."""
    try:
        secret = str(st.secrets.get("APP_PASSWORD", "")).strip()
        if secret:
            return secret
    except (FileNotFoundError, KeyError):
        pass
    return os.getenv("APP_PASSWORD", "").strip()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_login() -> bool:
    """Return True when the app may be shown.

    Local development remains usable without setup. On Community Cloud, add
    APP_PASSWORD in Secrets to enable the family login screen.
    """
    password = _configured_password()
    if not password:
        st.session_state["authenticated"] = True
        return True

    expected = _digest(password)
    if st.session_state.get("authenticated") is True:
        return True

    st.markdown(
        """
        <div class="login-card">
          <div class="login-icon">🍳</div>
          <h1>CookPlanner AI</h1>
          <p>花村家専用の献立アプリ</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        entered = st.text_input(
            "パスワード",
            type="password",
            placeholder="家族用パスワードを入力",
        )
        submitted = st.form_submit_button(
            "ログイン",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if hmac.compare_digest(_digest(entered), expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False


def logout_button() -> None:
    if not _configured_password():
        return
    if st.sidebar.button("🔒 ログアウト", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()
