import streamlit as st
from auth import require_auth, get_user, get_supabase, clear_session
from db import get_profile, TIER_LABELS

st.set_page_config(page_title="Pricing — Clara", page_icon="💳", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0b0b12; color:#F2EEE6; }
section[data-testid="stSidebar"] { background:#0f0f18 !important; border-right:0.5px solid #1c1c28; }
section[data-testid="stSidebar"] * { color:#c8c5bf !important; }
section[data-testid="stSidebar"] button[kind="primary"] { color:#0b0b12 !important; }
section[data-testid="stSidebar"] button[kind="primary"] * { color:#0b0b12 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
[data-testid="stHeader"] { display:none !important; }
[data-testid="stSidebarNav"] { display:none !important; }
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:opacity .15s !important; }
.stButton button[kind="primary"] { background:#F5B731 !important; color:#0b0b12 !important; border:none !important; }
.stLinkButton a { border-radius:8px !important; font-weight:500 !important; }

/* Pull buttons up tight against the card above */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="column"] > div > div > div[data-testid="stButton"],
div[data-testid="column"] > div > div > div[data-testid="stLinkButton"] {
    margin-top:-8px !important;
}
.pc { margin-bottom:0 !important; }

.pc {
    background:#171720; border:0.5px solid #1c1c28; border-radius:14px;
    padding:1.75rem 1.5rem; height:100%;
}
.pc.featured { border-color:#F5B731; }
.pc.current  { border-color:#252535; }
.pc-badge {
    display:inline-block; background:#F5B731; color:#0b0b12;
    font-size:10px; font-weight:500; padding:3px 10px;
    border-radius:20px; margin-bottom:.75rem;
    letter-spacing:.04em; text-transform:uppercase;
}
.pc-current-badge {
    display:inline-block; background:#252535; color:#666;
    font-size:10px; font-weight:500; padding:3px 10px;
    border-radius:20px; margin-bottom:.75rem;
}
.pc-name { font-size:1rem; font-weight:500; color:#F2EEE6; margin-bottom:.4rem; }
.pc-price {
    font-family:'DM Serif Display',serif; font-style:italic;
    font-size:2.4rem; color:#F2EEE6; line-height:1;
}
.pc-period { font-size:.85rem; color:#555; margin-left:3px; }
.pc-desc { font-size:.75rem; color:#444; margin:.35rem 0 1rem; }
.pc-div { border:none; border-top:0.5px solid #1c1c28; margin:.9rem 0; }
.pc-feat { font-size:.85rem; color:#666; padding:4px 0; display:flex; gap:8px; }
.pc-feat.on { color:#c8c5bf; }
.pc-tick { color:#F5B731; }
.pc-cross { color:#252535; }
[data-testid="stSidebarNav"] { display:none !important; }
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page("frontend.py")

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#555;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
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
    position:absolute; bottom:16px; left:0; right:0; padding:0 1rem;
  }
</style>
""")

# ── Handle Stripe redirects ────────────────────────────────────────────────────
qp = st.query_params
if qp.get("success") == "1":
    st.success("Payment successful! Your plan has been upgraded.")
    st.query_params.clear()
if qp.get("cancelled") == "1":
    st.info("Checkout cancelled — no charge was made.")
    st.query_params.clear()

# ── Pre-generate Stripe URLs ───────────────────────────────────────────────────
_starter_url   = None
_unlimited_url = None

if uid:
    try:
        import stripe as _stripe
        _stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
        _app_url = st.secrets.get("APP_URL", "").rstrip("/")

        if tier in ("free_trial", "starter"):
            if tier == "free_trial":
                _s = _stripe.checkout.Session.create(
                    mode="subscription",
                    line_items=[{"price": st.secrets.get("STRIPE_STARTER_PRICE_ID",""), "quantity": 1}],
                    success_url=f"{_app_url}/pricing?success=1",
                    cancel_url=f"{_app_url}/pricing?cancelled=1",
                    client_reference_id=uid, customer_email=email,
                    metadata={"uid": uid, "tier": "starter"},
                )
                _starter_url = _s.url

            _u = _stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": st.secrets.get("STRIPE_UNLIMITED_PRICE_ID",""), "quantity": 1}],
                success_url=f"{_app_url}/pricing?success=1",
                cancel_url=f"{_app_url}/pricing?cancelled=1",
                client_reference_id=uid, customer_email=email,
                metadata={"uid": uid, "tier": "unlimited"},
            )
            _unlimited_url = _u.url
    except Exception:
        pass

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:4px 0 8px">
  <span style="font-family:'DM Serif Display',serif;font-style:italic;font-size:2.8rem;
               color:#F5B731;letter-spacing:-.01em">Clara</span>
</div>
""", unsafe_allow_html=True)

st.markdown("## Plans & pricing")
st.markdown("<p style='color:#555;margin-top:-8px;margin-bottom:2rem'>Simple pricing, cancel anytime.</p>",
            unsafe_allow_html=True)

# ── Unlimited active banner ────────────────────────────────────────────────────
if tier == "unlimited":
    st.markdown("""
    <div style="background:#171720;border:0.5px solid #F5B731;border-radius:10px;
                padding:14px 18px;margin-bottom:1.5rem;display:flex;align-items:center;gap:10px">
      <span style="color:#F5B731;font-size:1.1rem">✦</span>
      <div>
        <div style="font-size:.9rem;font-weight:500;color:#F2EEE6;margin-bottom:2px">
          You're on Unlimited
        </div>
        <div style="font-size:.8rem;color:#555">
          No cap on analyses. All features included. To manage or cancel your subscription
          contact us at cosmond00@gmail.com.
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Usage bar for free/starter ─────────────────────────────────────────────────
elif tier == "free_trial":
    pct = min(used / 3 * 100, 100)
    bar_color = "#9e4a4a" if pct >= 100 else "#F5B731"
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                padding:12px 16px;margin-bottom:1.5rem">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px">
        <span style="font-size:.8rem;color:#555">Free trial</span>
        <span style="font-size:.8rem;color:#555">{used} / 3 lifetime analyses</span>
      </div>
      <div style="background:#0b0b12;border-radius:4px;height:5px">
        <div style="width:{pct}%;height:5px;border-radius:4px;background:{bar_color}"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

elif tier == "starter":
    pct = min(used / limit * 100, 100)
    bar_color = "#9e4a4a" if pct >= 100 else "#F5B731"
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                padding:12px 16px;margin-bottom:1.5rem">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px">
        <span style="font-size:.8rem;color:#555">Starter plan</span>
        <span style="font-size:.8rem;color:#555">{used} / {limit} analyses this month</span>
      </div>
      <div style="background:#0b0b12;border-radius:4px;height:5px">
        <div style="width:{pct}%;height:5px;border-radius:4px;background:{bar_color}"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Pricing cards ──────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

# Determine which card gets the gold border:
# free_trial → Starter featured
# starter    → Unlimited featured
# unlimited  → none featured
free_featured     = False
starter_featured  = tier == "free_trial"
unlimited_featured = tier == "starter"

with col1:
    is_current = tier == "free_trial"
    badge = '<div class="pc-current-badge">Current plan</div>' if is_current else '<div style="height:26px"></div>'
    st.markdown(f"""
    <div class="pc {'current' if is_current else ''}">
      {badge}
      <div class="pc-name">Free trial</div>
      <div style="margin:.35rem 0">
        <span class="pc-price">$0</span>
      </div>
      <div class="pc-desc">3 lifetime analyses</div>
      <hr class="pc-div">
      <div class="pc-feat on"><span class="pc-tick">✓</span>AI categorisation</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Spending charts</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Save report summaries</div>
      <div class="pc-feat"><span class="pc-cross">✗</span>AI insights</div>
      <div class="pc-feat"><span class="pc-cross">✗</span>Full transaction history</div>
      <div style="height:28px"></div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="free_btn", disabled=True, use_container_width=True)
    elif tier in ("starter", "unlimited"):
        st.button("Downgrade", key="free_btn", disabled=True,
                  use_container_width=True, help="Contact cosmond00@gmail.com to downgrade")

with col2:
    is_current = tier == "starter"
    if starter_featured:
        badge = '<div class="pc-badge">Most popular</div>'
    elif is_current:
        badge = '<div class="pc-current-badge">Current plan</div>'
    else:
        badge = '<div style="height:26px"></div>'

    st.markdown(f"""
    <div class="pc {'featured' if starter_featured else 'current' if is_current else ''}">
      {badge}
      <div class="pc-name">Starter</div>
      <div style="margin:.35rem 0">
        <span class="pc-price">$9</span>
        <span class="pc-period">/month</span>
      </div>
      <div class="pc-desc">10 analyses per month</div>
      <hr class="pc-div">
      <div class="pc-feat on"><span class="pc-tick">✓</span>Everything in free</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>AI insights</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Full transaction history</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Historical reports</div>
      <div class="pc-feat"><span class="pc-cross">✗</span>Unlimited analyses</div>
      <div style="margin-top:10px;font-size:.75rem;color:#3a3a50;font-style:italic">
        More features to come
      </div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="starter_btn", disabled=True, use_container_width=True)
    elif tier == "free_trial":
        if _starter_url:
            st.link_button("Get Starter →", _starter_url,
                           type="primary", use_container_width=True)
        else:
            st.button("Get Starter", key="starter_btn", disabled=True, use_container_width=True)
    elif tier == "unlimited":
        st.button("Downgrade to Starter", key="starter_btn", disabled=True,
                  use_container_width=True, help="Contact cosmond00@gmail.com to downgrade")

with col3:
    is_current = tier == "unlimited"
    if unlimited_featured:
        badge = '<div class="pc-badge">Upgrade</div>'
    elif is_current:
        badge = '<div class="pc-current-badge">Current plan</div>'
    else:
        badge = '<div style="height:26px"></div>'

    st.markdown(f"""
    <div class="pc {'featured' if unlimited_featured else 'current' if is_current else ''}">
      {badge}
      <div class="pc-name">Unlimited</div>
      <div style="margin:.35rem 0">
        <span class="pc-price">$29</span>
        <span class="pc-period">/month</span>
      </div>
      <div class="pc-desc">No monthly cap</div>
      <hr class="pc-div">
      <div class="pc-feat on"><span class="pc-tick">✓</span>Everything in Starter</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Unlimited analyses</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Saving ratio metric</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Investment projection</div>
      <div class="pc-feat on"><span class="pc-tick">✓</span>Budget targets</div>
      <div style="margin-top:10px;font-size:.75rem;color:#3a3a50;font-style:italic">
        More features to come
      </div>
    </div>
    """, unsafe_allow_html=True)
    if is_current:
        st.button("Current plan", key="unlimited_btn", disabled=True, use_container_width=True)
    else:
        if _unlimited_url:
            st.link_button("Get Unlimited →", _unlimited_url,
                           type="primary", use_container_width=True)
        else:
            st.button("Get Unlimited", key="unlimited_btn", disabled=True,
                      use_container_width=True)

# ── Subscription management ────────────────────────────────────────────────────
if tier in ("starter", "unlimited"):
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.markdown("<hr style='border:none;border-top:0.5px solid #1c1c28;margin-bottom:1.5rem'>",
                unsafe_allow_html=True)
    st.markdown("<p style='font-size:.75rem;color:#444;text-transform:uppercase;"
                "letter-spacing:.08em;margin-bottom:.5rem'>Manage subscription</p>",
                unsafe_allow_html=True)
    st.markdown("""
    <p style='font-size:.85rem;color:#555;line-height:1.7;margin-bottom:1rem'>
    To cancel, downgrade, or make changes to your subscription contact us at
    <a href='mailto:cosmond00@gmail.com' style='color:#666'>cosmond00@gmail.com</a>.
    We'll action your request within one business day.
    </p>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:#252535;font-size:.8rem'>"
    "Payments processed securely by Stripe · Cancel anytime</p>",
    unsafe_allow_html=True,
)
