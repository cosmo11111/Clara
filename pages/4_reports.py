import streamlit as st
import streamlit.components.v1 as components
from auth import require_auth, get_user, clear_session, get_supabase
from db import load_reports, load_report_items, delete_report, DEFAULT_CATEGORY_COLORS

st.set_page_config(page_title="Saved Reports — Expense AI", page_icon="💳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0f0f13; color:#e8e6e1; }
section[data-testid="stSidebar"] { background:#17171d !important; border-right:1px solid #2a2a35; }
section[data-testid="stSidebar"] * { color:#c9c7c0 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
.stButton button { border-radius:8px !important; font-weight:500 !important; }
.stButton button[kind="primary"] { background:#f0c040 !important; color:#0f0f13 !important; border:none !important; }
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

with st.sidebar:
    st.markdown("## 💳 Expense AI")
    st.markdown("---")
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin:0'>Signed in as</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500'>{email}</p>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("← Back to app", use_container_width=True):
        st.switch_page("frontend.py")
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

if not uid:
    st.warning("Please sign in.")
    st.stop()

# ── Handle delete via session state callback ────────────────────────────────────
if "pending_delete_report" in st.session_state:
    rid = st.session_state.pop("pending_delete_report")
    ok, err = delete_report(rid)
    st.toast("Report deleted" if ok else f"Error: {err}", icon="🗑️" if ok else "⚠️")
    st.rerun()

reports = load_reports(uid)

c1, c2 = st.columns([4, 1])
with c1:
    st.markdown("## 📂 Saved Reports")
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with c2:
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page("frontend.py")
st.markdown("---")

if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#e8e6e1;margin-bottom:8px">No saved reports yet</p>
        <p style="color:#666;font-size:.9rem">Upload a bank statement, categorize your expenses,
        then save the report from Step 3.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

def cat_pill(cat):
    color = CATEGORY_COLORS.get(cat, "#6b7280")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;'
            f'background:{color}22;color:{color};border:1px solid {color}44">{cat}</span>')

def fmt(v):
    return f"{'−' if v<0 else '+'}${abs(v):,.2f}"

def acol(v):
    return "#f87171" if v < 0 else "#34d399"

# ── Build all card HTML + delete buttons ───────────────────────────────────────
# Each card is self-contained HTML with a CSS checkbox hack for expand/collapse.
# The delete button is rendered as a native st.button BELOW each card,
# but we make it look integrated by styling and positioning.

cards_html = ""
delete_slots = []   # list of (rid, label) — we'll render st.buttons after

for i, report in enumerate(reports):
    rid          = report["id"]
    label        = report["label"]
    period_start = report.get("period_start") or ""
    period_end   = report.get("period_end") or ""
    total_spend  = float(report.get("total_spend") or 0)
    total_income = float(report.get("total_income") or 0)
    created_at   = (report.get("created_at") or "")[:10]
    net          = total_income + total_spend
    net_color    = "#34d399" if net >= 0 else "#f87171"
    net_sign     = "+" if net >= 0 else "−"

    period_str = f"{period_start} – {period_end} · " if period_start and period_end else (
                 f"From {period_start} · " if period_start else "")

    items = load_report_items(rid)
    n_tx  = len(items)

    tx_rows = ""
    for item in items:
        vendor    = item.get("vendor_name") or ""
        is_red    = item.get("is_redacted", False)
        amt       = float(item.get("amount") or 0)
        cat       = item.get("category","Unknown")
        date      = item.get("date","")
        v_cell    = '<i style="color:#444">⬛ redacted</i>' if is_red else vendor
        tx_rows  += f"""<tr>
          <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:#888;font-size:12px;white-space:nowrap">{date}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:#e8e6e1">{v_cell}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:{acol(amt)};font-family:'DM Mono',monospace;white-space:nowrap">{fmt(amt)}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e1e28">{cat_pill(cat)}</td>
        </tr>"""

    # Use CSS :checked pseudo-class to toggle body — no JS needed for expand
    cb_id = f"cb_{rid.replace('-','')}"
    cards_html += f"""
<div style="margin-bottom:12px">
  <input type="checkbox" id="{cb_id}" style="display:none">

  <label for="{cb_id}" style="display:block;cursor:pointer">
    <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:12px;
                padding:18px 22px;transition:background .15s">
      <div style="display:flex;justify-content:space-between;align-items:center">

        <div>
          <div style="font-size:15px;font-weight:500;color:#e8e6e1">{label}</div>
          <div style="font-size:12px;color:#555;margin-top:3px">{period_str}saved {created_at}</div>
        </div>

        <div style="display:flex;align-items:center;gap:28px">
          <div style="text-align:right">
            <div style="font-size:14px;font-weight:500;color:#f87171;font-family:'DM Mono',monospace">${abs(total_spend):,.2f}</div>
            <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.04em">spent</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:14px;font-weight:500;color:#34d399;font-family:'DM Mono',monospace">${total_income:,.2f}</div>
            <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.04em">income</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:14px;font-weight:500;color:#e8e6e1;font-family:'DM Mono',monospace">{n_tx}</div>
            <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.04em">transactions</div>
          </div>
          <div style="font-size:11px;color:#555;margin-left:8px" class="chev-{cb_id}">▼</div>
        </div>

      </div>

      <!-- Expanded content — shown when checkbox checked -->
      <div class="body-{cb_id}" style="display:none;margin-top:18px;padding-top:18px;border-top:1px solid #2a2a38">

        <!-- Metric strip -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:18px">
          <div style="background:#0f0f13;border-radius:8px;padding:10px 12px">
            <div style="font-size:15px;font-weight:500;color:#f87171;font-family:'DM Mono',monospace">${abs(total_spend):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:3px;text-transform:uppercase;letter-spacing:.04em">Total spent</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:10px 12px">
            <div style="font-size:15px;font-weight:500;color:#34d399;font-family:'DM Mono',monospace">${total_income:,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:3px;text-transform:uppercase;letter-spacing:.04em">Income</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:10px 12px">
            <div style="font-size:15px;font-weight:500;color:{net_color};font-family:'DM Mono',monospace">{net_sign}${abs(net):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:3px;text-transform:uppercase;letter-spacing:.04em">Net</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:10px 12px">
            <div style="font-size:15px;font-weight:500;color:#e8e6e1;font-family:'DM Mono',monospace">{n_tx}</div>
            <div style="font-size:10px;color:#555;margin-top:3px;text-transform:uppercase;letter-spacing:.04em">Transactions</div>
          </div>
        </div>

        <!-- Transaction table -->
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr>
            <th style="color:#555;font-weight:400;text-align:left;padding:6px 10px;border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em;width:12%">Date</th>
            <th style="color:#555;font-weight:400;text-align:left;padding:6px 10px;border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em;width:38%">Merchant</th>
            <th style="color:#555;font-weight:400;text-align:left;padding:6px 10px;border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em;width:15%">Amount</th>
            <th style="color:#555;font-weight:400;text-align:left;padding:6px 10px;border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em">Category</th>
          </tr></thead>
          <tbody>{tx_rows}</tbody>
        </table>

      </div>
    </div>
  </label>
</div>

<style>
  #{cb_id}:checked ~ * .body-{cb_id},
  label[for="{cb_id}"] #{cb_id}:checked .body-{cb_id} {{ display:block !important; }}
  #{cb_id}:checked + label .body-{cb_id} {{ display:block !important; }}
</style>
"""
    delete_slots.append((rid, label, i))

# Compute total height — collapsed cards + some extra for potential expansion
total_height = len(reports) * 90 + 40
components.html(f"""<!DOCTYPE html><html><head>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:transparent;padding:2px}}
</style>
</head><body>
{cards_html}
<script>
// CSS :checked sibling selector doesn't work well across the label structure
// so we use minimal JS for the toggle instead
document.querySelectorAll('input[type=checkbox]').forEach(function(cb) {{
  cb.addEventListener('change', function() {{
    var id = this.id;
    var label = document.querySelector('label[for="' + id + '"]');
    var body = label.querySelector('[class^="body-"]');
    if (body) body.style.display = this.checked ? 'block' : 'none';
    // Resize iframe
    var h = document.body.scrollHeight + 10;
    window.frameElement && (window.frameElement.style.height = h + 'px');
  }});
}});
</script>
</body></html>""", height=total_height, scrolling=False)

# ── Delete buttons — rendered natively, visually associated via caption ─────────
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

for rid, label, idx in delete_slots:
    _, _, del_col = st.columns([5, 1, 1])
    with del_col:
        def _make_cb(r):
            def _cb(): st.session_state.pending_delete_report = r
            return _cb
        st.button(f"🗑", key=f"del_{rid}", on_click=_make_cb(rid),
                  help=f"Delete '{label}'", use_container_width=True)
