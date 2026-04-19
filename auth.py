"""
auth.py — shared Supabase auth utilities
Import this in every page that needs auth.
"""
import streamlit as st
from supabase import create_client, Client


# ── Supabase client (cached so it's only created once) ────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url  = st.secrets["SUPABASE_URL"]
    key  = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


# ── Session helpers ───────────────────────────────────────────────────────────
def get_session():
    """Return the current Supabase session dict or None."""
    return st.session_state.get("sb_session", None)


def get_user():
    """Return the current user dict or None."""
    session = get_session()
    return session.get("user") if session else None


def is_logged_in() -> bool:
    return get_user() is not None


def set_session(session_data: dict):
    """Store a Supabase session response in session_state."""
    st.session_state["sb_session"] = session_data


def clear_session():
    """Wipe auth state and any app state."""
    keys_to_clear = [k for k in st.session_state.keys()]
    for k in keys_to_clear:
        del st.session_state[k]


# ── Page guard ────────────────────────────────────────────────────────────────
def require_auth():
    """
    Call at the top of any page that requires login.
    Redirects to the login page if the user is not authenticated.
    """
    if not is_logged_in():
        st.switch_page("pages/1_login.py")


# ── Shared CSS ────────────────────────────────────────────────────────────────
AUTH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

html, body, .stApp {
    font-family: 'DM Sans', sans-serif;
    background-color: #0b0b12;
    color: #F2EEE6;
}

[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { display: none !important; }

.auth-divider {
    border: none;
    border-top: 0.5px solid #1c1c28;
    margin: 20px 0;
}

.auth-link {
    text-align: center;
    font-size: 0.85rem;
    color: #555;
    margin-top: 16px;
}

.auth-link a {
    color: #F5B731;
    text-decoration: none;
    font-weight: 500;
}

.auth-link a:hover { text-decoration: underline; }

.auth-error {
    background: #1a0f0f;
    border-left: 3px solid #9e4a4a;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #c07070;
    margin-bottom: 16px;
}

.auth-success {
    background: #0f1a14;
    border-left: 3px solid #2e8f66;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #2e8f66;
    margin-bottom: 16px;
}

.stTextInput input {
    background: #0b0b12 !important;
    border: 0.5px solid #252535 !important;
    border-radius: 8px !important;
    color: #F2EEE6 !important;
    padding: 10px 14px !important;
}
.stTextInput input:focus {
    border-color: #F5B731 !important;
    box-shadow: 0 0 0 2px rgba(245,183,49,0.12) !important;
}

.stButton button {
    width: 100%;
    background: #F5B731 !important;
    color: #0b0b12 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    cursor: pointer !important;
    transition: opacity .15s !important;
}
.stButton button:hover { opacity: 0.88 !important; }
</style>
"""
