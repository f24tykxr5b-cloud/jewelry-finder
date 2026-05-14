import streamlit as st
import pandas as pd
import time
import json
from pathlib import Path
from datetime import datetime

from platforms_data import PLATFORMS
from traffic_fetcher import fetch_similarweb_data
from platform_discovery import search_new_platforms
from scanner import run_scan, load_scan_cache, save_scan_cache

st.set_page_config(
    page_title="💎 מצאן פלטפורמות תכשיטים",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CACHE_FILE = Path("traffic_cache.json")
TRAFFIC_TTL_HOURS = 12

CAT_EMOJI = {
    "מכרזים":               "🔨",
    "מרקטפלייס + מכרזים":   "🛒",
    "מרקטפלייס יד-עשייה":   "🎨",
    "יוקרה":                "👑",
    "יד שנייה יוקרה":       "✨",
    "אנטיק ווינטג'":        "🏺",
    "מרקטפלייס יד שנייה":   "♻️",
    "אגרגטור מכרזים":       "🔍",
    "בית מכירות":           "🏛️",
    "שעונים":               "⌚",
    "מכרזים לתכשיטים":      "💍",
}

def stars(n: int) -> str:
    return "💎" * n + "◇" * (5 - n)

def ts_label(ts: float) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if (time.time() - raw.get("_ts", 0)) / 3600 < TRAFFIC_TTL_HOURS:
                return raw
        except Exception:
            pass
    return {}

def _save_cache(data: dict):
    data["_ts"] = time.time()
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Session state ──────────────────────────────────────────────────────────────
if "traffic" not in st.session_state:
    cached = _load_cache()
    st.session_state.traffic    = cached.get("traffic", {})
    st.session_state.traffic_ts = cached.get("_ts", 0)
if "new_platforms" not in st.session_state:
    st.session_state.new_platforms = []
if "filter_cat" not in st.session_state:
    st.session_state.filter_cat = "הכל"
if "filter_focus" not in st.session_state:
    st.session_state.filter_focus = 1
if "scan_results" not in st.session_state:
    st.session_state.scan_results = load_scan_cache() or []


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ הגדרות")

    ts = st.session_state.get("traffic_ts", 0)
    if ts:
        st.success(f"✅ עודכן: {ts_label(ts)}")

    if st.button("🌐 רענן נתוני טראפיק", use_container_width=True):
        results = {}
        prog = st.progress(0)
        for i, p in enumerate(PLATFORMS):
            results[p["domain"]] = fetch_similarweb_data(p["domain"])
            prog.progress((i + 1) / len(PLATFORMS))
            time.sleep(1.0)
        prog.empty()
        st.session_state.traffic    = results
        st.session_state.traffic_ts = time.time()
        _save_cache({"traffic": results})
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
        st.success(f"נמצאו {len(found)} חדשות!" if found else "לא נמצאו חדשות")

    st.markdown("---")
    all_cats = ["הכל"] + sorted(set(p["category"] for p in PLATFORMS))
    st.session_state.filter_cat = st.selectbox(
        "סוג פלטפורמה", all_cats,
        index=all_cats.index(st.session_state.filter_cat),
    )
    st.session_state.filter_focus = st.slider(
        "רלוונטיות מינימלית 💎", 1, 5,
        st.session_state.filter_focus,
    )
    st.caption("נתוני טראפיק: SimilarWeb · חיפוש: DuckDuckGo")


# ── Filter ─────────────────────────────────────────────────────────────────────
filtered = [
    p for p in PLATFORMS
    if (st.session_state.filter_cat == "הכל" or p["category"] == st.session_state.filter_cat)
    and p["jewelry_focus"] >= st.session_state.filter_focus
]
filtered.sort(key=lambda p: (-p["jewelry_focus"], p["name"]))


# ── Hero ───────────────────────────────────────────────────────────────────────
st.title("💎 מצאן פלטפורמות תכשיטים")
st.caption("מוצא, מנתח ומשווה — כדי שתמכור במקום הכי טוב")

c1, c2, c3, c4 = st.columns(4)
c1.metric("פלטפורמות", len(PLATFORMS))
c2.metric("מוצגות כעת", len(filtered))
c3.metric("חדשות שנמצאו", len(st.session_state.new_platforms))
c4.metric("עדכון אחרון", ts_label(st.session_state.traffic_ts) or "—")

st.divider()

if not filtered:
    st.info("אין תוצאות — שנה את הסינון בסרגל הצד")
    st.stop()


# ── Cards ──────────────────────────────────────────────────────────────────────
cols = st.columns(2, gap="medium")

for i, p in enumerate(filtered):
    td      = st.session_state.traffic.get(p["domain"], {})
    monthly = td.get("monthly_visits", "—") if td else "—"
    g_rank  = td.get("global_rank",    "—") if td else "—"
    emoji   = CAT_EMOJI.get(p["category"], "🔹")

    with cols[i % 2]:
        with st.container(border=True):

            # ── Header ──
            h1, h2 = st.columns([2, 1])
            h1.markdown(f"### {p['name']}")
            h2.markdown(f"**{emoji} {p['category']}**")

            st.caption(p["specialty"])
            st.markdown(f"💰 **עמלת מוכר:** {p['seller_fees']}  |  🛒 **עמלת קונה:** {p['buyer_fees']}")

            # ── Traffic — live data first, fall back to static estimate ──
            live_visits = monthly if monthly != "—" else None
            est_visits  = p.get("monthly_visits_est")
            traf_parts  = []
            if live_visits:
                traf_parts.append(f"🌐 {live_visits}/חודש")
            elif est_visits:
                traf_parts.append(f"🌐 ~{est_visits}/חודש")
            if g_rank != "—":
                traf_parts.append(f"🏆 #{g_rank}")
            if traf_parts:
                st.info("  |  ".join(traf_parts))

            # ── Note ──
            st.warning(f"💡 {p['notes']}")

            # ── Footer ──
            f1, f2 = st.columns([1, 1])
            f1.markdown(f"**{stars(p['jewelry_focus'])}**")
            f2.link_button("🔗 בקר באתר", p["url"], use_container_width=True)

            # ── Details ──
            with st.expander("פרטים מלאים ▼"):
                d1, d2 = st.columns(2)
                with d1:
                    st.markdown("**📋 פרטי הפלטפורמה**")
                    st.markdown(f"🌍 **אזורים:** {' · '.join(p['regions'])}")
                    st.markdown(f"🗣 **שפות:** {' · '.join(p['languages'])}")
                    st.markdown(f"💎 **רלוונטיות:** {stars(p['jewelry_focus'])}")
                with d2:
                    st.markdown("**📊 טראפיק (SimilarWeb)**")
                    if not td:
                        st.caption("לחץ 'רענן נתוני טראפיק' בסרגל הצד")
                    else:
                        for label, val in [
                            ("🌐 ביקורים/חודש",  monthly),
                            ("🏆 דירוג גלובלי",  f"#{g_rank}" if g_rank != "—" else "—"),
                            ("↩️ Bounce Rate",    td.get("bounce_rate",        "—")),
                            ("📄 עמודים/ביקור",  td.get("pages_per_visit",    "—")),
                            ("⏱ זמן ממוצע",     td.get("avg_visit_duration", "—")),
                        ]:
                            r1, r2 = st.columns([1.5, 1])
                            r1.caption(label)
                            r2.markdown(f"**{val}**")
                        countries = td.get("top_countries", [])
                        if countries:
                            st.markdown("🗺 **מדינות:** " + " · ".join(countries))


# ── New platforms ──────────────────────────────────────────────────────────────
if st.session_state.new_platforms:
    st.divider()
    st.subheader("🆕 פלטפורמות חדשות שנמצאו")
    ncols = st.columns(2, gap="medium")
    for i, np_item in enumerate(st.session_state.new_platforms):
        with ncols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### 🆕 {np_item['title'][:50]}")
                st.caption(np_item["description"][:180])
                st.link_button("🔗 בקר באתר", np_item["url"], use_container_width=True)


# ── Active Scanner ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("🔭 סריקה אקטיבית — פלטפורמות בסגנון Catawiki")
st.caption("מחפש ברחבי האינטרנט אתרים עם מודל עסקי דומה: מכרזים, אוצנות, תכשיטים/אספנות")

scan_col1, scan_col2 = st.columns([2, 1])
with scan_col1:
    if st.session_state.scan_results:
        from scanner import SCAN_CACHE_FILE
        import json as _json
        try:
            raw = _json.loads(SCAN_CACHE_FILE.read_text(encoding="utf-8"))
            scan_age_h = (time.time() - raw.get("_ts", 0)) / 3600
            st.caption(f"✅ תוצאות מהסריקה האחרונה (לפני {scan_age_h:.1f} שעות) · מתרענן אוטומטית כל 24 שעות")
        except Exception:
            pass
with scan_col2:
    if st.button("🔭 הפעל סריקה", use_container_width=True, type="primary"):
        known = {p["domain"] for p in PLATFORMS}
        progress_bar = st.progress(0)
        status_text  = st.empty()

        def _progress(current, total, msg):
            progress_bar.progress(min(current / max(total, 1), 1.0))
            status_text.caption(msg)

        results = run_scan(known_domains=known, min_score=35, max_results=12, progress_cb=_progress)
        progress_bar.empty()
        status_text.empty()
        save_scan_cache(results)
        st.session_state.scan_results = results
        st.rerun()

if st.session_state.scan_results:
    scan_cols = st.columns(2, gap="medium")
    for i, r in enumerate(st.session_state.scan_results):
        with scan_cols[i % 2]:
            with st.container(border=True):
                # Score badge color
                score = r["score"]
                if score >= 70:
                    badge = "🟢"
                elif score >= 50:
                    badge = "🟡"
                else:
                    badge = "🟠"

                h1, h2 = st.columns([3, 1])
                h1.markdown(f"### {r['title'][:40] or r['domain']}")
                h2.markdown(f"**{badge} {score}/100**")

                st.caption(r["domain"])
                if r["description"]:
                    st.write(r["description"][:160])

                # Signal bars
                signals = r.get("signals", {})
                if signals:
                    sig_text = "  |  ".join(
                        f"{label} ×{val}"
                        for label, val in signals.items()
                        if val > 0
                    )
                    if sig_text:
                        st.caption(f"📡 אותות: {sig_text}")

                st.link_button("🔗 בקר באתר", r["url"], use_container_width=True)
else:
    st.info("לחץ **הפעל סריקה** כדי לחפש פלטפורמות חדשות בסגנון Catawiki · הסריקה לוקחת כ-60 שניות")


# ── Comparison table ───────────────────────────────────────────────────────────
st.divider()
with st.expander("📊 טבלת השוואה המהירה"):
    rows = []
    for p in filtered:
        td = st.session_state.traffic.get(p["domain"], {})
        rows.append({
            "פלטפורמה":     p["name"],
            "סוג":          p["category"],
            "עמלת מוכר":    p["seller_fees"],
            "ביקורים/חודש": td.get("monthly_visits", "—") if td else "—",
            "דירוג גלובלי": td.get("global_rank",    "—") if td else "—",
            "אזורים":       " / ".join(p["regions"]),
            "💎":           p["jewelry_focus"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
