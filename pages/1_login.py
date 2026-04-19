import streamlit as st
from auth import get_supabase, set_session, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Login — Clara", page_icon="💳", layout="centered")
st.markdown(AUTH_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
/* Make form submit button yellow with black text */
div[data-testid="stFormSubmitButton"] button {
    background-color: #F5B731 !important;
    color: #0b0b12 !important;
    border: none !important;
    font-weight: 600 !important;
    width: 100% !important;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background-color: #e8aa2a !important;
}
/* Hide Enter to submit hint */
[data-testid="InputInstructions"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Already logged in → go straight to app
if is_logged_in():
    st.switch_page("frontend.py")

st.markdown("""
<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Serif Display',serif;font-style:italic;font-size:3rem;
              color:#F5B731;letter-spacing:-.01em;margin-bottom:8px">
    Clara
  </div>
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Welcome back
  </div>
  <div style="font-size:.85rem;color:#666">
    Sign in to your account
  </div>
</div>
""", unsafe_allow_html=True)

# Centre the form using columns
_, col, _ = st.columns([1, 2, 1])

with col:
    msg_placeholder = st.empty()

    with st.form("login_form", border=False):
        email    = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        signin   = st.form_submit_button("Sign in", use_container_width=True)

    if signin:
        if not email or not password:
            msg_placeholder.markdown(
                '<div class="auth-error">Please enter your email and password.</div>',
                unsafe_allow_html=True,
            )
        else:
            try:
                sb = get_supabase()
                res = sb.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                set_session({"user": res.user, "access_token": res.session.access_token})
                st.switch_page("frontend.py")
            except Exception as e:
                err = str(e)
                if "Invalid login" in err or "invalid" in err.lower():
                    msg = "Incorrect email or password."
                elif "Email not confirmed" in err:
                    msg = "Please confirm your email before signing in."
                else:
                    msg = f"Sign-in failed: {err}"
                msg_placeholder.markdown(
                    f'<div class="auth-error">{msg}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)

    st.markdown(
        '<div class="auth-link">Forgot your password? '
        '<a href="/reset_password" target="_self">Reset it</a></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="auth-link" style="margin-top:8px">No account? '
        '<a href="/signup" target="_self">Sign up free</a></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="auth-link" style="margin-top:16px;font-size:.75rem;color:#444">'
        '<a href="https://drive.google.com/file/d/1Yl0ed8IiMzYalV2rcXUsLtBymnvvjyZ5/view?usp=sharing" target="_blank" style="color:#555">📄 Privacy Policy</a>'
        '</div>',
        unsafe_allow_html=True,
    )
