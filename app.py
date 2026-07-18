import streamlit as st

from data_store import initialize_data
from home import show_home
from inventory import show_inventory_page
from planner import show_planner_page
from recipes import show_recipe_page
from settings_page import show_settings_page
from shopping import show_shopping_page

st.set_page_config(page_title="CookPlanner AI", page_icon="🍳", layout="wide")
initialize_data()

st.title("🍳 CookPlanner AI")
st.caption("花村家の毎日のごはんを支えるアプリ")

page = st.sidebar.radio(
    "メニュー",
    ["🏠 ホーム", "🍳 レシピ", "📅 献立", "📦 冷蔵庫", "🛒 買い物", "⚙️ 設定"],
)

if page == "🏠 ホーム":
    show_home()
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
