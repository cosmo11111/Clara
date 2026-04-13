import streamlit as st
from auth import get_supabase, set_session, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Login — Expense AI", page_icon="💳", layout="centered")
st.markdown(AUTH_CSS, unsafe_allow_html=True)

# Already logged in → go straight to app
if is_logged_in():
    st.switch_page("frontend.py")

st.markdown("""
<div class="auth-card">
  <div class="auth-logo">💳</div>
  <div class="auth-title">Welcome back</div>
  <div class="auth-subtitle">Sign in to your Expense AI account</div>
</div>
""", unsafe_allow_html=True)

# Centre the form using columns
_, col, _ = st.columns([1, 2, 1])

with col:
    # Error / success placeholders
    msg_placeholder = st.empty()

    email    = st.text_input("Email address", placeholder="you@example.com")
    password = st.text_input("Password", type="password", placeholder="••••••••")

    if st.button("Sign in", type="primary"):
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
