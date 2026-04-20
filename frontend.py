"""
app.py — Clara router. Defines navigation and directs users based on auth state.
"""
import streamlit as st
from auth import is_logged_in

st.set_page_config(page_title="Clara", page_icon="💳", layout="wide")

# ── Define pages ───────────────────────────────────────────────────────────────
login_page   = st.Page("pages/login.py",   title="Log in",      url_path="login")
signup_page  = st.Page("pages/signup.py",  title="Sign up",     url_path="signup")
reset_page   = st.Page("pages/reset.py",   title="Reset password", url_path="reset")

home_page     = st.Page("pages/home.py",     title="Home",          url_path="home",     default=True)
reports_page  = st.Page("pages/reports.py",  title="Saved Reports", url_path="reports")
pricing_page  = st.Page("pages/pricing.py",  title="Pricing",       url_path="pricing")
settings_page = st.Page("pages/settings.py", title="Settings",      url_path="settings")

# ── Route based on auth state ─────────────────────────────────────────────────
if is_logged_in():
    nav = st.navigation(
        [home_page, reports_page, pricing_page, settings_page],
        position="hidden",
    )
else:
    nav = st.navigation(
        [login_page, signup_page, reset_page],
        position="hidden",
    )

nav.run()
