import streamlit as st
import requests
from auth import get_supabase, is_logged_in, AUTH_CSS

st.set_page_config(page_title="Reset Password — Categoriz", page_icon="💳", layout="centered")
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

SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

WORDMARK = """<div style="text-align:center;padding:48px 0 24px">
  <div style="font-family:'DM Serif Display',serif;font-style:italic;font-size:3rem;
              color:#F5B731;letter-spacing:-.01em;margin-bottom:8px">
    Clara
  </div>"""


def verify_token_hash(token_hash: str) -> tuple[bool, str, str]:
    """
    Verify a token_hash directly against Supabase REST API.
    Returns (success, access_token, error_message)
    This works server-side unlike the JS SDK approach.
    """
    url = f"{SUPABASE_URL}/auth/v1/verify"
    resp = requests.post(
        url,
        json={"token_hash": token_hash, "type": "recovery"},
        headers={
            "apikey":       SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        allow_redirects=False,
    )
    if resp.status_code in (200, 302):
        data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {}
        access_token = data.get("access_token", "")
        return True, access_token, ""
    else:
        try:
            err = resp.json().get("error_description") or resp.json().get("msg","Unknown error")
        except Exception:
            err = resp.text or "Unknown error"
        return False, "", err


def update_password_with_token(access_token: str, new_password: str) -> tuple[bool, str]:
    """Update password using the access token from verify."""
    url = f"{SUPABASE_URL}/auth/v1/user"
    resp = requests.put(
        url,
        json={"password": new_password},
        headers={
            "apikey":        SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
    )
    if resp.status_code == 200:
        return True, ""
    else:
        try:
            err = resp.json().get("message") or resp.json().get("msg", "Unknown error")
        except Exception:
            err = resp.text or "Unknown error"
        return False, err


# ── Mode detection ─────────────────────────────────────────────────────────────
if st.session_state.get("reset_access_token"):
    mode = "set_new"
elif st.session_state.get("reset_code_sent"):
    mode = "enter_code"
else:
    mode = "request"

# ── Request mode ───────────────────────────────────────────────────────────────
if mode == "request":
    st.markdown(WORDMARK + """
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Reset your password
  </div>
  <div style="font-size:.85rem;color:#666">We'll email you a reset code</div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg = st.empty()
        with st.form("email_form", border=False):
            email_input = st.text_input("Email address", placeholder="you@example.com")
            submitted   = st.form_submit_button("Send code", use_container_width=True)

        if submitted:
            if not email_input.strip():
                msg.markdown('<div class="auth-error">Please enter your email address.</div>',
                             unsafe_allow_html=True)
            else:
                try:
                    sb  = get_supabase()
                    app = st.secrets.get("APP_URL", "").rstrip("/")
                    sb.auth.reset_password_email(
                        email_input.strip(),
                        options={"redirect_to": f"{app}/reset_password"},
                    )
                    st.session_state.reset_email     = email_input.strip()
                    st.session_state.reset_code_sent = True
                    st.rerun()
                except Exception as e:
                    msg.markdown(f'<div class="auth-error">Something went wrong: {e}</div>',
                                 unsafe_allow_html=True)

        st.markdown('<hr class="auth-divider">', unsafe_allow_html=True)
        st.markdown('<div class="auth-link">Remembered it? '
                    '<a href="/1_login" target="_self">Back to sign in</a></div>',
                    unsafe_allow_html=True)

# ── Enter code mode ────────────────────────────────────────────────────────────
elif mode == "enter_code":
    st.markdown(WORDMARK + """
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Enter your reset code
  </div>
  <div style="font-size:.85rem;color:#666">Copy the code from your email</div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg         = st.empty()
        saved_email = st.session_state.get("reset_email", "")
        st.markdown(
            f"<p style='color:#888;font-size:.85rem;margin-bottom:8px'>"
            f"Code sent to <b style='color:#e8e6e1'>{saved_email}</b></p>",
            unsafe_allow_html=True,
        )

        with st.form("code_form", border=False):
            code_input = st.text_input("Reset code",
                                       placeholder="Paste the code from your email")
            submitted  = st.form_submit_button("Verify code", use_container_width=True)

        if submitted:
            if not code_input.strip():
                msg.markdown('<div class="auth-error">Please enter the code.</div>',
                             unsafe_allow_html=True)
            else:
                ok, access_token, err = verify_token_hash(code_input.strip())
                if ok and access_token:
                    st.session_state.reset_access_token = access_token
                    st.session_state.reset_code_sent    = False
                    st.rerun()
                else:
                    msg.markdown(
                        f'<div class="auth-error">Invalid or expired code: {err}<br>'
                        '<a href="/3_reset_password" target="_self" style="color:#f87171">'
                        'Request a new one</a>.</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown(
            "<p style='font-size:.8rem;color:#555;margin-top:8px'>"
            "Didn't receive it? Check spam or "
            "<a href='/3_reset_password' target='_self' style='color:#888'>try again</a>.</p>",
            unsafe_allow_html=True,
        )

# ── Set new password mode ──────────────────────────────────────────────────────
else:
    st.markdown(WORDMARK + """
  <div style="font-size:1.1rem;font-weight:500;color:#e8e6e1;margin-bottom:4px">
    Set a new password
  </div>
  <div style="font-size:.85rem;color:#666">Choose a strong password</div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        msg          = st.empty()
        access_token = st.session_state.get("reset_access_token", "")
        saved_email  = st.session_state.get("reset_email", "")

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
                ok, err = update_password_with_token(access_token, new_password)
                if ok:
                    msg.markdown(
                        '<div class="auth-success">✅ Password updated! '
                        '<a href="/1_login" target="_self" style="color:#34d399">'
                        'Sign in</a></div>',
                        unsafe_allow_html=True,
                    )
                    for k in ["reset_access_token", "reset_email", "reset_code_sent"]:
                        st.session_state.pop(k, None)
                else:
                    msg.markdown(
                        f'<div class="auth-error">Could not update password: {err}</div>',
                        unsafe_allow_html=True,
                    )
