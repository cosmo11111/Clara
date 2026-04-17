import streamlit as st
from auth import get_supabase, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Reset Password — Categoriz", page_icon="💳", layout="centered")
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

WORDMARK = """<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Sans',sans-serif;font-size:2.4rem;font-weight:700;
              font-style:italic;color:#f0c040;letter-spacing:.04em;margin-bottom:8px">
    CATEGORIZ
  </div>"""

# ── Detect mode ────────────────────────────────────────────────────────────────
# mode = "enter_code" if user has been sent a code (no URL params yet)
# mode = "set_new"    if user has verified their code
params = st.query_params

if st.session_state.get("reset_verified"):
    mode = "set_new"
else:
    mode = "request"

# ── Request mode — collect email, send code ───────────────────────────────────
if mode == "request":
    st.markdown(WORDMARK + """
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Reset your password
  </div>
  <div style="font-size:.85rem;color:#666">
    We'll email you a reset code
  </div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg = st.empty()

        if not st.session_state.get("reset_code_sent"):
            # Step 1 — enter email
            with st.form("email_form", border=False):
                email_input = st.text_input("Email address",
                                            placeholder="you@example.com")
                submitted = st.form_submit_button("Send code",
                                                   use_container_width=True)
            if submitted:
                if not email_input.strip():
                    msg.markdown(
                        '<div class="auth-error">Please enter your email address.</div>',
                        unsafe_allow_html=True)
                else:
                    try:
                        sb  = get_supabase()
                        app = st.secrets.get("APP_URL", "").rstrip("/")
                        sb.auth.reset_password_email(
                            email_input.strip(),
                            options={"redirect_to": f"{app}/reset_password"},
                        )
                        st.session_state.reset_email = email_input.strip()
                        st.session_state.reset_code_sent = True
                        st.rerun()
                    except Exception as e:
                        msg.markdown(
                            f'<div class="auth-error">Something went wrong: {e}</div>',
                            unsafe_allow_html=True)
        else:
            # Step 2 — enter the 6-digit code from email
            saved_email = st.session_state.get("reset_email", "")
            st.markdown(
                f"<p style='color:#888;font-size:.85rem;margin-bottom:8px'>"
                f"Enter the reset code sent to "
                f"<b style='color:#e8e6e1'>{saved_email}</b></p>",
                unsafe_allow_html=True,
            )
            with st.form("code_form", border=False):
                code_input = st.text_input("Reset code",
                                           placeholder="Paste the code from your email")
                submitted = st.form_submit_button("Verify code",
                                                   use_container_width=True)
            if submitted:
                if not code_input.strip():
                    msg.markdown(
                        '<div class="auth-error">Please enter the code from your email.</div>',
                        unsafe_allow_html=True)
                else:
                    try:
                        sb = get_supabase()
                        sb.auth.verify_otp({
                            "email": saved_email,
                            "token": code_input.strip(),
                            "type":  "recovery",
                        })
                        st.session_state.reset_verified = True
                        st.session_state.reset_code_sent = False
                        st.rerun()
                    except Exception as e:
                        msg.markdown(
                            f'<div class="auth-error">Invalid or expired code: {e}</div>',
                            unsafe_allow_html=True)

            st.markdown(
                "<p style='font-size:.8rem;color:#555;margin-top:8px'>"
                "Didn't receive it? Check your spam folder or "
                "<a href='/3_reset_password' target='_self' style='color:#888'>"
                "try again</a>.</p>",
                unsafe_allow_html=True,
            )

        st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
        st.markdown(
            '<div class="auth-link">Remembered it? '
            '<a href="/1_login" target="_self">Back to sign in</a></div>',
            unsafe_allow_html=True,
        )

# ── Set new password mode — code verified ─────────────────────────────────────
else:
    st.markdown(WORDMARK + """
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Set a new password
  </div>
  <div style="font-size:.85rem;color:#666">Choose a strong password</div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg = st.empty()
        saved_email = st.session_state.get("reset_email", "")
        if saved_email:
            st.markdown(
                f"<p style='color:#888;font-size:.85rem;margin-bottom:8px'>"
                f"Resetting password for <b style='color:#e8e6e1'>{saved_email}</b></p>",
                unsafe_allow_html=True,
            )

        with st.form("reset_form", border=False):
            new_password = st.text_input("New password", type="password",
                                         placeholder="At least 8 characters")
            confirm      = st.text_input("Confirm password", type="password",
                                         placeholder="••••••••")
            submitted    = st.form_submit_button("Update password",
                                                  use_container_width=True)

        if submitted:
            if len(new_password) < 8:
                msg.markdown(
                    '<div class="auth-error">Password must be at least 8 characters.</div>',
                    unsafe_allow_html=True)
            elif new_password != confirm:
                msg.markdown(
                    '<div class="auth-error">Passwords do not match.</div>',
                    unsafe_allow_html=True)
            else:
                try:
                    sb = get_supabase()
                    sb.auth.update_user({"password": new_password})
                    msg.markdown(
                        '<div class="auth-success">✅ Password updated! '
                        '<a href="/1_login" target="_self" style="color:#34d399">'
                        'Sign in</a></div>',
                        unsafe_allow_html=True,
                    )
                    for k in ["reset_verified", "reset_email",
                              "reset_code_sent"]:
                        st.session_state.pop(k, None)
                    st.query_params.clear()
                except Exception as e:
                    msg.markdown(
                        f'<div class="auth-error">Could not update password: {e}</div>',
                        unsafe_allow_html=True,
                    )
