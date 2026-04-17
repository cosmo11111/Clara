import streamlit as st
from auth import get_supabase, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Reset Password — Expense AI", page_icon="💳", layout="centered")
st.markdown(AUTH_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
div[data-testid="stFormSubmitButton"] button {
    background-color: #f0c040 !important;
    color: #0f0f13 !important;
    border: none !important;
    font-weight: 600 !important;
    width: 100% !important;
}
[data-testid="InputInstructions"] { display: none !important; }
</style>""", unsafe_allow_html=True)

if is_logged_in():
    st.switch_page("frontend.py")

params = st.query_params

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
    st.markdown("""<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Sans',sans-serif;font-size:2.4rem;font-weight:700;
              font-style:italic;color:#f0c040;letter-spacing:.04em;margin-bottom:8px">
    CATEGORIZ
  </div>
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Reset your password
  </div>
  <div style="font-size:.85rem;color:#666">
    We'll send a reset link to your email
  </div>
</div>""", unsafe_allow_html=True)

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
    st.markdown("""<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Sans',sans-serif;font-size:2.4rem;font-weight:700;
              font-style:italic;color:#f0c040;letter-spacing:.04em;margin-bottom:8px">
    CATEGORIZ
  </div>
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Set a new password
  </div>
  <div style="font-size:.85rem;color:#666">
    Choose a strong password for your account
  </div>
</div>""", unsafe_allow_html=True)

    # ── Exchange token for session immediately on page load ───────────────────
    # Supabase invalidates the OTP token quickly — we must verify it as soon
    # as the page loads and store the session, then use that session to update.
    if "reset_session_verified" not in st.session_state:
        try:
            sb    = get_supabase()
            token = params.get("token","")
            email_param = params.get("email","")
            # Try verify_otp to establish a session
            res = sb.auth.verify_otp({
                "email": email_param,
                "token": token,
                "type":  "recovery",
            })
            st.session_state.reset_session_verified = True
            st.session_state.reset_email = email_param
        except Exception:
            # Token may need email from user — fall through to form
            st.session_state.reset_session_verified = False

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg_placeholder = st.empty()
        # Only show email field if we couldn't auto-verify
        if not st.session_state.get("reset_session_verified"):
            email = st.text_input("Email address", placeholder="you@example.com")
        else:
            email = st.session_state.get("reset_email", "")
            st.markdown(
                f"<p style='color:#888;font-size:.85rem;margin-bottom:8px'>"
                f"Resetting password for <b style='color:#e8e6e1'>{email}</b></p>",
                unsafe_allow_html=True,
            )
        new_password = st.text_input("New password", type="password",
                                     placeholder="At least 8 characters")
        confirm      = st.text_input("Confirm password", type="password",
                                     placeholder="••••••••")

        if st.button("Update password", type="primary"):
            if not st.session_state.get("reset_session_verified") and not email.strip():
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
                    sb = get_supabase()

                    if not st.session_state.get("reset_session_verified"):
                        # Fallback: try verify with user-provided email
                        sb.auth.verify_otp({
                            "email": email.strip(),
                            "token": params.get("token",""),
                            "type":  "recovery",
                        })

                    sb.auth.update_user({"password": new_password})

                    msg_placeholder.markdown(
                        '<div class="auth-success">'
                        '✅ Password updated! '
                        '<a href="/1_login" target="_self" style="color:#34d399">Sign in</a>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    st.query_params.clear()
                    # Clear reset session so it doesn't persist
                    st.session_state.pop("reset_session_verified", None)
                    st.session_state.pop("reset_email", None)

                except Exception as e:
                    msg_placeholder.markdown(
                        f'<div class="auth-error">Could not update password: {e}<br>'
                        'The reset link may have expired — '
                        '<a href="/3_reset_password" target="_self" style="color:#f87171">'
                        'request a new one</a>.</div>',
                        unsafe_allow_html=True,
                    )
