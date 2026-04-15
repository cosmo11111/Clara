"""
db.py — all Supabase read/write operations for Expense AI
Import this wherever you need to talk to the database.
"""
from __future__ import annotations
import streamlit as st
from auth import get_supabase

# ── Helpers ───────────────────────────────────────────────────────────────────
def _uid(user) -> str | None:
    """Extract user id string from a Supabase user object or dict."""
    if user is None:
        return None
    return user.id if hasattr(user, "id") else user.get("id")


# ═══════════════════════════════════════════════════════════
# CUSTOM CATEGORIES
# ═══════════════════════════════════════════════════════════
DEFAULT_CATEGORY_COLORS = {
    "Food & Dining":  "#f59e0b",
    "Transport":      "#60a5fa",
    "Shopping":       "#a78bfa",
    "Entertainment":  "#f472b6",
    "Health":         "#34d399",
    "Utilities":      "#94a3b8",
    "Travel":         "#fb923c",
    "Subscriptions":  "#e879f9",
    "Income":         "#4ade80",
    "Unknown":        "#6b7280",
}


@st.cache_data(ttl=60, show_spinner=False)
def load_categories(user_id: str) -> dict:
    """Return merged {name: color} — defaults + user's custom ones."""
    merged = dict(DEFAULT_CATEGORY_COLORS)
    try:
        sb  = get_supabase()
        res = sb.table("user_categories") \
                .select("name, color") \
                .eq("user_id", user_id) \
                .execute()
        for row in (res.data or []):
            merged[row["name"]] = row["color"]
    except Exception:
        pass
    return merged


def save_category(user_id: str, name: str, color: str) -> tuple[bool, str]:
    """Upsert a custom category. Returns (success, error_message)."""
    try:
        sb = get_supabase()
        sb.table("user_categories").upsert(
            {"user_id": user_id, "name": name, "color": color},
            on_conflict="user_id,name",
        ).execute()
        load_categories.clear()
        return True, ""
    except Exception as e:
        return False, str(e)


def delete_category(user_id: str, name: str) -> tuple[bool, str]:
    """Delete a custom category."""
    try:
        sb = get_supabase()
        sb.table("user_categories") \
          .delete() \
          .eq("user_id", user_id) \
          .eq("name", name) \
          .execute()
        load_categories.clear()
        return True, ""
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════
# VENDOR RULES
# ═══════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def load_vendor_rules(user_id: str) -> list[dict]:
    """Return list of {vendor_name, category, match_type} for this user."""
    try:
        sb  = get_supabase()
        res = sb.table("vendor_rules") \
                .select("vendor_name, category, match_type") \
                .eq("user_id", user_id) \
                .execute()
        return res.data or []
    except Exception:
        return []


def apply_vendor_rules(rules: list[dict], vendor_name: str) -> str | None:
    """
    Given a vendor name, return the matched category or None.
    Exact rules are checked before contains rules.
    Redacted / empty vendor names are never matched.
    """
    if not vendor_name or vendor_name.strip().lower() in ("", "unknown"):
        return None
    vn = vendor_name.strip().upper()
    # Exact first
    for r in rules:
        if r["match_type"] == "exact" and r["vendor_name"].upper() == vn:
            return r["category"]
    # Then contains
    for r in rules:
        if r["match_type"] == "contains" and r["vendor_name"].upper() in vn:
            return r["category"]
    return None


def save_vendor_rule(user_id: str, vendor_name: str,
                     category: str, match_type: str = "contains") -> tuple[bool, str]:
    """Upsert a vendor rule."""
    try:
        sb = get_supabase()
        sb.table("vendor_rules").upsert(
            {
                "user_id":     user_id,
                "vendor_name": vendor_name.strip(),
                "category":    category,
                "match_type":  match_type,
            },
            on_conflict="user_id,vendor_name",
        ).execute()
        load_vendor_rules.clear()
        return True, ""
    except Exception as e:
        return False, str(e)


def delete_vendor_rule(user_id: str, vendor_name: str) -> tuple[bool, str]:
    """Delete a vendor rule."""
    try:
        sb = get_supabase()
        sb.table("vendor_rules") \
          .delete() \
          .eq("user_id", user_id) \
          .eq("vendor_name", vendor_name) \
          .execute()
        load_vendor_rules.clear()
        return True, ""
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════
# EXPENSE REPORTS + LINE ITEMS
# ═══════════════════════════════════════════════════════════
@st.cache_data(ttl=30, show_spinner=False)
def load_reports(user_id: str) -> list[dict]:
    """Return all saved expense reports for this user, newest first."""
    try:
        sb  = get_supabase()
        res = sb.table("expense_reports") \
                .select("id, label, period_start, period_end, total_spend, total_income, created_at") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
        return res.data or []
    except Exception:
        return []


def save_report(user_id: str, label: str,
                period_start: str | None, period_end: str | None,
                transactions: list[dict]) -> tuple[bool, str]:
    """
    Save a labelled expense report and its line items.
    transactions: list of dicts with keys date, name, amount, category.
    No PDF content is ever stored.
    """
    try:
        sb = get_supabase()

        # Calculate totals from transactions
        total_spend  = sum(float(t["amount"]) for t in transactions
                           if float(t["amount"]) < 0)
        total_income = sum(float(t["amount"]) for t in transactions
                           if float(t["amount"]) > 0)

        # Insert the report header
        report_res = sb.table("expense_reports").insert({
            "user_id":       user_id,
            "label":         label.strip(),
            "period_start":  period_start or None,
            "period_end":    period_end   or None,
            "total_spend":   round(total_spend,  2),
            "total_income":  round(total_income, 2),
        }).execute()

        report_id = report_res.data[0]["id"]

        # Insert line items in one batch
        items = []
        for t in transactions:
            vendor  = t.get("name", "") or ""
            is_redacted = vendor.strip().lower() in ("", "unknown")
            items.append({
                "report_id":   report_id,
                "user_id":     user_id,
                "date":        str(t.get("date", "")),
                "vendor_name": vendor if not is_redacted else None,
                "amount":      round(float(t["amount"]), 2),
                "category":    t.get("category", "Unknown"),
                "is_redacted": is_redacted,
            })

        sb.table("line_items").insert(items).execute()
        load_reports.clear()
        return True, ""

    except Exception as e:
        return False, str(e)


def load_report_items(report_id: str) -> list[dict]:
    """Load line items for a specific saved report."""
    try:
        sb  = get_supabase()
        res = sb.table("line_items") \
                .select("date, vendor_name, amount, category, is_redacted") \
                .eq("report_id", report_id) \
                .order("created_at") \
                .execute()
        return res.data or []
    except Exception:
        return []


def delete_report(report_id: str) -> tuple[bool, str]:
    """Delete a report and its line items (cascade handles items)."""
    try:
        sb = get_supabase()
        sb.table("expense_reports") \
          .delete() \
          .eq("id", report_id) \
          .execute()
        load_reports.clear()
        return True, ""
    except Exception as e:
        return False, str(e)


# ── Subscription / usage functions ─────────────────────────────────────────────

TIER_LIMITS = {
    "free_trial": 3,    # lifetime
    "starter":    10,   # per month
    "unlimited":  None, # no limit
}

TIER_PRICES = {
    "free_trial": 0,
    "starter":    9,
    "unlimited":  29,
}

TIER_LABELS = {
    "free_trial": "Free Trial",
    "starter":    "Starter",
    "unlimited":  "Unlimited",
}


def get_profile(uid: str) -> dict:
    """Fetch the user's profile row (subscription tier, usage etc.)."""
    try:
        sb  = get_supabase()
        res = sb.table("profiles").select("*").eq("id", uid).single().execute()
        return res.data or {}
    except Exception:
        return {}


def can_analyse(uid: str) -> tuple[bool, str]:
    """
    Check if the user is allowed to run an analysis.
    Returns (True, "") or (False, reason_string).
    """
    profile = get_profile(uid)
    if not profile:
        return False, "Profile not found. Please sign out and back in."

    tier  = profile.get("subscription_tier", "free_trial")
    used  = profile.get("analyses_used", 0)
    limit = profile.get("analyses_limit", 3)

    if tier == "unlimited":
        return True, ""

    if tier == "free_trial":
        if used >= 3:
            return False, (
                f"You've used all 3 free analyses. "
                f"Upgrade to Starter ($9/mo) for 10 analyses/month "
                f"or Unlimited ($29/mo) for unlimited access."
            )
        return True, ""

    if tier == "starter":
        if used >= limit:
            return False, (
                f"You've used all {limit} analyses this month. "
                f"Upgrade to Unlimited ($29/mo) for unlimited access, "
                f"or wait until your plan resets next month."
            )
        return True, ""

    return False, "Unknown subscription tier."


def increment_usage(uid: str) -> bool:
    """Increment analyses_used by 1 after a successful analysis."""
    try:
        sb      = get_supabase()
        profile = get_profile(uid)
        used    = profile.get("analyses_used", 0)
        sb.table("profiles") \
          .update({"analyses_used": used + 1, "updated_at": "now()"}) \
          .eq("id", uid) \
          .execute()
        return True
    except Exception:
        return False


def upgrade_user(uid: str, tier: str,
                 stripe_customer_id: str = None,
                 stripe_sub_id: str = None,
                 period_start=None,
                 period_end=None) -> tuple[bool, str]:
    """
    Update a user's subscription tier after successful Stripe payment.
    Called by the webhook handler.
    """
    try:
        sb      = get_supabase()
        updates = {
            "subscription_tier": tier,
            "analyses_used":     0,
            "analyses_limit":    TIER_LIMITS.get(tier, 10) or 10,
            "updated_at":        "now()",
        }
        if stripe_customer_id:
            updates["stripe_customer_id"] = stripe_customer_id
        if stripe_sub_id:
            updates["stripe_sub_id"] = stripe_sub_id
        if period_start:
            updates["sub_period_start"] = period_start
        if period_end:
            updates["sub_period_end"] = period_end

        sb.table("profiles").update(updates).eq("id", uid).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def downgrade_user(uid: str) -> tuple[bool, str]:
    """Downgrade user to free_trial when subscription is cancelled/expired."""
    try:
        sb = get_supabase()
        sb.table("profiles").update({
            "subscription_tier":  "free_trial",
            "analyses_limit":     3,
            "stripe_sub_id":      None,
            "sub_period_start":   None,
            "sub_period_end":     None,
            "updated_at":         "now()",
        }).eq("id", uid).execute()
        return True, ""
    except Exception as e:
        return False, str(e)
