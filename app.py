import streamlit as st

from ai_chef import show_ai_chef_page
from auth import logout_button, require_login
from data_store import initialize_data
from home import show_home
from inventory import show_inventory_page
from planner import show_planner_page
from recipes import show_recipe_page
from settings_page import show_settings_page
from shopping import show_shopping_page
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

page = st.sidebar.radio(
    "メニュー",
    [
        "🏠 ホーム",
        "🤖 AIシェフ",
        "🍳 レシピ",
        "📅 献立",
        "📦 冷蔵庫",
        "🛒 買い物",
        "⚙️ 設定・バックアップ",
    ],
)
logout_button()

if page == "🏠 ホーム":
    show_home()
elif page == "🤖 AIシェフ":
    show_ai_chef_page()
elif page == "🍳 レシピ":
    show_recipe_page()
elif page == "📅 献立":
    show_planner_page()
elif page == "📦 冷蔵庫":
    show_inventory_page()
elif page == "🛒 買い物":
    show_shopping_page()
else:
    show_settings_page()
