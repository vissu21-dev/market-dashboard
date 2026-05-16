"""
India Stock Market Dashboard — powered by Yahoo Finance (yfinance)
Run: streamlit run streamlit_app.py
Auto-refreshes every 30 seconds during market hours.
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz
import os
import csv

st.set_page_config(
    page_title="India Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

IST = pytz.timezone("Asia/Kolkata")

# ── Dark theme CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.metric-card {
    background: #1a1d2e; border-radius: 10px; padding: 14px 18px;
    border-left: 4px solid #3b82f6; margin-bottom: 10px;
}
.bull { color: #26a69a; } .bear { color: #ef5350; }
.neutral { color: #f59e0b; }
.section-title { font-size: 16px; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 1px; margin: 16px 0 8px; }
.signal-box {
    background: #1a1d2e; border-radius: 8px; padding: 12px 16px; margin: 6px 0;
}
.pill {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 600; margin: 2px;
}
.pill-green { background: rgba(38,166,154,0.2); color: #26a69a; border: 1px solid #26a69a; }
.pill-red   { background: rgba(239,83,80,0.2);  color: #ef5350; border: 1px solid #ef5350; }
.pill-yellow{ background: rgba(245,158,11,0.2); color: #f59e0b; border: 1px solid #f59e0b; }
div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700; }
.trade-card-call {
    background: linear-gradient(135deg, #0d2618 0%, #1a1d2e 100%);
    border: 2px solid #26a69a; border-radius: 14px; padding: 20px 24px; margin: 8px 0;
}
.trade-card-put {
    background: linear-gradient(135deg, #2a0d0d 0%, #1a1d2e 100%);
    border: 2px solid #ef5350; border-radius: 14px; padding: 20px 24px; margin: 8px 0;
}
.trade-header { font-size: 22px; font-weight: 800; letter-spacing: 1px; margin-bottom: 6px; }
.trade-strike { font-size: 15px; color: #9ca3af; margin-bottom: 14px; }
.trade-row { display: flex; justify-content: space-between; margin: 6px 0; }
.trade-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
.trade-value { font-size: 15px; font-weight: 700; }
.signal-buy  { background: #26a69a; color: #000; padding: 6px 18px; border-radius: 20px;
               font-weight: 800; font-size: 14px; display: inline-block; margin: 4px 4px 4px 0; }
.signal-exit { background: #ef5350; color: #fff; padding: 6px 18px; border-radius: 20px;
               font-weight: 800; font-size: 14px; display: inline-block; margin: 4px; }
.signal-wait { background: #f59e0b; color: #000; padding: 6px 18px; border-radius: 20px;
               font-weight: 800; font-size: 14px; display: inline-block; margin: 4px; }
.conf-high   { color: #26a69a; font-weight: 800; }
.conf-med    { color: #f59e0b; font-weight: 800; }
.conf-low    { color: #ef5350; font-weight: 800; }
.no-trade-banner {
    background: rgba(245,158,11,0.1); border: 2px solid #f59e0b;
    border-radius: 12px; padding: 20px; text-align: center;
    font-size: 18px; font-weight: 700; color: #f59e0b; margin: 20px 0;
}
.checklist-item-ok   { background:#0d2618; border-left:4px solid #26a69a;
    border-radius:8px; padding:10px 16px; margin:5px 0; font-size:14px; }
.checklist-item-warn { background:#2a1f0d; border-left:4px solid #f59e0b;
    border-radius:8px; padding:10px 16px; margin:5px 0; font-size:14px; }
.checklist-item-bad  { background:#2a0d0d; border-left:4px solid #ef5350;
    border-radius:8px; padding:10px 16px; margin:5px 0; font-size:14px; }
.alert-box { background:#1a1d2e; border:2px solid #3b82f6; border-radius:10px;
    padding:14px 18px; margin:8px 0; }
.alert-triggered { border-color:#ef5350 !important; background:#2a0d0d !important; }
</style>
""", unsafe_allow_html=True)

# ── Tickers ───────────────────────────────────────────────────────────────────
TICKERS = {
    "Nifty 50":     "^NSEI",
    "Bank Nifty":   "^NSEBANK",
    "India VIX":    "^INDIAVIX",
    "Sensex":       "^BSESN",
    "Nifty IT":     "^CNXIT",
}
GLOBAL = {
    "S&P 500":      "^GSPC",
    "Dow Jones":    "^DJI",
    "Nasdaq":       "^IXIC",
    "Nikkei 225":   "^N225",
    "Hang Seng":    "^HSI",
    "Crude Oil":    "CL=F",
    "Gold":         "GC=F",
    "USD/INR":      "USDINR=X",
    "Dollar Index": "DX-Y.NYB",
    "US 10Y Yield": "^TNX",
}

NIFTY50_STOCKS = {
    "Reliance":         "RELIANCE.NS",
    "TCS":              "TCS.NS",
    "HDFC Bank":        "HDFCBANK.NS",
    "Infosys":          "INFY.NS",
    "ICICI Bank":       "ICICIBANK.NS",
    "HUL":              "HINDUNILVR.NS",
    "ITC":              "ITC.NS",
    "SBI":              "SBIN.NS",
    "Bajaj Finance":    "BAJFINANCE.NS",
    "Bharti Airtel":    "BHARTIARTL.NS",
    "Kotak Bank":       "KOTAKBANK.NS",
    "L&T":              "LT.NS",
    "Axis Bank":        "AXISBANK.NS",
    "Asian Paints":     "ASIANPAINT.NS",
    "Maruti":           "MARUTI.NS",
    "Titan":            "TITAN.NS",
    "Sun Pharma":       "SUNPHARMA.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "Wipro":            "WIPRO.NS",
    "ONGC":             "ONGC.NS",
    "Power Grid":       "POWERGRID.NS",
    "NTPC":             "NTPC.NS",
    "Tech Mahindra":    "TECHM.NS",
    "Nestle":           "NESTLEIND.NS",
    "HCL Tech":         "HCLTECH.NS",
    "Tata Motors":      "TATAMOTORS.NS",
    "Tata Steel":       "TATASTEEL.NS",
    "JSW Steel":        "JSWSTEEL.NS",
    "Hindalco":         "HINDALCO.NS",
    "M&M":              "M&M.NS",
    "Dr Reddy's":       "DRREDDY.NS",
    "Cipla":            "CIPLA.NS",
    "Bajaj Auto":       "BAJAJ-AUTO.NS",
    "Eicher Motors":    "EICHERMOT.NS",
    "Coal India":       "COALINDIA.NS",
    "Hero MotoCorp":    "HEROMOTOCO.NS",
    "Apollo Hospitals": "APOLLOHOSP.NS",
    "Tata Consumer":    "TATACONSUM.NS",
    "Britannia":        "BRITANNIA.NS",
    "IndusInd Bank":    "INDUSINDBK.NS",
    "SBI Life":         "SBILIFE.NS",
    "HDFC Life":        "HDFCLIFE.NS",
    "Adani Ports":      "ADANIPORTS.NS",
    "Adani Ent.":       "ADANIENT.NS",
    "Grasim":           "GRASIM.NS",
    "Divi's Labs":      "DIVISLAB.NS",
    "Bajaj Finserv":    "BAJAJFINSV.NS",
    "UPL":              "UPL.NS",
    "Shree Cement":     "SHREECEM.NS",
}

STOCK_SECTORS = {
    "RELIANCE.NS": "Energy",    "ONGC.NS": "Energy",
    "HDFCBANK.NS": "Banking",   "ICICIBANK.NS": "Banking",  "SBIN.NS": "Banking",
    "AXISBANK.NS": "Banking",   "KOTAKBANK.NS": "Banking",  "INDUSINDBK.NS": "Banking",
    "TCS.NS": "IT",             "INFY.NS": "IT",            "WIPRO.NS": "IT",
    "HCLTECH.NS": "IT",         "TECHM.NS": "IT",
    "HINDUNILVR.NS": "FMCG",   "ITC.NS": "FMCG",          "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG",    "TATACONSUM.NS": "FMCG",
    "MARUTI.NS": "Auto",        "TATAMOTORS.NS": "Auto",    "M&M.NS": "Auto",
    "BAJAJ-AUTO.NS": "Auto",    "HEROMOTOCO.NS": "Auto",    "EICHERMOT.NS": "Auto",
    "SUNPHARMA.NS": "Pharma",   "DRREDDY.NS": "Pharma",    "CIPLA.NS": "Pharma",
    "DIVISLAB.NS": "Pharma",
    "BAJFINANCE.NS": "Finance", "BAJAJFINSV.NS": "Finance", "SBILIFE.NS": "Finance",
    "HDFCLIFE.NS": "Finance",
    "LT.NS": "Infra",           "POWERGRID.NS": "Infra",   "NTPC.NS": "Infra",
    "COALINDIA.NS": "Infra",    "ADANIPORTS.NS": "Infra",
    "TATASTEEL.NS": "Metals",   "JSWSTEEL.NS": "Metals",   "HINDALCO.NS": "Metals",
    "ASIANPAINT.NS": "Consumer","TITAN.NS": "Consumer",
    "ULTRACEMCO.NS": "Cement",  "GRASIM.NS": "Cement",     "SHREECEM.NS": "Cement",
    "BHARTIARTL.NS": "Telecom", "APOLLOHOSP.NS": "Healthcare",
    "UPL.NS": "Chemicals",      "ADANIENT.NS": "Conglomerate",
}

MUTUAL_FUNDS = [
    # Large Cap
    {"name": "Mirae Asset Large Cap Fund", "category": "Large Cap", "risk": "Moderate",
     "ret_1y": 18.5, "ret_3y": 16.2, "ret_5y": 17.8, "aum": "₹36,000 Cr",
     "min_sip": 1000, "stars": 5, "profiles": ["Moderate", "Aggressive"],
     "horizon": "3y+", "goal": ["Wealth Creation", "Retirement"],
     "why": "Consistent Nifty-beating returns, large AUM gives stability",
     "amfi_search": ["mirae asset large cap", "direct", "growth"]},
    {"name": "Axis Bluechip Fund", "category": "Large Cap", "risk": "Moderate",
     "ret_1y": 16.2, "ret_3y": 14.8, "ret_5y": 16.5, "aum": "₹28,000 Cr",
     "min_sip": 500, "stars": 4, "profiles": ["Conservative", "Moderate"],
     "horizon": "3y+", "goal": ["Wealth Creation", "Retirement"],
     "why": "Quality-focused portfolio, lower drawdown in bear markets",
     "amfi_search": ["axis bluechip", "direct", "growth"]},
    # Flexi Cap
    {"name": "Parag Parikh Flexi Cap Fund", "category": "Flexi Cap", "risk": "Moderate",
     "ret_1y": 22.1, "ret_3y": 19.4, "ret_5y": 21.2, "aum": "₹65,000 Cr",
     "min_sip": 1000, "stars": 5, "profiles": ["Moderate", "Aggressive"],
     "horizon": "5y+", "goal": ["Wealth Creation", "Retirement"],
     "why": "Globally diversified (US stocks included), Warren Buffett philosophy",
     "amfi_search": ["parag parikh flexi cap", "direct", "growth"]},
    {"name": "HDFC Flexi Cap Fund", "category": "Flexi Cap", "risk": "Moderate-High",
     "ret_1y": 24.8, "ret_3y": 21.6, "ret_5y": 20.4, "aum": "₹52,000 Cr",
     "min_sip": 100, "stars": 5, "profiles": ["Moderate", "Aggressive"],
     "horizon": "5y+", "goal": ["Wealth Creation"],
     "why": "Strong all-weather fund, moves between large/mid/small dynamically",
     "amfi_search": ["hdfc flexi cap", "direct", "growth"]},
    # Mid Cap
    {"name": "Nippon India Mid Cap Fund", "category": "Mid Cap", "risk": "High",
     "ret_1y": 35.2, "ret_3y": 27.8, "ret_5y": 28.4, "aum": "₹29,000 Cr",
     "min_sip": 100, "stars": 5, "profiles": ["Aggressive"],
     "horizon": "7y+", "goal": ["Wealth Creation"],
     "why": "Consistently top-performing mid-cap, ideal for long-term wealth",
     "amfi_search": ["nippon india mid cap", "direct", "growth"]},
    {"name": "HDFC Mid Cap Opportunities", "category": "Mid Cap", "risk": "High",
     "ret_1y": 32.8, "ret_3y": 25.6, "ret_5y": 26.9, "aum": "₹62,000 Cr",
     "min_sip": 100, "stars": 5, "profiles": ["Aggressive"],
     "horizon": "7y+", "goal": ["Wealth Creation"],
     "why": "India's largest mid-cap fund, proven 15-year track record",
     "amfi_search": ["hdfc mid-cap opportunities", "direct", "growth"]},
    # Small Cap
    {"name": "SBI Small Cap Fund", "category": "Small Cap", "risk": "Very High",
     "ret_1y": 28.4, "ret_3y": 22.1, "ret_5y": 29.6, "aum": "₹24,000 Cr",
     "min_sip": 500, "stars": 5, "profiles": ["Aggressive"],
     "horizon": "10y+", "goal": ["Wealth Creation"],
     "why": "Best small-cap fund for consistent long-term wealth creation",
     "amfi_search": ["sbi small cap", "direct", "growth"]},
    # Index Funds
    {"name": "UTI Nifty 50 Index Fund", "category": "Index Fund", "risk": "Moderate",
     "ret_1y": 16.8, "ret_3y": 14.2, "ret_5y": 15.6, "aum": "₹17,000 Cr",
     "min_sip": 500, "stars": 4, "profiles": ["Conservative", "Moderate"],
     "horizon": "3y+", "goal": ["Wealth Creation", "Retirement"],
     "why": "Lowest cost (0.1% expense ratio), tracks Nifty 50, no fund manager risk",
     "amfi_search": ["uti nifty 50 index", "direct", "growth"]},
    {"name": "Motilal Oswal Nifty Next 50 Index", "category": "Index Fund", "risk": "Moderate-High",
     "ret_1y": 19.2, "ret_3y": 16.8, "ret_5y": 17.4, "aum": "₹5,000 Cr",
     "min_sip": 500, "stars": 4, "profiles": ["Moderate", "Aggressive"],
     "horizon": "5y+", "goal": ["Wealth Creation"],
     "why": "Next 50 Nifty companies — future blue chips at lower price",
     "amfi_search": ["motilal oswal nifty next 50", "direct", "growth"]},
    # ELSS Tax Saving
    {"name": "Mirae Asset Tax Saver Fund", "category": "ELSS (Tax Saving)", "risk": "Moderate-High",
     "ret_1y": 20.4, "ret_3y": 17.6, "ret_5y": 19.8, "aum": "₹23,000 Cr",
     "min_sip": 500, "stars": 5, "profiles": ["Moderate", "Aggressive"],
     "horizon": "3y+ lock-in", "goal": ["Tax Saving", "Wealth Creation"],
     "why": "Best ELSS fund. Saves up to ₹46,800 tax under Section 80C",
     "amfi_search": ["mirae asset tax saver", "direct", "growth"]},
    {"name": "Quant ELSS Tax Saver Fund", "category": "ELSS (Tax Saving)", "risk": "High",
     "ret_1y": 28.6, "ret_3y": 24.2, "ret_5y": 28.1, "aum": "₹9,000 Cr",
     "min_sip": 500, "stars": 5, "profiles": ["Aggressive"],
     "horizon": "3y+ lock-in", "goal": ["Tax Saving", "Wealth Creation"],
     "why": "Highest-return ELSS in last 5 years, quantitative investing approach",
     "amfi_search": ["quant elss", "direct", "growth"]},
    # Hybrid
    {"name": "HDFC Balanced Advantage Fund", "category": "Hybrid / BAF", "risk": "Moderate",
     "ret_1y": 18.2, "ret_3y": 15.8, "ret_5y": 16.4, "aum": "₹86,000 Cr",
     "min_sip": 100, "stars": 4, "profiles": ["Conservative", "Moderate"],
     "horizon": "3y+", "goal": ["Wealth Creation", "Retirement", "Monthly Income"],
     "why": "Auto-balances equity/debt ratio based on market valuation",
     "amfi_search": ["hdfc balanced advantage", "direct", "growth"]},
    {"name": "SBI Equity Hybrid Fund", "category": "Hybrid / BAF", "risk": "Moderate",
     "ret_1y": 17.6, "ret_3y": 14.9, "ret_5y": 15.8, "aum": "₹62,000 Cr",
     "min_sip": 1000, "stars": 4, "profiles": ["Conservative", "Moderate"],
     "horizon": "3y+", "goal": ["Retirement", "Monthly Income"],
     "why": "Stable 75:25 equity-debt mix, good for first-time investors",
     "amfi_search": ["sbi equity hybrid", "direct", "growth"]},
    # Debt
    {"name": "HDFC Short Term Debt Fund", "category": "Short Duration Debt", "risk": "Low",
     "ret_1y": 7.8, "ret_3y": 6.9, "ret_5y": 7.2, "aum": "₹12,000 Cr",
     "min_sip": 100, "stars": 4, "profiles": ["Conservative"],
     "horizon": "1-3y", "goal": ["Emergency Fund", "Short-term Savings"],
     "why": "More tax-efficient than FD for 3+ year holding, stable returns",
     "amfi_search": ["hdfc short term debt", "direct", "growth"]},
    {"name": "Nippon India Liquid Fund", "category": "Liquid Fund", "risk": "Very Low",
     "ret_1y": 7.2, "ret_3y": 6.4, "ret_5y": 6.1, "aum": "₹28,000 Cr",
     "min_sip": 100, "stars": 4, "profiles": ["Conservative"],
     "horizon": "< 1y", "goal": ["Emergency Fund", "Parking Money"],
     "why": "Better than savings account, instant redemption, very safe",
     "amfi_search": ["nippon india liquid", "direct", "growth"]},
    # International
    {"name": "Motilal Oswal Nasdaq 100 FOF", "category": "International", "risk": "High",
     "ret_1y": 24.6, "ret_3y": 12.4, "ret_5y": 22.8, "aum": "₹4,000 Cr",
     "min_sip": 500, "stars": 4, "profiles": ["Aggressive"],
     "horizon": "5y+", "goal": ["Wealth Creation"],
     "why": "Invest in Apple, Microsoft, Google via Indian rupees. USD hedge benefit",
     "amfi_search": ["motilal oswal nasdaq 100", "direct", "growth"]},
]

# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def get_quote(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="2d", interval="1d")
        if hist.empty:
            return {}
        ltp   = float(info.last_price) if hasattr(info, "last_price") else float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else ltp
        chg   = ltp - prev
        pct   = (chg / prev) * 100 if prev else 0
        high  = float(hist["High"].iloc[-1])
        low   = float(hist["Low"].iloc[-1])
        open_ = float(hist["Open"].iloc[-1])
        return {"ltp": ltp, "open": open_, "high": high, "low": low,
                "prev": prev, "chg": chg, "pct": pct}
    except Exception:
        return {}


@st.cache_data(ttl=60)
def get_candles(ticker: str, period: str = "5d", interval: str = "15m") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        df = df.rename(columns={"datetime": "timestamp", "date": "timestamp"})
        if "timestamp" not in df.columns and df.columns[0] != "timestamp":
            df = df.rename(columns={df.columns[0]: "timestamp"})
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=21600)
def fetch_amfi_navs() -> dict:
    """
    Fetch all mutual fund NAVs from AMFI (official, free, updates daily).
    Returns dict keyed by lowercase scheme name → {nav, date, code}.
    """
    try:
        url = "https://www.amfiindia.com/spages/NAVAll.txt"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        nav_dict = {}
        for line in r.text.splitlines():
            parts = line.strip().split(";")
            if len(parts) < 6:
                continue
            try:
                nav = float(parts[4].strip())
                nav_dict[parts[3].strip().lower()] = {
                    "nav":  nav,
                    "date": parts[5].strip() if len(parts) > 5 else "",
                    "code": parts[0].strip(),
                }
            except ValueError:
                continue
        return nav_dict
    except Exception:
        return {}


def lookup_nav(nav_dict: dict, search_terms: list) -> dict:
    """Find the best matching Direct Growth fund by search keywords."""
    best, best_score = None, 0
    for name, data in nav_dict.items():
        if "direct" not in name or ("growth" not in name and "gr" not in name):
            continue
        score = sum(1 for t in search_terms if t.lower() in name)
        if score > best_score:
            best_score, best = score, data
    return best if best_score >= 2 else None


@st.cache_data(ttl=300)
def fetch_news_headlines() -> list:
    """Fetch latest market headlines from free RSS feeds."""
    import xml.etree.ElementTree as ET
    feeds = [
        ("Economic Times", "https://economictimes.indiatimes.com/markets/rss.cms"),
        ("Mint",           "https://www.livemint.com/rss/markets"),
        ("Reuters",        "https://feeds.reuters.com/reuters/businessNews"),
    ]
    BULL_WORDS = {"rally","surge","gain","rise","rises","rose","positive","growth",
                  "strong","up","bull","buying","recovery","boost","record","high"}
    BEAR_WORDS = {"fall","drop","decline","negative","recession","weak","down","bear",
                  "sell","crash","crisis","war","sanction","cut","fear","risk","loss"}
    headlines = []
    for source, url in feeds:
        try:
            r = requests.get(url, timeout=6,
                             headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:6]:
                title = (item.findtext("title") or "").strip()
                date  = (item.findtext("pubDate") or "")[:22]
                if not title:
                    continue
                words = set(title.lower().split())
                bull  = len(words & BULL_WORDS)
                bear  = len(words & BEAR_WORDS)
                sentiment = "bullish" if bull > bear else ("bearish" if bear > bull else "neutral")
                headlines.append({"source": source, "title": title,
                                   "date": date, "sentiment": sentiment})
        except Exception:
            continue
    return headlines[:18]


def compute_global_sentiment(global_quotes: dict) -> dict:
    """
    Composite global sentiment score (-10 to +10) for India markets.
    Uses already-fetched global index and macro quotes.
    """
    score = 0
    factors = []

    def chk(name, pct, bull_thr=0.3, bear_thr=-0.3, weight=1, invert=False):
        nonlocal score
        if pct is None:
            return
        effective = -pct if invert else pct
        if effective > bull_thr:
            score += weight
            factors.append((name, f"+{pct:+.2f}%", "bull"))
        elif effective < bear_thr:
            score -= weight
            factors.append((name, f"{pct:+.2f}%", "bear"))
        else:
            factors.append((name, f"{pct:+.2f}%", "neutral"))

    sp_pct    = global_quotes.get("S&P 500",      {}).get("pct")
    nas_pct   = global_quotes.get("Nasdaq",        {}).get("pct")
    nik_pct   = global_quotes.get("Nikkei 225",    {}).get("pct")
    crude_pct = global_quotes.get("Crude Oil",     {}).get("pct")
    gold_pct  = global_quotes.get("Gold",          {}).get("pct")
    dxy_pct   = global_quotes.get("Dollar Index",  {}).get("pct")
    usdinr_pct= global_quotes.get("USD/INR",       {}).get("pct")
    tnx_ltp   = global_quotes.get("US 10Y Yield",  {}).get("ltp")

    chk("S&P 500",       sp_pct,    weight=2)
    chk("Nasdaq",        nas_pct,   weight=1)
    chk("Nikkei 225",    nik_pct,   weight=1)
    chk("Crude Oil",     crude_pct, bull_thr=1.5, bear_thr=-1.0, weight=1, invert=True)
    chk("Dollar Index",  dxy_pct,   weight=1, invert=True)
    chk("USD/INR",       usdinr_pct,weight=1, invert=True)

    if gold_pct is not None:
        if gold_pct > 0.8:
            score -= 1; factors.append(("Gold", f"+{gold_pct:.2f}% (risk-off)", "bear"))
        else:
            factors.append(("Gold", f"{gold_pct:+.2f}%", "neutral"))

    if tnx_ltp is not None:
        if tnx_ltp > 4.5:
            score -= 1; factors.append(("US 10Y Yield", f"{tnx_ltp:.2f}% (too high)", "bear"))
        elif tnx_ltp < 4.0:
            score += 1; factors.append(("US 10Y Yield", f"{tnx_ltp:.2f}% (benign)", "bull"))
        else:
            factors.append(("US 10Y Yield", f"{tnx_ltp:.2f}%", "neutral"))

    score = max(-10, min(10, score))
    if score >= 4:     label, color = "Strong Global Tailwind 🌬️", "#26a69a"
    elif score >= 2:   label, color = "Mild Positive Cues 🟢",      "#26a69a"
    elif score >= -1:  label, color = "Mixed / Neutral 🟡",          "#f59e0b"
    elif score >= -3:  label, color = "Mild Headwinds 🟠",           "#f97316"
    else:              label, color = "Strong Headwinds ⛔",          "#ef5350"

    return {"score": score, "label": label, "color": color, "factors": factors}


@st.cache_data(ttl=300)
def screen_nifty50() -> pd.DataFrame:
    """Score all Nifty 50 stocks using RSI, EMA trend, MACD, volume, 52W position."""
    tickers = list(NIFTY50_STOCKS.values())
    try:
        raw = yf.download(
            " ".join(tickers), period="6mo", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker",
        )
    except Exception:
        return pd.DataFrame()

    results = []
    for name, ticker in NIFTY50_STOCKS.items():
        try:
            df = raw[ticker].dropna() if ticker in raw.columns.get_level_values(0) else pd.DataFrame()
            if df.empty or len(df) < 30:
                continue
            close  = df["Close"]
            ltp    = float(close.iloc[-1])
            prev   = float(close.iloc[-2])
            pct    = (ltp - prev) / prev * 100
            high52 = float(close.rolling(252, min_periods=30).max().iloc[-1])
            low52  = float(close.rolling(252, min_periods=30).min().iloc[-1])
            ema20  = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            ema50  = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
            # RSI
            delta = close.diff()
            gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
            loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
            rsi   = float(100 - 100 / (1 + gain / loss.replace(0, np.nan)).iloc[-1])
            # MACD
            macd_line = close.ewm(span=12).mean() - close.ewm(span=26).mean()
            macd_sig  = macd_line.ewm(span=9).mean()
            macd_bull = float(macd_line.iloc[-1]) > float(macd_sig.iloc[-1])
            # Volume
            vol_ratio = 1.0
            if "Volume" in df.columns:
                vol = float(df["Volume"].iloc[-1])
                avg = float(df["Volume"].tail(20).mean())
                vol_ratio = vol / avg if avg > 0 else 1.0
            # Score (-10 to +10)
            score = 0
            reasons = []
            if ltp > ema20 > ema50 > ema200:
                score += 4; reasons.append("Strong uptrend (EMA 20>50>200)")
            elif ltp > ema20 > ema50:
                score += 2; reasons.append("Uptrend (EMA 20>50)")
            elif ltp > ema20:
                score += 1; reasons.append("Above EMA20")
            elif ltp < ema20 < ema50 < ema200:
                score -= 4; reasons.append("Strong downtrend")
            elif ltp < ema20 < ema50:
                score -= 2; reasons.append("Downtrend (EMA 20<50)")
            else:
                score -= 1; reasons.append("Below EMA20")
            if 50 < rsi < 65:
                score += 2; reasons.append(f"RSI bullish zone ({rsi:.0f})")
            elif rsi >= 65:
                score += 1; reasons.append(f"RSI strong ({rsi:.0f})")
            elif 35 < rsi <= 50:
                score -= 1; reasons.append(f"RSI weak ({rsi:.0f})")
            elif rsi <= 35:
                score += 1; reasons.append(f"RSI oversold — reversal watch ({rsi:.0f})")
            if macd_bull:
                score += 2; reasons.append("MACD bullish")
            else:
                score -= 2; reasons.append("MACD bearish")
            if vol_ratio > 1.5 and pct > 0:
                score += 1; reasons.append(f"Volume surge ({vol_ratio:.1f}x)")
            elif vol_ratio > 1.5 and pct < 0:
                score -= 1; reasons.append(f"Volume on down move ({vol_ratio:.1f}x)")
            from52h = (ltp - high52) / high52 * 100
            from52l = (ltp - low52)  / low52  * 100
            if from52h > -5:
                score += 1; reasons.append("Near 52-week high — momentum")
            elif from52l < 15:
                score -= 1; reasons.append("Near 52-week low — weak")
            results.append({
                "Stock":      name,
                "Sector":     STOCK_SECTORS.get(ticker, "Other"),
                "LTP":        round(ltp, 2),
                "Chg%":       round(pct, 2),
                "RSI":        round(rsi, 1),
                "Vol Ratio":  round(vol_ratio, 1),
                "52W High":   round(high52, 2),
                "52W Low":    round(low52, 2),
                "From 52H%":  round(from52h, 1),
                "Score":      score,
                "Reasons":    " | ".join(reasons),
                "Signal":     "BUY" if score >= 4 else ("WATCH" if score >= 2 else ("AVOID" if score <= -2 else "NEUTRAL")),
                "_ticker":    ticker,
            })
        except Exception:
            continue
    return pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 20:
        return df
    c = df["close"]
    df["ema9"]  = c.ewm(span=9,  adjust=False).mean()
    df["ema21"] = c.ewm(span=21, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    # MACD
    df["macd"]   = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["macd_s"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_h"] = df["macd"] - df["macd_s"]
    # VWAP
    if "volume" in df.columns:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    # Bollinger
    df["bb_mid"]   = c.rolling(20).mean()
    df["bb_upper"] = df["bb_mid"] + 2 * c.rolling(20).std()
    df["bb_lower"] = df["bb_mid"] - 2 * c.rolling(20).std()
    # ATR (14-period) for volatility regime
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - c.shift()).abs(),
        (df["low"]  - c.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(com=13, min_periods=14).mean()
    df["atr_pct"] = df["atr"] / c * 100   # ATR as % of price
    # Stochastic RSI
    if "rsi" in df.columns:
        rsi_min = df["rsi"].rolling(14).min()
        rsi_max = df["rsi"].rolling(14).max()
        df["stoch_rsi"] = (df["rsi"] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    # OBV (On Balance Volume)
    if "volume" in df.columns:
        obv = (np.sign(c.diff()) * df["volume"]).fillna(0).cumsum()
        df["obv"] = obv
        df["obv_ema"] = obv.ewm(span=21, adjust=False).mean()
    # Supertrend (period=10, multiplier=3)
    df = add_supertrend(df, period=10, multiplier=3.0)
    return df


def add_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    try:
        hl2 = (df["high"] + df["low"]) / 2
        tr  = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"]  - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(com=period - 1, min_periods=period).mean()
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr
        st    = pd.Series(np.nan, index=df.index)
        st_dir= pd.Series(1,     index=df.index)
        for i in range(1, len(df)):
            prev_st  = st.iloc[i-1]  if not np.isnan(st.iloc[i-1])  else lower.iloc[i]
            prev_dir = st_dir.iloc[i-1]
            prev_cls = df["close"].iloc[i-1]
            upper.iloc[i] = min(upper.iloc[i], upper.iloc[i-1]) if prev_cls > upper.iloc[i-1] else upper.iloc[i]
            lower.iloc[i] = max(lower.iloc[i], lower.iloc[i-1]) if prev_cls < lower.iloc[i-1] else lower.iloc[i]
            if prev_dir == -1:
                st_dir.iloc[i] = 1  if df["close"].iloc[i] > upper.iloc[i] else -1
            else:
                st_dir.iloc[i] = -1 if df["close"].iloc[i] < lower.iloc[i] else  1
            st.iloc[i] = lower.iloc[i] if st_dir.iloc[i] == 1 else upper.iloc[i]
        df["supertrend"]     = st
        df["supertrend_dir"] = st_dir
    except Exception:
        pass
    return df


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    o = now.replace(hour=9, minute=15, second=0, microsecond=0)
    c = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return o <= now <= c


def next_expiry_info() -> dict:
    today = datetime.now(IST).date()
    n_days = (3 - today.weekday()) % 7 or 7   # Thursday = Nifty
    b_days = (2 - today.weekday()) % 7 or 7   # Wednesday = BankNifty
    n_date = today + timedelta(days=n_days)
    b_date = today + timedelta(days=b_days)
    return {
        "nifty":     {"date": n_date.strftime("%d %b"), "days": n_days},
        "banknifty": {"date": b_date.strftime("%d %b"), "days": b_days},
    }


@st.cache_data(ttl=60)
def get_orb(ticker: str) -> dict:
    """Opening Range = first 15 minutes (9:15–9:30) high and low."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if df.empty:
            return {}
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        orb = df.head(15)
        if orb.empty:
            return {}
        return {
            "high":  float(orb["high"].max()),
            "low":   float(orb["low"].min()),
            "range": float(orb["high"].max() - orb["low"].min()),
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_pivots(ticker: str) -> dict:
    """Classic pivot points from previous trading day's OHLC."""
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 2:
            return {}
        prev = df.iloc[-2]
        h = float(prev["High"])
        l = float(prev["Low"])
        c = float(prev["Close"])
        p = (h + l + c) / 3
        return {
            "P":  round(p),
            "R1": round(2 * p - l),
            "R2": round(p + h - l),
            "R3": round(h + 2 * (p - l)),
            "S1": round(2 * p - h),
            "S2": round(p - (h - l)),
            "S3": round(l - 2 * (h - p)),
        }
    except Exception:
        return {}


def trend_label(pct: float) -> tuple:
    if pct > 0.3:   return "Bullish ▲", "bull"
    if pct < -0.3:  return "Bearish ▼", "bear"
    return "Sideways ↔", "neutral"


def signal_summary(df: pd.DataFrame, ltp: float) -> dict:
    if df.empty or len(df) < 20:
        return {}
    last = df.iloc[-1]
    signals = {}
    rsi = last.get("rsi", np.nan)
    if pd.notna(rsi):
        if rsi < 30:   signals["RSI"] = (f"{rsi:.0f} — Oversold", "green")
        elif rsi > 70: signals["RSI"] = (f"{rsi:.0f} — Overbought", "red")
        else:          signals["RSI"] = (f"{rsi:.0f} — Neutral", "yellow")
    macd = last.get("macd", np.nan)
    ms   = last.get("macd_s", np.nan)
    if pd.notna(macd) and pd.notna(ms):
        signals["MACD"] = ("Bullish cross", "green") if macd > ms else ("Bearish cross", "red")
    vwap = last.get("vwap", np.nan)
    if pd.notna(vwap):
        signals["VWAP"] = (f"Price {'above' if ltp > vwap else 'below'} VWAP ({vwap:,.0f})",
                           "green" if ltp > vwap else "red")
    e9  = last.get("ema9",  np.nan)
    e21 = last.get("ema21", np.nan)
    if pd.notna(e9) and pd.notna(e21):
        signals["EMA"] = ("EMA9 > EMA21 — Uptrend", "green") if e9 > e21 else ("EMA9 < EMA21 — Downtrend", "red")
    return signals


def option_bias(df: pd.DataFrame, ltp: float, vix: float) -> dict:
    if df.empty:
        return {"bias": "Neutral", "confidence": "Low", "reason": "Insufficient data"}
    last = df.iloc[-1]
    score = 0
    reasons = []
    rsi = last.get("rsi", 50)
    if pd.notna(rsi):
        if rsi > 55: score += 1; reasons.append("RSI bullish")
        elif rsi < 45: score -= 1; reasons.append("RSI bearish")
    macd = last.get("macd", 0)
    ms   = last.get("macd_s", 0)
    if pd.notna(macd) and pd.notna(ms):
        if macd > ms: score += 1; reasons.append("MACD bullish")
        else: score -= 1; reasons.append("MACD bearish")
    vwap = last.get("vwap", ltp)
    if pd.notna(vwap):
        if ltp > vwap: score += 1; reasons.append("Above VWAP")
        else: score -= 1; reasons.append("Below VWAP")
    e9  = last.get("ema9",  ltp)
    e21 = last.get("ema21", ltp)
    if pd.notna(e9) and pd.notna(e21):
        if e9 > e21: score += 1; reasons.append("EMA bullish")
        else: score -= 1; reasons.append("EMA bearish")
    high_vix = vix > 18 if vix else False
    conf = "High" if abs(score) >= 3 else ("Medium" if abs(score) == 2 else "Low")
    if score >= 2:
        bias = "CE (Call Buying)" if not high_vix else "CE with caution (High VIX)"
    elif score <= -2:
        bias = "PE (Put Buying)" if not high_vix else "PE with caution (High VIX)"
    else:
        bias = "Neutral — avoid directional trade"
    return {"bias": bias, "confidence": conf, "score": score, "reasons": reasons}


def nearest_strike(price: float, step: int) -> int:
    return round(int(round(price / step) * step))


def intraday_option_setup(df: pd.DataFrame, ltp: float, vix: float,
                           name: str, step: int = 50) -> dict:
    """
    Generate CALL and PUT intraday trade setups from technical indicators.
    Returns dict with 'call', 'put', 'market_condition', 'no_trade'.
    """
    if df.empty or len(df) < 20 or ltp == 0:
        return {"no_trade": True, "reason": "Insufficient data"}

    last    = df.iloc[-1]
    prev    = df.iloc[-2] if len(df) > 2 else last

    rsi     = float(last.get("rsi",   50) or 50)
    macd    = float(last.get("macd",   0) or 0)
    macd_s  = float(last.get("macd_s", 0) or 0)
    ema9    = float(last.get("ema9",  ltp) or ltp)
    ema21   = float(last.get("ema21", ltp) or ltp)
    ema50   = float(last.get("ema50", ltp) or ltp)
    vwap    = float(last.get("vwap",  ltp) or ltp)
    bb_up   = float(last.get("bb_upper", ltp * 1.01) or ltp * 1.01)
    bb_lo   = float(last.get("bb_lower", ltp * 0.99) or ltp * 0.99)
    vol     = float(last.get("volume", 0) or 0)
    avg_vol = float(df["volume"].tail(20).mean() or 1)

    # ── Score each factor ────────────────────────────────────────────────────
    bull_score = 0
    bear_score = 0
    confirmations = []

    # EMA stack
    if ema9 > ema21 > ema50:
        bull_score += 2; confirmations.append("EMA stack bullish")
    elif ema9 < ema21 < ema50:
        bear_score += 2; confirmations.append("EMA stack bearish")
    elif ema9 > ema21:
        bull_score += 1; confirmations.append("EMA9 > EMA21")
    else:
        bear_score += 1; confirmations.append("EMA9 < EMA21")

    # VWAP
    if ltp > vwap * 1.001:
        bull_score += 2; confirmations.append("Price above VWAP")
    elif ltp < vwap * 0.999:
        bear_score += 2; confirmations.append("Price below VWAP")

    # RSI
    if 55 < rsi < 75:
        bull_score += 1; confirmations.append(f"RSI bullish ({rsi:.0f})")
    elif 25 < rsi < 45:
        bear_score += 1; confirmations.append(f"RSI bearish ({rsi:.0f})")
    elif rsi >= 75:
        bear_score += 1; confirmations.append(f"RSI overbought ({rsi:.0f}) — caution")
    elif rsi <= 25:
        bull_score += 1; confirmations.append(f"RSI oversold ({rsi:.0f}) — reversal watch")

    # MACD
    if macd > macd_s and macd > 0:
        bull_score += 2; confirmations.append("MACD bullish crossover above zero")
    elif macd > macd_s and macd < 0:
        bull_score += 1; confirmations.append("MACD bullish crossover (below zero)")
    elif macd < macd_s and macd < 0:
        bear_score += 2; confirmations.append("MACD bearish crossover below zero")
    elif macd < macd_s and macd > 0:
        bear_score += 1; confirmations.append("MACD bearish crossover (above zero)")

    # Volume
    if vol > avg_vol * 1.5:
        if ltp > float(prev.get("close", ltp) or ltp):
            bull_score += 1; confirmations.append("Volume breakout bullish")
        else:
            bear_score += 1; confirmations.append("Volume breakout bearish")

    # Bollinger
    if ltp > bb_up * 0.999:
        bull_score += 1; confirmations.append("Price at BB upper — strong breakout")
    elif ltp < bb_lo * 1.001:
        bear_score += 1; confirmations.append("Price at BB lower — strong breakdown")

    # Stochastic RSI
    stoch_rsi = float(last.get("stoch_rsi", 0.5) or 0.5)
    if stoch_rsi > 0.8:
        bull_score += 1; confirmations.append(f"Stoch RSI overbought ({stoch_rsi:.2f}) — momentum strong")
    elif stoch_rsi < 0.2:
        bear_score += 1; confirmations.append(f"Stoch RSI oversold ({stoch_rsi:.2f}) — bearish momentum")

    # OBV trend (smart money flow)
    obv     = float(last.get("obv",     0) or 0)
    obv_ema = float(last.get("obv_ema", 0) or 0)
    if obv > obv_ema:
        bull_score += 1; confirmations.append("OBV above EMA — smart money accumulating")
    elif obv < obv_ema:
        bear_score += 1; confirmations.append("OBV below EMA — smart money distributing")

    # Supertrend
    st_dir = int(last.get("supertrend_dir", 0) or 0)
    if st_dir == 1:
        bull_score += 1; confirmations.append("Supertrend bullish")
    elif st_dir == -1:
        bear_score += 1; confirmations.append("Supertrend bearish")

    # ATR volatility regime
    atr_pct = float(last.get("atr_pct", 0) or 0)
    if atr_pct > 0.8:
        confirmations.append(f"High volatility (ATR {atr_pct:.2f}%) — widen SL, reduce size")

    total   = bull_score + bear_score
    net     = bull_score - bear_score
    high_vix = vix > 18 if vix else False

    # ── No-trade conditions ──────────────────────────────────────────────────
    if vix > 22:
        return {"no_trade": True,
                "reason": f"India VIX too high ({vix:.1f}) — avoid all directional trades"}
    if abs(net) < 3:
        return {"no_trade": True,
                "reason": "Market is sideways — insufficient directional confirmation. Wait for a clear breakout."}

    # ── ATM strike calculation ───────────────────────────────────────────────
    atm      = nearest_strike(ltp, step)
    otm_call = atm + step
    otm_put  = atm - step

    # Approximate premium (simplified: ATM ~0.7–1.2% of underlying for weekly)
    base_prem = ltp * 0.008
    call_prem = round(base_prem * (1.0 if net > 0 else 0.7), 1)
    put_prem  = round(base_prem * (1.0 if net < 0 else 0.7), 1)
    call_prem = max(call_prem, 20)
    put_prem  = max(put_prem, 20)

    # ── Confidence ───────────────────────────────────────────────────────────
    def confidence(score):
        if score >= 6:   return "HIGH",   "conf-high", "🟢"
        if score >= 4:   return "MEDIUM", "conf-med",  "🟡"
        return               "LOW",    "conf-low",  "🔴"

    call_conf, call_cls, call_icon = confidence(bull_score)
    put_conf,  put_cls,  put_icon  = confidence(bear_score)

    # ── Signal status ─────────────────────────────────────────────────────────
    def signal_status(score, direction):
        if score >= 5:  return "BUY NOW",  "signal-buy"
        if score >= 3:  return "WATCH",    "signal-wait"
        return               "AVOID",    "signal-exit"

    call_status, call_status_cls = signal_status(bull_score, "call")
    put_status,  put_status_cls  = signal_status(bear_score, "put")

    # ── CALL setup ───────────────────────────────────────────────────────────
    call_entry  = call_prem
    call_sl     = round(call_entry * 0.70, 1)   # 30% SL
    call_tgt1   = round(call_entry * 1.50, 1)   # 50% profit
    call_tgt2   = round(call_entry * 2.20, 1)   # 120% profit
    call_rr     = round((call_tgt1 - call_entry) / (call_entry - call_sl), 2)
    call_exit_t = "Exit by 2:45 PM or at Target 1"

    # ── PUT setup ────────────────────────────────────────────────────────────
    put_entry   = put_prem
    put_sl      = round(put_entry * 0.70, 1)
    put_tgt1    = round(put_entry * 1.50, 1)
    put_tgt2    = round(put_entry * 2.20, 1)
    put_rr      = round((put_tgt1 - put_entry) / (put_entry - put_sl), 2)
    put_exit_t  = "Exit by 2:45 PM or at Target 1"

    market_cond = "Bullish" if net > 2 else ("Bearish" if net < -2 else "Neutral")

    return {
        "no_trade":      False,
        "market_cond":   market_cond,
        "net_score":     net,
        "confirmations": confirmations,
        "high_vix":      high_vix,
        "vix":           vix,
        "ltp":           ltp,
        "vwap":          vwap,
        "atm":           atm,
        "call": {
            "type":       "CALL (CE)",
            "strike":     f"{atm} CE" if net >= 0 else f"{otm_call} CE",
            "entry":      call_entry,
            "sl":         call_sl,
            "tgt1":       call_tgt1,
            "tgt2":       call_tgt2,
            "rr":         call_rr,
            "conf":       call_conf,
            "conf_cls":   call_cls,
            "conf_icon":  call_icon,
            "status":     call_status,
            "status_cls": call_status_cls,
            "exit_time":  call_exit_t,
            "score":      bull_score,
        },
        "put": {
            "type":       "PUT (PE)",
            "strike":     f"{atm} PE" if net <= 0 else f"{otm_put} PE",
            "entry":      put_entry,
            "sl":         put_sl,
            "tgt1":       put_tgt1,
            "tgt2":       put_tgt2,
            "rr":         put_rr,
            "conf":       put_conf,
            "conf_cls":   put_cls,
            "conf_icon":  put_icon,
            "status":     put_status,
            "status_cls": put_status_cls,
            "exit_time":  put_exit_t,
            "score":      bear_score,
        },
    }


def render_trade_card(setup: dict, side: str):
    t       = setup[side]
    is_call = side == "call"
    card_cls = "trade-card-call" if is_call else "trade-card-put"
    color    = "#26a69a" if is_call else "#ef5350"
    label    = "📈 CALL (CE)" if is_call else "📉 PUT (PE)"
    preferred = setup["net_score"] > 0 if is_call else setup["net_score"] < 0
    badge     = ' <span style="background:#f59e0b;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">★ PREFERRED</span>' if preferred else ""

    st.markdown(f"""
    <div class="{card_cls}">
      <div class="trade-header" style="color:{color}">{label}{badge}</div>
      <div class="trade-strike">Strike: <b>{t['strike']}</b> &nbsp;|&nbsp; ATM: {setup['atm']}</div>

      <div class="trade-row">
        <div><div class="trade-label">Entry Price</div>
             <div class="trade-value" style="color:{color}">₹{t['entry']}</div></div>
        <div><div class="trade-label">Stop-Loss</div>
             <div class="trade-value" style="color:#ef5350">₹{t['sl']}</div></div>
        <div><div class="trade-label">Target 1</div>
             <div class="trade-value" style="color:#26a69a">₹{t['tgt1']}</div></div>
        <div><div class="trade-label">Target 2</div>
             <div class="trade-value" style="color:#26a69a">₹{t['tgt2']}</div></div>
        <div><div class="trade-label">Risk:Reward</div>
             <div class="trade-value">1:{t['rr']}</div></div>
      </div>

      <div style="margin-top:12px">
        <span class="{t['status_cls']}">{t['status']}</span>
        <span class="pill {'pill-green' if t['conf']=='HIGH' else ('pill-yellow' if t['conf']=='MEDIUM' else 'pill-red')}">
          {t['conf_icon']} Confidence: {t['conf']} ({t['score']}/8)
        </span>
      </div>
      <div style="margin-top:8px;font-size:12px;color:#9ca3af">
        🕐 Exit: {t['exit_time']}
      </div>
    </div>
    """, unsafe_allow_html=True)


def candlestick_fig(df: pd.DataFrame, title: str,
                    pivots: dict = None, orb: dict = None) -> go.Figure:
    BG = "#0e1117"; GRID = "#1e2130"
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03,
                        subplot_titles=[title, "Volume", "RSI"])
    fig.add_trace(go.Candlestick(
        x=df["timestamp"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        name="Price", showlegend=False,
    ), row=1, col=1)
    for col, color, name in [("ema9","#f59e0b","EMA9"), ("ema21","#3b82f6","EMA21"), ("vwap","#a855f7","VWAP")]:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df[col],
                line=dict(color=color, width=1.2), name=name), row=1, col=1)
    # Supertrend
    if "supertrend" in df.columns and "supertrend_dir" in df.columns:
        bull_st = df[df["supertrend_dir"] == 1]
        bear_st = df[df["supertrend_dir"] == -1]
        if not bull_st.empty:
            fig.add_trace(go.Scatter(x=bull_st["timestamp"], y=bull_st["supertrend"],
                mode="markers", marker=dict(color="#26a69a", size=4, symbol="circle"),
                name="ST Bull"), row=1, col=1)
        if not bear_st.empty:
            fig.add_trace(go.Scatter(x=bear_st["timestamp"], y=bear_st["supertrend"],
                mode="markers", marker=dict(color="#ef5350", size=4, symbol="circle"),
                name="ST Bear"), row=1, col=1)
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bb_upper"],
            line=dict(color="rgba(99,102,241,0.4)", width=1, dash="dot"),
            name="BB", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bb_lower"],
            line=dict(color="rgba(99,102,241,0.4)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(99,102,241,0.05)",
            name="BB Lower", showlegend=False), row=1, col=1)
    # Pivot points
    if pivots:
        pivot_colors = {"P": "#f59e0b", "R1": "#ef5350", "R2": "#ef5350", "R3": "#ef5350",
                        "S1": "#26a69a", "S2": "#26a69a", "S3": "#26a69a"}
        for level, val in pivots.items():
            fig.add_hline(y=val,
                line=dict(color=pivot_colors.get(level, "#9ca3af"), width=1, dash="dot"),
                annotation_text=f" {level}:{val:,.0f}",
                annotation_font=dict(size=9, color=pivot_colors.get(level, "#9ca3af")),
                annotation_position="right", row=1, col=1)
    # Opening Range lines
    if orb and orb.get("high") and orb.get("low"):
        fig.add_hline(y=orb["high"],
            line=dict(color="#fbbf24", width=1.5, dash="dash"),
            annotation_text=f" ORB H:{orb['high']:,.0f}",
            annotation_font=dict(size=9, color="#fbbf24"),
            annotation_position="right", row=1, col=1)
        fig.add_hline(y=orb["low"],
            line=dict(color="#fbbf24", width=1.5, dash="dash"),
            annotation_text=f" ORB L:{orb['low']:,.0f}",
            annotation_font=dict(size=9, color="#fbbf24"),
            annotation_position="right", row=1, col=1)
    if "volume" in df.columns:
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(x=df["timestamp"], y=df["volume"],
            marker_color=colors, showlegend=False), row=2, col=1)
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rsi"],
            line=dict(color="#f59e0b", width=1.5), name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="rgba(239,83,80,0.5)", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="rgba(38,166,154,0.5)", row=3, col=1)
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color="#e0e0e0", size=11),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        margin=dict(l=10, r=10, t=40, b=10), height=580,
        xaxis_rangeslider_visible=False,
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor=GRID, row=i, col=1)
        fig.update_yaxes(gridcolor=GRID, row=i, col=1)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
now_ist = datetime.now(IST)
market_open = is_market_open()

# Header
col_h1, col_h2, col_h3, col_h4 = st.columns([3, 1, 1, 1])
with col_h1:
    st.markdown("## 📈 India Market Dashboard")
    st.caption(f"Last updated: {now_ist.strftime('%d %b %Y  %H:%M:%S IST')}  |  Data: Yahoo Finance (15-min delay)")
with col_h2:
    status_color = "#26a69a" if market_open else "#ef5350"
    st.markdown(f'<div style="margin-top:20px"><span style="color:{status_color}; font-size:16px; font-weight:700;">● Market {"OPEN" if market_open else "CLOSED"}</span></div>', unsafe_allow_html=True)
with col_h3:
    exp = next_expiry_info()
    n_exp = exp["nifty"]
    b_exp = exp["banknifty"]
    n_warn = "🔴" if n_exp["days"] <= 1 else ("🟡" if n_exp["days"] <= 2 else "🟢")
    b_warn = "🔴" if b_exp["days"] <= 1 else ("🟡" if b_exp["days"] <= 2 else "🟢")
    st.markdown(f"""
    <div style="margin-top:14px;font-size:11px;color:#9ca3af;line-height:1.8">
    {n_warn} <b>Nifty expiry:</b> {n_exp['date']} ({n_exp['days']}d)<br>
    {b_warn} <b>BNF expiry:</b> {b_exp['date']} ({b_exp['days']}d)
    </div>""", unsafe_allow_html=True)
with col_h4:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
# Auto-refresh meta tag during market hours (browser-level, non-blocking)
if market_open:
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)

st.divider()

# ── Fetch all Indian index quotes ─────────────────────────────────────────────
quotes = {name: get_quote(ticker) for name, ticker in TICKERS.items()}

# ── Row 1: Index cards ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Market Overview</div>', unsafe_allow_html=True)
idx_cols = st.columns(len(TICKERS))
for col, (name, q) in zip(idx_cols, quotes.items()):
    with col:
        if q:
            arrow = "▲" if q["chg"] >= 0 else "▼"
            cls   = "bull" if q["chg"] >= 0 else "bear"
            st.markdown(f"""
            <div style="background:#1a1d2e;border-radius:8px;padding:8px 12px;
                        border-left:3px solid {'#26a69a' if q['chg']>=0 else '#ef5350'};margin-bottom:6px">
              <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">{name}</div>
              <div style="font-size:17px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
              <div style="font-size:11px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
              <div style="font-size:10px;color:#6b7280">H:{q['high']:,.0f} L:{q['low']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.metric(name, "Loading…")

st.divider()

# ── Charts + Signals ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "🌅 Morning Checklist",
    "⚡ Intraday Signals",
    "🕯️ Nifty 50",
    "🏦 Bank Nifty",
    "🌍 Global Cues",
    "📋 Trade Plan",
    "🔔 Price Alerts",
    "📓 Trade Journal",
    "📊 Stock Picks",
    "💰 Mutual Funds",
])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 0 — Morning Checklist
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## 🌅 Morning Market Checklist")
    st.caption("Run this every morning before 9:15 AM to prepare your trading plan for the day.")

    nq_m   = quotes.get("Nifty 50",   {})
    bnq_m  = quotes.get("Bank Nifty", {})
    vix_m  = quotes.get("India VIX",  {}).get("ltp", 0)
    sp_m   = {name: get_quote(ticker) for name, ticker in {"S&P 500":"^GSPC","Crude Oil":"CL=F","USD/INR":"USDINR=X"}.items()}

    def check_item(label, status, value, ok_msg, warn_msg, bad_msg):
        if status == "ok":
            cls, icon = "checklist-item-ok",   "✅"
            msg = ok_msg
        elif status == "warn":
            cls, icon = "checklist-item-warn",  "⚠️"
            msg = warn_msg
        else:
            cls, icon = "checklist-item-bad",   "❌"
            msg = bad_msg
        st.markdown(f'<div class="{cls}">{icon} <b>{label}:</b> {value} — {msg}</div>',
                    unsafe_allow_html=True)

    st.markdown("### 1. Volatility Check")
    if vix_m:
        if vix_m < 14:
            check_item("India VIX", "ok",   f"{vix_m:.2f}", "Low volatility — good for range trades", "", "")
        elif vix_m < 18:
            check_item("India VIX", "warn", f"{vix_m:.2f}", "", "Moderate — use normal position size", "")
        else:
            check_item("India VIX", "bad",  f"{vix_m:.2f}", "", "", "High VIX — reduce size by 50%, avoid naked options")

    st.markdown("### 2. Gap Analysis")
    nifty_pct = nq_m.get("pct", 0)
    if abs(nifty_pct) < 0.3:
        check_item("Nifty Gap", "ok",   f"{nifty_pct:+.2f}%", "Flat open — wait for direction after 9:30 AM", "", "")
    elif nifty_pct > 0.3:
        check_item("Nifty Gap", "warn", f"{nifty_pct:+.2f}%", "", "Gap up — watch for gap fill or continuation", "")
    else:
        check_item("Nifty Gap", "warn", f"{nifty_pct:+.2f}%", "", "Gap down — watch for bounce or further selling", "")

    st.markdown("### 3. Global Cues")
    sp_pct = sp_m.get("S&P 500", {}).get("pct", 0)
    if sp_pct > 0.3:
        check_item("S&P 500", "ok",   f"{sp_pct:+.2f}%", "US positive — supports bullish bias", "", "")
    elif sp_pct < -0.3:
        check_item("S&P 500", "bad",  f"{sp_pct:+.2f}%", "", "", "US negative — caution on longs")
    else:
        check_item("S&P 500", "warn", f"{sp_pct:+.2f}%", "", "Flat US markets — neutral global cue", "")

    crude_pct = sp_m.get("Crude Oil", {}).get("pct", 0)
    if crude_pct > 1.5:
        check_item("Crude Oil", "bad",  f"{crude_pct:+.2f}%", "", "", "Crude spike — negative for India, watch auto/paint stocks")
    elif crude_pct < -1.0:
        check_item("Crude Oil", "ok",   f"{crude_pct:+.2f}%", "Crude down — positive for India economy", "", "")
    else:
        check_item("Crude Oil", "warn", f"{crude_pct:+.2f}%", "", "Crude stable — neutral", "")

    usdinr_ltp = sp_m.get("USD/INR", {}).get("ltp", 84)
    if usdinr_ltp > 85:
        check_item("USD/INR", "bad",  f"₹{usdinr_ltp:.2f}", "", "", "Rupee weak — FII selling pressure likely")
    elif usdinr_ltp < 83.5:
        check_item("USD/INR", "ok",   f"₹{usdinr_ltp:.2f}", "Rupee strong — FII positive", "", "")
    else:
        check_item("USD/INR", "warn", f"₹{usdinr_ltp:.2f}", "", "Rupee stable — neutral", "")

    st.markdown("### 4. Trend Direction")
    nifty_df_m = get_candles("^NSEI", period="5d", interval="15m")
    nifty_df_m = add_indicators(nifty_df_m)
    if not nifty_df_m.empty:
        last_m = nifty_df_m.iloc[-1]
        ema9_m  = last_m.get("ema9",  0)
        ema21_m = last_m.get("ema21", 0)
        vwap_m  = last_m.get("vwap",  0)
        ltp_m   = nq_m.get("ltp", 0)
        st_dir_m = last_m.get("supertrend_dir", 0)

        if ema9_m > ema21_m:
            check_item("EMA Trend", "ok",   "EMA9 > EMA21", "Bullish trend — prefer CE", "", "")
        else:
            check_item("EMA Trend", "bad",  "EMA9 < EMA21", "", "", "Bearish trend — prefer PE")

        if ltp_m and vwap_m:
            if ltp_m > vwap_m:
                check_item("VWAP", "ok",  f"Price {ltp_m:,.0f} > VWAP {vwap_m:,.0f}", "Above VWAP — bullish", "", "")
            else:
                check_item("VWAP", "bad", f"Price {ltp_m:,.0f} < VWAP {vwap_m:,.0f}", "", "", "Below VWAP — bearish")

        if st_dir_m == 1:
            check_item("Supertrend", "ok",  "Bullish",  "ST green — uptrend confirmed", "", "")
        elif st_dir_m == -1:
            check_item("Supertrend", "bad", "Bearish", "", "", "ST red — downtrend confirmed")

    st.markdown("### 5. Global Intelligence Score")
    g_quotes_m = {name: get_quote(ticker) for name, ticker in GLOBAL.items()}
    gs_m = compute_global_sentiment(g_quotes_m)
    st.markdown(f"""
    <div class="metric-card" style="border-left-color:{gs_m['color']}">
      <div style="font-size:13px;color:#9ca3af">Global Sentiment for India Today</div>
      <div style="font-size:20px;font-weight:800;color:{gs_m['color']}">{gs_m['label']}</div>
      <div style="font-size:12px;color:#9ca3af;margin-top:4px">Score: {gs_m['score']:+d}/10 &nbsp;|&nbsp;
        {'  ·  '.join([f"{f[0]}: {f[1]}" for f in gs_m['factors'][:4]])}
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("### 6. Trading Decision")
    bull_checks = 0
    bear_checks = 0
    if vix_m and vix_m < 18: bull_checks += 1
    if nifty_pct > 0: bull_checks += 1
    if sp_pct > 0: bull_checks += 1
    if gs_m["score"] >= 2: bull_checks += 1
    elif gs_m["score"] <= -2: bear_checks += 1
    if not nifty_df_m.empty:
        last_m = nifty_df_m.iloc[-1]
        if last_m.get("ema9", 0) > last_m.get("ema21", 0): bull_checks += 1
        if last_m.get("supertrend_dir", 0) == 1: bull_checks += 1
        if nq_m.get("ltp", 0) > last_m.get("vwap", 0): bull_checks += 1

    bear_checks = max(7 - bull_checks, bear_checks)
    if vix_m and vix_m > 20:
        st.markdown('<div class="no-trade-banner">⛔ NO TRADE DAY — VIX above 20. Sit on hands today.</div>',
                    unsafe_allow_html=True)
    elif gs_m["score"] <= -4:
        st.markdown('<div class="no-trade-banner">⛔ STRONG GLOBAL HEADWINDS — Avoid aggressive longs. Very defensive day.</div>',
                    unsafe_allow_html=True)
    elif bull_checks >= 4:
        st.markdown(f"""<div class="checklist-item-ok" style="font-size:16px;padding:16px">
        🟢 <b>BULLISH DAY</b> — {bull_checks}/7 factors bullish<br>
        <span style="font-size:13px;color:#9ca3af">
        Preferred: CE (Call) options | Wait for 9:30 AM | Buy dips near VWAP | Trail SL above supertrend
        </span></div>""", unsafe_allow_html=True)
    elif bear_checks >= 4:
        st.markdown(f"""<div class="checklist-item-bad" style="font-size:16px;padding:16px">
        🔴 <b>BEARISH DAY</b> — {bear_checks}/7 factors bearish<br>
        <span style="font-size:13px;color:#9ca3af">
        Preferred: PE (Put) options | Sell rallies near VWAP | Trail SL below supertrend
        </span></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="checklist-item-warn" style="font-size:16px;padding:16px">
        🟡 <b>NEUTRAL/SIDEWAYS DAY</b> — Mixed signals ({bull_checks} bull / {bear_checks} bear out of 7)<br>
        <span style="font-size:13px;color:#9ca3af">
        Avoid directional trades | Consider Iron Condor or wait for breakout after 10 AM
        </span></div>""", unsafe_allow_html=True)

    st.markdown("### ⏰ Intraday Time Guide")
    time_data = {
        "Time": ["9:15–9:30 AM", "9:30–10:00 AM", "10:00 AM–1:00 PM", "1:00–2:00 PM", "2:00–3:00 PM", "3:00–3:15 PM"],
        "Action": [
            "🚫 Do NOT trade — opening volatility",
            "👀 Observe — let range form, check VWAP side",
            "✅ Best time — high probability setups, trend confirmed",
            "⚠️ Lunch hours — low volume, avoid new entries",
            "✅ Good time — institutional activity picks up",
            "🚫 Exit all positions — do NOT hold into close",
        ]
    }
    st.dataframe(pd.DataFrame(time_data), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Intraday Signals
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## ⚡ Intraday Option Trade Signals")
    st.caption("Signals update on every Refresh. Data: Yahoo Finance (15-min delay). For live signals use Upstox/Angel API.")

    # Load data if not already loaded
    intra_nifty_df = get_candles("^NSEI",    period="5d", interval="15m")
    intra_bank_df  = get_candles("^NSEBANK", period="5d", interval="15m")
    intra_nifty_df = add_indicators(intra_nifty_df)
    intra_bank_df  = add_indicators(intra_bank_df)

    nq_i   = quotes.get("Nifty 50",    {})
    bnq_i  = quotes.get("Bank Nifty",  {})
    vix_i  = quotes.get("India VIX",   {}).get("ltp", 0)
    n_ltp  = nq_i.get("ltp",  0)
    bn_ltp = bnq_i.get("ltp", 0)

    # ── Market condition banner ───────────────────────────────────────────────
    ic1, ic2, ic3 = st.columns(3)
    with ic1:
        vix_color = "#ef5350" if vix_i > 18 else "#26a69a"
        st.markdown(f'<div style="background:#1a1d2e;border-radius:8px;padding:8px 14px;border-left:3px solid {vix_color}">'
                    f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase">India VIX</div>'
                    f'<div style="font-size:18px;font-weight:800;color:{vix_color}">{vix_i:.2f}</div>'
                    f'<div style="font-size:11px;color:#9ca3af">{"⚠️ High — reduce size" if vix_i > 18 else "✅ Normal range"}</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic2:
        n_color = "#26a69a" if nq_i.get("chg",0)>=0 else "#ef5350"
        st.markdown(f'<div style="background:#1a1d2e;border-radius:8px;padding:8px 14px;border-left:3px solid {n_color}">'
                    f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase">Nifty 50</div>'
                    f'<div style="font-size:18px;font-weight:800;color:{n_color}">{n_ltp:,.2f}</div>'
                    f'<div style="font-size:11px;color:#9ca3af">{nq_i.get("pct",0):+.2f}% today</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic3:
        b_color = "#26a69a" if bnq_i.get("chg",0)>=0 else "#ef5350"
        st.markdown(f'<div style="background:#1a1d2e;border-radius:8px;padding:8px 14px;border-left:3px solid {b_color}">'
                    f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase">Bank Nifty</div>'
                    f'<div style="font-size:18px;font-weight:800;color:{b_color}">{bn_ltp:,.2f}</div>'
                    f'<div style="font-size:11px;color:#9ca3af">{bnq_i.get("pct",0):+.2f}% today</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Opening Range Breakout ────────────────────────────────────────────────
    st.markdown("### 📐 Opening Range Breakout (ORB)")
    st.caption("First 15-min High & Low (9:15–9:30 AM) — the most watched intraday levels")
    orb_n  = get_orb("^NSEI")
    orb_bn = get_orb("^NSEBANK")

    orb_c1, orb_c2 = st.columns(2)
    for orb_col, orb_data, name_orb, ltp_orb in [
        (orb_c1, orb_n,  "Nifty 50",   n_ltp),
        (orb_c2, orb_bn, "Bank Nifty", bn_ltp),
    ]:
        with orb_col:
            if orb_data and ltp_orb:
                orb_h = orb_data["high"]
                orb_l = orb_data["low"]
                orb_r = orb_data["range"]
                if ltp_orb > orb_h:
                    orb_signal = "🟢 BREAKOUT — CE bias"
                    orb_cls    = "#26a69a"
                elif ltp_orb < orb_l:
                    orb_signal = "🔴 BREAKDOWN — PE bias"
                    orb_cls    = "#ef5350"
                else:
                    orb_signal = "🟡 Inside range — wait"
                    orb_cls    = "#f59e0b"
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{orb_cls}">
                  <div style="font-size:12px;color:#9ca3af;margin-bottom:6px"><b>{name_orb} ORB</b></div>
                  <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <div><div class="trade-label">ORB High</div>
                         <div style="color:#ef5350;font-weight:700;font-size:15px">{orb_h:,.2f}</div></div>
                    <div><div class="trade-label">ORB Low</div>
                         <div style="color:#26a69a;font-weight:700;font-size:15px">{orb_l:,.2f}</div></div>
                    <div><div class="trade-label">Range</div>
                         <div style="font-weight:700;font-size:15px">{orb_r:,.0f} pts</div></div>
                    <div><div class="trade-label">LTP</div>
                         <div style="font-weight:700;font-size:15px">{ltp_orb:,.2f}</div></div>
                  </div>
                  <div style="color:{orb_cls};font-weight:700;font-size:14px">{orb_signal}</div>
                  <div style="color:#9ca3af;font-size:11px;margin-top:4px">
                    Strategy: Buy breakout above ORB High → CE | Breakdown below ORB Low → PE<br>
                    SL: Re-entry inside the range | Target: 1.5× – 2× the range size
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.info(f"{name_orb} ORB data unavailable (market may not have opened yet)")

    st.divider()

    # ── Index selector ────────────────────────────────────────────────────────
    sel_index = st.radio("Select Index for Signals", ["Nifty 50", "Bank Nifty", "Both"],
                          horizontal=True)

    # Budget input — used inside show_intraday_signals below
    bgt_col, _ = st.columns([1, 3])
    with bgt_col:
        user_budget = st.number_input(
            "💰 My budget per lot (₹)", min_value=500, max_value=500000,
            value=10000, step=500, key="intra_budget",
            help="Dashboard will highlight strikes you can afford with this budget",
        )

    def show_intraday_signals(df, ltp, vix, name, step):
        setup = intraday_option_setup(df, ltp, vix, name, step)
        st.markdown(f"### {name} — Intraday Signals")

        if setup.get("no_trade"):
            st.markdown(f'<div class="no-trade-banner">⛔ NO TRADE ZONE<br>'
                        f'<span style="font-size:14px;font-weight:400">{setup["reason"]}</span></div>',
                        unsafe_allow_html=True)
            return

        # Market condition
        cond  = setup["market_cond"]
        cond_color = "#26a69a" if cond == "Bullish" else ("#ef5350" if cond == "Bearish" else "#f59e0b")
        st.markdown(f'<span style="color:{cond_color};font-size:18px;font-weight:700">'
                    f'Market Condition: {cond}</span> &nbsp;'
                    f'<span style="color:#9ca3af;font-size:13px">|&nbsp; VWAP: {setup["vwap"]:,.0f} &nbsp;'
                    f'| ATM Strike: {setup["atm"]}</span>', unsafe_allow_html=True)

        if setup.get("high_vix"):
            st.warning(f"⚠️ VIX is elevated ({setup['vix']:.1f}) — use smaller position size")

        # Confirmations
        with st.expander("📊 Signal Confirmations", expanded=False):
            for c in setup["confirmations"]:
                st.markdown(f"• {c}")

        # Trade cards
        c1, c2 = st.columns(2)
        with c1:
            render_trade_card(setup, "call")
        with c2:
            render_trade_card(setup, "put")

        # Quick reference table
        st.markdown("#### Quick Reference")
        call_t = setup["call"]
        put_t  = setup["put"]
        ref_df = pd.DataFrame({
            "": ["Strike", "Entry ₹", "Stop-Loss ₹", "Target 1 ₹", "Target 2 ₹", "Risk:Reward", "Confidence", "Signal"],
            "CALL (CE)": [call_t["strike"], call_t["entry"], call_t["sl"],
                          call_t["tgt1"], call_t["tgt2"], f"1:{call_t['rr']}",
                          call_t["conf"], call_t["status"]],
            "PUT (PE)":  [put_t["strike"],  put_t["entry"],  put_t["sl"],
                          put_t["tgt1"],  put_t["tgt2"],  f"1:{put_t['rr']}",
                          put_t["conf"],  put_t["status"]],
        })
        st.dataframe(ref_df.set_index(""), use_container_width=True)

        # ── Strike Ladder ─────────────────────────────────────────────────────
        st.markdown("#### 🎯 Strike Selection — Choose by Budget")
        st.caption("Estimated premiums based on VIX and days to expiry. Actual premiums may differ — verify on your broker.")

        atm     = setup["atm"]
        vix_val = max(float(vix) if vix else 15, 8)
        exp_info   = next_expiry_info()
        days_left  = exp_info["nifty"]["days"] if "Bank" not in name else exp_info["banknifty"]["days"]
        days_safe  = max(float(days_left), 0.5)
        lot_sz     = 75 if "Bank" not in name else 30

        # VIX + time-adjusted base premium (rough Black-Scholes approximation)
        base_prem = ltp * (vix_val / 100) * np.sqrt(days_safe / 252) * 0.45

        OTM_LEVELS = [
            ("ATM",       0,  1.00, "Highest delta — moves most with index. Best for strong trending days."),
            ("OTM 1",     1,  0.58, "Popular choice — good balance of cost vs. movement potential."),
            ("OTM 2",     2,  0.33, "Lower cost — needs ~0.5% index move to start profiting."),
            ("Deep OTM",  3,  0.18, "Cheapest — needs strong trending day (0.8%+ move). High risk."),
        ]

        for direction, sign, emoji in [("CE", +1, "📈"), ("PE", -1, "📉")]:
            is_preferred = (sign > 0 and setup["net_score"] > 0) or (sign < 0 and setup["net_score"] < 0)
            dir_color    = "#26a69a" if direction == "CE" else "#ef5350"
            badge        = ' <span style="background:#f59e0b;color:#000;padding:1px 8px;border-radius:8px;font-size:11px;font-weight:700">★ PREFERRED</span>' if is_preferred else ""
            st.markdown(
                f'<div style="color:{dir_color};font-weight:700;font-size:15px;margin:14px 0 6px">'
                f'{emoji} {direction} Options{badge}</div>',
                unsafe_allow_html=True,
            )

            rows = []
            for label, offset, mult, note in OTM_LEVELS:
                strike       = atm + sign * offset * step
                prem         = max(round(base_prem * mult, 1), 5.0)
                sl           = round(prem * 0.65, 1)
                t1           = round(prem * 1.60, 1)
                t2           = round(prem * 2.50, 1)
                rr           = round((t1 - prem) / max(prem - sl, 1), 1)
                budget_1lot  = int(prem * lot_sz)
                affordable   = budget_1lot <= user_budget
                max_lots     = int(user_budget // budget_1lot) if budget_1lot > 0 else 0
                rows.append({
                    "Strike":         f"{strike} {direction}",
                    "Type":           label,
                    "Est. Premium ₹": prem,
                    "Stop-Loss ₹":    sl,
                    "Target 1 ₹":     t1,
                    "Target 2 ₹":     t2,
                    "R:R":            f"1:{rr}",
                    f"Budget (1 lot)": f"₹{budget_1lot:,}",
                    f"Max lots @ ₹{user_budget:,}": max_lots if affordable else "—",
                    "Status":         "✅ Affordable" if affordable else "❌ Over budget",
                    "_note":          note,
                    "_affordable":    affordable,
                })

            for row in rows:
                aff     = row["_affordable"]
                bg      = "rgba(38,166,154,0.07)" if aff and direction == "CE" else \
                          ("rgba(239,83,80,0.07)"  if aff and direction == "PE" else "rgba(255,255,255,0.02)")
                border  = dir_color if aff else "#374151"
                opacity = "1" if aff else "0.45"
                lots_disp = row[f"Max lots @ ₹{user_budget:,}"]
                st.markdown(f"""
                <div style="background:{bg};border:1px solid {border};border-radius:8px;
                            padding:10px 14px;margin:5px 0;opacity:{opacity}">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                    <div>
                      <span style="color:{dir_color};font-weight:800;font-size:15px">{row['Strike']}</span>
                      <span style="background:#1a1d2e;color:#9ca3af;padding:2px 8px;border-radius:8px;
                                   font-size:11px;margin-left:8px">{row['Type']}</span>
                    </div>
                    <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:13px">
                      <div><span style="color:#6b7280">Premium</span>
                           <div style="font-weight:700;color:{dir_color}">₹{row['Est. Premium ₹']}</div></div>
                      <div><span style="color:#6b7280">SL</span>
                           <div style="font-weight:700;color:#ef5350">₹{row['Stop-Loss ₹']}</div></div>
                      <div><span style="color:#6b7280">Target 1</span>
                           <div style="font-weight:700;color:#26a69a">₹{row['Target 1 ₹']}</div></div>
                      <div><span style="color:#6b7280">Target 2</span>
                           <div style="font-weight:700;color:#26a69a">₹{row['Target 2 ₹']}</div></div>
                      <div><span style="color:#6b7280">R:R</span>
                           <div style="font-weight:700">{row['R:R']}</div></div>
                      <div><span style="color:#6b7280">1 lot costs</span>
                           <div style="font-weight:700">{row['Budget (1 lot)']}</div></div>
                      <div><span style="color:#6b7280">Max lots</span>
                           <div style="font-weight:800;color:{'#26a69a' if aff else '#6b7280'};font-size:15px">{lots_disp}</div></div>
                    </div>
                    <div style="font-size:12px;font-weight:700">{'✅' if aff else '❌'}</div>
                  </div>
                  <div style="font-size:11px;color:#6b7280;margin-top:5px">💡 {row['_note']}</div>
                </div>""", unsafe_allow_html=True)

        st.caption(f"Lot sizes — Nifty: 75 | Bank Nifty: 30 | Fin Nifty: 40 | Expiry in {days_left} day(s)")

        # Risk rules reminder
        st.markdown("""
        <div style="background:#1a1d2e;border-radius:8px;padding:12px 16px;margin-top:10px;
                    border-left:4px solid #f59e0b;font-size:13px;color:#9ca3af">
        ⚠️ <b style="color:#f59e0b">Risk Rules:</b>
        Risk max 1–2% capital per trade &nbsp;|&nbsp;
        Exit at SL without hesitation &nbsp;|&nbsp;
        Book Target 1 first, trail for Target 2 &nbsp;|&nbsp;
        Exit all positions before 3:15 PM
        </div>
        """, unsafe_allow_html=True)

    if sel_index == "Nifty 50":
        show_intraday_signals(intra_nifty_df, n_ltp, vix_i, "Nifty 50", 50)
    elif sel_index == "Bank Nifty":
        show_intraday_signals(intra_bank_df, bn_ltp, vix_i, "Bank Nifty", 100)
    else:
        show_intraday_signals(intra_nifty_df, n_ltp, vix_i, "Nifty 50", 50)
        st.divider()
        show_intraday_signals(intra_bank_df, bn_ltp, vix_i, "Bank Nifty", 100)


# ── TAB 2: Nifty ─────────────────────────────────────────────────────────────
with tab3:
    tf_row1, tf_row2 = st.columns([1, 5])
    with tf_row1:
        nifty_tf = st.selectbox("Timeframe", ["5m", "15m", "1h"], index=1, key="tf_nifty")
    nifty_tf_period = {"5m": "2d", "15m": "5d", "1h": "30d"}[nifty_tf]
    c1, c2 = st.columns([3, 1])
    with c1:
        nifty_df   = get_candles("^NSEI", period=nifty_tf_period, interval=nifty_tf)
        nifty_df   = add_indicators(nifty_df)
        nifty_pivs = get_pivots("^NSEI")
        nifty_orb  = get_orb("^NSEI") if nifty_tf in ("1m", "5m", "15m") else None
        if not nifty_df.empty:
            st.plotly_chart(
                candlestick_fig(nifty_df, f"Nifty 50 — {nifty_tf}",
                                pivots=nifty_pivs, orb=nifty_orb),
                use_container_width=True)
        else:
            st.info("Chart data unavailable. Market may be closed.")

    with c2:
        st.markdown('<div class="section-title">Nifty Signals</div>', unsafe_allow_html=True)
        nq = quotes.get("Nifty 50", {})
        ltp = nq.get("ltp", 0)
        vix_q = quotes.get("India VIX", {})
        vix = vix_q.get("ltp", 0)
        sigs = signal_summary(nifty_df, ltp) if not nifty_df.empty else {}
        pill_map = {"green": "pill-green", "red": "pill-red", "yellow": "pill-yellow"}
        for sig_name, (label, color) in sigs.items():
            st.markdown(f'<span class="pill {pill_map[color]}">{sig_name}: {label}</span>', unsafe_allow_html=True)

        st.markdown('<div class="section-title" style="margin-top:20px">Options Bias</div>', unsafe_allow_html=True)
        bias = option_bias(nifty_df, ltp, vix)
        bias_color = "pill-green" if "CE" in bias["bias"] else ("pill-red" if "PE" in bias["bias"] else "pill-yellow")
        conf_color = {"High": "pill-green", "Medium": "pill-yellow", "Low": "pill-red"}.get(bias["confidence"], "pill-yellow")
        st.markdown(f'<span class="pill {bias_color}">{bias["bias"]}</span>', unsafe_allow_html=True)
        st.markdown(f'<span class="pill {conf_color}">Confidence: {bias["confidence"]}</span>', unsafe_allow_html=True)
        if bias.get("reasons"):
            st.markdown("**Reasons:**")
            for r in bias["reasons"]:
                st.markdown(f"• {r}")

        st.markdown('<div class="section-title" style="margin-top:20px">Support & Resistance</div>', unsafe_allow_html=True)
        if not nifty_df.empty and ltp:
            recent = nifty_df.tail(40)
            resistance = float(recent["high"].max())
            support    = float(recent["low"].min())
            vwap_val   = float(nifty_df["vwap"].iloc[-1]) if "vwap" in nifty_df.columns else 0
            st.markdown(f"🔴 **Resistance:** {resistance:,.0f}")
            st.markdown(f"🟢 **Support:** {support:,.0f}")
            if vwap_val: st.markdown(f"🟣 **VWAP:** {vwap_val:,.0f}")

        if nifty_pivs:
            st.markdown('<div class="section-title" style="margin-top:16px">Pivot Points</div>', unsafe_allow_html=True)
            for level, val in nifty_pivs.items():
                color = "#ef5350" if level.startswith("R") else ("#26a69a" if level.startswith("S") else "#f59e0b")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 0">'
                            f'<span style="color:{color};font-weight:700;font-size:13px">{level}</span>'
                            f'<span style="font-size:13px">{val:,}</span></div>', unsafe_allow_html=True)

# ── TAB 3: Bank Nifty ────────────────────────────────────────────────────────
with tab4:
    tf_row_b1, tf_row_b2 = st.columns([1, 5])
    with tf_row_b1:
        bnf_tf = st.selectbox("Timeframe", ["5m", "15m", "1h"], index=1, key="tf_banknifty")
    bnf_tf_period = {"5m": "2d", "15m": "5d", "1h": "30d"}[bnf_tf]
    bc1, bc2 = st.columns([3, 1])
    with bc1:
        bnf_df   = get_candles("^NSEBANK", period=bnf_tf_period, interval=bnf_tf)
        bnf_df   = add_indicators(bnf_df)
        bnf_pivs = get_pivots("^NSEBANK")
        bnf_orb  = get_orb("^NSEBANK") if bnf_tf in ("1m", "5m", "15m") else None
        if not bnf_df.empty:
            st.plotly_chart(
                candlestick_fig(bnf_df, f"Bank Nifty — {bnf_tf}",
                                pivots=bnf_pivs, orb=bnf_orb),
                use_container_width=True)
        else:
            st.info("Chart data unavailable. Market may be closed.")

    with bc2:
        st.markdown('<div class="section-title">Bank Nifty Signals</div>', unsafe_allow_html=True)
        bnq = quotes.get("Bank Nifty", {})
        bnltp = bnq.get("ltp", 0)
        bnsigs = signal_summary(bnf_df, bnltp) if not bnf_df.empty else {}
        for sig_name, (label, color) in bnsigs.items():
            st.markdown(f'<span class="pill {pill_map[color]}">{sig_name}: {label}</span>', unsafe_allow_html=True)

        st.markdown('<div class="section-title" style="margin-top:20px">Options Bias</div>', unsafe_allow_html=True)
        bn_bias = option_bias(bnf_df, bnltp, vix)
        bn_bias_color = "pill-green" if "CE" in bn_bias["bias"] else ("pill-red" if "PE" in bn_bias["bias"] else "pill-yellow")
        bn_conf_color = {"High": "pill-green", "Medium": "pill-yellow", "Low": "pill-red"}.get(bn_bias["confidence"], "pill-yellow")
        st.markdown(f'<span class="pill {bn_bias_color}">{bn_bias["bias"]}</span>', unsafe_allow_html=True)
        st.markdown(f'<span class="pill {bn_conf_color}">Confidence: {bn_bias["confidence"]}</span>', unsafe_allow_html=True)
        if bn_bias.get("reasons"):
            st.markdown("**Reasons:**")
            for r in bn_bias["reasons"]:
                st.markdown(f"• {r}")

        st.markdown('<div class="section-title" style="margin-top:20px">Support & Resistance</div>', unsafe_allow_html=True)
        if not bnf_df.empty and bnltp:
            recent_bn = bnf_df.tail(40)
            st.markdown(f"🔴 **Resistance:** {float(recent_bn['high'].max()):,.0f}")
            st.markdown(f"🟢 **Support:** {float(recent_bn['low'].min()):,.0f}")
            if "vwap" in bnf_df.columns:
                st.markdown(f"🟣 **VWAP:** {float(bnf_df['vwap'].iloc[-1]):,.0f}")

        if bnf_pivs:
            st.markdown('<div class="section-title" style="margin-top:16px">Pivot Points</div>', unsafe_allow_html=True)
            for level, val in bnf_pivs.items():
                color = "#ef5350" if level.startswith("R") else ("#26a69a" if level.startswith("S") else "#f59e0b")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 0">'
                            f'<span style="color:{color};font-weight:700;font-size:13px">{level}</span>'
                            f'<span style="font-size:13px">{val:,}</span></div>', unsafe_allow_html=True)

# ── TAB 4: Global Cues ───────────────────────────────────────────────────────
with tab5:
    global_quotes = {name: get_quote(ticker) for name, ticker in GLOBAL.items()}
    gs = compute_global_sentiment(global_quotes)

    # ── Composite Sentiment Banner ────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.3);border:2px solid {gs['color']};border-radius:14px;
                padding:16px 24px;margin-bottom:16px;display:flex;align-items:center;gap:24px">
      <div>
        <div style="font-size:12px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">
          Global Sentiment for India</div>
        <div style="font-size:22px;font-weight:800;color:{gs['color']}">{gs['label']}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #374151;padding-left:24px">
        <div style="font-size:11px;color:#9ca3af">Score</div>
        <div style="font-size:36px;font-weight:900;color:{gs['color']}">{gs['score']:+d}</div>
        <div style="font-size:10px;color:#6b7280">out of ±10</div>
      </div>
      <div style="font-size:12px;color:#9ca3af;flex:1">
        {'  ·  '.join([f"<span style='color:{'#26a69a' if f[2]=='bull' else ('#ef5350' if f[2]=='bear' else '#9ca3af')}'>{f[0]}: {f[1]}</span>" for f in gs['factors']])}
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Global index grid ─────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Global Markets</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    for i, (name, q) in enumerate(global_quotes.items()):
        col = g1 if i % 2 == 0 else g2
        with col:
            if q:
                arrow = "▲" if q["chg"] >= 0 else "▼"
                cls   = "bull" if q["chg"] >= 0 else "bear"
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{'#26a69a' if q['chg']>=0 else '#ef5350'}">
                  <div style="font-size:11px;color:#9ca3af">{name}</div>
                  <div style="font-size:18px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
                  <div style="font-size:12px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
                </div>""", unsafe_allow_html=True)

    # ── Macro Impact Matrix ───────────────────────────────────────────────────
    st.markdown('<div class="section-title" style="margin-top:16px">Macro Impact on India</div>',
                unsafe_allow_html=True)
    crude_pct  = global_quotes.get("Crude Oil",    {}).get("pct", 0) or 0
    gold_pct   = global_quotes.get("Gold",         {}).get("pct", 0) or 0
    dxy_pct    = global_quotes.get("Dollar Index", {}).get("pct", 0) or 0
    usdinr_pct = global_quotes.get("USD/INR",      {}).get("pct", 0) or 0
    tnx_ltp    = global_quotes.get("US 10Y Yield", {}).get("ltp", 4.2) or 4.2

    macro_rows = [
        ("Crude Oil", f"{crude_pct:+.2f}%",
         "🔴 Negative — raises import costs, inflation" if crude_pct > 1.5
         else "🟢 Positive — lower costs, rupee support" if crude_pct < -1.0
         else "🟡 Neutral"),
        ("Gold", f"{gold_pct:+.2f}%",
         "🔴 Risk-off signal — FII may sell equities" if gold_pct > 0.8
         else "🟢 Risk-on — equity positive" if gold_pct < -0.3
         else "🟡 Neutral"),
        ("Dollar Index", f"{dxy_pct:+.2f}%",
         "🔴 Strong dollar → FII outflows from India" if dxy_pct > 0.3
         else "🟢 Weak dollar → FII inflows into EM" if dxy_pct < -0.3
         else "🟡 Neutral"),
        ("USD/INR", f"{usdinr_pct:+.2f}%",
         "🔴 Rupee weakening → FII selling pressure" if usdinr_pct > 0.2
         else "🟢 Rupee strengthening → positive" if usdinr_pct < -0.2
         else "🟡 Stable"),
        ("US 10Y Yield", f"{tnx_ltp:.2f}%",
         "🔴 High yield → FII prefers US bonds over India" if tnx_ltp > 4.5
         else "🟢 Low yield → EM equities attractive" if tnx_ltp < 3.8
         else "🟡 Moderate"),
    ]
    macro_df = pd.DataFrame(macro_rows, columns=["Factor", "Change", "India Impact"])
    st.dataframe(macro_df.set_index("Factor"), use_container_width=True)

    # ── Live News Feed ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title" style="margin-top:16px">📰 Latest Market News</div>',
                unsafe_allow_html=True)
    st.caption("Headlines from Economic Times, Mint & Reuters — updates every 5 minutes")
    with st.spinner("Fetching news..."):
        headlines = fetch_news_headlines()

    if headlines:
        bull_count = sum(1 for h in headlines if h["sentiment"] == "bullish")
        bear_count = sum(1 for h in headlines if h["sentiment"] == "bearish")
        news_sentiment = "🟢 Mostly Positive" if bull_count > bear_count + 1 \
                    else ("🔴 Mostly Negative" if bear_count > bull_count + 1 else "🟡 Mixed")
        st.markdown(f"**News Sentiment:** {news_sentiment} &nbsp;|&nbsp; "
                    f"🟢 {bull_count} positive &nbsp;|&nbsp; 🔴 {bear_count} negative &nbsp;|&nbsp; "
                    f"{len(headlines)} headlines scanned")
        st.divider()
        for h in headlines:
            s_color = "#26a69a" if h["sentiment"] == "bullish" else \
                      ("#ef5350" if h["sentiment"] == "bearish" else "#9ca3af")
            s_icon  = "▲" if h["sentiment"] == "bullish" else \
                      ("▼" if h["sentiment"] == "bearish" else "—")
            st.markdown(
                f'<div style="padding:7px 0;border-bottom:1px solid #1e2130;font-size:13px">'
                f'<span style="color:{s_color};font-weight:700;margin-right:6px">{s_icon}</span>'
                f'<span style="color:#e0e0e0">{h["title"]}</span>'
                f'<span style="color:#6b7280;font-size:11px;margin-left:8px">[{h["source"]}]</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("News feed temporarily unavailable. Check internet connection.")

    st.caption("⚠️ News sentiment uses keyword analysis — not financial advice. Verify before acting.")

# ── TAB 5: Trade Plan ────────────────────────────────────────────────────────
with tab6:
    st.markdown('<div class="section-title">Today\'s Trade Plan</div>', unsafe_allow_html=True)
    nq  = quotes.get("Nifty 50", {})
    bnq = quotes.get("Bank Nifty", {})
    vix_val = quotes.get("India VIX", {}).get("ltp", 0)
    nifty_ltp  = nq.get("ltp", 0)
    bnifty_ltp = bnq.get("ltp", 0)

    if nifty_ltp:
        nifty_bias  = option_bias(nifty_df, nifty_ltp, vix_val) if not nifty_df.empty else {}
        bank_bias   = option_bias(bnf_df, bnifty_ltp, vix_val) if not bnf_df.empty else {}
        vwap_nifty  = float(nifty_df["vwap"].iloc[-1]) if not nifty_df.empty and "vwap" in nifty_df.columns else 0
        vwap_bank   = float(bnf_df["vwap"].iloc[-1])   if not bnf_df.empty  and "vwap" in bnf_df.columns  else 0

        tp1, tp2 = st.columns(2)
        with tp1:
            st.markdown("### Nifty 50")
            if nifty_bias:
                st.markdown(f"**Bias:** {nifty_bias['bias']}")
                st.markdown(f"**Confidence:** {nifty_bias['confidence']}")
            if vwap_nifty:
                sl    = round(vwap_nifty * 0.997, 0)
                tgt1  = round(nifty_ltp + (nifty_ltp - sl) * 1.5, 0)
                tgt2  = round(nifty_ltp + (nifty_ltp - sl) * 2.5, 0)
                st.markdown(f"**Entry zone:** {nifty_ltp - 30:,.0f} – {nifty_ltp + 30:,.0f}")
                st.markdown(f"**Stop-loss:** {sl:,.0f}")
                st.markdown(f"**Target 1:** {tgt1:,.0f}  |  **Target 2:** {tgt2:,.0f}")
                st.markdown(f"**VWAP:** {vwap_nifty:,.0f}")
            if vix_val:
                st.markdown(f"**India VIX:** {vix_val:.2f} {'⚠️ High — reduce size' if vix_val > 18 else '✅ Normal'}")

        with tp2:
            st.markdown("### Bank Nifty")
            if bank_bias:
                st.markdown(f"**Bias:** {bank_bias['bias']}")
                st.markdown(f"**Confidence:** {bank_bias['confidence']}")
            if vwap_bank:
                sl_b   = round(vwap_bank * 0.997, 0)
                tgt1_b = round(bnifty_ltp + (bnifty_ltp - sl_b) * 1.5, 0)
                tgt2_b = round(bnifty_ltp + (bnifty_ltp - sl_b) * 2.5, 0)
                st.markdown(f"**Entry zone:** {bnifty_ltp - 50:,.0f} – {bnifty_ltp + 50:,.0f}")
                st.markdown(f"**Stop-loss:** {sl_b:,.0f}")
                st.markdown(f"**Target 1:** {tgt1_b:,.0f}  |  **Target 2:** {tgt2_b:,.0f}")
                st.markdown(f"**VWAP:** {vwap_bank:,.0f}")

        st.divider()
        st.markdown("### 🧮 Position Size Calculator")
        ps1, ps2, ps3 = st.columns(3)
        with ps1:
            ps_capital = st.number_input("Capital (₹)", value=100000, step=10000, key="ps_cap")
            ps_risk_pct = st.number_input("Risk per trade (%)", value=1.0, min_value=0.1, max_value=5.0, step=0.1, key="ps_rp")
        with ps2:
            ps_entry = st.number_input("Option Entry Price (₹)", value=100.0, step=1.0, key="ps_entry")
            ps_sl    = st.number_input("Stop-Loss Price (₹)", value=70.0, step=1.0, key="ps_sl")
        with ps3:
            ps_index   = st.selectbox("Index", ["Nifty 50 (75)", "Bank Nifty (30)", "Fin Nifty (40)"], key="ps_idx")
            lot_sizes  = {"Nifty 50 (75)": 75, "Bank Nifty (30)": 30, "Fin Nifty (40)": 40}
            ps_lotsize = lot_sizes[ps_index]
            st.caption(f"Lot size: {ps_lotsize}")

        if ps_entry > ps_sl > 0:
            max_loss_per_lot = (ps_entry - ps_sl) * ps_lotsize
            max_risk_amt     = ps_capital * (ps_risk_pct / 100)
            max_lots         = int(max_risk_amt / max_loss_per_lot) if max_loss_per_lot > 0 else 0
            premium_needed   = ps_entry * ps_lotsize * max(max_lots, 1)
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:#3b82f6;margin-top:8px">
              <div style="display:flex;gap:40px;flex-wrap:wrap">
                <div><div class="trade-label">Max Risk Amount</div>
                     <div style="color:#f59e0b;font-weight:800;font-size:18px">₹{max_risk_amt:,.0f}</div></div>
                <div><div class="trade-label">Loss per Lot</div>
                     <div style="color:#ef5350;font-weight:800;font-size:18px">₹{max_loss_per_lot:,.0f}</div></div>
                <div><div class="trade-label">Max Lots to Trade</div>
                     <div style="color:#26a69a;font-weight:800;font-size:28px">{max_lots}</div></div>
                <div><div class="trade-label">Premium Required</div>
                     <div style="font-weight:700;font-size:18px">₹{premium_needed:,.0f}</div></div>
              </div>
              <div style="font-size:11px;color:#6b7280;margin-top:8px">
                Formula: Risk = (Entry − SL) × Lot size × Lots | Max Lots = Max Risk ÷ Loss per Lot
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.caption("Enter valid Entry and Stop-Loss prices to calculate position size.")

        st.divider()
        st.markdown("### ⚠️ Risk Management Rules")
        st.markdown("""
        - **Max 1-2% risk per trade** — never exceed your daily loss limit
        - **Wait for first 15–30 min** — avoid trading in the opening range before 9:45 AM
        - **No trade if VIX > 20** — volatility too high for directional bets
        - **Exit at 3:15 PM** — never hold options to expiry without a plan
        - **Signals are analytical guidance only, not guaranteed advice**
        """)
    else:
        st.info("Market data loading. Click Refresh if it takes too long.")

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 7 — Price Alerts
# ══════════════════════════════════════════════════════════════════════════════
ALERTS_FILE = os.path.join(os.path.dirname(__file__), "price_alerts.csv")

def load_alerts() -> pd.DataFrame:
    if os.path.exists(ALERTS_FILE):
        try:
            return pd.read_csv(ALERTS_FILE)
        except Exception:
            pass
    return pd.DataFrame(columns=["index","condition","price","note","active"])

def save_alerts(df: pd.DataFrame):
    df.to_csv(ALERTS_FILE, index=False)

with tab7:
    st.markdown("## 🔔 Price Alerts")
    st.caption("Set price levels — dashboard highlights when they are triggered on Refresh.")

    alerts_df = load_alerts()
    current_prices = {
        "Nifty 50":   quotes.get("Nifty 50",   {}).get("ltp", 0),
        "Bank Nifty": quotes.get("Bank Nifty",  {}).get("ltp", 0),
        "India VIX":  quotes.get("India VIX",   {}).get("ltp", 0),
        "Sensex":     quotes.get("Sensex",       {}).get("ltp", 0),
    }

    # Current prices reference
    st.markdown("**Current Prices**")
    pc1, pc2, pc3, pc4 = st.columns(4)
    for col, (name, price) in zip([pc1,pc2,pc3,pc4], current_prices.items()):
        col.metric(name, f"{price:,.2f}" if price else "N/A")

    st.divider()

    # Add new alert
    st.markdown("### ➕ Add New Alert")
    with st.form("alert_form", clear_on_submit=True):
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            a_index = st.selectbox("Index", ["Nifty 50", "Bank Nifty", "India VIX", "Sensex"])
        with ac2:
            a_cond  = st.selectbox("Condition", ["Crosses Above", "Crosses Below"])
        with ac3:
            cur = current_prices.get(a_index, 0)
            a_price = st.number_input("Alert Price", value=float(cur) if cur else 0.0, step=10.0)
        a_note = st.text_input("Note (optional)", placeholder="e.g. Key resistance level, breakout watch")
        if st.form_submit_button("🔔 Set Alert", use_container_width=True):
            new_row = pd.DataFrame([{
                "index":     a_index,
                "condition": a_cond,
                "price":     a_price,
                "note":      a_note,
                "active":    True,
            }])
            alerts_df = pd.concat([alerts_df, new_row], ignore_index=True)
            save_alerts(alerts_df)
            st.success(f"Alert set: {a_index} {a_cond} {a_price:,.2f}")
            st.rerun()

    # Check and display alerts
    st.markdown("### 📋 Active Alerts")
    if alerts_df.empty:
        st.info("No alerts set yet. Add one above.")
    else:
        triggered_any = False
        for idx, row in alerts_df.iterrows():
            cur_price = current_prices.get(row["index"], 0)
            triggered = False
            if cur_price:
                if row["condition"] == "Crosses Above" and cur_price >= row["price"]:
                    triggered = True
                elif row["condition"] == "Crosses Below" and cur_price <= row["price"]:
                    triggered = True

            if triggered:
                triggered_any = True
                st.markdown(f"""
                <div class="alert-box alert-triggered">
                🚨 <b>TRIGGERED!</b> &nbsp;
                <b>{row['index']}</b> {row['condition']} <b>{row['price']:,.2f}</b><br>
                Current: <b style="color:#ef5350">{cur_price:,.2f}</b> &nbsp;|&nbsp;
                <span style="color:#9ca3af">{row.get('note','')}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="alert-box">
                🔔 <b>{row['index']}</b> {row['condition']} <b>{row['price']:,.2f}</b> &nbsp;|&nbsp;
                Current: {cur_price:,.2f} &nbsp;|&nbsp;
                Gap: {abs(cur_price - row['price']):,.2f} pts &nbsp;|&nbsp;
                <span style="color:#9ca3af">{row.get('note','')}</span>
                </div>""", unsafe_allow_html=True)

        if triggered_any:
            st.balloons()

        st.divider()
        # Delete alerts
        if st.button("🗑️ Clear All Alerts"):
            save_alerts(pd.DataFrame(columns=["index","condition","price","note","active"]))
            st.success("All alerts cleared.")
            st.rerun()

        del_idx = st.number_input("Delete alert number (row)", min_value=0,
                                   max_value=max(len(alerts_df)-1, 0), value=0, step=1)
        if st.button("Delete Selected Alert"):
            alerts_df = alerts_df.drop(index=del_idx).reset_index(drop=True)
            save_alerts(alerts_df)
            st.success("Alert deleted.")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 8 — Trade Journal
# ══════════════════════════════════════════════════════════════════════════════
JOURNAL_FILE = os.path.join(os.path.dirname(__file__), "trade_journal.csv")
JOURNAL_COLS = ["date", "time", "index", "strategy", "direction", "strike",
                "expiry", "qty", "entry_price", "exit_price", "pnl",
                "result", "setup_quality", "emotion", "notes"]

def load_journal() -> pd.DataFrame:
    if os.path.exists(JOURNAL_FILE):
        try:
            df = pd.read_csv(JOURNAL_FILE)
            for col in JOURNAL_COLS:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=JOURNAL_COLS)

def save_trade(row: dict):
    file_exists = os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOURNAL_COLS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def journal_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    df = df.copy()
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0)
    total      = len(df)
    wins       = len(df[df["pnl"] > 0])
    losses     = len(df[df["pnl"] < 0])
    be         = len(df[df["pnl"] == 0])
    win_rate   = (wins / total * 100) if total > 0 else 0
    total_pnl  = df["pnl"].sum()
    avg_win    = df[df["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
    avg_loss   = df[df["pnl"] < 0]["pnl"].mean() if losses > 0 else 0
    best       = df["pnl"].max()
    worst      = df["pnl"].min()
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss) if total > 0 else 0
    return {"total": total, "wins": wins, "losses": losses, "be": be,
            "win_rate": win_rate, "total_pnl": total_pnl,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "best": best, "worst": worst, "expectancy": expectancy}

with tab8:
    st.markdown("## 📓 Trade Journal")
    st.caption("Log every trade — paper or real. Track your performance and improve over time.")

    j_tab1, j_tab2, j_tab3 = st.tabs(["➕ Log Trade", "📊 Performance", "📋 History"])

    # ── LOG TRADE ─────────────────────────────────────────────────────────────
    with j_tab1:
        st.markdown("### Log a New Trade")
        now_ist = datetime.now(IST)

        with st.form("trade_form", clear_on_submit=True):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                t_date = st.date_input("Date", value=now_ist.date())
            with r1c2:
                t_time = st.time_input("Entry Time", value=now_ist.time())
            with r1c3:
                t_index = st.selectbox("Index / Stock", ["Nifty 50", "Bank Nifty", "Fin Nifty", "Midcap Nifty", "Other"])
            with r1c4:
                t_strategy = st.selectbox("Strategy", ["Intraday", "Scalping", "BTST", "Swing"])

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                t_dir = st.selectbox("Direction", ["CE (Call)", "PE (Put)"])
            with r2c2:
                t_strike = st.text_input("Strike + Expiry", placeholder="e.g. 23700 CE 22-May")
            with r2c3:
                t_qty = st.number_input("Quantity (lots)", min_value=1, value=1, step=1)
            with r2c4:
                t_expiry = st.text_input("Expiry Date", placeholder="e.g. 22-May-2026")

            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c1:
                t_entry = st.number_input("Entry Price ₹", min_value=0.0, value=0.0, step=0.5)
            with r3c2:
                t_exit = st.number_input("Exit Price ₹", min_value=0.0, value=0.0, step=0.5)
            with r3c3:
                lot_size = 75 if "Nifty 50" in t_index else (30 if "Bank" in t_index else 75)
                pnl_calc = round((t_exit - t_entry) * t_qty * lot_size, 2)
                st.metric("Calculated P&L", f"₹{pnl_calc:,.2f}",
                          delta=f"{'Profit' if pnl_calc > 0 else 'Loss' if pnl_calc < 0 else 'Breakeven'}")

            r4c1, r4c2, r4c3 = st.columns(3)
            with r4c1:
                t_quality = st.select_slider("Setup Quality", options=["Poor", "Below Avg", "Average", "Good", "Excellent"], value="Average")
            with r4c2:
                t_emotion = st.selectbox("Emotional State", ["Calm & Disciplined", "Slightly Anxious", "FOMO Entry", "Revenge Trade", "Overconfident"])
            with r4c3:
                t_result = st.selectbox("Result", ["Win", "Loss", "Breakeven", "Partial Exit"])

            t_notes = st.text_area("Trade Notes (what worked, what didn't, lessons learned)",
                                    placeholder="e.g. Entered after VWAP confirmation, RSI was 58, volume breakout confirmed. Exited at Target 1. Should have held for Target 2.", height=100)

            submitted = st.form_submit_button("💾 Save Trade", use_container_width=True)
            if submitted:
                if t_entry == 0:
                    st.error("Please enter the Entry Price.")
                else:
                    row = {
                        "date":          str(t_date),
                        "time":          str(t_time),
                        "index":         t_index,
                        "strategy":      t_strategy,
                        "direction":     t_dir,
                        "strike":        t_strike,
                        "expiry":        t_expiry,
                        "qty":           t_qty,
                        "entry_price":   t_entry,
                        "exit_price":    t_exit,
                        "pnl":           pnl_calc,
                        "result":        t_result,
                        "setup_quality": t_quality,
                        "emotion":       t_emotion,
                        "notes":         t_notes,
                    }
                    save_trade(row)
                    st.success(f"✅ Trade saved! P&L: ₹{pnl_calc:,.2f}")
                    st.balloons() if pnl_calc > 0 else None

    # ── PERFORMANCE ───────────────────────────────────────────────────────────
    with j_tab2:
        st.markdown("### Performance Dashboard")
        jdf = load_journal()

        if jdf.empty:
            st.info("No trades logged yet. Start by logging your first trade in the 'Log Trade' tab.")
        else:
            jdf["pnl"] = pd.to_numeric(jdf["pnl"], errors="coerce").fillna(0)
            jdf["date"] = pd.to_datetime(jdf["date"], errors="coerce")
            stats = journal_stats(jdf)

            # KPI row
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Total Trades",  stats["total"])
            k2.metric("Win Rate",      f"{stats['win_rate']:.1f}%",
                      delta=f"{stats['wins']}W / {stats['losses']}L")
            k3.metric("Total P&L",     f"₹{stats['total_pnl']:,.0f}",
                      delta="Profit" if stats["total_pnl"] > 0 else "Loss")
            k4.metric("Avg Win",       f"₹{stats['avg_win']:,.0f}")
            k5.metric("Avg Loss",      f"₹{stats['avg_loss']:,.0f}")
            k6.metric("Expectancy",    f"₹{stats['expectancy']:,.0f}")

            st.divider()
            pc1, pc2 = st.columns(2)

            # Cumulative P&L chart
            with pc1:
                st.markdown("#### Cumulative P&L")
                jdf_sorted = jdf.sort_values("date").copy()
                jdf_sorted["cum_pnl"] = jdf_sorted["pnl"].cumsum()
                fig_pnl = go.Figure()
                fig_pnl.add_trace(go.Scatter(
                    x=jdf_sorted["date"], y=jdf_sorted["cum_pnl"],
                    fill="tozeroy",
                    line=dict(color="#26a69a" if stats["total_pnl"] >= 0 else "#ef5350", width=2),
                    fillcolor="rgba(38,166,154,0.1)" if stats["total_pnl"] >= 0 else "rgba(239,83,80,0.1)",
                ))
                fig_pnl.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font=dict(color="#e0e0e0"), margin=dict(l=10,r=10,t=10,b=10), height=250,
                    xaxis=dict(gridcolor="#1e2130"), yaxis=dict(gridcolor="#1e2130"))
                st.plotly_chart(fig_pnl, use_container_width=True)

            # Win/Loss pie
            with pc2:
                st.markdown("#### Win / Loss Breakdown")
                fig_pie = go.Figure(go.Pie(
                    labels=["Wins", "Losses", "Breakeven"],
                    values=[stats["wins"], stats["losses"], stats["be"]],
                    marker_colors=["#26a69a", "#ef5350", "#f59e0b"],
                    hole=0.5,
                ))
                fig_pie.update_layout(paper_bgcolor="#0e1117",
                    font=dict(color="#e0e0e0"), margin=dict(l=10,r=10,t=10,b=10), height=250)
                st.plotly_chart(fig_pie, use_container_width=True)

            # P&L by index
            pc3, pc4 = st.columns(2)
            with pc3:
                st.markdown("#### P&L by Index")
                by_index = jdf.groupby("index")["pnl"].sum().reset_index()
                fig_idx = go.Figure(go.Bar(
                    x=by_index["index"], y=by_index["pnl"],
                    marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in by_index["pnl"]],
                ))
                fig_idx.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font=dict(color="#e0e0e0"), margin=dict(l=10,r=10,t=10,b=10), height=220,
                    xaxis=dict(gridcolor="#1e2130"), yaxis=dict(gridcolor="#1e2130"))
                st.plotly_chart(fig_idx, use_container_width=True)

            with pc4:
                st.markdown("#### P&L by Strategy")
                by_strat = jdf.groupby("strategy")["pnl"].sum().reset_index()
                fig_strat = go.Figure(go.Bar(
                    x=by_strat["strategy"], y=by_strat["pnl"],
                    marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in by_strat["pnl"]],
                ))
                fig_strat.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font=dict(color="#e0e0e0"), margin=dict(l=10,r=10,t=10,b=10), height=220,
                    xaxis=dict(gridcolor="#1e2130"), yaxis=dict(gridcolor="#1e2130"))
                st.plotly_chart(fig_strat, use_container_width=True)

            # Emotion analysis
            st.markdown("#### Emotion vs P&L")
            by_emotion = jdf.groupby("emotion")["pnl"].agg(["sum","count"]).reset_index()
            by_emotion.columns = ["Emotional State", "Total P&L", "Trades"]
            by_emotion["Avg P&L"] = (by_emotion["Total P&L"] / by_emotion["Trades"]).round(0)
            by_emotion = by_emotion.sort_values("Avg P&L", ascending=False)
            st.dataframe(by_emotion, use_container_width=True, hide_index=True)

            st.markdown("#### Best & Worst Trades")
            bc1, bc2 = st.columns(2)
            with bc1:
                best_row = jdf.loc[jdf["pnl"].idxmax()]
                st.markdown(f"""
                <div class="trade-card-call">
                  <div style="color:#26a69a;font-weight:700;font-size:16px">🏆 Best Trade</div>
                  <div style="font-size:24px;font-weight:800;color:#26a69a">₹{best_row['pnl']:,.0f}</div>
                  <div style="color:#9ca3af;font-size:13px">{best_row['date'].date() if pd.notna(best_row['date']) else ''} &nbsp;|&nbsp; {best_row['index']} &nbsp;|&nbsp; {best_row['direction']}</div>
                  <div style="color:#9ca3af;font-size:12px;margin-top:6px">{best_row['notes'][:120] if best_row['notes'] else ''}...</div>
                </div>""", unsafe_allow_html=True)
            with bc2:
                worst_row = jdf.loc[jdf["pnl"].idxmin()]
                st.markdown(f"""
                <div class="trade-card-put">
                  <div style="color:#ef5350;font-weight:700;font-size:16px">📉 Worst Trade</div>
                  <div style="font-size:24px;font-weight:800;color:#ef5350">₹{worst_row['pnl']:,.0f}</div>
                  <div style="color:#9ca3af;font-size:13px">{worst_row['date'].date() if pd.notna(worst_row['date']) else ''} &nbsp;|&nbsp; {worst_row['index']} &nbsp;|&nbsp; {worst_row['direction']}</div>
                  <div style="color:#9ca3af;font-size:12px;margin-top:6px">{worst_row['notes'][:120] if worst_row['notes'] else ''}...</div>
                </div>""", unsafe_allow_html=True)

    # ── HISTORY ───────────────────────────────────────────────────────────────
    with j_tab3:
        st.markdown("### Trade History")
        jdf_h = load_journal()

        if jdf_h.empty:
            st.info("No trades logged yet.")
        else:
            jdf_h["pnl"] = pd.to_numeric(jdf_h["pnl"], errors="coerce").fillna(0)

            # Filters
            hc1, hc2, hc3 = st.columns(3)
            with hc1:
                f_index = st.multiselect("Filter by Index", options=jdf_h["index"].unique().tolist(), default=[])
            with hc2:
                f_result = st.multiselect("Filter by Result", options=["Win","Loss","Breakeven","Partial Exit"], default=[])
            with hc3:
                f_dir = st.multiselect("Filter by Direction", options=["CE (Call)","PE (Put)"], default=[])

            filtered = jdf_h.copy()
            if f_index:  filtered = filtered[filtered["index"].isin(f_index)]
            if f_result: filtered = filtered[filtered["result"].isin(f_result)]
            if f_dir:    filtered = filtered[filtered["direction"].isin(f_dir)]

            # Color P&L column
            def color_pnl(val):
                try:
                    v = float(val)
                    if v > 0:   return "color: #26a69a; font-weight: 700"
                    if v < 0:   return "color: #ef5350; font-weight: 700"
                except Exception: pass
                return "color: #f59e0b"

            display_cols = ["date","index","direction","strike","qty","entry_price","exit_price","pnl","result","setup_quality","emotion"]
            available = [c for c in display_cols if c in filtered.columns]
            st.dataframe(
                filtered[available].sort_values("date", ascending=False)
                    .style.map(color_pnl, subset=["pnl"]),
                use_container_width=True, height=400,
            )

            # Download
            csv_data = filtered.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Journal as CSV", data=csv_data,
                               file_name="trade_journal.csv", mime="text/csv")

            # Delete last trade
            if st.button("🗑️ Delete Last Trade", type="secondary"):
                jdf_del = load_journal()
                if not jdf_del.empty:
                    jdf_del = jdf_del.iloc[:-1]
                    jdf_del.to_csv(JOURNAL_FILE, index=False)
                    st.success("Last trade deleted.")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 9 — Stock Picks
# ══════════════════════════════════════════════════════════════════════════════
with tab9:
    st.markdown("## 📊 Nifty 50 Stock Screener")
    st.caption("Scores all 50 Nifty stocks using EMA trend, RSI, MACD, and volume. Updates every 5 minutes. Use for swing/positional ideas — not intraday.")

    sp_col1, sp_col2 = st.columns([1, 3])
    with sp_col1:
        sector_filter = st.selectbox("Filter by Sector", [
            "All", "Banking", "IT", "FMCG", "Auto", "Pharma",
            "Finance", "Energy", "Infra", "Metals", "Cement", "Consumer",
            "Telecom", "Healthcare", "Chemicals", "Conglomerate",
        ])
        signal_filter = st.selectbox("Filter by Signal", ["All", "BUY", "WATCH", "NEUTRAL", "AVOID"])
        top_n = st.slider("Show top N stocks", 5, 50, 15)

    with sp_col2:
        with st.spinner("Scanning Nifty 50 stocks..."):
            screen_df = screen_nifty50()

        if screen_df.empty:
            st.error("Stock data unavailable. Check internet connection.")
        else:
            filtered_df = screen_df.copy()
            if sector_filter != "All":
                filtered_df = filtered_df[filtered_df["Sector"] == sector_filter]
            if signal_filter != "All":
                filtered_df = filtered_df[filtered_df["Signal"] == signal_filter]
            filtered_df = filtered_df.head(top_n)

            # Top picks summary
            buys    = screen_df[screen_df["Signal"] == "BUY"]
            watches = screen_df[screen_df["Signal"] == "WATCH"]
            avoids  = screen_df[screen_df["Signal"] == "AVOID"]

            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Strong Buys", len(buys),   delta=f"Score ≥ 4")
            sc2.metric("Watch List",  len(watches), delta=f"Score 2-3")
            sc3.metric("Avoid",       len(avoids),  delta=f"Score ≤ -2")

    st.divider()

    if not screen_df.empty:
        # Top 5 BUY picks — detailed cards
        st.markdown("### 🟢 Top Buy Candidates")
        top_buys = screen_df[screen_df["Signal"].isin(["BUY", "WATCH"])].head(5)
        if top_buys.empty:
            st.info("No strong buy signals right now — market may be consolidating.")
        else:
            for _, row in top_buys.iterrows():
                score_pct = min(int((row["Score"] / 10) * 100), 100)
                sig_color = "#26a69a" if row["Signal"] == "BUY" else "#f59e0b"
                chg_color = "#26a69a" if row["Chg%"] >= 0 else "#ef5350"
                rsi_color = "#26a69a" if 50 < row["RSI"] < 70 else ("#f59e0b" if row["RSI"] <= 35 else "#e0e0e0")
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{sig_color}">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                    <div>
                      <div style="font-size:18px;font-weight:800;color:{sig_color}">{row['Stock']}</div>
                      <div style="font-size:11px;color:#6b7280">{row['Sector']} &nbsp;|&nbsp;
                        <span style="background:{sig_color};color:#000;padding:1px 8px;border-radius:10px;font-weight:700;font-size:11px">{row['Signal']}</span>
                      </div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">LTP</div>
                      <div style="font-size:18px;font-weight:700">₹{row['LTP']:,}</div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">Today</div>
                      <div style="font-size:16px;font-weight:700;color:{chg_color}">{row['Chg%']:+.2f}%</div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">RSI</div>
                      <div style="font-size:16px;font-weight:700;color:{rsi_color}">{row['RSI']}</div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">Volume</div>
                      <div style="font-size:16px;font-weight:700">{row['Vol Ratio']}x</div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">Score</div>
                      <div style="font-size:20px;font-weight:800;color:{sig_color}">{row['Score']}/10</div>
                    </div>
                    <div style="text-align:center">
                      <div class="trade-label">From 52W High</div>
                      <div style="font-size:14px;font-weight:700">{row['From 52H%']}%</div>
                    </div>
                  </div>
                  <div style="margin-top:8px;font-size:11px;color:#9ca3af">📋 {row['Reasons']}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("### 🔴 Top Stocks to Avoid / Short Watch")
        top_avoids = screen_df[screen_df["Signal"] == "AVOID"].tail(5)
        if not top_avoids.empty:
            avoid_data = top_avoids[["Stock", "Sector", "LTP", "Chg%", "RSI", "Score", "Reasons"]].copy()
            avoid_data = avoid_data.sort_values("Score")
            st.dataframe(avoid_data.set_index("Stock"), use_container_width=True)

        st.divider()
        st.markdown("### 📋 Full Screener Table")
        display_cols = ["Stock", "Sector", "LTP", "Chg%", "RSI", "Vol Ratio", "From 52H%", "Score", "Signal"]
        disp = filtered_df[display_cols].copy()

        def color_signal(val):
            if val == "BUY":    return "background-color:#0d2618;color:#26a69a;font-weight:700"
            if val == "WATCH":  return "background-color:#2a1f0d;color:#f59e0b;font-weight:700"
            if val == "AVOID":  return "background-color:#2a0d0d;color:#ef5350;font-weight:700"
            return ""

        def color_score(val):
            try:
                v = float(val)
                if v >= 4:  return "color:#26a69a;font-weight:700"
                if v >= 2:  return "color:#f59e0b;font-weight:700"
                if v <= -2: return "color:#ef5350;font-weight:700"
            except Exception:
                pass
            return ""

        st.dataframe(
            disp.style
                .map(color_signal, subset=["Signal"])
                .map(color_score, subset=["Score"]),
            use_container_width=True, height=420, hide_index=True,
        )

        st.markdown("""
        <div style="background:#1a1d2e;border-radius:8px;padding:12px 16px;margin-top:8px;
                    border-left:4px solid #f59e0b;font-size:12px;color:#9ca3af">
        ⚠️ <b style="color:#f59e0b">Disclaimer:</b>
        These scores use technical indicators on daily data. They are for research and swing trade ideas only —
        not financial advice. Always do your own analysis before investing. Past performance does not guarantee future returns.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 10 — Mutual Funds
# ══════════════════════════════════════════════════════════════════════════════
with tab10:
    st.markdown("## 💰 Mutual Fund Recommender")
    st.caption("Answer 3 questions — the dashboard will suggest the best mutual funds for your profile.")

    st.markdown("### Tell me about yourself")
    mf_c1, mf_c2, mf_c3 = st.columns(3)
    with mf_c1:
        mf_risk = st.selectbox("Risk Profile", [
            "Conservative — I don't like losing money",
            "Moderate — I can handle some ups and downs",
            "Aggressive — I want maximum growth",
        ])
    with mf_c2:
        mf_goal = st.selectbox("Investment Goal", [
            "Wealth Creation",
            "Retirement",
            "Tax Saving (80C)",
            "Monthly Income",
            "Emergency Fund",
            "Short-term Savings",
            "Parking Money",
        ])
    with mf_c3:
        mf_horizon = st.selectbox("Investment Horizon", [
            "< 1 year",
            "1 – 3 years",
            "3 – 5 years",
            "5 – 7 years",
            "7+ years",
        ])

    mf_sip = st.number_input("Monthly SIP Amount (₹)", min_value=100, value=5000, step=500)

    # Map selections to filter keys
    risk_map = {
        "Conservative — I don't like losing money": "Conservative",
        "Moderate — I can handle some ups and downs": "Moderate",
        "Aggressive — I want maximum growth": "Aggressive",
    }
    user_risk    = risk_map[mf_risk]
    user_goal    = mf_goal
    user_horizon = mf_horizon

    # Filter and score funds
    def mf_score(fund: dict) -> int:
        s = 0
        if user_risk in fund["profiles"]:                     s += 3
        elif user_risk == "Moderate" and "Moderate-High" in fund["risk"]: s += 2
        elif user_risk == "Aggressive" and fund["risk"] in ("High", "Very High"): s += 2
        elif user_risk == "Conservative" and fund["risk"] == "Low":       s += 3
        if user_goal in fund["goal"]:                         s += 3
        h_map = {
            "< 1 year":   ["< 1y", "1-3y"],
            "1 – 3 years":["1-3y", "3y+"],
            "3 – 5 years":["3y+", "5y+"],
            "5 – 7 years":["5y+", "7y+", "10y+"],
            "7+ years":   ["7y+", "10y+", "5y+"],
        }
        for h in h_map.get(user_horizon, []):
            if h in fund["horizon"]: s += 2; break
        if mf_sip >= fund["min_sip"]: s += 1
        return s

    scored_funds = sorted(MUTUAL_FUNDS, key=mf_score, reverse=True)
    top_funds    = [f for f in scored_funds if mf_score(f) >= 4][:6]
    if not top_funds:
        top_funds = scored_funds[:4]

    st.divider()
    st.markdown(f"### 🎯 Recommended Funds for You")
    st.caption(f"Profile: **{user_risk}** | Goal: **{user_goal}** | Horizon: **{user_horizon}** | SIP: ₹{mf_sip:,}/month")

    with st.spinner("Fetching live NAV from AMFI..."):
        amfi_navs = fetch_amfi_navs()
    if amfi_navs:
        st.caption(f"✅ Live NAV loaded from AMFI — {len(amfi_navs):,} funds")
    else:
        st.caption("⚠️ NAV fetch failed — showing fund details without live NAV")

    risk_colors = {
        "Very Low": "#3b82f6", "Low": "#26a69a", "Moderate": "#f59e0b",
        "Moderate-High": "#f97316", "High": "#ef5350", "Very High": "#dc2626",
    }
    star_map = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐"}

    for i, fund in enumerate(top_funds):
        rc = risk_colors.get(fund["risk"], "#9ca3af")
        ret_color_1y = "#26a69a" if fund["ret_1y"] > 15 else ("#f59e0b" if fund["ret_1y"] > 10 else "#ef5350")
        corpus_10y = round(mf_sip * (((1 + fund["ret_5y"]/100/12) ** 120 - 1) / (fund["ret_5y"]/100/12)), 0)

        # Live NAV lookup
        nav_data = lookup_nav(amfi_navs, fund.get("amfi_search", []))
        if nav_data:
            nav_html = f"""
              <div style="text-align:center;border:1px solid {rc};border-radius:8px;padding:6px 14px">
                <div class="trade-label">Live NAV</div>
                <div style="font-size:20px;font-weight:800;color:{rc}">₹{nav_data['nav']:,.2f}</div>
                <div style="font-size:10px;color:#6b7280">as of {nav_data['date']}</div>
              </div>"""
        else:
            nav_html = '<div style="text-align:center"><div class="trade-label">NAV</div><div style="color:#6b7280;font-size:12px">N/A</div></div>'

        st.markdown(f"""
        <div class="metric-card" style="border-left-color:{rc};margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
            <div style="flex:1;min-width:200px">
              <div style="font-size:16px;font-weight:800;color:#e0e0e0">#{i+1} {fund['name']}</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:2px">
                {fund['category']} &nbsp;|&nbsp;
                <span style="color:{rc};font-weight:700">{fund['risk']} Risk</span> &nbsp;|&nbsp;
                {star_map.get(fund['stars'], '⭐⭐⭐')} &nbsp;|&nbsp;
                Min SIP: ₹{fund['min_sip']:,} &nbsp;|&nbsp; AUM: {fund['aum']}
              </div>
              <div style="font-size:12px;color:#6b7280;margin-top:4px">🕐 Horizon: {fund['horizon']}</div>
            </div>
            <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
              {nav_html}
              <div style="text-align:center">
                <div class="trade-label">1Y Return</div>
                <div style="font-size:18px;font-weight:800;color:{ret_color_1y}">{fund['ret_1y']}%</div>
              </div>
              <div style="text-align:center">
                <div class="trade-label">3Y Return</div>
                <div style="font-size:16px;font-weight:700;color:#26a69a">{fund['ret_3y']}%</div>
              </div>
              <div style="text-align:center">
                <div class="trade-label">5Y Return</div>
                <div style="font-size:16px;font-weight:700;color:#26a69a">{fund['ret_5y']}%</div>
              </div>
              <div style="text-align:center">
                <div class="trade-label">₹{mf_sip:,} SIP → 10Y</div>
                <div style="font-size:16px;font-weight:700;color:#a855f7">₹{corpus_10y/100000:.1f}L</div>
              </div>
            </div>
          </div>
          <div style="margin-top:10px;font-size:13px;color:#d1d5db">
            💡 <b>Why this fund:</b> {fund['why']}
          </div>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📚 Fund Categories — Quick Guide")
    guide_data = {
        "Category":     ["Liquid Fund", "Short Duration Debt", "Index Fund (Nifty 50)", "Large Cap", "Flexi Cap", "Mid Cap", "Small Cap", "ELSS", "Hybrid/BAF"],
        "Best For":     ["Emergency Fund / Parking", "1-3 Year Goals", "Safe Long-term Wealth", "Stable Growth", "All-weather Portfolio", "High Growth", "Maximum Growth", "Tax Saving + Growth", "First-time Investors"],
        "Risk":         ["Very Low", "Low", "Moderate", "Moderate", "Moderate", "High", "Very High", "Moderate-High", "Moderate"],
        "Min Horizon":  ["Any", "1 Year", "3 Years", "3 Years", "5 Years", "7 Years", "10 Years", "3 Years (Lock-in)", "3 Years"],
        "Expected Return": ["6-7%", "7-8%", "12-15%", "12-16%", "14-18%", "18-25%", "20-30%", "16-24%", "14-18%"],
    }
    st.dataframe(pd.DataFrame(guide_data).set_index("Category"), use_container_width=True)

    st.markdown("""
    <div style="background:#1a1d2e;border-radius:8px;padding:14px 18px;margin-top:12px;
                border-left:4px solid #3b82f6;font-size:13px;color:#9ca3af">
    ⚠️ <b style="color:#3b82f6">Disclaimer:</b>
    Returns shown are approximate historical figures for reference only.
    Mutual fund investments are subject to market risks. Past returns do not guarantee future performance.
    Please read the Scheme Information Document (SID) carefully before investing.
    Consider consulting a SEBI-registered financial advisor for personalised advice.
    </div>""", unsafe_allow_html=True)


st.divider()
st.caption("📡 Dashboard auto-refreshes every 30 seconds during market hours (9:15 AM – 3:30 PM IST) via browser meta-refresh.")
