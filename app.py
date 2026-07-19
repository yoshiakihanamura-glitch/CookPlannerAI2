import streamlit as st

from auth import require_login
from data_store import initialize_data
from home import show_home
from ui import apply_mobile_styles


st.set_page_config(
    page_title="CookPlanner AI",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_mobile_styles()
initialize_data()

if not require_login():
    st.stop()

st.title("🍳 CookPlanner AI")
st.caption("花村家の毎日のごはんを支えるアプリ｜無料AIシェフ")

# サイドバーを使わず、ホーム画面だけを表示する
show_home()