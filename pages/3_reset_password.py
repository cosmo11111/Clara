import streamlit as st
from auth import get_supabase, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Reset Password — Expense AI", page_icon="💳", layout="centered")
st.markdown(AUTH_CSS, unsafe_allow_html=True)

if is_logged_in():
    st.switch_page("frontend.py")

params = st.query_params

# ── DEBUG — shows exactly what Supabase sent back ─────────────────────────────
# Remove this block once password reset is confirmed working
with st.expander("🐛 Debug info (remove before launch)", expanded=True):
    st.write("**All query params received:**", dict(params))
    st.write("**Keys present:**", list(params.keys()))
    st.write("**'code' present:**", "code" in params)
    st.write("**'token' present:**", "token" in params)
    st.write("**'type' present:**", "type" in params)
    if "code" in params:
        st.write("**code value (first 20 chars):**", str(params["code"])[:20] + "...")
    if "type" in params:
        st.write("**type value:**", params["type"])
    st.caption("This tells us exactly what Supabase is sending and whether Streamlit is receiving it.")

# ── Detect mode ────────────────────────────────────────────────────────────────
# Supabase PKCE flow sends ?code=...
# Supabase magic link sends #access_token=... (fragment — Streamlit can't read)
# We also check for ?token= and ?type=recovery as fallbacks
has_code     = "code" in params
has_token    = "token" in params
is_recovery  = params.get("type") == "recovery"

mode = "set_new" if (has_code or has_token or is_recovery) else "request"

# ── Request mode — send reset email ───────────────────────────────────────────
if mode == "request":
    st.markdown("""
    <div class="auth-card">
      <div class="auth-logo">🔑</div>
      <div class="auth-title">Reset your password</div>
      <div class="auth-subtitle">We'll send a reset link to your email</div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg_placeholder = st.empty()
        email = st.text_input("Email address", placeholder="you@example.com")

        if st.button("Send reset link", type="primary"):
            if not email.strip():
                msg_placeholder.markdown(
                    '<div class="auth-error">Please enter your email address.</div>',
                    unsafe_allow_html=True,
                )
            else:
                try:
                    sb  = get_supabase()
                    app = st.secrets.get("APP_URL", "").rstrip("/")

                    # Use the full Streamlit page path as redirect
                    # Supabase will append ?code=... to this URL
                    redirect = f"{app}/reset_password"

                    sb.auth.reset_password_email(
                        email.strip(),
                        options={"redirect_to": redirect},
                    )
                    msg_placeholder.markdown(
                        '<div class="auth-success">'
                        "✅ If that email is registered, you'll receive a reset link shortly. "
                        'Check your spam folder too.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    msg_placeholder.markdown(
                        f'<div class="auth-error">Something went wrong: {e}</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
        st.markdown(
            '<div class="auth-link">Remembered it? '
            '<a href="/1_login" target="_self">Back to sign in</a></div>',
            unsafe_allow_html=True,
        )

# ── Set new password mode — arrived via email link ────────────────────────────
else:
    st.markdown("""
    <div class="auth-card">
      <div class="auth-logo">🔑</div>
      <div class="auth-title">Set a new password</div>
      <div class="auth-subtitle">Choose a strong password for your account</div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg_placeholder = st.empty()
        email        = st.text_input("Email address", placeholder="you@example.com")
        new_password = st.text_input("New password", type="password",
                                     placeholder="At least 8 characters")
        confirm      = st.text_input("Confirm password", type="password",
                                     placeholder="••••••••")

        if st.button("Update password", type="primary"):
            if not email.strip():
                msg_placeholder.markdown(
                    '<div class="auth-error">Please enter your email address.</div>',
                    unsafe_allow_html=True,
                )
            elif len(new_password) < 8:
                msg_placeholder.markdown(
                    '<div class="auth-error">Password must be at least 8 characters.</div>',
                    unsafe_allow_html=True,
                )
            elif new_password != confirm:
                msg_placeholder.markdown(
                    '<div class="auth-error">Passwords do not match.</div>',
                    unsafe_allow_html=True,
                )
            else:
                try:
                    sb    = get_supabase()
                    token = params["token"]

                    st.info(f"🐛 Verifying token for {email.strip()}...")
                    res = sb.auth.verify_otp({
                        "email": email.strip(),
                        "token": token,
                        "type":  "recovery",
                    })
                    st.info(f"🐛 Verify OK, updating password...")

                    sb.auth.update_user({"password": new_password})

                    msg_placeholder.markdown(
                        '<div class="auth-success">'
                        '✅ Password updated! '
                        '<a href="/1_login" target="_self" style="color:#34d399">Sign in</a>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    st.query_params.clear()

                except Exception as e:
                    msg_placeholder.markdown(
                        f'<div class="auth-error">Could not update password: {e}<br>'
                        'The reset link may have expired — '
                        '<a href="/3_reset_password" target="_self" style="color:#f87171">'
                        'request a new one</a>.</div>',
                        unsafe_allow_html=True,
                    )
                    st.write("🐛 Full exception:", str(e))
