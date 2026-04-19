import streamlit as st
from auth import require_auth, get_user, get_supabase, clear_session
from db import get_profile, TIER_LABELS, upgrade_user

st.set_page_config(page_title="Pricing — Clara", page_icon="💳", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0b0b12; color:#F2EEE6; }
section[data-testid="stSidebar"] { background:#0f0f18 !important; border-right:0.5px solid #1c1c28; }
section[data-testid="stSidebar"] * { color:#c8c5bf !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:all .15s !important; }
.stButton button[kind="primary"] { background:#F5B731 !important; color:#0f0f13 !important; border:none !important; }

.pricing-card {
    background:#171720; border:0.5px solid #1c1c28; border-radius:16px;
    padding:28px 24px; margin-bottom:8px;
}
.pricing-card.featured {
    border-color:#F5B731; position:relative;
}
.badge {
    display:inline-block; background:#F5B731; color:#0f0f13;
    font-size:11px; font-weight:600; padding:3px 10px;
    border-radius:20px; margin-bottom:12px;
    letter-spacing:.04em; text-transform:uppercase;
}
.price-amount {
    font-size:2.2rem; font-weight:600; color:#F2EEE6;
    font-family:'DM Sans',sans-serif;font-weight:300; line-height:1;
}
.price-period { font-size:.85rem; color:#666; margin-left:4px; }
.feature { font-size:.88rem; color:#c8c5bf; padding:5px 0;
           border-bottom:0.5px solid #1c1c28; }
.feature:last-child { border-bottom:none; }
.feature-tick { color:#F5B731; margin-right:8px; }
.current-badge {
    display:inline-block; background:#252535; color:#888;
    font-size:11px; padding:3px 10px; border-radius:20px;
    margin-bottom:12px;
}
.usage-bar-bg { background:#171720; border-radius:4px; height:6px; margin:8px 0; }
.usage-bar { background:#F5B731; border-radius:4px; height:6px; transition:width .3s; }
  [data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

require_auth()

user    = get_user()
uid     = user.id if hasattr(user,"id") else user.get("id") if user else None
email   = user.email if hasattr(user,"email") else user.get("email","") if user else ""
profile = get_profile(uid) if uid else {}
tier    = profile.get("subscription_tier", "free_trial")
used    = profile.get("analyses_used", 0)
limit   = profile.get("analyses_limit", 3)

with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page("frontend.py")
    st.markdown("<div style='padding-top:20vh'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#F2EEE6;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

st.html("""
<style>
  .st-key-sidebar_bottom {
    position: absolute;
    bottom: 16px;
    left: 0;
    right: 0;
    padding: 0 1rem;
  }
</style>
""")


# ── Handle successful Stripe redirect ─────────────────────────────────────────
qp = st.query_params
if qp.get("success") == "1":
    st.success("🎉 Payment successful! Your plan has been upgraded.")
    st.query_params.clear()
if qp.get("cancelled") == "1":
    st.info("Checkout cancelled — no charge was made.")
    st.query_params.clear()

# ── Pre-generate Stripe checkout URLs on page load ────────────────────────────
# Done here so the upgrade buttons are instant one-click links
_starter_url   = None
_unlimited_url = None

if uid and tier not in ("starter", "unlimited"):
    try:
        import stripe as _stripe
        _stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
        _app_url = st.secrets.get("APP_URL", "").rstrip("/")

        if tier == "free_trial":
            # Pre-generate both so either button works instantly
            _s = _stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": st.secrets.get("STRIPE_STARTER_PRICE_ID",""), "quantity": 1}],
                success_url=f"{_app_url}/pricing?success=1",
                cancel_url=f"{_app_url}/pricing?cancelled=1",
                client_reference_id=uid,
                customer_email=email,
                metadata={"uid": uid, "tier": "starter"},
            )
            _starter_url = _s.url

            _u = _stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": st.secrets.get("STRIPE_UNLIMITED_PRICE_ID",""), "quantity": 1}],
                success_url=f"{_app_url}/pricing?success=1",
                cancel_url=f"{_app_url}/pricing?cancelled=1",
                client_reference_id=uid,
                customer_email=email,
                metadata={"uid": uid, "tier": "unlimited"},
            )
            _unlimited_url = _u.url

        elif tier == "starter":
            _u = _stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": st.secrets.get("STRIPE_UNLIMITED_PRICE_ID",""), "quantity": 1}],
                success_url=f"{_app_url}/pricing?success=1",
                cancel_url=f"{_app_url}/pricing?cancelled=1",
                client_reference_id=uid,
                customer_email=email,
                metadata={"uid": uid, "tier": "unlimited"},
            )
            _unlimited_url = _u.url
    except Exception:
        pass  # Buttons will be disabled if URLs couldn't be generated

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## ⚡ Choose your plan")
st.markdown("<p style='color:#666;margin-top:-8px'>Simple pricing, cancel anytime.</p>",
            unsafe_allow_html=True)

# ── Current usage summary ──────────────────────────────────────────────────────
if tier == "free_trial":
    pct = min(used / 3 * 100, 100)
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                padding:14px 18px;margin-bottom:20px">
      <p style="margin:0 0 6px;font-size:.85rem;color:#888">
        Free trial &nbsp;·&nbsp; {used} of 3 lifetime analyses used
      </p>
      <div class="usage-bar-bg">
        <div class="usage-bar" style="width:{pct}%"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
elif tier == "starter":
    pct = min(used / limit * 100, 100)
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                padding:14px 18px;margin-bottom:20px">
      <p style="margin:0 0 6px;font-size:.85rem;color:#888">
        Starter plan &nbsp;·&nbsp; {used} of {limit} analyses used this month
      </p>
      <div class="usage-bar-bg">
        <div class="usage-bar" style="width:{pct}%"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
elif tier == "unlimited":
    st.markdown("""
    <div style="background:#171720;border:0.5px solid #F5B731;border-radius:10px;
                padding:14px 18px;margin-bottom:20px">
      <p style="margin:0;font-size:.85rem;color:#F5B731">
        ✓ You're on the Unlimited plan — no limits on analyses.
      </p>
    </div>
    """, unsafe_allow_html=True)

# ── Pricing cards ──────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    is_current = tier == "free_trial"
    st.markdown(f"""
    <div class="pricing-card">
      {'<div class="current-badge">Current plan</div>' if is_current else '<div style="height:24px"></div>'}
      <div style="font-size:1rem;font-weight:600;color:#F2EEE6;margin-bottom:6px">Free trial</div>
      <div style="margin-bottom:16px">
        <span class="price-amount">$0</span>
      </div>
      <div class="feature"><span class="feature-tick">✓</span>3 lifetime analyses</div>
      <div class="feature"><span class="feature-tick">✓</span>All features included</div>
      <div class="feature"><span class="feature-tick">✓</span>Saved reports</div>
      <div class="feature" style="color:#444"><span style="margin-right:8px">✗</span>No monthly reset</div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="free_btn", disabled=True, use_container_width=True)
    else:
        st.button("Downgrade", key="free_btn", disabled=True,
                  use_container_width=True, help="Contact support to downgrade")

with col2:
    is_current = tier == "starter"
    st.markdown(f"""
    <div class="pricing-card {'featured' if not is_current else ''}">
      {'<div class="badge">Most popular</div>' if not is_current else '<div class="current-badge">Current plan</div>'}
      <div style="font-size:1rem;font-weight:600;color:#F2EEE6;margin-bottom:6px">Starter</div>
      <div style="margin-bottom:16px">
        <span class="price-amount">$9</span>
        <span class="price-period">/month</span>
      </div>
      <div class="feature"><span class="feature-tick">✓</span>10 analyses per month</div>
      <div class="feature"><span class="feature-tick">✓</span>Resets monthly</div>
      <div class="feature"><span class="feature-tick">✓</span>All features included</div>
      <div class="feature"><span class="feature-tick">✓</span>Saved reports</div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="starter_btn", disabled=True, use_container_width=True)
    elif tier == "unlimited":
        st.button("Downgrade to Starter", key="starter_btn", disabled=True,
                  use_container_width=True, help="Contact support to downgrade")
    else:
        if _starter_url:
            st.link_button("Upgrade to Starter →", _starter_url,
                           type="primary", use_container_width=True)
        else:
            st.button("Upgrade to Starter", key="starter_btn", disabled=True,
                      use_container_width=True)

with col3:
    is_current = tier == "unlimited"
    st.markdown(f"""
    <div class="pricing-card">
      {'<div class="current-badge">Current plan</div>' if is_current else '<div style="height:24px"></div>'}
      <div style="font-size:1rem;font-weight:600;color:#F2EEE6;margin-bottom:6px">Unlimited</div>
      <div style="margin-bottom:16px">
        <span class="price-amount">$29</span>
        <span class="price-period">/month</span>
      </div>
      <div class="feature"><span class="feature-tick">✓</span>Unlimited analyses</div>
      <div class="feature"><span class="feature-tick">✓</span>No monthly cap</div>
      <div class="feature"><span class="feature-tick">✓</span>All features included</div>
      <div class="feature"><span class="feature-tick">✓</span>Priority support</div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="unlimited_btn", disabled=True, use_container_width=True)
    else:
        if _unlimited_url:
            st.link_button("Upgrade to Unlimited →", _unlimited_url,
                           type="primary", use_container_width=True)
        else:
            st.button("Upgrade to Unlimited", key="unlimited_btn", disabled=True,
                      use_container_width=True)

# ── Stripe Checkout redirect ────────────────────────────────────────────────────
# Triggered on next rerun after button click above
if st.session_state.get("_checkout_tier"):
    chosen_tier = st.session_state.pop("_checkout_tier")

    PRICE_IDS = {
        "starter":   st.secrets.get("STRIPE_STARTER_PRICE_ID", ""),
        "unlimited": st.secrets.get("STRIPE_UNLIMITED_PRICE_ID", ""),
    }
    price_id = PRICE_IDS.get(chosen_tier, "")
    app_url  = st.secrets.get("APP_URL", "").rstrip("/")

    if not price_id:
        st.error("Stripe price ID not configured. Add STRIPE_STARTER_PRICE_ID / "
                 "STRIPE_UNLIMITED_PRICE_ID to your Streamlit secrets.")
        st.stop()

    try:
        import stripe
        stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

        checkout = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{app_url}/pricing?success=1",
            cancel_url=f"{app_url}/pricing?cancelled=1",
            client_reference_id=uid,
            customer_email=email,
            metadata={"uid": uid, "tier": chosen_tier},
        )
        # Store URL in session and rerun to show loading screen
        st.session_state._stripe_url = checkout.url
        st.rerun()  # Rerun to show the link button cleanly
    except ImportError:
        st.error("stripe package not installed. Run: pip install stripe")
    except Exception as e:
        st.error(f"Could not create checkout session: {e}")

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#444;font-size:.8rem'>"
    "Payments processed securely by Stripe · Cancel anytime · "
    "Questions? cosmond00@gmail.com"
    "</p>",
    unsafe_allow_html=True,
)
