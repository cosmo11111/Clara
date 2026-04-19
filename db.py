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
# ── Encryption helpers ────────────────────────────────────────────────────────
# Encrypts sensitive line_item fields (vendor_name, vendor_name_clean, amount)
# before writing to Supabase. Decrypts on read. Key stored in Streamlit secrets.
# If no key is configured, data is stored in plaintext (graceful fallback).

def _get_cipher():
    """Return a Fernet cipher from ENCRYPTION_KEY secret, or None if not set."""
    try:
        from cryptography.fernet import Fernet
        key = st.secrets.get("ENCRYPTION_KEY", "")
        if not key:
            return None
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _encrypt(value: str | float | None, cipher) -> str | None:
    """Encrypt a value to a base64 string. Returns None if value is None."""
    if value is None or cipher is None:
        return str(value) if value is not None else None
    try:
        return cipher.encrypt(str(value).encode()).decode()
    except Exception:
        return str(value)


def _decrypt(value: str | None, cipher) -> str | None:
    """Decrypt a base64 string back to plaintext. Returns value as-is if not encrypted."""
    if value is None or cipher is None:
        return value
    try:
        return cipher.decrypt(value.encode()).decode()
    except Exception:
        # Not encrypted (legacy data) — return as-is
        return value


DEFAULT_CATEGORY_COLORS = {
    # Primary categories — brand secondary palette
    "Food & Dining":  "#D97A6A",  # Warm Coral
    "Transport":      "#6F8FAF",  # Dusty Blue
    "Shopping":       "#8D7AA8",  # Lavender
    "Health":         "#7FA58A",  # Sage
    "Utilities":      "#8C8F9A",  # Cool Grey
    "Subscriptions":  "#9D8AB8",  # Lavender lighter
    "Travel":         "#C4694A",  # Warm Coral deeper
    "Entertainment":  "#B87898",  # Muted pink
    "Housing":        "#4A6A8F",  # Dusty Blue deeper
    "Groceries":      "#C49040",  # Warm amber
    "Education":      "#5A8A9F",  # Dusty teal
    "Personal Care":  "#A07898",  # Dusty mauve
    "Insurance":      "#7A8A8A",  # Muted teal-grey
    "Investments":    "#5A8A6A",  # Sage deeper
    "Transfers":      "#6A6D78",  # Cool grey muted
    "Income":         "#4ade80",  # Keep saturated green
    "Other":          "#6A6D78",  # Cool Grey muted
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
                .select("id, label, period_start, period_end, total_spend, total_income, category_totals, monthly_totals, top_vendors, transaction_count, tier_required, ai_insight, created_at") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
        return res.data or []
    except Exception:
        return []


def _parse_date(date_str: str):
    """Parse a transaction date string to a datetime.date, return None if unparseable."""
    from datetime import datetime
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _build_monthly_totals(transactions: list[dict]) -> dict:
    """
    Split spending transactions by calendar month.
    Returns {"2026-03": {"Food & Dining": 120.00, ...}, "2026-04": {...}}
    Works for cross-month statements. Uses transaction date for accurate split.
    Falls back to proportional split if date is unparseable.
    """
    from datetime import date as _date
    monthly: dict[str, dict[str, float]] = {}

    parseable = []
    unparseable = []
    for t in transactions:
        if float(t.get("amount", 0)) >= 0:
            continue  # skip income
        d = _parse_date(str(t.get("date", "")))
        if d:
            parseable.append((d, t))
        else:
            unparseable.append(t)

    # Add parseable transactions to their month bucket
    for d, t in parseable:
        month_key = d.strftime("%Y-%m")
        cat = t.get("category", "Other")
        amt = abs(float(t["amount"]))
        if month_key not in monthly:
            monthly[month_key] = {}
        monthly[month_key][cat] = round(
            monthly[month_key].get(cat, 0) + amt, 2
        )

    # For unparseable dates distribute evenly across months already found
    # (or put in a fallback bucket)
    if unparseable:
        if monthly:
            keys = list(monthly.keys())
            per_month_weight = 1 / len(keys)
            for t in unparseable:
                cat = t.get("category", "Other")
                amt = abs(float(t["amount"]))
                for key in keys:
                    if key not in monthly:
                        monthly[key] = {}
                    monthly[key][cat] = round(
                        monthly[key].get(cat, 0) + amt * per_month_weight, 2
                    )
        else:
            monthly["unknown"] = {}
            for t in unparseable:
                cat = t.get("category", "Other")
                amt = abs(float(t["amount"]))
                monthly["unknown"][cat] = round(
                    monthly["unknown"].get(cat, 0) + amt, 2
                )

    # Round all values
    for mk in monthly:
        for cat in monthly[mk]:
            monthly[mk][cat] = round(monthly[mk][cat], 2)

    return monthly


def _build_top_vendors(transactions: list[dict], n: int = 3) -> list[dict]:
    """
    Return top N vendors by total spend.
    Uses vendor_clean if available, falls back to raw name.
    Returns [{"vendor": "Woolworths", "amount": 245.50, "category": "Groceries"}]
    """
    vendor_spend: dict[str, float] = {}
    vendor_cat:   dict[str, str]   = {}

    for t in transactions:
        if float(t.get("amount", 0)) >= 0:
            continue
        raw   = t.get("name", "") or ""
        clean = t.get("vendor_clean", "") or raw
        if not clean or str(clean).lower() in ("nan", "none", "unknown", ""):
            clean = raw
        if not clean:
            continue
        amt = abs(float(t["amount"]))
        vendor_spend[clean] = round(vendor_spend.get(clean, 0) + amt, 2)
        if clean not in vendor_cat:
            vendor_cat[clean] = t.get("category", "Other")

    top = sorted(vendor_spend.items(), key=lambda x: x[1], reverse=True)[:n]
    return [{"vendor": v, "amount": a, "category": vendor_cat.get(v, "Other")}
            for v, a in top]


def check_duplicate_report(user_id: str,
                            period_start: str | None,
                            period_end:   str | None) -> bool:
    """
    Return True if an existing report overlaps the given date range.
    Used to warn the user before saving a duplicate.
    """
    if not period_start or not period_end:
        return False
    try:
        sb  = get_supabase()
        res = sb.table("expense_reports")                 .select("id, period_start, period_end")                 .eq("user_id", user_id)                 .execute()
        existing = res.data or []
        from datetime import datetime
        def _d(s):
            try: return datetime.strptime(s, "%Y-%m-%d").date()
            except: return None
        new_s = _d(period_start)
        new_e = _d(period_end)
        if not new_s or not new_e:
            return False
        for r in existing:
            ex_s = _d(r.get("period_start", ""))
            ex_e = _d(r.get("period_end",   ""))
            if not ex_s or not ex_e:
                continue
            # Overlap: not (new ends before existing starts OR new starts after existing ends)
            if not (new_e < ex_s or new_s > ex_e):
                return True
        return False
    except Exception:
        return False


def save_report(user_id: str, label: str,
                period_start: str | None, period_end: str | None,
                transactions: list[dict],
                tier_required: str = "starter",
                ai_insight: str | None = None) -> tuple[bool, str]:
    """
    Save a labelled expense report.
    - All tiers: saves summary (category_totals, monthly_totals, top_vendors, metrics)
    - Starter+:  also saves line_items for full transaction review
    transactions: list of dicts with keys date, name, vendor_clean, amount, category.
    No PDF content is ever stored.
    """
    try:
        sb = get_supabase()

        # ── Compute summary fields ────────────────────────────────────────────
        total_spend  = sum(float(t["amount"]) for t in transactions
                           if float(t.get("amount", 0)) < 0)
        total_income = sum(float(t["amount"]) for t in transactions
                           if float(t.get("amount", 0)) > 0)

        cat_totals     = {}
        for t in transactions:
            if float(t.get("amount", 0)) < 0:
                cat = t.get("category", "Other")
                cat_totals[cat] = round(
                    cat_totals.get(cat, 0) + abs(float(t["amount"])), 2
                )

        monthly_totals = _build_monthly_totals(transactions)
        top_vendors    = _build_top_vendors(transactions, n=3)

        # ── Insert report header (all tiers) ──────────────────────────────────
        report_res = sb.table("expense_reports").insert({
            "user_id":           user_id,
            "label":             label.strip(),
            "period_start":      period_start or None,
            "period_end":        period_end   or None,
            "total_spend":       round(total_spend,  2),
            "total_income":      round(total_income, 2),
            "category_totals":   cat_totals,
            "monthly_totals":    monthly_totals,
            "top_vendors":       top_vendors,
            "transaction_count": len(transactions),
            "tier_required":     tier_required,
            "ai_insight":        ai_insight or None,
        }).execute()

        report_id = report_res.data[0]["id"]

        # ── Insert line items (starter+ only, encrypted) ─────────────────────
        if tier_required in ("starter", "unlimited"):  # free tier saves summary only
            cipher = _get_cipher()
            items  = []
            for t in transactions:
                raw_name    = t.get("name", "") or ""
                clean_name  = t.get("vendor_clean", "") or raw_name
                is_redacted = raw_name.strip().lower() in ("", "unknown")
                amt         = round(float(t["amount"]), 2)
                items.append({
                    "report_id":         report_id,
                    "user_id":           user_id,
                    "date":              str(t.get("date", "")),
                    "vendor_name":       _encrypt(raw_name,   cipher) if not is_redacted else None,
                    "vendor_name_clean": _encrypt(clean_name, cipher) if not is_redacted else None,
                    "amount":            _encrypt(amt,        cipher),
                    "category":          t.get("category", "Other"),
                    "is_redacted":       is_redacted,
                })
            if items:
                sb.table("line_items").insert(items).execute()

        load_reports.clear()
        return True, ""

    except Exception as e:
        return False, str(e)


def load_report_items(report_id: str) -> list[dict]:
    """Load and decrypt line items for a specific saved report."""
    try:
        sb  = get_supabase()
        res = sb.table("line_items")                 .select("date, vendor_name, vendor_name_clean, amount, category, is_redacted")                 .eq("report_id", report_id)                 .order("created_at")                 .execute()
        rows   = res.data or []
        cipher = _get_cipher()
        for row in rows:
            row["vendor_name"]       = _decrypt(row.get("vendor_name"),       cipher)
            row["vendor_name_clean"] = _decrypt(row.get("vendor_name_clean"), cipher)
            # amount stored as encrypted string — decrypt then convert back to float
            raw_amt = _decrypt(row.get("amount"), cipher)
            try:
                row["amount"] = float(raw_amt) if raw_amt is not None else 0.0
            except (ValueError, TypeError):
                row["amount"] = 0.0
        return rows
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
                "You've used all 3 free analyses. "
                "Upgrade to Starter (9/mo) for 10 analyses/month "
                "or Unlimited (29/mo) for unlimited access."
            )
        return True, ""

    if tier == "starter":
        if used >= limit:
            return False, (
                f"You've used all {limit} analyses this month. "
                "Upgrade to Unlimited (29/mo) for unlimited access, "
                "or wait until your plan resets next month."
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
