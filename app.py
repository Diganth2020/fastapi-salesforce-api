import streamlit as st
from openai import AzureOpenAI, AuthenticationError
import json, re, os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="McAfee Competitor Intelligence",
    page_icon="🛡️",
    layout="wide",
)

# ── Minimal CSS (safe for Streamlit) ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.5rem !important; max-width: 1400px !important; }

.kpi-box {
    background: #0e1f2f;
    border: 1px solid #1e3448;
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
}
.kpi-box.green { border-color: #00c47755; background: #06180e; }
.kpi-box.red   { border-color: #e63b2e55; background: #1a0808; }
.kpi-box.blue  { border-color: #0078d455; background: #071525; }

.kpi-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.15em; color: #3a6080; margin-bottom: 6px; }
.kpi-value { font-family: 'Syne', sans-serif; font-size: 1.8rem; font-weight: 800; color: #fff; }
.kpi-value.green { color: #00c477; }
.kpi-value.red   { color: #e63b2e; }
.kpi-value.blue  { color: #4da3f5; }
.kpi-sub   { font-size: 0.7rem; color: #3a6080; margin-top: 4px; }

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem; font-weight: 700;
    color: #c8dced; letter-spacing: -0.01em;
    border-left: 3px solid #e63b2e;
    padding-left: 10px;
    margin: 24px 0 12px;
}
.vendor-header {
    font-family: 'Syne', sans-serif;
    font-size: 1rem; font-weight: 800; color: #fff;
}
.vendor-sub { font-size: 0.72rem; color: #4d7090; margin-top: 2px; }
.price-big  { font-family: 'Syne', sans-serif; font-size: 1.5rem; font-weight: 800; }
.price-orig { font-size: 0.72rem; color: #3a6080; text-decoration: line-through; }
.badge-green {
    display: inline-block;
    background: #00c47718; border: 1px solid #00c47744;
    color: #00c477; border-radius: 4px;
    padding: 2px 7px; font-size: 0.62rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}
.badge-red {
    display: inline-block;
    background: #e63b2e18; border: 1px solid #e63b2e44;
    color: #e63b2e; border-radius: 4px;
    padding: 2px 7px; font-size: 0.62rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}
.pro-item  { color: #00c477; font-size: 0.78rem; padding: 2px 0; }
.con-item  { color: #e06060; font-size: 0.78rem; padding: 2px 0; }
.verdict   { font-size: 0.78rem; color: #5a80a0; font-style: italic; line-height: 1.5; }
hr.sec     { border: none; border-top: 1px solid #1a3050; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
MCAFEE_PRODUCTS = [
    "McAfee Total Protection",
    "McAfee LiveSafe",
    "McAfee AntiVirus Plus",
    "McAfee Internet Security",
    "McAfee Identity Protection",
    "McAfee Small Business Security",
]

VENDOR_COLORS = {
    "McAfee":      "#e63b2e",
    "Norton":      "#e6b800",
    "Bitdefender": "#ED1C24",
    "Kaspersky":   "#00a070",
    "Avast":       "#FF6900",
    "Trend Micro": "#D71920",
    "ESET":        "#008CBA",
}

AZURE_API_VERSIONS = [
    "2025-01-01-preview",
    "2024-12-01-preview",
    "2024-10-21",
    "2024-08-01-preview",
    "2024-05-01-preview",
    "2024-02-01",
]

FEATURES = [
    ("real_time_protection",      "🛡️ Real-Time Protection"),
    ("firewall",                  "🔥 Firewall"),
    ("vpn",                       "🔒 VPN Included"),
    ("password_manager",          "🔑 Password Manager"),
    ("parental_controls",         "👨‍👩‍👧 Parental Controls"),
    ("dark_web_monitoring",       "🕵️ Dark Web Monitoring"),
    ("identity_theft_protection", "🪪 Identity Theft Protection"),
    ("anti_ransomware",           "💀 Anti-Ransomware"),
    ("cloud_backup",              "☁️ Cloud Backup"),
    ("webcam_protection",         "📷 Webcam Protection"),
    ("safe_browsing",             "🌐 Safe Browsing"),
    ("email_protection",          "📧 Email Protection"),
]

# ── Prompts ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior cybersecurity market intelligence analyst.
Return only valid JSON, no markdown fences, no explanation."""

PROMPT_TEMPLATE = """A sales team is comparing competitors against "{product}" from McAfee.

Return a JSON array. First entry = McAfee itself, then 5 competitors:
Norton, Bitdefender, Kaspersky, Avast, Trend Micro, ESET.

Each object MUST use this exact schema (all fields required):
{{
  "competitor": "Norton",
  "product": "Norton 360 Standard",
  "tier": "Standard",
  "price_usd_year": 39.99,
  "original_price_usd_year": 84.99,
  "devices": 3,
  "rating": 4.5,
  "url": "https://norton.com",
  "verdict": "Best for families needing multi-device coverage with VPN",
  "features": {{
    "real_time_protection": true,
    "firewall": true,
    "vpn": true,
    "password_manager": true,
    "parental_controls": false,
    "dark_web_monitoring": true,
    "identity_theft_protection": false,
    "anti_ransomware": true,
    "cloud_backup": true,
    "webcam_protection": false,
    "safe_browsing": true,
    "email_protection": false
  }},
  "pros": ["Strong malware detection", "Includes VPN", "Good multi-device value"],
  "cons": ["Renewal price is high", "No parental controls"]
}}

IMPORTANT: Return ONLY the raw JSON array. No markdown. No explanation.
"""

# ── Azure helpers ──────────────────────────────────────────────────────────────
def get_cfg():
    return {
        "api_key":    os.getenv("AZURE_OPENAI_API_KEY",     st.session_state.get("az_key", "")),
        "endpoint":   os.getenv("AZURE_OPENAI_ENDPOINT",    st.session_state.get("az_endpoint", "")),
        "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT",  st.session_state.get("az_deploy", "")),
        "api_ver":    os.getenv("AZURE_OPENAI_API_VERSION", st.session_state.get("az_ver", AZURE_API_VERSIONS[0])),
    }

def cfg_ok(cfg):
    return all(cfg.values())

def parse_json(text):
    clean = re.sub(r"```json|```", "", text).strip()
    for src in [clean, (re.search(r"\[[\s\S]*\]", clean) or type("o",(),({"group":lambda s,_=None:""}))()).group()]:
        try:
            d = json.loads(src)
            if isinstance(d, list): return d
            if isinstance(d, dict) and "competitors" in d: return d["competitors"]
        except: pass
    return None

def call_azure(product, cfg):
    client = AzureOpenAI(
        api_key=cfg["api_key"],
        azure_endpoint=cfg["endpoint"].rstrip("/"),
        api_version=cfg["api_ver"],
    )
    r = client.chat.completions.create(
        model=cfg["deployment"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": PROMPT_TEMPLATE.format(product=product)},
        ],
        temperature=0.1,
        max_tokens=3500,
    )
    raw = r.choices[0].message.content or ""
    return parse_json(raw), raw

# ── Build comparison DataFrame ─────────────────────────────────────────────────
def build_dataframe(data):
    rows = {}

    # Pricing rows
    rows["💰 Sale Price / yr"]     = {d["competitor"]: f"${d.get('price_usd_year','—')}"     for d in data}
    rows["💸 Regular Price / yr"]  = {d["competitor"]: f"${d.get('original_price_usd_year','—')}" for d in data}
    rows["📱 Devices Covered"]     = {d["competitor"]: str(d.get("devices", "—"))            for d in data}
    rows["⭐ User Rating"]         = {d["competitor"]: f"{d.get('rating','—')} / 5"          for d in data}
    rows["📦 Tier / Plan"]         = {d["competitor"]: d.get("tier", "—")                    for d in data}

    # Separator
    rows["── FEATURES ──"] = {d["competitor"]: "" for d in data}

    # Feature rows
    for key, label in FEATURES:
        rows[label] = {
            d["competitor"]: "✅ Yes" if (d.get("features") or {}).get(key) else "❌ No"
            for d in data
        }

    df = pd.DataFrame(rows).T
    df.index.name = "Attribute"
    return df

# ── Styled dataframe ───────────────────────────────────────────────────────────
def style_df(df, best_vendor):
    def color_cells(val):
        if val == "✅ Yes":  return "color: #00c477; font-weight: 600"
        if val == "❌ No":   return "color: #c0392b"
        if val == "── FEATURES ──": return "color: #3a6080; font-size: 0.6rem"
        return "color: #c8dced"

    def highlight_best_col(col):
        if col.name == best_vendor:
            return ["background-color: #06180e; border-left: 2px solid #00c477"] * len(col)
        return [""] * len(col)

    styled = (
        df.style
        .map(color_cells)
        .apply(highlight_best_col, axis=0)
        .set_table_styles([
            {"selector": "thead th",
             "props": [("background", "#0a1a2a"), ("color", "#7aaac8"),
                       ("font-size", "0.8rem"), ("text-align", "center"),
                       ("padding", "10px 12px"), ("border-bottom", "2px solid #1e3448")]},
            {"selector": "tbody td",
             "props": [("text-align", "center"), ("padding", "8px 12px"),
                       ("border-bottom", "1px solid #0e2030"), ("font-size", "0.82rem")]},
            {"selector": "tbody th",
             "props": [("text-align", "left"), ("padding", "8px 14px"),
                       ("background", "#091520"), ("color", "#8aadcc"),
                       ("font-size", "0.78rem"), ("border-right", "1px solid #1e3448"),
                       ("white-space", "nowrap"), ("border-bottom", "1px solid #0e2030")]},
            {"selector": "table",
             "props": [("border-collapse", "collapse"), ("width", "100%")]},
        ])
        .set_properties(**{"background-color": "#07111e"})
    )
    return styled

# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

# Header
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.markdown("## 🛡️ McAfee Competitor Pricing Intelligence")
    st.caption("Powered by Azure OpenAI · Side-by-side feature & pricing comparison")
with col_h2:
    st.markdown("<div style='padding-top:12px;text-align:right'>"
                "<span style='font-size:0.7rem;color:#3a6080'>☁️ Azure OpenAI</span></div>",
                unsafe_allow_html=True)

st.divider()

# ── Azure config ───────────────────────────────────────────────────────────────
cfg = get_cfg()
with st.expander("☁️ Azure OpenAI Configuration", expanded=not cfg_ok(cfg)):
    st.caption("Find these in Azure Portal → your resource → Keys and Endpoint, and Azure AI Foundry → Deployments.")
    c1, c2 = st.columns(2)
    with c1:
        ep  = st.text_input("Endpoint URL",     value=cfg["endpoint"],   placeholder="https://<resource>.openai.azure.com/")
        dep = st.text_input("Deployment Name",  value=cfg["deployment"], placeholder="gpt-4.1")
    with c2:
        key = st.text_input("API Key",          value=cfg["api_key"],    type="password", placeholder="••••••••")
        ver = st.selectbox("API Version",       AZURE_API_VERSIONS,
                           index=AZURE_API_VERSIONS.index(cfg["api_ver"])
                           if cfg["api_ver"] in AZURE_API_VERSIONS else 0)
    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.update(az_key=key, az_endpoint=ep, az_deploy=dep, az_ver=ver)
        st.success("✅ Configuration saved.")
        st.rerun()

cfg = get_cfg()

# ── Product selector ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Select a McAfee Product</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    selected = st.selectbox("Product", ["— choose a product —"] + MCAFEE_PRODUCTS, label_visibility="collapsed")
with c2:
    custom = st.text_input("Custom product", placeholder="Or type a product e.g. McAfee Safe Connect", label_visibility="collapsed")
with c3:
    go = st.button("🔍 Compare Now", use_container_width=True, type="primary",
                   disabled=not (custom.strip() or selected != "— choose a product —"))

product = custom.strip() or (selected if selected != "— choose a product —" else "")

# ── API call ───────────────────────────────────────────────────────────────────
if go:
    if not cfg_ok(cfg):
        st.error("⚠️ Please fill in all Azure OpenAI configuration fields above.")
        st.stop()

    with st.spinner(f"🌐 Fetching competitor data for **{product}**…"):
        try:
            data, raw = call_azure(product, cfg)
        except AuthenticationError:
            st.error("❌ 401 Authentication Error — Invalid API key. "
                     "Check Azure Portal → Keys and Endpoint.")
            st.stop()
        except Exception as e:
            err = str(e)
            if "404" in err:
                st.error("❌ 404 Resource Not Found")
                st.info("""**Common fixes:**
- Use a valid API version e.g. `2025-01-01-preview` or `2024-10-21`
- Deployment name must exactly match Azure AI Foundry (case-sensitive)
- Endpoint must be `https://<resource>.openai.azure.com/`""")
                with st.expander("Current config (debug)"):
                    st.json({k: "••••" if k == "api_key" else v for k, v in cfg.items()})
            else:
                st.error(f"❌ {e}")
            st.stop()

    if not data:
        st.warning("⚠️ Could not parse a JSON array from the response.")
        with st.expander("Raw model response"):
            st.text(raw)
        st.stop()

    st.session_state["data"]  = data
    st.session_state["query"] = product

# ── Results ────────────────────────────────────────────────────────────────────
if st.session_state.get("data"):
    data  = st.session_state["data"]
    query = st.session_state.get("query", "")

    # Derive summary stats
    prices      = [(d.get("price_usd_year") or 999, d) for d in data]
    best_entry  = min(prices, key=lambda x: x[0])[1]
    min_price   = best_entry.get("price_usd_year", "—")
    mcafee_e    = next((d for d in data if d.get("competitor") == "McAfee"), None)
    feat_counts = {
        d["competitor"]: sum(1 for v in (d.get("features") or {}).values() if v is True)
        for d in data
    }
    top_feat_vendor = max(feat_counts, key=feat_counts.get) if feat_counts else "—"
    top_feat_count  = feat_counts.get(top_feat_vendor, 0)

    st.divider()

    # ── KPI row ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Summary</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-box">
            <div class="kpi-label">Vendors Compared</div>
            <div class="kpi-value">{len(data)}</div>
            <div class="kpi-sub">incl. McAfee</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-box green">
            <div class="kpi-label">💰 Lowest Price</div>
            <div class="kpi-value green">${min_price}/yr</div>
            <div class="kpi-sub">{best_entry.get('competitor')} — {best_entry.get('product','')}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-box blue">
            <div class="kpi-label">🏆 Most Features</div>
            <div class="kpi-value blue">{top_feat_vendor}</div>
            <div class="kpi-sub">{top_feat_count} of {len(FEATURES)} features</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        mp = mcafee_e.get("price_usd_year", "—") if mcafee_e else "—"
        st.markdown(f"""<div class="kpi-box red">
            <div class="kpi-label">🛡️ McAfee Price</div>
            <div class="kpi-value red">${mp}/yr</div>
            <div class="kpi-sub">{query}</div>
        </div>""", unsafe_allow_html=True)

    # ── Main comparison table ──────────────────────────────────────────────────
    st.markdown('<div class="section-title">Full Feature & Pricing Comparison</div>', unsafe_allow_html=True)
    st.caption("✅ Yes = feature included  |  ❌ No = not included  |  Green column = best price")

    df = build_dataframe(data)
    best_vendor = best_entry.get("competitor", "")
    styled = style_df(df, best_vendor)
    st.dataframe(styled, use_container_width=True, height=620)

    # ── Vendor detail cards ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Vendor Details</div>', unsafe_allow_html=True)

    # Arrange in rows of 3
    for row_start in range(0, len(data), 3):
        cols = st.columns(3)
        for col_i, d in enumerate(data[row_start:row_start+3]):
            vendor  = d.get("competitor", "")
            color   = VENDOR_COLORS.get(vendor, "#7a9bbf")
            price   = d.get("price_usd_year")
            orig    = d.get("original_price_usd_year")
            devices = d.get("devices")
            rating  = d.get("rating")
            url     = d.get("url", "")
            verdict = d.get("verdict", "")
            pros    = d.get("pros") or []
            cons    = d.get("cons") or []
            is_best = vendor == best_vendor
            is_mcaf = vendor == "McAfee"

            with cols[col_i]:
                with st.container(border=True):
                    # Vendor name + badges
                    badge_html = ""
                    if is_best: badge_html += '<span class="badge-green">💰 Best Price</span> '
                    if is_mcaf: badge_html += '<span class="badge-red">🛡️ McAfee</span>'

                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                        f'<div style="width:10px;height:10px;border-radius:50%;background:{color};flex-shrink:0"></div>'
                        f'<span class="vendor-header">{vendor}</span></div>'
                        f'{badge_html}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="vendor-sub">{d.get("product","")}</div>', unsafe_allow_html=True)
                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    # Price
                    price_color = "#00c477" if is_best else "#ffffff"
                    st.markdown(
                        f'<div class="price-big" style="color:{price_color}">'
                        f'${price}/yr</div>'
                        + (f'<div class="price-orig">Regular: ${orig}/yr</div>' if orig and orig > (price or 0) else ""),
                        unsafe_allow_html=True,
                    )

                    # Metrics row
                    mc1, mc2 = st.columns(2)
                    mc1.metric("Devices", f"{devices}" if devices else "—")
                    mc2.metric("Rating", f"⭐ {rating}/5" if rating else "—")

                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    # Feature count
                    f_count = feat_counts.get(vendor, 0)
                    st.progress(f_count / len(FEATURES), text=f"{f_count}/{len(FEATURES)} features")

                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    # Pros
                    if pros:
                        st.markdown("**✅ Pros**")
                        for p in pros:
                            st.markdown(f'<div class="pro-item">＋ {p}</div>', unsafe_allow_html=True)

                    # Cons
                    if cons:
                        st.markdown("**❌ Cons**")
                        for c in cons:
                            st.markdown(f'<div class="con-item">－ {c}</div>', unsafe_allow_html=True)

                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    # Verdict
                    st.markdown(f'<div class="verdict">💡 {verdict}</div>', unsafe_allow_html=True)

                    # Link
                    if url:
                        st.markdown(f"[🔗 Visit website]({url})")

    # ── Price bar chart ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Price Comparison Chart</div>', unsafe_allow_html=True)
    chart_data = {
        d["competitor"]: d.get("price_usd_year", 0)
        for d in data if d.get("price_usd_year")
    }
    chart_df = (
        pd.DataFrame.from_dict(chart_data, orient="index", columns=["Price (USD/yr)"])
        .sort_values("Price (USD/yr)")
    )
    st.bar_chart(chart_df, color="#e63b2e", height=300)

    # ── Feature coverage heatmap ───────────────────────────────────────────────
    st.markdown('<div class="section-title">Feature Coverage Overview</div>', unsafe_allow_html=True)
    heat_rows = {}
    for key, label in FEATURES:
        heat_rows[label] = {
            d["competitor"]: 1 if (d.get("features") or {}).get(key) else 0
            for d in data
        }
    heat_df = pd.DataFrame(heat_rows).T
    st.dataframe(
        heat_df.style
            .background_gradient(cmap="RdYlGn", axis=None, vmin=0, vmax=1)
            .format(lambda v: "✅" if v == 1 else "❌"),
        use_container_width=True,
        height=460,
    )

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Export</div>', unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(data, indent=2),
            file_name=f"mcafee_comparison_{query.replace(' ','_')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with e2:
        csv_rows = ["Vendor,Product,Sale Price/yr,Regular Price/yr,Devices,Rating,"
                    + ",".join(lbl for _, lbl in FEATURES) + ",Pros,Cons,Verdict"]
        for d in data:
            feats  = ",".join("Yes" if (d.get("features") or {}).get(k) else "No" for k, _ in FEATURES)
            pros_s = " | ".join(d.get("pros") or [])
            cons_s = " | ".join(d.get("cons") or [])
            csv_rows.append(
                f'{d.get("competitor","")},{d.get("product","")}'
                f',{d.get("price_usd_year","")},{d.get("original_price_usd_year","")}'
                f',{d.get("devices","")},{d.get("rating","")}'
                f',{feats},"{pros_s}","{cons_s}","{d.get("verdict","")}"'
            )
        st.download_button(
            "⬇️ Download CSV",
            data="\n".join(csv_rows),
            file_name=f"mcafee_comparison_{query.replace(' ','_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.caption("Data generated by Azure OpenAI · Prices are indicative · Verify on official vendor websites.")
