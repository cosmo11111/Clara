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
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, .stApp {
    font-family: 'DM Sans', sans-serif;
    background-color: #0f0f13;
    color: #e8e6e1;
}

/* Hide default Streamlit nav/hamburger on auth pages */
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

.auth-card {
    max-width: 420px;
    margin: 60px auto 0;
    background: #1a1a24;
    border: 1px solid #2a2a38;
    border-radius: 16px;
    padding: 40px 36px;
}

.auth-logo {
    text-align: center;
    font-size: 2rem;
    margin-bottom: 4px;
}

.auth-title {
    text-align: center;
    font-size: 1.4rem;
    font-weight: 600;
    color: #e8e6e1;
    margin-bottom: 4px;
}

.auth-subtitle {
    text-align: center;
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 28px;
}

.auth-divider {
    border: none;
    border-top: 1px solid #2a2a38;
    margin: 20px 0;
}

.auth-link {
    text-align: center;
    font-size: 0.85rem;
    color: #666;
    margin-top: 16px;
}

.auth-link a {
    color: #f0c040;
    text-decoration: none;
    font-weight: 500;
}

.auth-link a:hover { text-decoration: underline; }

.auth-error {
    background: #1f0f0f;
    border-left: 3px solid #f87171;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #f87171;
    margin-bottom: 16px;
}

.auth-success {
    background: #0f1f1a;
    border-left: 3px solid #34d399;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #34d399;
    margin-bottom: 16px;
}

/* Style Streamlit inputs on auth pages */
.stTextInput input {
    background: #0f0f13 !important;
    border: 1px solid #2a2a38 !important;
    border-radius: 8px !important;
    color: #e8e6e1 !important;
    padding: 10px 14px !important;
}
.stTextInput input:focus {
    border-color: #f0c040 !important;
    box-shadow: 0 0 0 2px rgba(240,192,64,0.15) !important;
}

.stButton button {
    width: 100%;
    background: #f0c040 !important;
    color: #0f0f13 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    cursor: pointer !important;
    transition: background .15s !important;
}
.stButton button:hover { background: #e5b830 !important; }
</style>
"""
