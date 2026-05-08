"""Service layer for Azure OpenAI integration."""
import re
import json
import os
from typing import Optional, List, Dict, Tuple
from openai import AzureOpenAI, AuthenticationError


# ── Constants ──────────────────────────────────────────────────────────────────
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

MCAFEE_PRODUCTS = [
    "McAfee Total Protection",
    "McAfee LiveSafe",
    "McAfee AntiVirus Plus",
    "McAfee Internet Security",
    "McAfee Identity Protection",
    "McAfee Small Business Security",
]


def parse_json(text: str) -> Optional[List[Dict]]:
    """Parse JSON response from Azure OpenAI."""
    clean = re.sub(r"```json|```", "", text).strip()
    for src in [clean, (re.search(r"\[[\s\S]*\]", clean) or type("o", ((),), {"group": lambda s, _=None: ""})()).group()]:
        try:
            d = json.loads(src)
            if isinstance(d, list):
                return d
            if isinstance(d, dict) and "competitors" in d:
                return d["competitors"]
        except:
            pass
    return None


def call_azure(product: str, api_key: str, endpoint: str, deployment: str, api_version: str) -> Tuple[Optional[List[Dict]], str]:
    """Call Azure OpenAI API and return parsed data."""
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint.rstrip("/"),
        api_version=api_version,
    )
    r = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT_TEMPLATE.format(product=product)},
        ],
        temperature=0.1,
        max_tokens=3500,
    )
    raw = r.choices[0].message.content or ""
    return parse_json(raw), raw


def get_mcafee_products() -> List[str]:
    """Get list of available McAfee products."""
    return MCAFEE_PRODUCTS


def calculate_summary(data: List[Dict]) -> Dict:
    """Calculate summary statistics from comparison data."""
    if not data:
        return {}

    prices = [(d.get("price_usd_year", 999), d) for d in data]
    best_entry = min(prices, key=lambda x: x[0])[1]
    mcafee_entry = next((d for d in data if d.get("competitor") == "McAfee"), None)
    
    feat_counts = {
        d["competitor"]: sum(1 for v in (d.get("features") or {}).values() if v is True)
        for d in data
    }
    
    top_feat_vendor = max(feat_counts, key=feat_counts.get) if feat_counts else "—"
    top_feat_count = feat_counts.get(top_feat_vendor, 0)

    return {
        "vendors_compared": len(data),
        "lowest_price": best_entry.get("price_usd_year"),
        "lowest_price_vendor": best_entry.get("competitor"),
        "most_features_vendor": top_feat_vendor,
        "most_features_count": top_feat_count,
        "mcafee_price": mcafee_entry.get("price_usd_year") if mcafee_entry else None,
    }
