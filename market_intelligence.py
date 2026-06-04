"""
Comprehensive Market Intelligence Engine
Synthesizes Indian + global data into actionable trade context.

Sources:
  • yfinance        — global indices, US futures, commodities, yields, currencies
  • NSE India API   — FII/DII flows, advance/decline breadth, sector data
  • Forex Factory   — economic calendar (high-impact events)
  • RSS feeds       — news with geopolitical / policy sentiment scoring
  • Upstox          — live India VIX, option chain OI/PCR
"""

import yfinance as yf
import numpy as np
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
import logging

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# TICKER MAPS
# ─────────────────────────────────────────────────────────────────────────────

US_FUTURES = {
    "S&P 500 Fut":   "ES=F",
    "Nasdaq Fut":    "NQ=F",
    "Dow Fut":       "YM=F",
    "Crude Oil":     "CL=F",
    "Gold":          "GC=F",
    "Natural Gas":   "NG=F",
}

GLOBAL_INDICES = {
    # Americas
    "S&P 500":      "^GSPC",
    "Nasdaq":       "^IXIC",
    "Dow Jones":    "^DJI",
    # Europe
    "FTSE 100":     "^FTSE",
    "DAX":          "^GDAXI",
    "Euro Stoxx 50":"^STOXX50E",
    # Asia-Pacific
    "Nikkei 225":   "^N225",
    "Hang Seng":    "^HSI",
    "Shanghai":     "000001.SS",
    "KOSPI":        "^KS11",
    "ASX 200":      "^AXJO",
}

MACRO_TICKERS = {
    # Currencies
    "USD/INR":      "USDINR=X",
    "EUR/USD":      "EURUSD=X",
    "GBP/USD":      "GBPUSD=X",
    "USD/JPY":      "JPY=X",
    "Dollar Index": "DX-Y.NYB",
    # Commodities
    "Crude Oil":    "CL=F",
    "Brent Crude":  "BZ=F",
    "Gold":         "GC=F",
    "Silver":       "SI=F",
    "Copper":       "HG=F",
    # Bonds / Yields
    "US 2Y Yield":  "^FVX",        # 5Y (proxy)
    "US 10Y Yield": "^TNX",
    "US 30Y Yield": "^TYX",
    "US VIX":       "^VIX",
}

NSE_SECTORS = {
    "Nifty Bank":   "^NSEBANK",
    "Nifty IT":     "^CNXIT",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty FMCG":   "^CNXFMCG",
    "Nifty Auto":   "^CNXAUTO",
    "Nifty Realty": "^CNXREALTY",
    "Nifty Metal":  "^CNXMETAL",
    "Nifty Energy": "^CNXENERGY",
    "Fin Nifty":    "^CNXFIN",
    "Nifty MidCap": "^NSEMDCP50",
}

# ─────────────────────────────────────────────────────────────────────────────
# NEWS SENTIMENT
# ─────────────────────────────────────────────────────────────────────────────

BULL_KW = {
    "rally","surge","gain","rise","rises","rose","positive","growth","strong","up",
    "bull","buying","recovery","boost","record","high","stimulus","cut","easing",
    "beat","exceed","profit","upgrade","accumulate","buy","invest","optimism","hope",
}
BEAR_KW = {
    "fall","drop","decline","negative","recession","weak","down","bear","sell",
    "crash","crisis","fear","risk","loss","miss","warning","downgrade","avoid",
    "slowdown","contraction","default","debt","deficit","inflation","hike","tighten",
}
GEO_KW = {
    "war","conflict","sanction","tension","attack","military","nuclear","missile",
    "ceasefire","invasion","geopolitical","terror","coup","protest","unrest",
}
POLICY_KW = {
    "rbi","fed","ecb","boe","rate","monetary","policy","mpc","fomc","inflation",
    "gdp","cpi","pmi","npa","budget","fiscal","tariff","duty","regulation","sebi",
}
EARNINGS_KW = {
    "earnings","quarterly","results","profit","revenue","guidance","eps","q1","q2",
    "q3","q4","fy","annual","dividend","buyback","capex","margin","ebitda",
}

NEWS_FEEDS = [
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rss.cms"),
    ("Mint Markets",   "https://www.livemint.com/rss/markets"),
    ("Reuters Biz",    "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC World",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
]


def fetch_news_intelligence() -> dict:
    """
    Fetch and score news across multiple dimensions:
    bull_score, bear_score, geo_risk, policy_event, earnings_alerts
    Returns aggregated sentiment and key headlines per category.
    """
    headlines = []
    for source, url in NEWS_FEEDS:
        try:
            r = requests.get(url, timeout=6,
                             headers={"User-Agent": "Mozilla/5.0",
                                      "Accept": "application/rss+xml"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:8]:
                title = (item.findtext("title") or "").strip()
                if title:
                    headlines.append({"source": source, "title": title})
        except Exception:
            continue

    bull = bear = geo = policy = earnings = 0
    geo_headlines = []
    policy_headlines = []
    earnings_headlines = []
    top_bull = []
    top_bear = []

    for h in headlines:
        words = set(h["title"].lower().split())
        b = len(words & BULL_KW)
        d = len(words & BEAR_KW)
        g = len(words & GEO_KW)
        p = len(words & POLICY_KW)
        e = len(words & EARNINGS_KW)

        bull += b; bear += d; geo += g; policy += p; earnings += e

        if g > 0:
            geo_headlines.append(h["title"])
        if p > 0:
            policy_headlines.append(h["title"])
        if e > 0:
            earnings_headlines.append(h["title"])
        if b > d:
            top_bull.append(h["title"])
        elif d > b:
            top_bear.append(h["title"])

    net = bull - bear
    if net >= 6:      news_label, news_bias = "Strongly positive news flow", "bullish"
    elif net >= 2:    news_label, news_bias = "Mildly positive news flow",   "bullish"
    elif net >= -2:   news_label, news_bias = "Neutral / mixed news flow",   "neutral"
    elif net >= -6:   news_label, news_bias = "Mildly negative news flow",   "bearish"
    else:             news_label, news_bias = "Strongly negative news flow",  "bearish"

    geo_risk = "HIGH" if geo >= 4 else ("MEDIUM" if geo >= 2 else "LOW")

    return {
        "net_score":          net,
        "label":              news_label,
        "bias":               news_bias,
        "geo_risk":           geo_risk,
        "geo_headlines":      geo_headlines[:3],
        "policy_headlines":   policy_headlines[:3],
        "earnings_headlines": earnings_headlines[:3],
        "top_bull":           top_bull[:3],
        "top_bear":           top_bear[:3],
        "total_headlines":    len(headlines),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ECONOMIC CALENDAR
# ─────────────────────────────────────────────────────────────────────────────

def fetch_economic_events() -> list:
    """
    Fetch today's high-impact economic events from Forex Factory RSS.
    Returns list of {time, currency, event, impact}
    """
    events = []
    today_str = datetime.now(IST).strftime("%b %d").lstrip("0")
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        data = r.json()
        for ev in data:
            if ev.get("impact") not in ("High", "Medium"):
                continue
            ev_date = ev.get("date", "")
            currency = ev.get("currency", "")
            title    = ev.get("title", "")
            if currency not in ("USD", "EUR", "GBP", "JPY", "INR", "CNY"):
                continue
            # Check if it's today (rough match)
            try:
                ev_dt = datetime.fromisoformat(ev_date.replace("Z", "+00:00"))
                ev_ist = ev_dt.astimezone(IST)
                if ev_ist.date() == datetime.now(IST).date():
                    events.append({
                        "time":     ev_ist.strftime("%H:%M IST"),
                        "currency": currency,
                        "event":    title,
                        "impact":   ev.get("impact", "Medium"),
                    })
            except Exception:
                continue
    except Exception as e:
        log.debug("Economic calendar fetch failed: %s", e)

    # Fallback: known RBI MPC and major event keywords from news
    return events


# ─────────────────────────────────────────────────────────────────────────────
# MARKET DATA FETCHERS
# ─────────────────────────────────────────────────────────────────────────────

def _quick_quote(ticker: str) -> dict:
    """Fast single-ticker quote using fast_info."""
    try:
        fi = yf.Ticker(ticker).fast_info
        ltp  = float(fi.last_price   or 0)
        prev = float(fi.previous_close or ltp)
        chg  = ltp - prev
        pct  = (chg / prev * 100) if prev else 0
        return {"ltp": ltp, "prev": prev, "chg": round(chg, 2), "pct": round(pct, 2)}
    except Exception:
        return {}


def fetch_us_futures() -> dict:
    """Fetch US index futures + key commodities for pre-market read."""
    result = {}
    try:
        tickers = list(US_FUTURES.values())
        raw = yf.download(tickers, period="2d", interval="5m",
                          progress=False, auto_adjust=True, group_by="ticker")
        for name, ticker in US_FUTURES.items():
            try:
                df = raw[ticker].dropna() if ticker in raw.columns.get_level_values(0) else pd.DataFrame()
                if not df.empty:
                    ltp  = float(df["Close"].iloc[-1])
                    prev = float(df["Close"].iloc[0])
                    pct  = (ltp - prev) / prev * 100 if prev else 0
                    result[name] = {"ltp": ltp, "pct": round(pct, 2)}
            except Exception:
                result[name] = _quick_quote(ticker)
    except Exception:
        for name, ticker in US_FUTURES.items():
            result[name] = _quick_quote(ticker)
    return result


def fetch_global_indices() -> dict:
    """Fetch extended global index coverage."""
    result = {}
    for name, ticker in GLOBAL_INDICES.items():
        q = _quick_quote(ticker)
        if q:
            result[name] = q
    return result


def fetch_macro_data() -> dict:
    """Fetch currencies, commodities, bonds, VIX."""
    result = {}
    for name, ticker in MACRO_TICKERS.items():
        q = _quick_quote(ticker)
        if q:
            result[name] = q
    return result


def fetch_sector_performance() -> dict:
    """Fetch all NSE sector index performance."""
    result = {}
    for name, ticker in NSE_SECTORS.items():
        q = _quick_quote(ticker)
        if q:
            result[name] = q
    # Sort by pct change
    ranked = dict(sorted(result.items(), key=lambda x: x[1].get("pct", 0), reverse=True))
    return ranked


def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":      "application/json",
        "Referer":     "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except Exception:
        pass
    return s


def fetch_fii_dii() -> dict:
    try:
        s = _nse_session()
        r = s.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=10)
        r.raise_for_status()
        rows = r.json()
        result = {}
        for row in rows:
            cat = row.get("category", "")
            if "FII" in cat or "FPI" in cat:
                result["fii_buy"]  = float(row.get("buyValue",  0) or 0)
                result["fii_sell"] = float(row.get("sellValue", 0) or 0)
                result["fii_net"]  = float(row.get("netValue",  0) or 0)
                result["date"]     = row.get("date", "")
            elif "DII" in cat:
                result["dii_buy"]  = float(row.get("buyValue",  0) or 0)
                result["dii_sell"] = float(row.get("sellValue", 0) or 0)
                result["dii_net"]  = float(row.get("netValue",  0) or 0)
        return result
    except Exception:
        return {}


def fetch_market_breadth() -> dict:
    try:
        s = _nse_session()
        r = s.get(
            "https://www.nseindia.com/api/live-analysis-variations?index=secGtr",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        advances = declines = unchanged = 0
        for item in data:
            for sym in (item.get("data") or []):
                pct = sym.get("pChange", 0) or 0
                if pct > 0.5:      advances  += 1
                elif pct < -0.5:   declines  += 1
                else:              unchanged += 1
        total = max(advances + declines + unchanged, 1)
        ratio = round(advances / max(declines, 1), 2)
        pct_adv = round(advances / total * 100, 1)
        if ratio >= 2.0:    label, bias = f"Strong breadth {advances}A/{declines}D", "bullish"
        elif ratio >= 1.2:  label, bias = f"Positive breadth {advances}A/{declines}D", "bullish"
        elif ratio >= 0.8:  label, bias = f"Mixed breadth {advances}A/{declines}D", "neutral"
        else:               label, bias = f"Weak breadth {advances}A/{declines}D", "bearish"
        return {
            "advances": advances, "declines": declines,
            "unchanged": unchanged, "ratio": ratio,
            "pct_adv": pct_adv, "label": label, "bias": bias,
        }
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHESIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def synthesize(
    global_indices: dict,
    macro_data:     dict,
    us_futures:     dict,
    sectors:        dict,
    fii_dii:        dict,
    breadth:        dict,
    news:           dict,
    vix_india:      float = 15.0,
    nifty_pct:      float = 0.0,
) -> dict:
    """
    Combine all intelligence into a single macro score (-20 to +20)
    and a structured list of market drivers.

    Returns:
      macro_score    : int (-20 to +20)
      market_regime  : RISK_ON / RISK_OFF / NEUTRAL
      risk_level     : LOW / MEDIUM / HIGH / EXTREME
      drivers        : list of {factor, signal, note, weight}
      summary        : one-line market summary
      bull_factors   : list[str]
      bear_factors   : list[str]
      geo_alert      : str or None
      policy_alert   : str or None
    """
    score = 0
    bull_factors = []
    bear_factors = []
    drivers = []

    def _add(factor, signal, note, weight, is_bull):
        nonlocal score
        score += weight if is_bull else -weight
        drivers.append({
            "factor": factor, "signal": signal,
            "note": note, "weight": weight, "bull": is_bull,
        })
        if is_bull:
            bull_factors.append(f"✅ {factor}: {note}")
        else:
            bear_factors.append(f"❌ {factor}: {note}")

    # 1. US Equity Trend (weight 4)
    sp_pct  = global_indices.get("S&P 500",  {}).get("pct", 0)
    nas_pct = global_indices.get("Nasdaq",    {}).get("pct", 0)
    if sp_pct > 0.5:
        _add("US Markets", "🟢 Bullish", f"S&P {sp_pct:+.2f}%, Nasdaq {nas_pct:+.2f}%", 4, True)
    elif sp_pct < -0.5:
        _add("US Markets", "🔴 Bearish", f"S&P {sp_pct:+.2f}%, Nasdaq {nas_pct:+.2f}%", 4, False)
    else:
        drivers.append({"factor": "US Markets", "signal": "🟡 Flat",
                         "note": f"S&P {sp_pct:+.2f}%", "weight": 0, "bull": None})

    # 2. US Futures (pre-market signal when India is open, weight 3)
    es_pct  = us_futures.get("S&P 500 Fut", {}).get("pct", 0)
    nq_pct  = us_futures.get("Nasdaq Fut",  {}).get("pct", 0)
    if es_pct > 0.3 or nq_pct > 0.3:
        _add("US Futures", "🟢 Positive", f"S&P Fut {es_pct:+.2f}%, NQ Fut {nq_pct:+.2f}%", 3, True)
    elif es_pct < -0.3 or nq_pct < -0.3:
        _add("US Futures", "🔴 Negative", f"S&P Fut {es_pct:+.2f}%, NQ Fut {nq_pct:+.2f}%", 3, False)

    # 3. Asian Markets (weight 3)
    nik_pct = global_indices.get("Nikkei 225", {}).get("pct", 0)
    hsi_pct = global_indices.get("Hang Seng",  {}).get("pct", 0)
    kos_pct = global_indices.get("KOSPI",       {}).get("pct", 0)
    asia_avg = np.mean([p for p in [nik_pct, hsi_pct, kos_pct] if p != 0] or [0])
    if asia_avg > 0.4:
        _add("Asian Markets", "🟢 Bullish",
             f"Nikkei {nik_pct:+.2f}%, HSI {hsi_pct:+.2f}%, KOSPI {kos_pct:+.2f}%", 3, True)
    elif asia_avg < -0.4:
        _add("Asian Markets", "🔴 Bearish",
             f"Nikkei {nik_pct:+.2f}%, HSI {hsi_pct:+.2f}%, KOSPI {kos_pct:+.2f}%", 3, False)

    # 4. European Markets (weight 2)
    ftse_pct = global_indices.get("FTSE 100",     {}).get("pct", 0)
    dax_pct  = global_indices.get("DAX",           {}).get("pct", 0)
    eur_avg  = np.mean([p for p in [ftse_pct, dax_pct] if p != 0] or [0])
    if eur_avg > 0.4:
        _add("European Mkts", "🟢 Bullish", f"FTSE {ftse_pct:+.2f}%, DAX {dax_pct:+.2f}%", 2, True)
    elif eur_avg < -0.4:
        _add("European Mkts", "🔴 Bearish", f"FTSE {ftse_pct:+.2f}%, DAX {dax_pct:+.2f}%", 2, False)

    # 5. Crude Oil (weight 2 — inverted: high crude = bad for India)
    crude_pct = macro_data.get("Crude Oil", {}).get("pct", 0)
    crude_ltp = macro_data.get("Crude Oil", {}).get("ltp", 75)
    if crude_pct > 1.5:
        _add("Crude Oil", "🔴 Rising fast",
             f"${crude_ltp:.1f}/bbl ({crude_pct:+.2f}%) — CAD impact, inflation risk", 2, False)
    elif crude_pct < -1.5:
        _add("Crude Oil", "🟢 Falling",
             f"${crude_ltp:.1f}/bbl ({crude_pct:+.2f}%) — positive for India (import relief)", 2, True)
    else:
        drivers.append({"factor": "Crude Oil", "signal": "🟡 Stable",
                         "note": f"${crude_ltp:.1f}/bbl ({crude_pct:+.2f}%)", "weight": 0, "bull": None})

    # 6. USD/INR — rupee strength (weight 2)
    usdinr_pct = macro_data.get("USD/INR", {}).get("pct", 0)
    usdinr_ltp = macro_data.get("USD/INR", {}).get("ltp", 83)
    if usdinr_pct > 0.3:     # Rupee weakening
        _add("USD/INR", "🔴 Rupee Weakening",
             f"₹{usdinr_ltp:.2f}/$ ({usdinr_pct:+.2f}%) — FII outflow risk", 2, False)
    elif usdinr_pct < -0.3:  # Rupee strengthening
        _add("USD/INR", "🟢 Rupee Strengthening",
             f"₹{usdinr_ltp:.2f}/$ ({usdinr_pct:+.2f}%) — FII inflow positive", 2, True)
    else:
        drivers.append({"factor": "USD/INR", "signal": "🟡 Stable",
                         "note": f"₹{usdinr_ltp:.2f}/$ ({usdinr_pct:+.2f}%)", "weight": 0, "bull": None})

    # 7. US 10Y Yield (weight 2)
    tnx_ltp = macro_data.get("US 10Y Yield", {}).get("ltp", 4.2)
    tnx_pct = macro_data.get("US 10Y Yield", {}).get("pct", 0)
    if tnx_ltp > 4.5 or tnx_pct > 2:
        _add("US 10Y Yield", "🔴 Elevated / Rising",
             f"{tnx_ltp:.2f}% ({tnx_pct:+.2f}%) — tightening financial conditions", 2, False)
    elif tnx_ltp < 3.8 or tnx_pct < -2:
        _add("US 10Y Yield", "🟢 Low / Falling",
             f"{tnx_ltp:.2f}% ({tnx_pct:+.2f}%) — accommodative, positive for equities", 2, True)
    else:
        drivers.append({"factor": "US 10Y Yield", "signal": "🟡 Neutral",
                         "note": f"{tnx_ltp:.2f}%", "weight": 0, "bull": None})

    # 8. US VIX — global fear gauge (weight 3)
    us_vix = macro_data.get("US VIX", {}).get("ltp", 18)
    if us_vix > 25:
        _add("US VIX", "🔴 Extreme Fear",
             f"VIX {us_vix:.1f} — global risk-off, avoid aggressive positions", 3, False)
    elif us_vix > 20:
        _add("US VIX", "🟠 Elevated Fear",
             f"VIX {us_vix:.1f} — caution warranted, reduce size", 2, False)
    elif us_vix < 15:
        _add("US VIX", "🟢 Low Fear",
             f"VIX {us_vix:.1f} — risk-on environment, favours option buying", 2, True)
    else:
        drivers.append({"factor": "US VIX", "signal": "🟡 Normal",
                         "note": f"VIX {us_vix:.1f}", "weight": 0, "bull": None})

    # 9. India VIX (weight 2)
    if vix_india > 20:
        _add("India VIX", "🔴 High",
             f"VIX {vix_india:.1f} — volatility elevated, buy ATM only, cut size", 2, False)
    elif vix_india < 13:
        _add("India VIX", "🟢 Very Low",
             f"VIX {vix_india:.1f} — cheap options, good for directional buys", 2, True)
    else:
        drivers.append({"factor": "India VIX", "signal": "🟡 Normal",
                         "note": f"VIX {vix_india:.1f}", "weight": 0, "bull": None})

    # 10. Dollar Index (weight 1)
    dxy_pct = macro_data.get("Dollar Index", {}).get("pct", 0)
    dxy_ltp = macro_data.get("Dollar Index", {}).get("ltp", 104)
    if dxy_pct > 0.3:
        _add("Dollar Index", "🔴 DXY Strengthening",
             f"DXY {dxy_ltp:.2f} ({dxy_pct:+.2f}%) — EM outflows, rupee pressure", 1, False)
    elif dxy_pct < -0.3:
        _add("Dollar Index", "🟢 DXY Weakening",
             f"DXY {dxy_ltp:.2f} ({dxy_pct:+.2f}%) — EM inflows, rupee support", 1, True)

    # 11. Gold (weight 1 — risk-off indicator)
    gold_pct = macro_data.get("Gold", {}).get("pct", 0)
    gold_ltp = macro_data.get("Gold", {}).get("ltp", 2000)
    if gold_pct > 1.0:
        _add("Gold", "🔴 Risk-Off Signal",
             f"${gold_ltp:.0f}/oz ({gold_pct:+.2f}%) — flight to safety, caution", 1, False)
    elif gold_pct < -0.8:
        _add("Gold", "🟢 Risk-On Signal",
             f"${gold_ltp:.0f}/oz ({gold_pct:+.2f}%) — investors prefer equities", 1, True)

    # 12. FII/DII (weight 3)
    if fii_dii:
        fii_net = fii_dii.get("fii_net", 0)
        dii_net = fii_dii.get("dii_net", 0)
        if fii_net > 1000:
            _add("FII Activity", "🟢 Strong Buying",
                 f"FII net +₹{fii_net:,.0f}Cr — institutional support", 3, True)
        elif fii_net > 300:
            _add("FII Activity", "🟢 Buying",
                 f"FII net +₹{fii_net:,.0f}Cr", 2, True)
        elif fii_net < -1000:
            _add("FII Activity", "🔴 Heavy Selling",
                 f"FII net ₹{fii_net:,.0f}Cr — institutional exit", 3, False)
        elif fii_net < -300:
            _add("FII Activity", "🔴 Selling",
                 f"FII net ₹{fii_net:,.0f}Cr", 2, False)
        if dii_net > 500:
            _add("DII Activity", "🟢 Buying",
                 f"DII net +₹{dii_net:,.0f}Cr — domestic support", 1, True)
        elif dii_net < -500:
            _add("DII Activity", "🔴 Selling",
                 f"DII net ₹{dii_net:,.0f}Cr", 1, False)
    else:
        drivers.append({"factor": "FII/DII", "signal": "⏳ Pending",
                         "note": "NSE updates after 4 PM", "weight": 0, "bull": None})

    # 13. Market Breadth (weight 2)
    if breadth:
        b_bias = breadth.get("bias", "neutral")
        ratio  = breadth.get("ratio", 1)
        if b_bias == "bullish":
            _add("Market Breadth", "🟢 Broad Rally", breadth.get("label",""), 2, True)
        elif b_bias == "bearish":
            _add("Market Breadth", "🔴 Broad Decline", breadth.get("label",""), 2, False)

    # 14. News Intelligence (weight 2)
    if news:
        news_net = news.get("net_score", 0)
        if news_net >= 3:
            _add("News Flow", "🟢 Positive",
                 f"{news.get('label','')} ({news.get('total_headlines',0)} headlines)", 2, True)
        elif news_net <= -3:
            _add("News Flow", "🔴 Negative",
                 f"{news.get('label','')} — market-moving negative headlines", 2, False)
        else:
            drivers.append({"factor": "News Flow", "signal": "🟡 Mixed",
                             "note": news.get("label",""), "weight": 0, "bull": None})

    # 15. Sector Performance (bonus)
    if sectors:
        top_sector = list(sectors.keys())[0] if sectors else None
        bot_sector = list(sectors.keys())[-1] if sectors else None
        top_pct = sectors.get(top_sector, {}).get("pct", 0) if top_sector else 0
        bot_pct = sectors.get(bot_sector, {}).get("pct", 0) if bot_sector else 0
        if top_pct > 1.5:
            drivers.append({"factor": "Sector Leader", "signal": "🟢",
                             "note": f"{top_sector} leading +{top_pct:.2f}%",
                             "weight": 0, "bull": True})
        if bot_pct < -1.5:
            drivers.append({"factor": "Sector Drag", "signal": "🔴",
                             "note": f"{bot_sector} dragging {bot_pct:.2f}%",
                             "weight": 0, "bull": False})

    # ── Final synthesis ───────────────────────────────────────────────────────
    score = max(-20, min(20, score))

    if score >= 8:
        regime, risk = "RISK_ON",  "LOW"
        summary = "Strong global tailwinds — institutional buying, positive sentiment across markets"
    elif score >= 4:
        regime, risk = "RISK_ON",  "LOW"
        summary = "Moderately positive — most global cues supportive, manageable risk environment"
    elif score >= 1:
        regime, risk = "NEUTRAL",  "MEDIUM"
        summary = "Mixed signals — proceed with caution, use strict risk management"
    elif score >= -3:
        regime, risk = "NEUTRAL",  "MEDIUM"
        summary = "Cautious environment — headwinds present, prefer smaller size or pass"
    elif score >= -8:
        regime, risk = "RISK_OFF", "HIGH"
        summary = "Risk-off mode — multiple headwinds, avoid aggressive option buying"
    else:
        regime, risk = "RISK_OFF", "EXTREME"
        summary = "Extreme caution — stay out. Multiple serious headwinds. Capital preservation first."

    # Override: geopolitical risk
    geo_risk = news.get("geo_risk", "LOW") if news else "LOW"
    geo_alert    = None
    policy_alert = None
    if geo_risk == "HIGH":
        risk = "HIGH"
        geo_alert = "⚠️ GEOPOLITICAL RISK: " + (news.get("geo_headlines", [""])[0][:80] if news else "")
    if news and news.get("policy_headlines"):
        policy_alert = "📢 POLICY EVENT: " + news["policy_headlines"][0][:80]

    return {
        "macro_score":    score,
        "market_regime":  regime,
        "risk_level":     risk,
        "summary":        summary,
        "drivers":        drivers,
        "bull_factors":   bull_factors,
        "bear_factors":   bear_factors,
        "geo_alert":      geo_alert,
        "policy_alert":   policy_alert,
        "news":           news or {},
        "sectors":        sectors,
        "fii_dii":        fii_dii,
        "breadth":        breadth,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def get_full_intelligence(vix_india: float = 15.0, nifty_pct: float = 0.0) -> dict:
    """
    Fetch all data sources and synthesize into comprehensive market intelligence.
    Call this once per tab render; use Streamlit @st.cache_data(ttl=300) externally.
    """
    global_idx = fetch_global_indices()
    macro      = fetch_macro_data()
    futures    = fetch_us_futures()
    sectors    = fetch_sector_performance()
    fii_dii    = fetch_fii_dii()
    breadth    = fetch_market_breadth()
    news       = fetch_news_intelligence()
    events     = fetch_economic_events()

    intel = synthesize(
        global_indices=global_idx,
        macro_data=macro,
        us_futures=futures,
        sectors=sectors,
        fii_dii=fii_dii,
        breadth=breadth,
        news=news,
        vix_india=vix_india,
        nifty_pct=nifty_pct,
    )
    intel["global_indices"] = global_idx
    intel["macro_data"]     = macro
    intel["us_futures"]     = futures
    intel["eco_events"]     = events
    return intel
