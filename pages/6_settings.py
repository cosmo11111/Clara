import streamlit as st
from auth import require_auth, get_user, clear_session, get_supabase, AUTH_CSS
from db import (get_profile, TIER_LABELS, load_categories, save_category, auto_assign_color,
                delete_category, load_vendor_rules, save_vendor_rule,
                delete_vendor_rule, DEFAULT_CATEGORY_COLORS)

st.set_page_config(page_title="Settings — Clara", page_icon="💳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0b0b12; color:#F2EEE6; }
section[data-testid="stSidebar"] { background:#0f0f18 !important; border-right:0.5px solid #1c1c28; }
section[data-testid="stSidebar"] * { color:#c8c5bf !important; }
section[data-testid="stSidebar"] button[kind="primary"] { color: #0f0f13 !important; }
section[data-testid="stSidebar"] button[kind="primary"] * { color: #0f0f13 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebarHeader"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 1rem !important; overflow: hidden !important; }
.stButton button { border-radius:8px !important; font-weight:500 !important; }
.stButton button[kind="primary"] { background:#F5B731 !important; color:#0f0f13 !important; border:none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
.section-card {
    background:#171720; border:0.5px solid #1c1c28; border-radius:12px;
    padding:20px 24px; margin-bottom:20px;
}
.section-title {
    font-size:.75rem; font-weight:600; color:#555; text-transform:uppercase;
    letter-spacing:.08em; margin:0 0 16px;
}
.rule-row {
    display:flex; align-items:center; justify-content:space-between;
    padding:8px 0; border-bottom:0.5px solid #1c1c28; font-size:.875rem;
}
.rule-row:last-child { border-bottom:none; }
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

profile    = get_profile(uid) if uid else {}
tier       = profile.get("subscription_tier", "free_trial")
used       = profile.get("analyses_used", 0)
limit      = profile.get("analyses_limit", 3)
tier_label = TIER_LABELS.get(tier, "Free Trial")
TIER_COLORS = {"free_trial":"#666","starter":"#3b82f6","unlimited":"#F5B731"}
tier_color  = TIER_COLORS.get(tier, "#666")
usage_str   = "Unlimited analyses" if tier=="unlimited" else \
              f"{used}/3 lifetime analyses" if tier=="free_trial" else \
              f"{used}/{limit} analyses this month"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page("frontend.py")
    st.markdown("<div style='padding-top:1rem'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#F2EEE6;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:8px;
                padding:8px 12px;margin-bottom:10px">
      <span style="font-size:11px;font-weight:600;color:#F2EEE6;
                   text-transform:uppercase;letter-spacing:.05em">{tier_label}</span>
      <div style="font-size:11px;color:#555;margin-top:2px">{usage_str}</div>
    </div>
    """, unsafe_allow_html=True)
    if tier == "free_trial":
        if st.button("⚡ Upgrade plan", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    elif tier == "starter":
        if st.button("⚡ Upgrade to Unlimited", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    else:
        if st.button("⚡ Manage plan", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    if st.button("📂 Saved Reports", use_container_width=True):
        st.switch_page("pages/4_reports.py")
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

st.html("""
<style>
  .st-key-sidebar_bottom {
    position: absolute; bottom: 16px; left: 0; right: 0; padding: 0 1rem;
  }
</style>
""")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:4px 0 8px">
  <span style="font-family:'DM Serif Display',serif;font-style:italic;font-size:2.8rem;color:#F5B731;letter-spacing:-.01em">Clara</span>
</div>
""", unsafe_allow_html=True)
st.markdown("## Settings")
st.markdown("---")

col1, col2 = st.columns([1, 1], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Account + Subscription
# ══════════════════════════════════════════════════════════════════════════════
with col1:

    # ── Account ───────────────────────────────────────────────────────────────
    st.markdown("<p class='section-title'>Account</p>", unsafe_allow_html=True)
    with st.container():
        st.markdown(f"<p style='color:#888;font-size:.8rem;margin:0 0 2px'>Email</p>",
                    unsafe_allow_html=True)
        st.markdown(f"<p style='color:#F2EEE6;font-size:.95rem;margin:0 0 16px'>{email}</p>",
                    unsafe_allow_html=True)

        if st.button("Change password", use_container_width=True):
            try:
                sb  = get_supabase()
                app = st.secrets.get("APP_URL", "").rstrip("/")
                sb.auth.reset_password_email(
                    email,
                    options={"redirect_to": f"{app}/reset_password"},
                )
                st.success("✅ Password reset email sent — check your inbox.")
            except Exception as e:
                st.error(f"Could not send reset email: {e}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Delete account — confirm before doing anything
        if st.session_state.get("_confirm_delete"):
            st.warning("⚠️ This will permanently delete your account and all saved reports. This cannot be undone.")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Yes, delete my account", type="primary",
                             use_container_width=True):
                    try:
                        sb = get_supabase()
                        # Delete user data then sign out
                        sb.table("expense_reports").delete().eq("user_id", uid).execute()
                        sb.table("line_items").delete().eq("user_id", uid).execute()
                        sb.table("user_categories").delete().eq("user_id", uid).execute()
                        sb.table("vendor_rules").delete().eq("user_id", uid).execute()
                        sb.auth.sign_out()
                        clear_session()
                        st.switch_page("pages/1_login.py")
                    except Exception as e:
                        st.error(f"Could not delete account: {e}")
                        st.session_state._confirm_delete = False
            with d2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state._confirm_delete = False
                    st.rerun()
        else:
            if st.button("Delete account", use_container_width=True):
                st.session_state._confirm_delete = True
                st.rerun()

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Subscription ──────────────────────────────────────────────────────────
    st.markdown("<p class='section-title'>Subscription</p>", unsafe_allow_html=True)

    # Usage bar
    if tier == "free_trial":
        pct = min(used / 3 * 100, 100)
        bar_color = "#f87171" if pct >= 100 else "#F5B731"
    elif tier == "starter":
        pct = min(used / limit * 100, 100)
        bar_color = "#f87171" if pct >= 100 else "#3b82f6"
    else:
        pct = 0
        bar_color = "#F5B731"

    st.markdown(f"""
    <div style="background:#0b0b12;border-radius:8px;padding:14px 16px;margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <span style="font-size:.85rem;font-weight:600;color:#F2EEE6;
                     text-transform:uppercase;letter-spacing:.04em">{tier_label}</span>
        <span style="font-size:.8rem;color:#888">{usage_str}</span>
      </div>
      {'<div style="background:#171720;border-radius:4px;height:6px"><div style="width:' + str(pct) + '%;height:6px;border-radius:4px;background:' + bar_color + '"></div></div>' if tier != "unlimited" else
       '<div style="font-size:.8rem;color:#4ade80">✓ Unlimited — no monthly cap</div>'}
    </div>
    """, unsafe_allow_html=True)

    if tier == "free_trial":
        if st.button("⚡ Upgrade plan", key="sub_upgrade_btn",
                     type="primary", use_container_width=True):
            st.switch_page("pages/5_pricing.py")
    elif tier == "starter":
        if st.button("⚡ Upgrade to Unlimited", key="sub_upgrade_btn",
                     type="primary", use_container_width=True):
            st.switch_page("pages/5_pricing.py")
        st.markdown(
            "<p style='font-size:.8rem;color:#444;margin-top:8px'>To cancel or downgrade "
            "email <a href='mailto:cosmond00@gmail.com' style='color:#555'>"
            "cosmond00@gmail.com</a></p>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<p style='font-size:.85rem;color:#F5B731;font-weight:500;margin:0 0 6px'>"
            "✦ Unlimited plan active</p>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='font-size:.8rem;color:#444;margin:0'>To cancel or downgrade "
            "email <a href='mailto:cosmond00@gmail.com' style='color:#555'>"
            "cosmond00@gmail.com</a></p>",
            unsafe_allow_html=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Categories + Vendor Rules
# ══════════════════════════════════════════════════════════════════════════════
with col2:

    # ── Categories ────────────────────────────────────────────────────────────
    st.markdown("<p class='section-title'>Categories</p>", unsafe_allow_html=True)

    cats = load_categories(uid) if uid else DEFAULT_CATEGORY_COLORS

    # Render existing categories
    for cat_name, cat_color in cats.items():
        is_default = cat_name in DEFAULT_CATEGORY_COLORS
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;padding:6px 0'>"
                f"<span style='width:10px;height:10px;border-radius:50%;"
                f"background:{cat_color};display:inline-block;flex-shrink:0'></span>"
                f"<span style='font-size:.875rem;color:#F2EEE6'>{cat_name}</span>"
                f"{'<span style=\"font-size:.7rem;color:#444;margin-left:4px\">default</span>' if is_default else ''}"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            pass  # spacer
        with c3:
            if not is_default:
                if st.button("✕", key=f"del_cat_{cat_name}",
                             use_container_width=True, help=f"Delete {cat_name}"):
                    ok, err = delete_category(uid, cat_name)
                    if ok:
                        st.toast(f"'{cat_name}' deleted")
                        load_categories.clear()
                        st.rerun()
                    else:
                        st.error(err)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown(
        "<p style='font-size:.75rem;color:#444;margin:4px 0 8px'>"
        "Colours are assigned automatically from the Clara palette.</p>",
        unsafe_allow_html=True
    )

    # Add new category
    with st.expander("＋ Add new category"):
        nc1, nc2 = st.columns([4, 1])
        with nc1:
            new_cat_name = st.text_input("Name", placeholder="e.g. Pet Care",
                                          key="settings_cat_name",
                                          label_visibility="collapsed")
        with nc2:
            if st.button("Save", key="settings_cat_save", use_container_width=True):
                if new_cat_name.strip():
                    ok, err = save_category(uid, new_cat_name.strip())
                    if ok:
                        st.toast(f"'{new_cat_name}' saved")
                        load_categories.clear()
                        st.rerun()
                    else:
                        st.error(err)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Vendor Rules ──────────────────────────────────────────────────────────
    st.markdown("<p class='section-title'>Vendor Rules</p>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:.8rem;color:#555;margin:-8px 0 12px'>When a vendor name matches, "
        "it's automatically assigned that category.</p>",
        unsafe_allow_html=True
    )

    rules = load_vendor_rules(uid) if uid else []

    if not rules:
        st.markdown("<p style='font-size:.85rem;color:#444;font-style:italic'>"
                    "No vendor rules yet — they're created automatically when you "
                    "change a category in the results page.</p>",
                    unsafe_allow_html=True)
    else:
        for rule in rules:
            vname = rule.get("vendor_name", "")
            vcat  = rule.get("category", "")
            mtype = rule.get("match_type", "contains")
            r1, r2, r3 = st.columns([3, 2, 1])
            with r1:
                st.markdown(
                    f"<p style='font-size:.875rem;color:#F2EEE6;margin:6px 0'>{vname}</p>",
                    unsafe_allow_html=True
                )
            with r2:
                st.markdown(
                    f"<p style='font-size:.875rem;color:#888;margin:6px 0'>"
                    f"→ {vcat} <span style='font-size:.75rem;color:#444'>({mtype})</span></p>",
                    unsafe_allow_html=True
                )
            with r3:
                if st.button("✕", key=f"del_rule_{vname}",
                             use_container_width=True, help=f"Delete rule for {vname}"):
                    ok, err = delete_vendor_rule(uid, vname)
                    if ok:
                        st.toast(f"Rule for '{vname}' deleted")
                        load_vendor_rules.clear()
                        st.rerun()
                    else:
                        st.error(err)

    # Add vendor rule manually
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("＋ Add vendor rule"):
        all_cat_names = list(cats.keys())
        vr1, vr2, vr3, vr4 = st.columns([3, 2, 1, 1])
        with vr1:
            new_vname = st.text_input("Vendor", placeholder="e.g. Ampol",
                                       key="settings_rule_vendor",
                                       label_visibility="collapsed")
        with vr2:
            new_vcat = st.selectbox("Category", all_cat_names,
                                     key="settings_rule_cat",
                                     label_visibility="collapsed")
        with vr3:
            new_mtype = st.selectbox("Match", ["contains", "exact"],
                                      key="settings_rule_match",
                                      label_visibility="collapsed")
        with vr4:
            if st.button("Save", key="settings_rule_save", use_container_width=True):
                if new_vname.strip():
                    ok, err = save_vendor_rule(uid, new_vname.strip(),
                                               new_vcat, new_mtype)
                    if ok:
                        st.toast(f"Rule saved for '{new_vname}'")
                        load_vendor_rules.clear()
                        st.rerun()
                    else:
                        st.error(err)
