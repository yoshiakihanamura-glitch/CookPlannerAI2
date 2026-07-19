from __future__ import annotations

import streamlit as st


def apply_mobile_styles() -> None:
    st.markdown(
        """
        <style>
        :root { --cp-radius: 16px; }
        .block-container {
            max-width: 1120px;
            padding-top: 1.4rem;
            padding-bottom: 4rem;
        }
        div[data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: var(--cp-radius);
            padding: .85rem 1rem;
            background: rgba(255,255,255,.035);
        }
        .stButton > button, .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 3rem;
            border-radius: 12px;
            font-weight: 700;
        }
        div[data-baseweb="select"] > div,
        .stTextInput input, .stNumberInput input, .stDateInput input,
        .stTextArea textarea {
            border-radius: 12px !important;
        }
        .login-card {
            max-width: 430px;
            margin: 8vh auto 1.5rem auto;
            text-align: center;
            padding: 1.5rem 1rem .5rem;
        }
        .login-icon { font-size: 4rem; }
        .login-card h1 { margin-bottom: .2rem; }
        .login-card p { opacity: .72; }

        @media (max-width: 768px) {
            .block-container {
                padding: .75rem .85rem 5rem;
            }
            h1 { font-size: 2rem !important; line-height: 1.12 !important; }
            h2 { font-size: 1.55rem !important; }
            h3 { font-size: 1.25rem !important; }
            div[data-testid="stHorizontalBlock"] {
                gap: .65rem;
            }
            div[data-testid="stMetric"] {
                padding: .65rem .75rem;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.55rem;
            }
            .stButton > button, .stDownloadButton > button,
            div[data-testid="stFormSubmitButton"] > button {
                min-height: 3.25rem;
                font-size: 1rem;
            }
            textarea { font-size: 16px !important; }
            input { font-size: 16px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
