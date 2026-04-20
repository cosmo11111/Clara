import streamlit as st
from auth import get_supabase, is_logged_in, AUTH_CSS
import re

st.set_page_config(page_title="Sign Up — Clara", page_icon="💳", layout="centered", initial_sidebar_state="collapsed")
st.markdown(AUTH_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
div[data-testid="stFormSubmitButton"] button {
    background-color: #F5B731 !important;
    color: #0b0b12 !important;
    border: none !important;
    font-weight: 600 !important;
    width: 100% !important;
}
[data-testid="InputInstructions"] { display: none !important; }
</style>""", unsafe_allow_html=True)

if is_logged_in():
    st.switch_page("frontend.py")

st.markdown("""<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Serif Display',serif;font-style:italic;font-size:3rem;
              color:#F5B731;letter-spacing:-.01em;margin-bottom:8px">
    Clara
  </div>
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Create your account
  </div>
  <div style="font-size:.85rem;color:#666">
    Start your free beta access today
  </div>
</div>""", unsafe_allow_html=True)

_, col, _ = st.columns([1, 2, 1])

with col:
    msg_placeholder = st.empty()

    email    = st.text_input("Email address", placeholder="you@example.com")
    password = st.text_input("Password", type="password",
                             placeholder="At least 8 characters",
                             help="Minimum 8 characters")
    confirm  = st.text_input("Confirm password", type="password", placeholder="••••••••")

    def validate(email, password, confirm):
        if not email or not password or not confirm:
            return "Please fill in all fields."
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "Please enter a valid email address."
        if len(password) < 8:
            return "Password must be at least 8 characters."
        if password != confirm:
            return "Passwords do not match."
        return None

    if st.button("Create account", type="primary"):
        err = validate(email, password, confirm)
        if err:
            msg_placeholder.markdown(
                f'<div class="auth-error">{err}</div>',
                unsafe_allow_html=True,
            )
        else:
            try:
                sb = get_supabase()
                res = sb.auth.sign_up(
                    {"email": email.strip(), "password": password}
                )
                # Supabase returns a user even if email confirmation is pending
                if res.user:
                    msg_placeholder.markdown(
                        '<div class="auth-success">'
                        '✅ Account created! Check your email to confirm your address, '
                        'then <a href="/login" target="_self" style="color:#34d399">sign in</a>.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    msg_placeholder.markdown(
                        '<div class="auth-error">Sign-up failed — please try again.</div>',
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                err_str = str(e)
                if "already registered" in err_str.lower() or "already exists" in err_str.lower():
                    msg = ('An account with this email already exists. '
                           '<a href="/login" target="_self" style="color:#f87171">Sign in instead?</a>')
                else:
                    msg = f"Sign-up failed: {err_str}"
                msg_placeholder.markdown(
                    f'<div class="auth-error">{msg}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
    st.markdown(
        '<div class="auth-link">Already have an account? '
        '<a href="/login" target="_self">Sign in</a></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="auth-link" style="margin-top:12px;font-size:.75rem;color:#444">'
        'By signing up you agree to our '
        '<a href="https://drive.google.com/file/d/1Yl0ed8IiMzYalV2rcXUsLtBymnvvjyZ5/view?usp=sharing" target="_blank" style="color:#555">Privacy Policy</a>'
        '</div>',
        unsafe_allow_html=True,
    )
