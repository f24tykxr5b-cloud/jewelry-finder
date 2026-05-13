import streamlit as st
import pandas as pd
import time
import json
from pathlib import Path
from datetime import datetime

from platforms_data import PLATFORMS
from traffic_fetcher import fetch_similarweb_data
from platform_discovery import search_new_platforms

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="💎 מצאן פלטפורמות תכשיטים",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CACHE_FILE = Path("traffic_cache.json")
TRAFFIC_TTL_HOURS = 12


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap');

* { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Heebo', sans-serif !important;
    direction: rtl;
}

/* ── Hero ── */
.hero {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 20px;
    padding: 36px 28px 28px;
    margin-bottom: 24px;
    color: white;
    text-align: center;
}
.hero-title { font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 800; margin: 0 0 6px; }
.hero-sub   { font-size: 1rem; opacity: 0.7; margin: 0 0 20px; }
.hero-stats { display: flex; justify-content: center; gap: 32px; flex-wrap: wrap; }
.hero-stat  { text-align: center; }
.hero-stat-val { font-size: 1.8rem; font-weight: 700; color: #F59E0B; }
.hero-stat-lbl { font-size: 0.75rem; opacity: 0.65; }

/* ── Filter chips ── */
.chip-row {
    display: flex; flex-wrap: wrap; gap: 8px;
    justify-content: center; margin-bottom: 20px;
}

/* ── Cards grid ── */
.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

/* ── Card ── */
.pcard {
    background: white;
    border-radius: 18px;
    padding: 0;
    border: 1px solid #e8ecf0;
    box-shadow: 0 2px 10px rgba(0,0,0,.05);
    overflow: hidden;
    transition: transform .15s, box-shadow .15s;
    cursor: pointer;
}
.pcard:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.1); }

.pcard-top {
    height: 6px;
}
.pcard-body { padding: 18px 20px 16px; }
.pcard-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.pcard-name { font-size: 1.2rem; font-weight: 700; color: #1a1a2e; }
.pcard-cat  {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; color: white; white-space: nowrap;
}
.pcard-spec { color: #666; font-size: 0.88rem; margin: 6px 0 12px; line-height: 1.4; }
.pcard-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.pill {
    background: #f1f5f9; color: #475569; padding: 3px 10px;
    border-radius: 12px; font-size: 0.78rem;
}
.pill-fee  { background: #fef3c7; color: #92400e; }
.pill-rank { background: #ede9fe; color: #5b21b6; }
.pill-traf { background: #dcfce7; color: #166534; }
.pcard-note {
    background: #fffbeb; border-right: 3px solid #F59E0B;
    padding: 8px 12px; border-radius: 0 8px 8px 0;
    font-size: 0.82rem; color: #78350f; line-height: 1.4;
}
.pcard-footer {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px;
    border-top: 1px solid #f0f0f0;
    background: #fafafa;
}
.pcard-stars { font-size: 1rem; letter-spacing: 1px; }
.pcard-link {
    display: inline-flex; align-items: center; gap: 4px;
    background: #1a1a2e; color: white !important; text-decoration: none;
    padding: 6px 14px; border-radius: 8px; font-size: 0.8rem; font-weight: 600;
}
.pcard-link:hover { background: #0f3460; }

/* ── Details panel ── */
.detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 10px; margin: 12px 0;
}
.dbox {
    background: #f8fafc; border-radius: 12px; padding: 12px;
    text-align: center;
}
.dbox-val { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; }
.dbox-lbl { font-size: 0.72rem; color: #94a3b8; margin-top: 2px; }

/* ── Updated badge ── */
.updated-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;
    padding: 4px 12px; border-radius: 20px; font-size: 0.78rem;
}

/* ── New find badge ── */
.new-badge {
    display: inline-block; background: #7c3aed; color: white;
    padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700;
    vertical-align: middle; margin-right: 6px;
}

/* ── Loading spinner override ── */
.stSpinner > div { justify-content: center; }

/* ── Streamlit cleanup ── */
.block-container { padding-top: 1.5rem !important; }
#MainMenu, footer, header { visibility: hidden; }
.stExpander { border: 1px solid #e8ecf0!important; border-radius: 14px!important; overflow:hidden; }
</style>
""", unsafe_allow_html=True)


# ── Cache helpers ──────────────────────────────────────────────────────────────
def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            age_h = (time.time() - raw.get("_ts", 0)) / 3600
            if age_h < TRAFFIC_TTL_HOURS:
                return raw
        except Exception:
            pass
    return {}


def _save_cache(data: dict):
    data["_ts"] = time.time()
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@st.cache_data(ttl=TRAFFIC_TTL_HOURS * 3600, show_spinner=False)
def get_traffic_cached(domain: str) -> dict:
    return fetch_similarweb_data(domain)


# ── Session state init ────────────────────────────────────────────────────────
if "traffic" not in st.session_state:
    cached = _load_cache()
    st.session_state.traffic = cached.get("traffic", {})
    st.session_state.traffic_ts = cached.get("_ts", 0)

if "new_platforms" not in st.session_state:
    st.session_state.new_platforms = []

if "filter_cat" not in st.session_state:
    st.session_state.filter_cat = "הכל"

if "filter_focus" not in st.session_state:
    st.session_state.filter_focus = 1


# ── Helpers ───────────────────────────────────────────────────────────────────
CAT_COLORS = {
    "מכרזים":               "#E74C3C",
    "מרקטפלייס + מכרזים":   "#E67E22",
    "מרקטפלייס יד-עשייה":   "#27AE60",
    "יוקרה":                "#8E44AD",
    "יד שנייה יוקרה":       "#2980B9",
    "אנטיק ווינטג'":        "#795548",
    "מרקטפלייס יד שנייה":   "#F39C12",
    "אגרגטור מכרזים":       "#16A085",
    "בית מכירות":           "#2C3E50",
    "שעונים":               "#1ABC9C",
    "מכרזים לתכשיטים":      "#D4AC0D",
}

def stars(n: int) -> str:
    return "💎" * n + "◇" * (5 - n)

def ts_label(ts: float) -> str:
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%d/%m/%Y %H:%M")

def render_card(p: dict, td: dict, is_new: bool = False):
    domain  = p["domain"]
    color   = p.get("color", "#666")
    cat_col = CAT_COLORS.get(p["category"], "#888")
    monthly = td.get("monthly_visits", "—") if td else "—"
    g_rank  = td.get("global_rank", "—")    if td else "—"
    new_tag = '<span class="new-badge">חדש</span>' if is_new else ""

    rank_pill = f'<span class="pill pill-rank">🏆 #{g_rank}</span>' if g_rank != "—" else ""
    traf_pill = f'<span class="pill pill-traf">🌐 {monthly}/חודש</span>' if monthly != "—" else ""

    html = f"""
    <div class="pcard">
        <div class="pcard-top" style="background:{color}"></div>
        <div class="pcard-body">
            <div class="pcard-head">
                <span class="pcard-name">{new_tag}{p['name']}</span>
                <span class="pcard-cat" style="background:{cat_col}">{p['category']}</span>
            </div>
            <div class="pcard-spec">{p['specialty']}</div>
            <div class="pcard-pills">
                <span class="pill pill-fee">💰 {p['seller_fees']}</span>
                {rank_pill}
                {traf_pill}
            </div>
            <div class="pcard-note">💡 {p['notes']}</div>
        </div>
        <div class="pcard-footer">
            <span class="pcard-stars">{stars(p['jewelry_focus'])}</span>
            <a href="{p['url']}" target="_blank" class="pcard-link">בקר באתר ←</a>
        </div>
    </div>
    """
    return html


def render_detail(p: dict, td: dict):
    """Detailed expander content."""
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**📋 פרטי הפלטפורמה**")
        rows = {
            "💰 עמלת מוכר":  p["seller_fees"],
            "🛒 עמלת קונה":  p["buyer_fees"],
            "🌍 אזורים":     " · ".join(p["regions"]),
            "🗣 שפות":       " · ".join(p["languages"]),
        }
        for k, v in rows.items():
            st.markdown(f"**{k}** — {v}")

    with col2:
        st.markdown("**📊 טראפיק (SimilarWeb)**")
        if not td:
            st.caption("לחץ 'רענן טראפיק' בסרגל הצד")
        else:
            metrics = [
                ("🌐 ביקורים/חודש", td.get("monthly_visits", "—")),
                ("🏆 דירוג גלובלי",  "#" + td.get("global_rank", "—") if td.get("global_rank", "—") != "—" else "—"),
                ("↩️ Bounce Rate",   td.get("bounce_rate", "—")),
                ("📄 עמודים/ביקור", td.get("pages_per_visit", "—")),
                ("⏱ זמן ממוצע",    td.get("avg_visit_duration", "—")),
            ]
            grid_html = '<div class="detail-grid">' + "".join(
                f'<div class="dbox"><div class="dbox-val">{v}</div><div class="dbox-lbl">{l}</div></div>'
                for l, v in metrics
            ) + "</div>"
            st.markdown(grid_html, unsafe_allow_html=True)

            countries = td.get("top_countries", [])
            if countries:
                st.markdown("**🗺 מדינות מובילות:** " + " · ".join(countries))

            if td.get("error"):
                st.caption(f"⚠️ {td['error']}")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ הגדרות")

    st.markdown("### 🔄 עדכון נתונים")

    ts = st.session_state.get("traffic_ts", 0)
    if ts:
        st.markdown(
            f'<span class="updated-badge">✅ עודכן {ts_label(ts)}</span>',
            unsafe_allow_html=True,
        )

    if st.button("🌐 רענן נתוני טראפיק", use_container_width=True):
        st.session_state.traffic = {}
        st.session_state.traffic_ts = 0
        with st.spinner("מאחזר נתונים..."):
            results = {}
            prog = st.progress(0)
            all_domains = [p["domain"] for p in PLATFORMS]
            for i, p in enumerate(PLATFORMS):
                results[p["domain"]] = fetch_similarweb_data(p["domain"])
                prog.progress((i + 1) / len(PLATFORMS))
                time.sleep(1.0)
            prog.empty()
        st.session_state.traffic = results
        st.session_state.traffic_ts = time.time()
        cache_data = {"traffic": results}
        _save_cache(cache_data)
        st.success("✅ עודכן!")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 חפש פלטפורמות חדשות")
    st.caption("מחפש ב-DuckDuckGo פלטפורמות שלא ברשימה")

    if st.button("🔎 חפש חדשות", use_container_width=True):
        known = {p["domain"] for p in PLATFORMS}
        with st.spinner("מחפש..."):
            found = search_new_platforms(known, max_results=5)
        st.session_state.new_platforms = found
        if found:
            st.success(f"נמצאו {len(found)} פלטפורמות חדשות!")
        else:
            st.info("לא נמצאו חדשות כרגע")

    st.markdown("---")
    st.markdown("### 🔎 סינון")

    all_cats = ["הכל"] + sorted(set(p["category"] for p in PLATFORMS))
    st.session_state.filter_cat = st.selectbox(
        "סוג פלטפורמה", all_cats,
        index=all_cats.index(st.session_state.filter_cat),
    )
    st.session_state.filter_focus = st.slider(
        "רלוונטיות מינימלית לתכשיטים", 1, 5,
        st.session_state.filter_focus
    )

    st.markdown("---")
    st.caption("נתוני טראפיק: SimilarWeb · חיפוש: DuckDuckGo · חינמי לחלוטין")


# ── Filter ────────────────────────────────────────────────────────────────────
filtered = [
    p for p in PLATFORMS
    if (st.session_state.filter_cat == "הכל" or p["category"] == st.session_state.filter_cat)
    and p["jewelry_focus"] >= st.session_state.filter_focus
]
filtered.sort(key=lambda p: (-p["jewelry_focus"], p["name"]))


# ── Hero ──────────────────────────────────────────────────────────────────────
total_traffic = sum(
    1 for p in PLATFORMS
    if st.session_state.traffic.get(p["domain"], {}).get("monthly_visits", "—") != "—"
)
avg_focus = sum(p["jewelry_focus"] for p in PLATFORMS) / len(PLATFORMS)

st.markdown(f"""
<div class="hero">
    <div class="hero-title">💎 מצאן פלטפורמות תכשיטים</div>
    <div class="hero-sub">מוצא, מנתח ומשווה — כדי שתמכור במקום הכי טוב</div>
    <div class="hero-stats">
        <div class="hero-stat">
            <div class="hero-stat-val">{len(PLATFORMS)}</div>
            <div class="hero-stat-lbl">פלטפורמות</div>
        </div>
        <div class="hero-stat">
            <div class="hero-stat-val">{len(filtered)}</div>
            <div class="hero-stat-lbl">מוצגות כעת</div>
        </div>
        <div class="hero-stat">
            <div class="hero-stat-val">{len(st.session_state.new_platforms)}</div>
            <div class="hero-stat-lbl">חדשות שנמצאו</div>
        </div>
        <div class="hero-stat">
            <div class="hero-stat-val">{ts_label(st.session_state.traffic_ts) or "—"}</div>
            <div class="hero-stat-lbl">עדכון אחרון</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Main cards grid ───────────────────────────────────────────────────────────
if not filtered:
    st.info("אין תוצאות לסינון הנוכחי — שנה בסרגל הצד")
    st.stop()

# Render in 2-column grid using expanders for detail
cols = st.columns(2, gap="medium")

for i, p in enumerate(filtered):
    td = st.session_state.traffic.get(p["domain"], {})
    with cols[i % 2]:
        card_html = render_card(p, td, is_new=False)
        st.markdown(card_html, unsafe_allow_html=True)
        with st.expander(f"פרטים מלאים — {p['name']}"):
            render_detail(p, td)


# ── New platforms section ──────────────────────────────────────────────────────
if st.session_state.new_platforms:
    st.markdown("---")
    st.markdown("## 🆕 פלטפורמות חדשות שנמצאו")
    st.caption("נמצאו ע\"י חיפוש DuckDuckGo — לא נמצאות ברשימה הקבועה")

    new_cols = st.columns(2, gap="medium")
    for i, np_item in enumerate(st.session_state.new_platforms):
        with new_cols[i % 2]:
            st.markdown(f"""
            <div class="pcard">
                <div class="pcard-top" style="background:#7c3aed"></div>
                <div class="pcard-body">
                    <div class="pcard-head">
                        <span class="pcard-name">
                            <span class="new-badge">חדש</span>
                            {np_item['title'][:40]}
                        </span>
                    </div>
                    <div class="pcard-spec">{np_item['description'][:150]}...</div>
                    <div class="pcard-note">🔍 {np_item['domain']}</div>
                </div>
                <div class="pcard-footer">
                    <span></span>
                    <a href="{np_item['url']}" target="_blank" class="pcard-link">בקר באתר ←</a>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ── Comparison table ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📊 טבלת השוואה מהירה"):
    rows = []
    for p in filtered:
        td = st.session_state.traffic.get(p["domain"], {})
        rows.append({
            "פלטפורמה":      p["name"],
            "סוג":           p["category"],
            "עמלת מוכר":     p["seller_fees"],
            "ביקורים/חודש":  td.get("monthly_visits", "—") if td else "—",
            "דירוג גלובלי":  td.get("global_rank", "—")    if td else "—",
            "אזורים":        " / ".join(p["regions"]),
            "💎":            p["jewelry_focus"],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
