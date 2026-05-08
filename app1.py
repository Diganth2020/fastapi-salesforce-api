"""
McAfee Competitor Pricing Intelligence Agent
============================================
Strategy: Search REVIEW & COMPARISON sites (PCMag, TechRadar, CNET, Tom's Guide, Forbes)
instead of vendor sites (which block scrapers with JS/Cloudflare).

Review sites:
  ✅ Publish real current prices in plain HTML
  ✅ No bot protection / Cloudflare
  ✅ Multiple independent sources = cross-validation
  ✅ Include feature comparisons, pros/cons, ratings

Pipeline per vendor:
  1. Run 3 targeted Tavily queries (review sites + official + pricing)
  2. Combine all content (~12,000 chars of real pricing data)
  3. Azure OpenAI focused extraction per vendor (temperature=0)
  4. Display full comparison
"""

import streamlit as st
from openai import AzureOpenAI, AuthenticationError
from tavily import TavilyClient
import json, re, os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="McAfee Competitor Intelligence", page_icon="🛡️", layout="wide")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.5rem !important; max-width: 1400px !important; }
.kpi-box { background:#0e1f2f; border:1px solid #1e3448; border-radius:12px; padding:18px 20px; text-align:center; }
.kpi-box.green { border-color:#00c47755; background:#06180e; }
.kpi-box.red   { border-color:#e63b2e55; background:#1a0808; }
.kpi-box.blue  { border-color:#0078d455; background:#071525; }
.kpi-label { font-size:0.62rem; text-transform:uppercase; letter-spacing:0.15em; color:#3a6080; margin-bottom:6px; }
.kpi-value { font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800; color:#fff; }
.kpi-value.green{color:#00c477;} .kpi-value.red{color:#e63b2e;} .kpi-value.blue{color:#4da3f5;}
.kpi-sub { font-size:0.7rem; color:#3a6080; margin-top:4px; }
.section-title { font-family:'Syne',sans-serif; font-size:0.95rem; font-weight:700;
    color:#c8dced; border-left:3px solid #e63b2e; padding-left:10px; margin:24px 0 12px; }
.vendor-header { font-family:'Syne',sans-serif; font-size:1rem; font-weight:800; color:#fff; }
.vendor-sub { font-size:0.72rem; color:#4d7090; margin-top:2px; }
.price-big { font-family:'Syne',sans-serif; font-size:1.5rem; font-weight:800; }
.price-orig { font-size:0.72rem; color:#3a6080; text-decoration:line-through; }
.badge-green { display:inline-block; background:#00c47718; border:1px solid #00c47744; color:#00c477;
    border-radius:4px; padding:2px 7px; font-size:0.62rem; font-weight:700; text-transform:uppercase; }
.badge-red { display:inline-block; background:#e63b2e18; border:1px solid #e63b2e44; color:#e63b2e;
    border-radius:4px; padding:2px 7px; font-size:0.62rem; font-weight:700; text-transform:uppercase; }
.source-chip { display:inline-block; background:#0a1929; border:1px solid #1a3050; border-radius:4px;
    padding:2px 8px; font-size:0.65rem; color:#4da3f5; margin:2px; }
.pro-item{color:#00c477;font-size:0.78rem;padding:2px 0;}
.con-item{color:#e06060;font-size:0.78rem;padding:2px 0;}
.verdict{font-size:0.78rem;color:#5a80a0;font-style:italic;line-height:1.5;}
hr.sec{border:none;border-top:1px solid #1a3050;margin:12px 0;}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
MCAFEE_PRODUCTS = [
    "McAfee Total Protection", "McAfee LiveSafe", "McAfee AntiVirus Plus",
    "McAfee Internet Security", "McAfee Identity Protection", "McAfee Small Business Security",
]

VENDOR_COLORS = {
    "McAfee":"#e63b2e","Norton":"#e6b800","Bitdefender":"#ED1C24",
    "Kaspersky":"#00a070","Avast":"#FF6900","Trend Micro":"#D71920","ESET":"#008CBA",
}

AZURE_API_VERSIONS = [
    "2025-01-01-preview","2024-12-01-preview","2024-10-21",
    "2024-08-01-preview","2024-05-01-preview","2024-02-01",
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

# ── 3 targeted queries per vendor ─────────────────────────────────────────────
# Query 1: Review sites (most reliable — public HTML, real prices)
# Query 2: Price + year specific (catches deal pages & aggregators)
# Query 3: Feature comparison (catches feature tables on review sites)

VENDOR_QUERIES = {
    "McAfee": [
        'McAfee Total Protection price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'McAfee antivirus annual subscription cost USD 2025',
        'McAfee Total Protection features review rating 2025',
    ],
    "Norton": [
        'Norton 360 antivirus price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'Norton 360 annual subscription cost USD 2025',
        'Norton antivirus features VPN review 2025',
    ],
    "Bitdefender": [
        'Bitdefender Total Security price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'Bitdefender antivirus annual subscription cost USD 2025',
        'Bitdefender Total Security features review rating 2025',
    ],
    "Kaspersky": [
        'Kaspersky antivirus price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'Kaspersky Plus Total Security annual cost USD 2025',
        'Kaspersky antivirus features comparison review 2025',
    ],
    "Avast": [
        'Avast Premium Security price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'Avast antivirus annual subscription cost USD 2025',
        'Avast Premium Security features review rating 2025',
    ],
    "Trend Micro": [
        'Trend Micro Maximum Security price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'Trend Micro antivirus annual subscription cost USD 2025',
        'Trend Micro antivirus features review rating 2025',
    ],
    "ESET": [
        'ESET Internet Security price 2025 review site:pcmag.com OR site:techradar.com OR site:cnet.com OR site:tomsguide.com',
        'ESET antivirus annual subscription cost USD 2025',
        'ESET Internet Security features review rating 2025',
    ],
}

# ── Config ─────────────────────────────────────────────────────────────────────
def get_cfg():
    return {
        "az_key":      os.getenv("AZURE_OPENAI_API_KEY",     st.session_state.get("az_key", "")),
        "az_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT",    st.session_state.get("az_endpoint", "")),
        "az_deploy":   os.getenv("AZURE_OPENAI_DEPLOYMENT",  st.session_state.get("az_deploy", "")),
        "az_ver":      os.getenv("AZURE_OPENAI_API_VERSION", st.session_state.get("az_ver", AZURE_API_VERSIONS[0])),
        "tavily_key":  os.getenv("TAVILY_API_KEY",           st.session_state.get("tavily_key", "")),
    }

def cfg_ok(cfg):
    return all([cfg["az_key"], cfg["az_endpoint"], cfg["az_deploy"], cfg["az_ver"], cfg["tavily_key"]])


# ── Tavily: 3 queries per vendor → rich content ───────────────────────────────
def fetch_vendor_content(vendor: str, tavily: TavilyClient) -> dict:
    """
    Run 3 Tavily search queries per vendor targeting review/comparison sites.
    Returns combined content with source metadata.
    """
    queries  = VENDOR_QUERIES.get(vendor, [f"{vendor} antivirus price review 2025"])
    parts    = []
    sources  = []
    errors   = []

    for i, query in enumerate(queries, 1):
        try:
            resp = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=4,
                include_answer=True,
                include_raw_content=True,   # full article text, not just snippets
            )

            # Tavily's own AI-generated answer
            answer = (resp.get("answer") or "").strip()
            if answer:
                parts.append(f"[TAVILY ANSWER Q{i}]: {answer}")

            # Full content from each search result
            for r in (resp.get("results") or []):
                url     = r.get("url", "")
                title   = r.get("title", "")
                # prefer raw_content (full article), fall back to content (snippet)
                content = (r.get("raw_content") or r.get("content") or "").strip()
                if content and len(content) > 80:
                    parts.append(f"[SOURCE: {title} | {url}]\n{content[:3000]}")
                    sources.append({"url": url, "title": title, "query": i})

        except Exception as e:
            errors.append(f"Query {i} failed: {e}")

    combined = "\n\n".join(parts)
    return {
        "vendor":   vendor,
        "content":  combined[:12000],   # up to 12k chars
        "sources":  sources,
        "errors":   errors,
        "chars":    len(combined),
        "queries":  queries,
    }


# ── Azure: focused per-vendor extraction ──────────────────────────────────────
def extract_vendor_data(
    vendor: str, content: str, product: str,
    az_client: AzureOpenAI, deploy: str
) -> dict:
    """
    Extract structured JSON for one vendor from review site content.
    Grounded extraction — model told not to guess missing prices.
    """
    prompt = f"""You are a pricing data extraction engine.

Extract structured data for **{vendor}** antivirus from the LIVE REVIEW CONTENT below.
This content was fetched RIGHT NOW from PCMag, TechRadar, CNET, Tom's Guide and similar review sites.
The customer is comparing against: "{product}" from McAfee.

--- LIVE REVIEW CONTENT FOR {vendor.upper()} ---
{content}
--- END ---

Return ONE JSON object for {vendor}. Use this exact schema:
{{
  "competitor": "{vendor}",
  "product": "<exact product name from the content e.g. Norton 360 Standard>",
  "tier": "<plan name e.g. Standard / Plus / Premium / Deluxe>",
  "price_usd_year": <first-year USD price as a number, e.g. 39.99, or null if not found>,
  "original_price_usd_year": <regular/renewal USD price as a number, or null>,
  "devices": <number of devices covered, integer, or null>,
  "rating": <review score out of 5 or 10 normalized to 5, float, or null>,
  "url": "<URL of the most relevant source found>",
  "verdict": "<one sentence summary of who this product is best for, from the review>",
  "data_source": "<domain name(s) where price was found e.g. pcmag.com>",
  "features": {{
    "real_time_protection": <true/false>,
    "firewall": <true/false>,
    "vpn": <true/false>,
    "password_manager": <true/false>,
    "parental_controls": <true/false>,
    "dark_web_monitoring": <true/false>,
    "identity_theft_protection": <true/false>,
    "anti_ransomware": <true/false>,
    "cloud_backup": <true/false>,
    "webcam_protection": <true/false>,
    "safe_browsing": <true/false>,
    "email_protection": <true/false>
  }},
  "pros": ["<pro from the review>", "<pro from the review>"],
  "cons":  ["<con from the review>", "<con from the review>"]
}}

STRICT RULES:
- price_usd_year: ONLY set if you see an actual dollar amount in the content. Set null if not found.
- If you see "$X.99/year" or "$X.99 per year" or "$X.99 for 1 year", that is price_usd_year.
- If only monthly price: multiply by 12 for annual.
- original_price_usd_year: the regular or renewal price (often higher than first-year).
- features: true only if the review/source explicitly mentions the feature for this product.
- pros/cons: copy short phrases directly from the review content.
- Return ONLY the JSON object. No markdown fences. No explanation.
"""

    resp = az_client.chat.completions.create(
        model=deploy,
        messages=[
            {"role": "system",  "content": "You are a JSON data extraction engine. Return only valid JSON."},
            {"role": "user",    "content": prompt},
        ],
        temperature=0.0,
        max_tokens=1200,
    )
    raw   = resp.choices[0].message.content or ""
    clean = re.sub(r"```json|```", "", raw).strip()

    # Try full parse first
    try:
        obj = json.loads(clean)
        if isinstance(obj, dict):
            obj["competitor"] = vendor
            return obj
    except Exception:
        pass

    # Try finding JSON object anywhere in response
    m = re.search(r"\{[\s\S]*\}", clean)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                obj["competitor"] = vendor
                return obj
        except Exception:
            pass

    # Fallback — return null-price shell so UI still shows the vendor
    return {
        "competitor": vendor, "product": f"{vendor} Security Suite", "tier": "—",
        "price_usd_year": None, "original_price_usd_year": None,
        "devices": None, "rating": None,
        "url": "", "verdict": "Price data not found in review sources.",
        "data_source": "extraction_failed",
        "features": {k: False for k, _ in FEATURES},
        "pros": [], "cons": ["Could not find pricing in review content"],
    }


# ── DataFrame + styling ────────────────────────────────────────────────────────
def build_dataframe(data: list) -> pd.DataFrame:
    def fmt_price(d, key):
        v = d.get(key)
        return f"${v}" if v else "N/A"

    rows = {
        "💰 Sale Price / yr":    {d["competitor"]: fmt_price(d, "price_usd_year")          for d in data},
        "💸 Regular Price / yr": {d["competitor"]: fmt_price(d, "original_price_usd_year") for d in data},
        "📱 Devices":            {d["competitor"]: str(d["devices"]) if d.get("devices") else "N/A" for d in data},
        "⭐ Rating":             {d["competitor"]: f"{d['rating']}/5" if d.get("rating") else "N/A" for d in data},
        "📦 Plan Tier":          {d["competitor"]: d.get("tier","N/A") for d in data},
        "🔗 Source":             {d["competitor"]: d.get("data_source","—") for d in data},
        "── FEATURES ──":        {d["competitor"]: "" for d in data},
    }
    for key, label in FEATURES:
        rows[label] = {
            d["competitor"]: "✅ Yes" if (d.get("features") or {}).get(key) else "❌ No"
            for d in data
        }
    df = pd.DataFrame(rows).T
    df.index.name = "Attribute"
    return df


def style_df(df: pd.DataFrame, best_vendor: str):
    def color_cell(val):
        if val == "✅ Yes": return "color:#00c477;font-weight:600"
        if val == "❌ No":  return "color:#c0392b"
        return "color:#c8dced"

    def highlight_best(col):
        if col.name == best_vendor:
            return ["background-color:#06180e;border-left:2px solid #00c477"] * len(col)
        return [""] * len(col)

    return (
        df.style.map(color_cell).apply(highlight_best, axis=0)
        .set_table_styles([
            {"selector": "thead th",
             "props": [("background","#0a1a2a"),("color","#7aaac8"),
                       ("font-size","0.8rem"),("text-align","center"),
                       ("padding","10px 12px"),("border-bottom","2px solid #1e3448")]},
            {"selector": "tbody td",
             "props": [("text-align","center"),("padding","8px 12px"),
                       ("border-bottom","1px solid #0e2030"),("font-size","0.82rem")]},
            {"selector": "tbody th",
             "props": [("text-align","left"),("padding","8px 14px"),
                       ("background","#091520"),("color","#8aadcc"),("font-size","0.78rem"),
                       ("border-right","1px solid #1e3448"),("white-space","nowrap"),
                       ("border-bottom","1px solid #0e2030")]},
        ])
        .set_properties(**{"background-color":"#07111e"})
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════════════════════════════════════
col_h1, col_h2 = st.columns([5, 1])
with col_h1:
    st.markdown("## 🛡️ McAfee Competitor Pricing Intelligence")
    st.caption("🔍 Live review sites (PCMag · TechRadar · CNET · Tom's Guide) → ☁️ Azure OpenAI → 📊 Comparison")
with col_h2:
    st.markdown("<div style='padding-top:14px;text-align:right'>"
                "<span style='font-size:0.7rem;color:#3a6080'>☁️ Azure + Tavily</span></div>",
                unsafe_allow_html=True)

st.divider()

# ── Config panel ───────────────────────────────────────────────────────────────
cfg = get_cfg()
with st.expander("⚙️ Configuration", expanded=not cfg_ok(cfg)):
    st.markdown("#### ☁️ Azure OpenAI")
    c1, c2 = st.columns(2)
    with c1:
        ep  = st.text_input("Endpoint URL",    value=cfg["az_endpoint"], placeholder="https://<resource>.openai.azure.com/")
        dep = st.text_input("Deployment Name", value=cfg["az_deploy"],   placeholder="gpt-4.1")
    with c2:
        key = st.text_input("API Key",         value=cfg["az_key"],      type="password")
        ver = st.selectbox("API Version",      AZURE_API_VERSIONS,
                           index=AZURE_API_VERSIONS.index(cfg["az_ver"])
                           if cfg["az_ver"] in AZURE_API_VERSIONS else 0)
    st.markdown("#### 🔍 Tavily API")
    st.caption("Free 1,000 searches/month → [app.tavily.com](https://app.tavily.com)")
    tav = st.text_input("Tavily API Key", value=cfg["tavily_key"], type="password", placeholder="tvly-...")
    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.update(az_key=key, az_endpoint=ep, az_deploy=dep, az_ver=ver, tavily_key=tav)
        st.success("✅ Saved.")
        st.rerun()

cfg = get_cfg()

# ── Product selector ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Select McAfee Product to Compare</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    selected = st.selectbox("Product", ["— choose —"] + MCAFEE_PRODUCTS, label_visibility="collapsed")
with c2:
    custom = st.text_input("Custom", placeholder="Or type a product…", label_visibility="collapsed")
with c3:
    go = st.button("🔍 Compare Now", use_container_width=True, type="primary",
                   disabled=not (custom.strip() or selected != "— choose —"))

product = custom.strip() or (selected if selected != "— choose —" else "")

# ── Pipeline ───────────────────────────────────────────────────────────────────
if go:
    if not cfg_ok(cfg):
        st.error("⚠️ Fill in all Azure OpenAI and Tavily fields above.")
        st.stop()

    vendors       = list(VENDOR_QUERIES.keys())
    tavily_client = TavilyClient(api_key=cfg["tavily_key"])
    az_client     = AzureOpenAI(
        api_key=cfg["az_key"],
        azure_endpoint=cfg["az_endpoint"].rstrip("/"),
        api_version=cfg["az_ver"],
    )

    st.markdown('<div class="section-title">🔄 Fetching Live Data from Review Sites</div>', unsafe_allow_html=True)
    st.caption("Searching PCMag · TechRadar · CNET · Tom's Guide · Forbes · AV-Test for each vendor…")

    progress_bar = st.progress(0, text="Starting…")
    log_box      = st.empty()
    all_data     = []
    fetch_log    = {}
    total_steps  = len(vendors) * 2   # fetch + extract per vendor

    for i, vendor in enumerate(vendors):
        # ── Fetch ──────────────────────────────────────────────────────────────
        progress_bar.progress(
            (i * 2) / total_steps,
            text=f"🔍 [{i+1}/{len(vendors)}] Searching review sites for {vendor}…"
        )
        log_box.info(f"📡 Running 3 targeted queries for **{vendor}** on review sites…")

        fetch_result = fetch_vendor_content(vendor, tavily_client)
        fetch_log[vendor] = fetch_result
        n_sources = len(fetch_result["sources"])
        n_chars   = fetch_result["chars"]

        # ── Extract ────────────────────────────────────────────────────────────
        progress_bar.progress(
            (i * 2 + 1) / total_steps,
            text=f"🤖 [{i+1}/{len(vendors)}] Extracting {vendor} data via Azure OpenAI…"
        )
        log_box.info(
            f"🤖 Extracting **{vendor}** — {n_sources} sources · {n_chars:,} chars of review content"
        )

        try:
            vendor_data = extract_vendor_data(
                vendor, fetch_result["content"], product, az_client, cfg["az_deploy"]
            )
            all_data.append(vendor_data)
        except AuthenticationError:
            st.error("❌ Azure API Key invalid.")
            st.stop()
        except Exception as e:
            err = str(e)
            if "404" in err:
                st.error("❌ Azure 404 — check deployment name and API version.")
                st.stop()
            # Non-fatal: add fallback entry and continue
            all_data.append({
                "competitor": vendor, "product": f"{vendor} Antivirus", "tier":"—",
                "price_usd_year": None, "original_price_usd_year": None,
                "devices": None, "rating": None, "url":"", "verdict":"Extraction error.",
                "data_source":"error", "features":{k:False for k,_ in FEATURES},
                "pros":[], "cons":[str(e)[:80]],
            })

    progress_bar.progress(1.0, text="✅ All vendors processed!")
    log_box.empty()

    if not all_data:
        st.error("No data extracted. Check your API keys.")
        st.stop()

    # Sort: McAfee first, then cheapest
    all_data.sort(key=lambda d: (
        0 if d["competitor"] == "McAfee" else 1,
        d.get("price_usd_year") or 9999
    ))

    # Success summary
    priced_count = sum(1 for d in all_data if d.get("price_usd_year"))
    st.success(f"✅ Done! Found real prices for **{priced_count}/{len(all_data)}** vendors from live review sites.")

    if priced_count < len(all_data):
        st.warning(
            f"⚠️ {len(all_data)-priced_count} vendor(s) returned N/A — "
            "review sites may not have covered them yet. Try again or check the raw content below."
        )

    # Raw content expander
    with st.expander("🔍 Review site content fetched per vendor"):
        for vendor, fr in fetch_log.items():
            matched = next((d for d in all_data if d["competitor"] == vendor), {})
            price_found = matched.get("price_usd_year")
            st.markdown(
                f"**{vendor}** — "
                f"{'✅' if price_found else '❌'} "
                f"Price: {'$'+str(price_found) if price_found else 'not found'} | "
                f"{len(fr['sources'])} sources | {fr['chars']:,} chars"
            )
            for src in fr["sources"][:4]:
                st.markdown(
                    f'<span class="source-chip">🔗 {src["title"][:60]}</span>',
                    unsafe_allow_html=True,
                )
            for err in fr["errors"]:
                st.caption(f"⚠️ {err}")
            with st.expander(f"Raw content — {vendor}"):
                st.text(fr["content"][:2000] + ("…" if fr["chars"] > 2000 else ""))
            st.divider()

    st.session_state["data"]  = all_data
    st.session_state["query"] = product


# ── Results ────────────────────────────────────────────────────────────────────
if st.session_state.get("data"):
    data  = st.session_state["data"]
    query = st.session_state.get("query", "")

    priced      = [d for d in data if d.get("price_usd_year")]
    best_entry  = min(priced, key=lambda d: d["price_usd_year"]) if priced else data[0]
    best_vendor = best_entry.get("competitor","")
    min_price   = best_entry.get("price_usd_year")
    mcafee_e    = next((d for d in data if d.get("competitor") == "McAfee"), None)
    feat_counts = {
        d["competitor"]: sum(1 for v in (d.get("features") or {}).values() if v is True)
        for d in data
    }
    top_vendor = max(feat_counts, key=feat_counts.get) if feat_counts else "—"

    st.divider()

    # ── KPIs ───────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📊 Summary</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-box">
            <div class="kpi-label">Vendors Compared</div>
            <div class="kpi-value">{len(data)}</div>
            <div class="kpi-sub">{sum(1 for d in data if d.get('price_usd_year'))} with live prices</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        mp = f"${min_price}/yr" if min_price else "N/A"
        st.markdown(f"""<div class="kpi-box green">
            <div class="kpi-label">💰 Lowest Price</div>
            <div class="kpi-value green">{mp}</div>
            <div class="kpi-sub">{best_entry.get('competitor')} · {best_entry.get('product','')}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-box blue">
            <div class="kpi-label">🏆 Most Features</div>
            <div class="kpi-value blue" style="font-size:1.3rem">{top_vendor}</div>
            <div class="kpi-sub">{feat_counts.get(top_vendor,0)}/{len(FEATURES)} features</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        mp2 = f"${mcafee_e['price_usd_year']}/yr" if mcafee_e and mcafee_e.get("price_usd_year") else "N/A"
        st.markdown(f"""<div class="kpi-box red">
            <div class="kpi-label">🛡️ McAfee Price</div>
            <div class="kpi-value red">{mp2}</div>
            <div class="kpi-sub">{query}</div>
        </div>""", unsafe_allow_html=True)

    # ── Table ──────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📋 Full Feature & Pricing Comparison</div>', unsafe_allow_html=True)
    st.caption("All data sourced live from PCMag · TechRadar · CNET · Tom's Guide  |  🟢 Green = best price")
    df     = build_dataframe(data)
    styled = style_df(df, best_vendor)
    st.dataframe(styled, use_container_width=True, height=660)

    # ── Vendor cards ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🏢 Vendor Details</div>', unsafe_allow_html=True)
    for row_start in range(0, len(data), 3):
        cols = st.columns(3)
        for col_i, d in enumerate(data[row_start:row_start + 3]):
            vendor  = d.get("competitor","")
            color   = VENDOR_COLORS.get(vendor,"#7a9bbf")
            price   = d.get("price_usd_year")
            orig    = d.get("original_price_usd_year")
            is_best = vendor == best_vendor
            is_mcaf = vendor == "McAfee"
            f_count = feat_counts.get(vendor, 0)

            with cols[col_i]:
                with st.container(border=True):
                    badges = (
                        ('<span class="badge-green">💰 Best Price</span> ' if is_best else "")
                        + ('<span class="badge-red">🛡️ McAfee</span>' if is_mcaf else "")
                    )
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                        f'<div style="width:10px;height:10px;border-radius:50%;background:{color}"></div>'
                        f'<span class="vendor-header">{vendor}</span></div>{badges}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="vendor-sub">{d.get("product","")}</div>', unsafe_allow_html=True)
                    src = d.get("data_source","")
                    if src and src not in ("extraction_failed","error"):
                        st.markdown(f'<span class="source-chip">📰 {src}</span>', unsafe_allow_html=True)
                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    p_color   = "#00c477" if is_best else "#ffffff"
                    price_str = f"${price}/yr" if price else "N/A"
                    orig_html = (f'<div class="price-orig">Regular: ${orig}/yr</div>'
                                 if orig and orig > (price or 0) else "")
                    st.markdown(
                        f'<div class="price-big" style="color:{p_color}">{price_str}</div>{orig_html}',
                        unsafe_allow_html=True,
                    )
                    mc1, mc2 = st.columns(2)
                    mc1.metric("Devices", str(d["devices"]) if d.get("devices") else "N/A")
                    mc2.metric("Rating",  f"⭐ {d['rating']}/5" if d.get("rating") else "N/A")
                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)
                    st.progress(f_count / len(FEATURES), text=f"{f_count}/{len(FEATURES)} features")
                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)

                    pros = d.get("pros") or []
                    cons = d.get("cons") or []
                    if pros:
                        st.markdown("**✅ Pros**")
                        for p in pros:
                            st.markdown(f'<div class="pro-item">＋ {p}</div>', unsafe_allow_html=True)
                    if cons:
                        st.markdown("**❌ Cons**")
                        for c in cons:
                            st.markdown(f'<div class="con-item">－ {c}</div>', unsafe_allow_html=True)
                    st.markdown("<hr class='sec'>", unsafe_allow_html=True)
                    st.markdown(f'<div class="verdict">💡 {d.get("verdict","")}</div>', unsafe_allow_html=True)
                    if d.get("url"):
                        st.markdown(f"[🔗 View source]({d['url']})")

    # ── Price chart ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">💰 Price Comparison Chart</div>', unsafe_allow_html=True)
    chart_data = {d["competitor"]: d["price_usd_year"] for d in data if d.get("price_usd_year")}
    if chart_data:
        st.bar_chart(
            pd.DataFrame.from_dict(chart_data, orient="index", columns=["Price (USD/yr)"])
            .sort_values("Price (USD/yr)"),
            color="#e63b2e", height=320,
        )
    else:
        st.info("No price data to chart — see raw content above for details.")

    # ── Feature heatmap ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🗺️ Feature Coverage Heatmap</div>', unsafe_allow_html=True)
    heat_df = pd.DataFrame({
        label: {d["competitor"]: 1 if (d.get("features") or {}).get(key) else 0 for d in data}
        for key, label in FEATURES
    }).T
    st.dataframe(
        heat_df.style
            .background_gradient(cmap="RdYlGn", axis=None, vmin=0, vmax=1)
            .format(lambda v: "✅" if v == 1 else "❌"),
        use_container_width=True, height=460,
    )

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">⬇️ Export</div>', unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    with e1:
        st.download_button("⬇️ JSON", data=json.dumps(data, indent=2),
                           file_name=f"mcafee_{query.replace(' ','_')}.json",
                           mime="application/json", use_container_width=True)
    with e2:
        csv_rows = ["Vendor,Product,Sale Price/yr,Regular Price/yr,Devices,Rating,Source,"
                    + ",".join(lbl for _, lbl in FEATURES) + ",Pros,Cons,Verdict"]
        for d in data:
            feats = ",".join("Yes" if (d.get("features") or {}).get(k) else "No" for k, _ in FEATURES)
            csv_rows.append(
                f'{d.get("competitor","")},{d.get("product","")}'
                f',{d.get("price_usd_year","N/A")},{d.get("original_price_usd_year","N/A")}'
                f',{d.get("devices","N/A")},{d.get("rating","N/A")},{d.get("data_source","")}'
                f',{feats}'
                f',"{"|".join(d.get("pros") or [])}"'
                f',"{"|".join(d.get("cons") or [])}"'
                f',"{d.get("verdict","")}"'
            )
        st.download_button("⬇️ CSV", data="\n".join(csv_rows),
                           file_name=f"mcafee_{query.replace(' ','_')}.csv",
                           mime="text/csv", use_container_width=True)

    st.caption("⚡ Prices sourced from PCMag · TechRadar · CNET · Tom's Guide · Forbes · AV-Test  |  Verify at official vendor sites")
