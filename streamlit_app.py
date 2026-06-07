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
import sys

# Local modules (same folder)
_dashboard_dir = os.path.dirname(os.path.abspath(__file__))
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

# Performance & caching
try:
    from cache_manager import CacheManager, QuoteCache, CandleCache, IndicatorCache, OptionChainCache
    _CACHE_OK = True
except Exception:
    _CACHE_OK = False

# Options viewer
try:
    import options_viewer as ov
    _OPTIONS_VIEWER_OK = True
except Exception:
    _OPTIONS_VIEWER_OK = False

# Zerodha (primary data source)
try:
    import zerodha_fetcher as zd
    _ZERODHA_AVAILABLE = zd.is_available()
except Exception:
    _ZERODHA_AVAILABLE = False

# Trade recommendation engine
try:
    import trade_engine as te
    _TRADE_ENGINE_OK = True
except Exception:
    _TRADE_ENGINE_OK = False

# Market intelligence engine
try:
    import market_intelligence as mi
    _MI_OK = True
except Exception:
    _MI_OK = False

# AI Expert chatbot
try:
    import ai_expert
    _AI_OK = True
except Exception:
    _AI_OK = False

# Trade Advisor & Risk Management (NEW)
try:
    import trade_advisor_page
    import trade_journal
    import ui_components
    import risk_manager as rm
    _TRADE_ADVISOR_OK = True
except Exception as e:
    _TRADE_ADVISOR_OK = False

# Upstox (secondary data source, fallback)
try:
    import config as upstox_config
    import data_fetcher as upstox_df
    _UPSTOX_AVAILABLE = bool(upstox_config.ACCESS_TOKEN)
except Exception:
    _UPSTOX_AVAILABLE = False

st.set_page_config(
    page_title="India Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

IST = pytz.timezone("Asia/Kolkata")

# ── Owner detection via secret URL key ───────────────────────────────────────
# Owner accesses: https://your-app.streamlit.app/?key=YOUR_OWNER_KEY
# Public users access the normal URL — toolbar is hidden for them
_OWNER_KEY = os.getenv("OWNER_KEY", "vissu@dashboard2026")  # change in .env / Streamlit secrets

def _check_owner() -> bool:
    """Returns True if current session belongs to the owner."""
    # Persist across page interactions via session_state
    if st.session_state.get("_is_owner"):
        return True
    params = st.query_params
    if params.get("key") == _OWNER_KEY:
        st.session_state["_is_owner"] = True
        return True
    return False

_IS_OWNER = _check_owner()

# ── Dark theme CSS ────────────────────────────────────────────────────────────
# Toolbar hidden for PUBLIC users; owner sees full Streamlit UI
_public_hide_css = "" if _IS_OWNER else """
/* Hide Streamlit toolbar icons and sidebar toggle for public users */
header[data-testid="stHeader"]            { display: none !important; }
[data-testid="stToolbar"]                 { display: none !important; }
[data-testid="collapsedControl"]          { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.block-container { padding-top: 1rem !important; }
"""

st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   TRADINGVIEW-INSPIRED DESIGN SYSTEM
   bg: #131722  panel: #1e222d  border: #2a2e39
   bull: #089981  bear: #f23645  blue: #2962ff  neutral: #b2b5be
   ═══════════════════════════════════════════════════════════════════════════ */

html, body, .stApp {
    background-color: #131722 !important;
    color: #d1d4dc !important;
    font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", "Inter",
                 Roboto, Ubuntu, sans-serif !important;
    font-size: 13px;
}
html { background-color: #131722 !important; }

.stApp > header                         { display: none !important; }
footer                                  { visibility: hidden !important; }
#MainMenu                               { visibility: hidden !important; }
.block-container                        { padding: 1rem 2rem 2rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"]        { background: #1e222d !important; border-right: 1px solid #2a2e39; }
[data-stale]                            { opacity: 0.75; transition: opacity 0.2s ease; }

/* Tabs — TradingView underline style */
[data-testid="stTabs"] > div:first-child {
    background: #131722 !important;
    border-bottom: 1px solid #2a2e39 !important;
    padding: 0 !important; gap: 0 !important;
}
button[data-baseweb="tab"] {
    background: transparent !important; color: #9598a1 !important;
    border: none !important; border-bottom: 2px solid transparent !important;
    padding: 10px 16px !important; font-size: 13px !important;
    font-weight: 500 !important; border-radius: 0 !important;
    transition: color 0.15s, border-color 0.15s !important;
}
button[data-baseweb="tab"]:hover { color: #d1d4dc !important; background: rgba(42,46,57,0.5) !important; }
button[aria-selected="true"][data-baseweb="tab"] {
    color: #d1d4dc !important; border-bottom: 2px solid #2962ff !important;
    background: transparent !important; font-weight: 600 !important;
}
[data-testid="stTabsContent"] { padding: 1rem 0 !important; }

/* Index / Metric cards */
.metric-card {
    background: #1e222d; border: 1px solid #2a2e39;
    border-radius: 6px; padding: 12px 16px; margin-bottom: 8px;
    transition: border-color 0.15s;
}
.metric-card:hover { border-color: #363a45; background: #232732; }

[data-testid="stMetric"] {
    background: #1e222d !important; border: 1px solid #2a2e39 !important;
    border-radius: 6px !important; padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] { color: #9598a1 !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.08em; }
[data-testid="stMetricValue"] { color: #d1d4dc !important; font-size: 1.4rem !important; font-weight: 600 !important; font-variant-numeric: tabular-nums; }

/* Color tokens */
.bull    { color: #089981 !important; }
.bear    { color: #f23645 !important; }
.neutral { color: #b2b5be !important; }

/* Section titles */
.section-title {
    font-size: 12px; font-weight: 600; color: #9598a1;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 20px 0 10px; padding-bottom: 6px;
    border-bottom: 1px solid #2a2e39;
}

/* Pills */
.pill { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin: 2px; }
.pill-green  { background: rgba(8,153,129,0.15);  color: #089981; border: 1px solid rgba(8,153,129,0.3); }
.pill-red    { background: rgba(242,54,69,0.15);   color: #f23645; border: 1px solid rgba(242,54,69,0.3); }
.pill-yellow { background: rgba(255,160,0,0.15);   color: #ffa500; border: 1px solid rgba(255,160,0,0.3); }

/* Signal boxes */
.signal-box { background: #1e222d; border: 1px solid #2a2e39; border-radius: 4px; padding: 10px 14px; margin: 4px 0; }
.signal-buy  { background: #089981; color: #fff; padding: 5px 14px; border-radius: 4px; font-weight: 700; font-size: 12px; display: inline-block; margin: 3px 3px 3px 0; }
.signal-exit { background: #f23645; color: #fff; padding: 5px 14px; border-radius: 4px; font-weight: 700; font-size: 12px; display: inline-block; margin: 3px; }
.signal-wait { background: #ffa500; color: #131722; padding: 5px 14px; border-radius: 4px; font-weight: 700; font-size: 12px; display: inline-block; margin: 3px; }

/* Trade cards */
.trade-card-call { background: #1a2a23; border: 1px solid #089981; border-radius: 6px; padding: 18px 20px; margin: 6px 0; }
.trade-card-put  { background: #2a1a1e; border: 1px solid #f23645; border-radius: 6px; padding: 18px 20px; margin: 6px 0; }
.trade-header { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.trade-strike { font-size: 13px; color: #9598a1; margin-bottom: 12px; }
.trade-row    { display: flex; justify-content: space-between; margin: 5px 0; }
.trade-label  { font-size: 12px; color: #9598a1; text-transform: uppercase; letter-spacing: 0.08em; }
.trade-value  { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }

.conf-high { color: #089981; font-weight: 700; }
.conf-med  { color: #ffa500; font-weight: 700; }
.conf-low  { color: #f23645; font-weight: 700; }

.no-trade-banner { background: rgba(255,160,0,0.08); border: 1px solid #ffa500; border-radius: 6px; padding: 16px; text-align: center; font-size: 15px; font-weight: 600; color: #ffa500; margin: 16px 0; }

.checklist-item-ok   { background:#0d1f18; border-left:3px solid #089981; border-radius:4px; padding:9px 14px; margin:4px 0; font-size:13px; }
.checklist-item-warn { background:#1f1a0d; border-left:3px solid #ffa500; border-radius:4px; padding:9px 14px; margin:4px 0; font-size:13px; }
.checklist-item-bad  { background:#1f0d0f; border-left:3px solid #f23645; border-radius:4px; padding:9px 14px; margin:4px 0; font-size:13px; }

.alert-box { background: #1e222d; border: 1px solid #2962ff; border-radius: 6px; padding: 12px 16px; margin: 6px 0; }
.alert-triggered { border-color: #f23645 !important; background: #1f0d0f !important; }

/* Buttons */
[data-testid="baseButton-secondary"] {
    background: #1e222d !important; color: #d1d4dc !important;
    border: 1px solid #2a2e39 !important; border-radius: 4px !important;
    font-size: 12px !important; font-weight: 500 !important;
}
[data-testid="baseButton-secondary"]:hover { background: #2a2e39 !important; }
[data-testid="baseButton-primary"] {
    background: #2962ff !important; color: #fff !important;
    border: none !important; border-radius: 4px !important;
    font-size: 12px !important; font-weight: 600 !important;
}
[data-testid="baseButton-primary"]:hover { background: #1e53e5 !important; }

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: #1e222d !important; color: #d1d4dc !important;
    border: 1px solid #2a2e39 !important; border-radius: 4px !important;
}
[data-testid="stTextInput"] input:focus { border-color: #2962ff !important; }

/* Chat */
[data-testid="stChatInput"] textarea { background: #1e222d !important; border: 1px solid #2a2e39 !important; color: #d1d4dc !important; border-radius: 6px !important; }
[data-testid="stChatMessageContent"] { background: #1e222d !important; border: 1px solid #2a2e39 !important; border-radius: 6px !important; }

/* Expanders */
[data-testid="stExpander"] { background: #1e222d !important; border: 1px solid #2a2e39 !important; border-radius: 6px !important; }
[data-testid="stExpander"] summary { color: #9598a1 !important; font-size: 12px !important; }

/* Dividers */
hr { border-color: #2a2e39 !important; margin: 16px 0 !important; }

/* DataFrames */
[data-testid="stDataFrame"] { border: 1px solid #2a2e39 !important; border-radius: 6px !important; }
[data-testid="stDataFrame"] th { background: #1e222d !important; color: #9598a1 !important; font-size: 12px !important; text-transform: uppercase; }
[data-testid="stDataFrame"] td { background: #131722 !important; color: #d1d4dc !important; font-size: 12px !important; }
[data-testid="stDataFrame"] tr:hover td { background: #1e222d !important; }

/* Scrollbar */
::-webkit-scrollbar              { width: 6px; height: 6px; }
::-webkit-scrollbar-track        { background: #131722; }
::-webkit-scrollbar-thumb        { background: #2a2e39; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover  { background: #363a45; }

/* Headings */
h1 { font-size: 20px !important; font-weight: 700 !important; color: #d1d4dc !important; margin: 0 0 4px !important; }
h2 { font-size: 16px !important; font-weight: 600 !important; color: #d1d4dc !important; }
h3 { font-size: 14px !important; font-weight: 600 !important; color: #b2b5be !important; }
</style>
""", unsafe_allow_html=True)

# ── Conditionally hide toolbar for public users (owner sees full UI) ──────────
if not _IS_OWNER:
    st.markdown("""
    <style>
    header[data-testid="stHeader"]            { display: none !important; }
    [data-testid="stToolbar"]                 { display: none !important; }
    [data-testid="collapsedControl"]          { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Tickers ───────────────────────────────────────────────────────────────────
TICKERS = {
    "Nifty 50":     "^NSEI",
    "Bank Nifty":   "^NSEBANK",
    "India VIX":    "^INDIAVIX",
    "Sensex":       "^BSESN",
    "Nifty IT":     "^CNXIT",
    "Fin Nifty":    "^CNXFIN",
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

# ── Ticker ↔ Upstox instrument key mapping ────────────────────────────────────
_YF_TO_UPSTOX = {
    "^NSEI":      "NSE_INDEX|Nifty 50",
    "^NSEBANK":   "NSE_INDEX|Nifty Bank",
    "^BSESN":     "BSE_INDEX|SENSEX",
    "^INDIAVIX":  "NSE_INDEX|India VIX",
    "^CNXIT":     "NSE_INDEX|Nifty IT",
    "^CNXFIN":    "NSE_INDEX|Nifty Fin Service",
    "^NSEMDCP50": "NSE_INDEX|NIFTY MID SELECT",
}

# Option chain keys and metadata for tradeable indices
_OPTION_INDEX_META = {
    "Nifty 50":   {"upstox_key": "NSE_INDEX|Nifty 50",       "step": 50,  "lot": 75,  "yf": "^NSEI"},
    "Bank Nifty": {"upstox_key": "NSE_INDEX|Nifty Bank",      "step": 100, "lot": 30,  "yf": "^NSEBANK"},
    "Fin Nifty":  {"upstox_key": "NSE_INDEX|Nifty Fin Service","step": 50,  "lot": 40,  "yf": "^CNXFIN"},
}
_YF_INT_TO_UPSTOX = {
    "1m": "1minute", "2m": "2minute", "5m": "5minute",
    "15m": "15minute", "30m": "30minute",
    "1h": "60minute", "60m": "60minute",
    "1d": "day", "1wk": "week", "1mo": "month",
}
_PERIOD_TO_DAYS = {
    "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
    "6mo": 180, "1y": 365, "2y": 730,
}

def _upstox_quote(upstox_key: str) -> dict:
    """Fetch single index quote from Upstox. Returns get_quote-compatible dict."""
    try:
        import requests as _req
        headers = {"Authorization": f"Bearer {upstox_config.ACCESS_TOKEN}", "Accept": "application/json"}
        r = _req.get(upstox_config.BASE_URL + "/market-quote/quotes",
                     params={"instrument_key": upstox_key}, headers=headers, timeout=8)
        r.raise_for_status()
        v = list(r.json().get("data", {}).values())[0]
        ltp  = float(v.get("last_price") or 0)
        chg  = float(v.get("net_change") or 0)
        ohlc = v.get("ohlc") or {}
        prev = round(ltp - chg, 2)
        pct  = (chg / prev * 100) if prev else 0
        return {
            "ltp":  ltp,
            "open": float(ohlc.get("open") or ltp),
            "high": float(ohlc.get("high") or ltp),
            "low":  float(ohlc.get("low")  or ltp),
            "prev": prev, "chg": chg, "pct": pct,
        }
    except Exception:
        return {}


def _upstox_candles(upstox_key: str, upstox_interval: str,
                    from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch OHLCV candles from Upstox and return normalised DataFrame."""
    try:
        import requests as _req
        headers = {"Authorization": f"Bearer {upstox_config.ACCESS_TOKEN}", "Accept": "application/json"}
        _intraday = {"1minute","2minute","5minute","10minute","15minute","30minute","60minute"}
        if upstox_interval in _intraday:
            url = f"{upstox_config.BASE_URL}/historical-candle/intraday/{upstox_key}/{upstox_interval}"
            params = {}
        else:
            url = f"{upstox_config.BASE_URL}/historical-candle/{upstox_key}/{upstox_interval}/{to_date}/{from_date}"
            params = {}
        r = _req.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        candles = r.json().get("data", {}).get("candles", [])
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume","oi"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


# ── Data helpers ──────────────────────────────────────────────────────────────
def _fetch_quote_raw(ticker: str) -> dict:
    """Raw quote fetch (used by cache manager)."""
    if _UPSTOX_AVAILABLE and ticker in _YF_TO_UPSTOX:
        q = _upstox_quote(_YF_TO_UPSTOX[ticker])
        if q:
            return q
    # Yahoo Finance fallback
    try:
        fi = yf.Ticker(ticker).fast_info
        prev = 0.0
        try:
            daily = yf.download(ticker, period="5d", interval="1d",
                                progress=False, auto_adjust=True,
                                multi_level_index=False)
            if len(daily) >= 2:
                prev = float(daily["Close"].iloc[-2])
        except Exception:
            pass
        if not prev:
            prev = float(fi.previous_close) if hasattr(fi, "previous_close") and fi.previous_close else 0.0
        try:
            intra = yf.download(ticker, period="1d", interval="1m",
                                progress=False, auto_adjust=True,
                                multi_level_index=False)
            if not intra.empty and "Close" in intra.columns and len(intra) > 1:
                ltp   = float(intra["Close"].iloc[-1])
                open_ = float(intra["Open"].iloc[0])
                high  = float(intra["High"].max())
                low   = float(intra["Low"].min())
                if not prev: prev = open_
                chg = ltp - prev
                pct = (chg / prev) * 100 if prev else 0
                return {"ltp": ltp, "open": open_, "high": high, "low": low,
                        "prev": prev, "chg": chg, "pct": pct}
        except Exception:
            pass
        ltp   = float(fi.last_price)
        open_ = float(fi.open)     if fi.open     else ltp
        high  = float(fi.day_high) if fi.day_high else ltp
        low   = float(fi.day_low)  if fi.day_low  else ltp
        if not prev: prev = ltp
        chg = ltp - prev
        pct = (chg / prev) * 100 if prev else 0
        return {"ltp": ltp, "open": open_, "high": high, "low": low,
                "prev": prev, "chg": chg, "pct": pct}
    except Exception:
        return {}


def get_quote(ticker: str) -> dict:
    """Get quote with intelligent caching (90s TTL)."""
    if _CACHE_OK:
        return QuoteCache.get_quote(ticker, _fetch_quote_raw)
    return _fetch_quote_raw(ticker)


def _fetch_candles_raw(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Raw candle fetch (used by cache manager)."""
    today     = datetime.now(IST).date()
    days      = _PERIOD_TO_DAYS.get(period, 5)
    from_date = str(today - timedelta(days=days))
    to_date   = str(today)

    # 1. Zerodha (most accurate)
    if _ZERODHA_AVAILABLE:
        df = zd.get_candles(ticker, interval, from_date, to_date)
        if not df.empty:
            return df

    # 2. Upstox fallback
    if _UPSTOX_AVAILABLE and ticker in _YF_TO_UPSTOX:
        upstox_key = _YF_TO_UPSTOX[ticker]
        upstox_int = _YF_INT_TO_UPSTOX.get(interval, "15minute")
        df = _upstox_candles(upstox_key, upstox_int, from_date, to_date)
        if not df.empty:
            return df
    # Yahoo Finance fallback
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        df = df.rename(columns={"datetime": "timestamp", "date": "timestamp"})
        if "timestamp" not in df.columns:
            df = df.rename(columns={df.columns[0]: "timestamp"})
        return df
    except Exception:
        return pd.DataFrame()


def get_candles(ticker: str, period: str = "5d", interval: str = "15m") -> pd.DataFrame:
    """Get candles with smart caching (60s for intraday, 1h for daily)."""
    if _CACHE_OK:
        return CandleCache.get_candles(ticker, period, interval, _fetch_candles_raw)
    return _fetch_candles_raw(ticker, period, interval)


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

    # Safe nested dict access
    def safe_get(d, key, subkey):
        val = d.get(key) if d else None
        return val.get(subkey) if val and isinstance(val, dict) else None

    sp_pct    = safe_get(global_quotes, "S&P 500",      "pct")
    nas_pct   = safe_get(global_quotes, "Nasdaq",        "pct")
    nik_pct   = safe_get(global_quotes, "Nikkei 225",    "pct")
    crude_pct = safe_get(global_quotes, "Crude Oil",     "pct")
    gold_pct  = safe_get(global_quotes, "Gold",          "pct")
    dxy_pct   = safe_get(global_quotes, "Dollar Index",  "pct")
    usdinr_pct= safe_get(global_quotes, "USD/INR",       "pct")
    tnx_ltp   = safe_get(global_quotes, "US 10Y Yield",  "ltp")

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
    if score >= 4:     label, color = "Strong Global Tailwind 🌬️", "#089981"
    elif score >= 2:   label, color = "Mild Positive Cues 🟢",      "#089981"
    elif score >= -1:  label, color = "Mixed / Neutral 🟡",          "#ffa500"
    elif score >= -3:  label, color = "Mild Headwinds 🟠",           "#f97316"
    else:              label, color = "Strong Headwinds ⛔",          "#f23645"

    return {"score": score, "label": label, "color": color, "factors": factors}


@st.cache_data(ttl=300)
def screen_nifty50() -> pd.DataFrame:
    """Score all Nifty 50 stocks using RSI, EMA trend, MACD, volume, 52W position.
    LTP & change: Zerodha real-time (if available), else yfinance.
    Historical indicators (RSI, MACD, EMA): yfinance batch download (efficient).
    """
    tickers = list(NIFTY50_STOCKS.values())
    # Fetch 6-month daily history for indicator calculations (yfinance batch)
    try:
        raw = yf.download(
            " ".join(tickers), period="6mo", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker",
        )
    except Exception:
        return pd.DataFrame()

    # Zerodha real-time quotes for all 50 stocks (1 batch API call)
    zd_quotes = zd.get_stock_quotes() if _ZERODHA_AVAILABLE else {}

    results = []
    for name, ticker in NIFTY50_STOCKS.items():
        try:
            df = raw[ticker].dropna() if ticker in raw.columns.get_level_values(0) else pd.DataFrame()
            if df.empty or len(df) < 30:
                continue
            close = df["Close"]

            # Use Zerodha real-time LTP & change if available
            if name in zd_quotes and zd_quotes[name]["ltp"] > 0:
                zq  = zd_quotes[name]
                ltp = zq["ltp"]
                pct = zq["pct"]
                vol_today = zq["volume"]
            else:
                ltp = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                pct = (ltp - prev) / prev * 100
                vol_today = None
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
            # Volume ratio (Zerodha live vol preferred over yfinance historical)
            vol_ratio = 1.0
            if "Volume" in df.columns:
                avg = float(df["Volume"].tail(20).mean())
                vol = float(vol_today) if vol_today else float(df["Volume"].iloc[-1])
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
    # VWAP — use volume if available; fall back to price-only typical-price average
    if "volume" in df.columns and df["volume"].sum() > 0:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        vol = df["volume"].replace(0, np.nan)
        df["vwap"] = (tp * vol).cumsum() / vol.cumsum()
        # If still all-NaN (index has no volume), use simple TP cumulative mean
        if df["vwap"].isna().all():
            df["vwap"] = tp.expanding().mean()
    else:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = tp.expanding().mean()
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


def safe_quote_get(quotes_dict: dict, key: str, subkey: str, default=0):
    """Safely get quote data with multiple levels of fallback."""
    if not quotes_dict:
        return default
    quote = quotes_dict.get(key)
    if not quote or not isinstance(quote, dict):
        return default
    return quote.get(subkey, default)


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    o = now.replace(hour=9, minute=15, second=0, microsecond=0)
    c = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return o <= now <= c


def next_expiry_info() -> dict:
    now   = datetime.now(IST)
    today = now.date()
    after_close = now.hour > 15 or (now.hour == 15 and now.minute >= 30)

    # Nifty weekly = Tuesday (weekday 1); BankNifty weekly = Wednesday (weekday 2)
    n_days = (1 - today.weekday()) % 7
    b_days = (2 - today.weekday()) % 7

    # On expiry day after market close, roll to next week
    if n_days == 0 and after_close:
        n_days = 7
    if b_days == 0 and after_close:
        b_days = 7

    n_date = today + timedelta(days=n_days)
    b_date = today + timedelta(days=b_days)
    n_label = "Today" if n_days == 0 else n_date.strftime("%d %b")
    b_label = "Today" if b_days == 0 else b_date.strftime("%d %b")
    return {
        "nifty":     {"date": n_label, "days": n_days,
                      "date_str": n_date.strftime("%Y-%m-%d")},
        "banknifty": {"date": b_label, "days": b_days,
                      "date_str": b_date.strftime("%Y-%m-%d")},
    }


# Upstox key → yfinance ticker mapping for batch index quotes
_UPSTOX_INDEX_KEYS = {
    "^NSEI":    "NSE_INDEX|Nifty 50",
    "^NSEBANK": "NSE_INDEX|Nifty Bank",
    "^BSESN":   "BSE_INDEX|SENSEX",
    "^INDIAVIX":"NSE_INDEX|India VIX",
    "^CNXIT":   "NSE_INDEX|Nifty IT",
    "^CNXFIN":  "NSE_INDEX|Nifty Fin Service",
    "NIFTY_MID":"NSE_INDEX|NIFTY MID SELECT",
}

@st.cache_data(ttl=15)
def get_upstox_index_quotes() -> dict:
    """
    Fetch live quotes for all indices from Upstox in one call.
    Returns {yf_ticker: {"ltp","open","high","low","prev","chg","pct"}}
    """
    if not _UPSTOX_AVAILABLE:
        return {}
    try:
        joined = ",".join(_UPSTOX_INDEX_KEYS.values())
        r = upstox_df._headers.__func__(upstox_df) if False else None  # unused
        import requests as _req
        headers = {"Authorization": f"Bearer {upstox_config.ACCESS_TOKEN}", "Accept": "application/json"}
        resp = _req.get(upstox_config.BASE_URL + "/market-quote/quotes",
                        params={"instrument_key": joined}, headers=headers, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", {})
        result = {}
        inv_map = {v.replace("|", ":"): k for k, v in _UPSTOX_INDEX_KEYS.items()}
        for api_key, v in raw.items():
            yf_ticker = inv_map.get(api_key)
            if not yf_ticker:
                continue
            ltp  = float(v.get("last_price") or 0)
            chg  = float(v.get("net_change") or 0)
            ohlc = v.get("ohlc") or {}
            prev = round(ltp - chg, 2) if ltp and chg else float(ohlc.get("close") or ltp)
            pct  = (chg / prev * 100) if prev else 0
            result[yf_ticker] = {
                "ltp":  ltp,
                "open": float(ohlc.get("open") or ltp),
                "high": float(ohlc.get("high") or ltp),
                "low":  float(ohlc.get("low")  or ltp),
                "prev": prev,
                "chg":  chg,
                "pct":  pct,
            }
        return result
    except Exception:
        return {}


@st.cache_data(ttl=12)
def get_live_chain(instrument_key: str, expiry_date: str) -> dict:
    """
    Fetch live option premiums from Upstox.
    Returns {strike: {"ce": ltp, "pe": ltp, "ce_iv": iv, "pe_iv": iv}}
    Falls back to empty dict if token missing or API fails.
    """
    if not _UPSTOX_AVAILABLE:
        return {}
    try:
        df = upstox_df.get_option_chain(instrument_key, expiry_date)
        if df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            result[int(row["strike"])] = {
                "ce":     float(row.get("ce_ltp",    0) or 0),
                "pe":     float(row.get("pe_ltp",    0) or 0),
                "ce_iv":  float(row.get("ce_iv",     0) or 0),
                "pe_iv":  float(row.get("pe_iv",     0) or 0),
                "ce_oi":  float(row.get("ce_oi",     0) or 0),
                "pe_oi":  float(row.get("pe_oi",     0) or 0),
                "ce_vol": float(row.get("ce_volume", 0) or 0),
                "pe_vol": float(row.get("pe_volume", 0) or 0),
            }
        return result
    except Exception:
        return {}


@st.cache_data(ttl=60)
def get_orb(ticker: str) -> dict:
    """Opening Range = first 15 minutes (9:15–9:30). Upstox-first."""
    try:
        if _UPSTOX_AVAILABLE and ticker in _YF_TO_UPSTOX:
            today   = datetime.now(IST).date()
            df = _upstox_candles(_YF_TO_UPSTOX[ticker], "1minute", str(today), str(today))
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                market_open_t = pd.Timestamp(today).tz_localize(IST).replace(hour=9, minute=15)
                orb_end_t     = pd.Timestamp(today).tz_localize(IST).replace(hour=9, minute=30)
                ts = df["timestamp"]
                if ts.dt.tz is None:
                    ts = ts.dt.tz_localize(IST)
                orb = df[(ts >= market_open_t) & (ts < orb_end_t)]
                if orb.empty:
                    orb = df.head(15)
                if not orb.empty:
                    return {
                        "high":  float(orb["high"].max()),
                        "low":   float(orb["low"].min()),
                        "range": float(orb["high"].max() - orb["low"].min()),
                    }
        # Yahoo fallback
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
    """Classic pivot points from previous trading day's OHLC. Upstox-first."""
    try:
        if _UPSTOX_AVAILABLE and ticker in _YF_TO_UPSTOX:
            today     = datetime.now(IST).date()
            from_date = str(today - timedelta(days=7))
            df = _upstox_candles(_YF_TO_UPSTOX[ticker], "day", from_date, str(today))
            if not df.empty and len(df) >= 2:
                prev = df.iloc[-2]
                h = float(prev["high"]); l = float(prev["low"]); c = float(prev["close"])
                p = (h + l + c) / 3
                return {
                    "P": round(p), "R1": round(2*p - l), "R2": round(p + h - l),
                    "R3": round(h + 2*(p - l)), "S1": round(2*p - h),
                    "S2": round(p - (h - l)),   "S3": round(l - 2*(h - p)),
                }
        # Yahoo fallback
        df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
        if len(df) < 2:
            return {}
        prev = df.iloc[-2]
        h = float(prev["High"]); l = float(prev["Low"]); c = float(prev["Close"])
        p = (h + l + c) / 3
        return {
            "P": round(p), "R1": round(2*p - l), "R2": round(p + h - l),
            "R3": round(h + 2*(p - l)), "S1": round(2*p - h),
            "S2": round(p - (h - l)),   "S3": round(l - 2*(h - p)),
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
                           name: str, step: int = 50,
                           orb: dict = None, pivots: dict = None) -> dict:
    """
    Trading-expert signal engine for Indian intraday options.
    ORB breakout is primary signal; VWAP/EMA/MACD/Supertrend are confirmations.
    Returns actionable dict with index-level SL/targets, not just premium %.
    """
    if df.empty or len(df) < 20 or ltp == 0:
        return {"no_trade": True, "reason": "Insufficient data — market may not be open yet."}

    last    = df.iloc[-1]
    prev_c  = df.iloc[-2] if len(df) > 2 else last

    rsi      = float(last.get("rsi",   50) or 50)
    macd     = float(last.get("macd",   0) or 0)
    macd_s   = float(last.get("macd_s", 0) or 0)
    ema9     = float(last.get("ema9",  ltp) or ltp)
    ema21    = float(last.get("ema21", ltp) or ltp)
    ema50    = float(last.get("ema50", ltp) or ltp)
    vwap     = float(last.get("vwap",  ltp) or ltp)
    bb_up    = float(last.get("bb_upper", ltp * 1.01) or ltp * 1.01)
    bb_lo    = float(last.get("bb_lower", ltp * 0.99) or ltp * 0.99)
    st_dir   = int(last.get("supertrend_dir", 0) or 0)
    stoch_rsi= float(last.get("stoch_rsi", 0.5) or 0.5)
    obv      = float(last.get("obv",     0) or 0)
    obv_ema  = float(last.get("obv_ema", 0) or 0)
    atr_pct  = float(last.get("atr_pct", 0) or 0)
    vol      = float(last.get("volume", 0) or 0)
    avg_vol  = float(df["volume"].tail(20).mean() or 1)

    orb_high = float(orb["high"]) if orb and orb.get("high") else None
    orb_low  = float(orb["low"])  if orb and orb.get("low")  else None
    piv_p  = float(pivots["P"])  if pivots and pivots.get("P")  else None
    piv_r1 = float(pivots["R1"]) if pivots and pivots.get("R1") else None
    piv_r2 = float(pivots["R2"]) if pivots and pivots.get("R2") else None
    piv_s1 = float(pivots["S1"]) if pivots and pivots.get("S1") else None
    piv_s2 = float(pivots["S2"]) if pivots and pivots.get("S2") else None

    bull_score = 0
    bear_score = 0
    confirmations = []

    # ── ORB (primary signal — highest weight) ────────────────────────────────
    orb_bias = 0  # +1 bull, -1 bear, 0 inside
    if orb_high and orb_low:
        if ltp > orb_high:
            bull_score += 3; orb_bias = 1
            confirmations.append(f"ORB BREAKOUT UP — price above {orb_high:,.0f}")
        elif ltp < orb_low:
            bear_score += 3; orb_bias = -1
            confirmations.append(f"ORB BREAKDOWN — price below {orb_low:,.0f}")
        else:
            confirmations.append(f"Inside ORB ({orb_low:,.0f}–{orb_high:,.0f}) — wait for breakout")

    # ── Pivot vs price ────────────────────────────────────────────────────────
    if piv_p:
        if ltp > piv_p:
            bull_score += 1; confirmations.append(f"Above Pivot P ({piv_p:,.0f}) — bullish bias")
        else:
            bear_score += 1; confirmations.append(f"Below Pivot P ({piv_p:,.0f}) — bearish bias")

    # ── VWAP ─────────────────────────────────────────────────────────────────
    if ltp > vwap * 1.001:
        bull_score += 2; confirmations.append(f"Price above VWAP ({vwap:,.0f})")
    elif ltp < vwap * 0.999:
        bear_score += 2; confirmations.append(f"Price below VWAP ({vwap:,.0f})")

    # ── EMA stack ─────────────────────────────────────────────────────────────
    if ema9 > ema21 > ema50:
        bull_score += 2; confirmations.append("EMA stack bullish (9>21>50)")
    elif ema9 < ema21 < ema50:
        bear_score += 2; confirmations.append("EMA stack bearish (9<21<50)")
    elif ema9 > ema21:
        bull_score += 1; confirmations.append("EMA9 > EMA21")
    else:
        bear_score += 1; confirmations.append("EMA9 < EMA21")

    # ── Supertrend ────────────────────────────────────────────────────────────
    if st_dir == 1:
        bull_score += 2; confirmations.append("Supertrend BULLISH")
    elif st_dir == -1:
        bear_score += 2; confirmations.append("Supertrend BEARISH")

    # ── MACD ─────────────────────────────────────────────────────────────────
    if macd > macd_s and macd > 0:
        bull_score += 2; confirmations.append("MACD above zero + bullish cross")
    elif macd > macd_s:
        bull_score += 1; confirmations.append("MACD bullish cross (below zero)")
    elif macd < macd_s and macd < 0:
        bear_score += 2; confirmations.append("MACD below zero + bearish cross")
    elif macd < macd_s:
        bear_score += 1; confirmations.append("MACD bearish cross (above zero)")

    # ── RSI ───────────────────────────────────────────────────────────────────
    if 55 < rsi < 70:
        bull_score += 1; confirmations.append(f"RSI bullish zone ({rsi:.0f})")
    elif 30 < rsi < 45:
        bear_score += 1; confirmations.append(f"RSI bearish zone ({rsi:.0f})")
    elif rsi >= 70:
        confirmations.append(f"RSI overbought ({rsi:.0f}) — use tighter SL on CE")
    elif rsi <= 30:
        confirmations.append(f"RSI oversold ({rsi:.0f}) — use tighter SL on PE")

    # ── Volume surge ─────────────────────────────────────────────────────────
    if vol > avg_vol * 1.5:
        prev_close_val = float(prev_c.get("close", ltp) or ltp)
        if ltp > prev_close_val:
            bull_score += 1; confirmations.append("Volume surge with price up")
        else:
            bear_score += 1; confirmations.append("Volume surge with price down")

    # ── OBV ───────────────────────────────────────────────────────────────────
    if obv > obv_ema:
        bull_score += 1; confirmations.append("OBV rising — buying interest")
    elif obv < obv_ema:
        bear_score += 1; confirmations.append("OBV falling — selling pressure")

    net = bull_score - bear_score
    vix_f = float(vix) if vix else 15

    # ── No-trade conditions ───────────────────────────────────────────────────
    if vix_f > 28:
        return {"no_trade": True,
                "reason": f"VIX too high ({vix_f:.1f}) — extreme volatility, avoid buying options."}
    if orb_bias == 0 and orb_high and orb_low:
        # Inside ORB = no confirmed breakout
        return {
            "no_trade": True,
            "reason": (f"Price inside ORB ({orb_low:,.0f}–{orb_high:,.0f}). "
                       f"Wait for breakout above {orb_high:,.0f} (BUY CE) "
                       f"or below {orb_low:,.0f} (BUY PE) on 5-min candle close."),
            "orb_high": orb_high, "orb_low": orb_low,
            "vwap": vwap, "atm": nearest_strike(ltp, step),
            "pivots": {"P": piv_p, "R1": piv_r1, "S1": piv_s1},
        }
    if abs(net) < 2:
        return {"no_trade": True,
                "reason": "Indicators mixed — no clear edge. Wait for alignment before entering."}

    # ── Trade direction ───────────────────────────────────────────────────────
    direction = "CE" if net > 0 else "PE"
    atm       = nearest_strike(ltp, step)

    # ── Premium estimate (range) ──────────────────────────────────────────────
    exp_info    = next_expiry_info()
    days_left   = exp_info["nifty"]["days"]  if "Bank" not in name else exp_info["banknifty"]["days"]
    expiry_date = exp_info["nifty"]["date"]  if "Bank" not in name else exp_info["banknifty"]["date"]
    days_safe   = max(float(days_left), 0.5)
    vix_ann     = max(vix_f, 8) / 100
    # BS ATM approx: P = 0.4 × S × σ × √(T/252)
    # Nifty actual IV ≈ VIX × 0.77; BNF actual IV ≈ VIX × 1.00
    # Combined constant: Nifty = 0.4×0.77 = 0.308; BNF = 0.4×1.00 = 0.40
    bs_factor   = 0.40 if "Bank" in name else 0.308
    base_mid    = ltp * vix_ann * np.sqrt(days_safe / 252) * bs_factor
    base_lo   = round(base_mid * 0.75, 0)
    base_hi   = round(base_mid * 1.35, 0)

    # ── Index-level SL / targets ──────────────────────────────────────────────
    if direction == "CE":
        # SL = ORB low (or VWAP if ORB not available), Target = R1 / R2
        idx_sl  = orb_low  if orb_low  else round(ltp - step * 2)
        idx_t1  = piv_r1   if piv_r1   else round(ltp + step * 2)
        idx_t2  = piv_r2   if piv_r2   else round(ltp + step * 4)
        idx_sl_label = f"{idx_sl:,.0f} (ORB Low)" if orb_low else f"{idx_sl:,.0f}"
        idx_t1_label = f"{idx_t1:,.0f} (Pivot R1)" if piv_r1 else f"{idx_t1:,.0f}"
        idx_t2_label = f"{idx_t2:,.0f} (Pivot R2)" if piv_r2 else f"{idx_t2:,.0f}"
        entry_cond = (f"Enter after {'ORB high (' + str(int(orb_high)) + ')' if orb_high else 'resistance'} "
                      f"breaks on 5-min candle close with volume")
    else:
        # SL = ORB high (or VWAP), Target = S1 / S2
        idx_sl  = orb_high if orb_high else round(ltp + step * 2)
        idx_t1  = piv_s1   if piv_s1   else round(ltp - step * 2)
        idx_t2  = piv_s2   if piv_s2   else round(ltp - step * 4)
        idx_sl_label = f"{idx_sl:,.0f} (ORB High)" if orb_high else f"{idx_sl:,.0f}"
        idx_t1_label = f"{idx_t1:,.0f} (Pivot S1)" if piv_s1 else f"{idx_t1:,.0f}"
        idx_t2_label = f"{idx_t2:,.0f} (Pivot S2)" if piv_s2 else f"{idx_t2:,.0f}"
        entry_cond = (f"Enter after {'ORB low (' + str(int(orb_low)) + ')' if orb_low else 'support'} "
                      f"breaks on 5-min candle close with volume")

    # ── Confidence ────────────────────────────────────────────────────────────
    dom_score = max(bull_score, bear_score)
    if dom_score >= 8:   conf_label, conf_color = "HIGH", "#089981"
    elif dom_score >= 5: conf_label, conf_color = "MEDIUM", "#ffa500"
    else:                conf_label, conf_color = "LOW", "#f23645"

    # ── VIX advisory ─────────────────────────────────────────────────────────
    if vix_f >= 20:
        vix_advice = f"VIX {vix_f:.1f} — high IV. Use ATM (not OTM), keep lot size small."
    elif vix_f >= 15:
        vix_advice = f"VIX {vix_f:.1f} — elevated. OTM1 is fine; avoid deep OTM."
    else:
        vix_advice = f"VIX {vix_f:.1f} — normal. All strikes tradeable."

    return {
        "no_trade":      False,
        "direction":     direction,
        "net_score":     net,
        "bull_score":    bull_score,
        "bear_score":    bear_score,
        "conf_label":    conf_label,
        "conf_color":    conf_color,
        "confirmations": confirmations,
        "vix_advice":    vix_advice,
        "ltp":           ltp,
        "vwap":          vwap,
        "atm":           atm,
        "days_left":     days_left,
        "expiry_date":   expiry_date,
        "base_lo":       base_lo,
        "base_hi":       base_hi,
        "entry_cond":    entry_cond,
        "idx_sl":        idx_sl,
        "idx_sl_label":  idx_sl_label,
        "idx_t1":        idx_t1,
        "idx_t1_label":  idx_t1_label,
        "idx_t2":        idx_t2,
        "idx_t2_label":  idx_t2_label,
        "orb_high":      orb_high,
        "orb_low":       orb_low,
        "pivots": {"P": piv_p, "R1": piv_r1, "R2": piv_r2, "S1": piv_s1, "S2": piv_s2},
    }


def render_trade_card(setup: dict, side: str):
    t       = setup[side]
    is_call = side == "call"
    card_cls = "trade-card-call" if is_call else "trade-card-put"
    color    = "#089981" if is_call else "#f23645"
    label    = "📈 CALL (CE)" if is_call else "📉 PUT (PE)"
    preferred = setup["net_score"] > 0 if is_call else setup["net_score"] < 0
    badge     = ' <span style="background:#ffa500;color:#000;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:700">★ PREFERRED</span>' if preferred else ""

    st.markdown(f"""
    <div class="{card_cls}">
      <div class="trade-header" style="color:{color}">{label}{badge}</div>
      <div class="trade-strike">Strike: <b>{t['strike']}</b> &nbsp;|&nbsp; ATM: {setup['atm']}</div>

      <div class="trade-row">
        <div><div class="trade-label">Entry Price</div>
             <div class="trade-value" style="color:{color}">₹{t['entry']}</div></div>
        <div><div class="trade-label">Stop-Loss</div>
             <div class="trade-value" style="color:#f23645">₹{t['sl']}</div></div>
        <div><div class="trade-label">Target 1</div>
             <div class="trade-value" style="color:#089981">₹{t['tgt1']}</div></div>
        <div><div class="trade-label">Target 2</div>
             <div class="trade-value" style="color:#089981">₹{t['tgt2']}</div></div>
        <div><div class="trade-label">Risk:Reward</div>
             <div class="trade-value">1:{t['rr']}</div></div>
      </div>

      <div style="margin-top:12px">
        <span class="{t['status_cls']}">{t['status']}</span>
        <span class="pill {'pill-green' if t['conf']=='HIGH' else ('pill-yellow' if t['conf']=='MEDIUM' else 'pill-red')}">
          {t['conf_icon']} Confidence: {t['conf']} ({t['score']}/8)
        </span>
      </div>
      <div style="margin-top:8px;font-size:12px;color:#b2b5be">
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
        increasing_line_color="#089981", decreasing_line_color="#f23645",
        name="Price", showlegend=False,
    ), row=1, col=1)
    for col, color, name in [("ema9","#ffa500","EMA9"), ("ema21","#3b82f6","EMA21"), ("vwap","#a855f7","VWAP")]:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df[col],
                line=dict(color=color, width=1.2), name=name), row=1, col=1)
    # Supertrend
    if "supertrend" in df.columns and "supertrend_dir" in df.columns:
        bull_st = df[df["supertrend_dir"] == 1]
        bear_st = df[df["supertrend_dir"] == -1]
        if not bull_st.empty:
            fig.add_trace(go.Scatter(x=bull_st["timestamp"], y=bull_st["supertrend"],
                mode="markers", marker=dict(color="#089981", size=4, symbol="circle"),
                name="ST Bull"), row=1, col=1)
        if not bear_st.empty:
            fig.add_trace(go.Scatter(x=bear_st["timestamp"], y=bear_st["supertrend"],
                mode="markers", marker=dict(color="#f23645", size=4, symbol="circle"),
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
        pivot_colors = {"P": "#ffa500", "R1": "#f23645", "R2": "#f23645", "R3": "#f23645",
                        "S1": "#089981", "S2": "#089981", "S3": "#089981"}
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
        colors = ["#089981" if c >= o else "#f23645"
                  for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(x=df["timestamp"], y=df["volume"],
            marker_color=colors, showlegend=False), row=2, col=1)
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rsi"],
            line=dict(color="#ffa500", width=1.5), name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="rgba(242,54,69,0.5)", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="rgba(8,153,129,0.5)", row=3, col=1)
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

# Initialize performance cache (critical for reducing API calls)
if _CACHE_OK:
    CacheManager.init_session()

# Initialize trade journal database
if _TRADE_ADVISOR_OK:
    try:
        trade_journal.init_database()
    except Exception:
        pass

now_ist = datetime.now(IST)
market_open = is_market_open()

# ── SIDEBAR: Upstox Token Manager ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔑 Upstox Token")

    # Auto-capture auth code from redirect URL (?code=XXX)
    _qp = st.query_params
    _auto_code = _qp.get("code", "")
    if _auto_code and _UPSTOX_AVAILABLE is False or _auto_code:
        if _auto_code and not st.session_state.get("_token_exchanged_code") == _auto_code:
            st.info(f"Auth code detected in URL. Click **Get Token** to activate.")
            st.session_state["_pending_code"] = _auto_code

    # Token status
    if _UPSTOX_AVAILABLE:
        _tok_preview = upstox_config.ACCESS_TOKEN[:12] + "..." if upstox_config.ACCESS_TOKEN else ""
        st.success(f"✅ Token active  `{_tok_preview}`")
        st.caption("Expires at midnight IST. Refresh each morning.")
    else:
        st.error("❌ No token — using Yahoo Finance fallback")

    st.markdown("---")
    st.markdown("**Refresh token (daily)**")

    # Step 1 — generate auth URL
    if st.button("Step 1 — Open Upstox Login", use_container_width=True):
        if _UPSTOX_AVAILABLE or True:
            try:
                _auth_url = upstox_auth.get_auth_url()
                st.session_state["_auth_url"] = _auth_url
            except Exception as _e:
                st.error(f"Could not generate URL: {_e}")

    if st.session_state.get("_auth_url"):
        st.markdown(
            f'<a href="{st.session_state["_auth_url"]}" target="_blank" '
            f'style="display:block;background:#3b82f6;color:#fff;text-align:center;'
            f'padding:8px;border-radius:6px;text-decoration:none;font-weight:700">'
            f'👉 Login to Upstox</a>', unsafe_allow_html=True)
        st.caption("After login you'll be redirected back here automatically.")

    # Step 2 — paste or auto-filled code
    _default_code = st.session_state.get("_pending_code", "")
    _code_input = st.text_input("Step 2 — Paste auth code", value=_default_code,
                                placeholder="Paste code from redirect URL")

    if st.button("Get New Token ✅", use_container_width=True, type="primary"):
        _code = _code_input.strip()
        if not _code:
            st.warning("Paste the auth code first.")
        else:
            with st.spinner("Exchanging code for token..."):
                try:
                    _tokens = upstox_auth.exchange_code_for_token(_code)
                    _new_token = _tokens.get("access_token", "")
                    if _new_token:
                        # Write to .env
                        _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        _lines = open(_env_path).readlines() if os.path.exists(_env_path) else []
                        _updated = False
                        _new_lines = []
                        for _l in _lines:
                            if _l.startswith("UPSTOX_ACCESS_TOKEN="):
                                _new_lines.append(f"UPSTOX_ACCESS_TOKEN={_new_token}\n")
                                _updated = True
                            else:
                                _new_lines.append(_l)
                        if not _updated:
                            _new_lines.append(f"UPSTOX_ACCESS_TOKEN={_new_token}\n")
                        with open(_env_path, "w") as _f:
                            _f.writelines(_new_lines)
                        # Update in-memory config
                        upstox_config.ACCESS_TOKEN = _new_token
                        st.session_state["_token_exchanged_code"] = _code
                        st.session_state["_pending_code"] = ""
                        st.session_state["_auth_url"] = ""
                        st.cache_data.clear()
                        st.success("✅ Token saved! Dashboard refreshing...")
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error("No token in response — code may be expired. Try again.")
                except Exception as _ex:
                    st.error(f"Error: {_ex}")

    st.markdown("---")
    st.caption("Token valid for current trading day only.\nRun Step 1 each morning before 9:15 AM.")

# Header
col_h1, col_h2, col_h3, col_h4 = st.columns([3, 1, 1, 1])
with col_h1:
    st.markdown("## 📈 India Market Dashboard")
    st.caption(f"Last updated: {now_ist.strftime('%d %b %Y  %H:%M:%S IST')}  |  Data: Yahoo Finance (live via fast_info)")
with col_h2:
    status_color = "#089981" if market_open else "#f23645"
    st.markdown(f'<div style="margin-top:20px"><span style="color:{status_color}; font-size:16px; font-weight:700;">● Market {"OPEN" if market_open else "CLOSED"}</span></div>', unsafe_allow_html=True)
with col_h3:
    exp = next_expiry_info()
    n_exp = exp["nifty"]
    b_exp = exp["banknifty"]
    n_warn = "🔴" if n_exp["days"] <= 1 else ("🟡" if n_exp["days"] <= 2 else "🟢")
    b_warn = "🔴" if b_exp["days"] <= 1 else ("🟡" if b_exp["days"] <= 2 else "🟢")
    st.markdown(f"""
    <div style="margin-top:14px;font-size:12px;color:#b2b5be;line-height:1.8">
    {n_warn} <b>Nifty expiry:</b> {n_exp['date']} ({n_exp['days']}d)<br>
    {b_warn} <b>BNF expiry:</b> {b_exp['date']} ({b_exp['days']}d)
    </div>""", unsafe_allow_html=True)
with col_h4:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
# Smooth auto-refresh — paused when AI Expert is actively generating a response
# Market hours: every 30s | After hours: every 5 min
try:
    from streamlit_autorefresh import st_autorefresh
    if not st.session_state.get("_ai_busy", False):
        _refresh_interval = 30_000 if market_open else 300_000
        st_autorefresh(interval=_refresh_interval, key="live_refresh", debounce=False)
except ImportError:
    pass

st.divider()

# ── Fetch all Indian index quotes (Zerodha → Upstox → Yahoo fallback) ────────
_fetch_time = datetime.now(IST).strftime("%H:%M:%S")
_ticker_to_name = {v: k for k, v in TICKERS.items()}
quotes = {}

if _ZERODHA_AVAILABLE:
    _zdq = zd.get_index_quotes()           # {'^NSEI': {...}, '^BSESN': {...}, ...}
    for name, ticker in TICKERS.items():
        quotes[name] = _zdq.get(ticker) or get_quote(ticker)
    _data_source = "🟢 Live data · Zerodha"
else:
    _upstox_quotes = get_upstox_index_quotes()
    for name, ticker in TICKERS.items():
        uq = _upstox_quotes.get(ticker)
        quotes[name] = uq if uq else get_quote(ticker)
    if _upstox_quotes:
        _data_source = "🟡 Live data · Upstox"
    else:
        _data_source = "🔴 Delayed (15 min) · Yahoo Finance — add UPSTOX_ACCESS_TOKEN to Streamlit secrets for live data"

# ── Data source badge ─────────────────────────────────────────────────────────
_badge_color = "#089981" if _ZERODHA_AVAILABLE else ("#ffa500" if _UPSTOX_AVAILABLE else "#f23645")
st.markdown(
    f'<div style="font-size:12px;color:{_badge_color};margin-bottom:4px">'
    f'{_data_source} · as of {_fetch_time} IST</div>',
    unsafe_allow_html=True,
)

# ── Row 1: Index cards ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Market Overview</div>', unsafe_allow_html=True)
idx_cols = st.columns([1, 1, 1, 1, 1, 1.5])   # 5 tiles + right spacer
for col, (name, q) in zip(idx_cols, quotes.items()):
    with col:
        if q:
            arrow = "▲" if q["chg"] >= 0 else "▼"
            cls   = "bull" if q["chg"] >= 0 else "bear"
            st.markdown(f"""
            <div class="metric-card">
              <div style="font-size:12px;color:#b2b5be;text-transform:uppercase;letter-spacing:.06em">{name}</div>
              <div style="font-size:22px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
              <div style="font-size:13px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
              <div style="font-size:12px;color:#9598a1;margin-top:4px">H:{q['high']:,.0f} L:{q['low']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.metric(name, "Loading…")

st.divider()

# ── Charts + Signals ──────────────────────────────────────────────────────────
tab_advisor, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "🎯 Trade Advisor",
    "🎯 Trade Command",
    "🤖 AI Expert",
    "🌅 Morning Checklist",
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
#  TAB ADVISOR — Trade Advisor (NEW - Professional Trading)
# ══════════════════════════════════════════════════════════════════════════════
with tab_advisor:
    if _TRADE_ADVISOR_OK:
        # Initialize session state for trade advisor
        if "account_size" not in st.session_state:
            st.session_state.account_size = 100000
        if "risk_percent" not in st.session_state:
            st.session_state.risk_percent = 1.0
        if "active_trades" not in st.session_state:
            st.session_state.active_trades = []
        if "daily_pnl" not in st.session_state:
            st.session_state.daily_pnl = 0
        if "active_trades_count" not in st.session_state:
            st.session_state.active_trades_count = 0
        if "total_daily_risk" not in st.session_state:
            st.session_state.total_daily_risk = 0

        # Store candle data in session state for advisor to access
        try:
            nifty_intraday = get_candles("^NSEI", period="1d", interval="15m") if not nifty_df.empty else pd.DataFrame()
            if not nifty_intraday.empty:
                nifty_intraday = add_indicators(nifty_intraday)
            st.session_state.NIFTY_candles = nifty_intraday

            banknifty_intraday = get_candles("^NSEBANK", period="1d", interval="15m") if not bank_df.empty else pd.DataFrame()
            if not banknifty_intraday.empty:
                banknifty_intraday = add_indicators(banknifty_intraday)
            st.session_state.BANKNIFTY_candles = banknifty_intraday

            finnifty_intraday = get_candles("^NSEfinnifty", period="1d", interval="15m") if not finnifty_df.empty else pd.DataFrame()
            if not finnifty_intraday.empty:
                finnifty_intraday = add_indicators(finnifty_intraday)
            st.session_state.FINNIFTY_candles = finnifty_intraday
        except Exception:
            pass

        # Prepare market data for trade advisor
        market_data = {
            "NIFTY 50": {
                "ltp": quotes.get("Nifty 50", {}).get("ltp", 0),
                "vix": quotes.get("India VIX", {}).get("ltp", 15) if quotes.get("India VIX") else 15,
                "orb": nifty_orb,
                "pivots": nifty_pivots_i,
            },
            "BANK NIFTY": {
                "ltp": quotes.get("Bank Nifty", {}).get("ltp", 0),
                "vix": quotes.get("India VIX", {}).get("ltp", 15) if quotes.get("India VIX") else 15,
                "orb": bank_orb,
                "pivots": bank_pivots_i,
            },
            "FIN NIFTY": {
                "ltp": 0,  # Will fetch if available
                "vix": quotes.get("India VIX", {}).get("ltp", 15) if quotes.get("India VIX") else 15,
                "orb": {},
                "pivots": {},
            },
        }

        # Get options chains if available
        options_chains = {
            "NIFTY": nifty_chain if isinstance(nifty_chain, dict) else {},
            "BANKNIFTY": bank_chain if isinstance(bank_chain, dict) else {},
            "FINNIFTY": {},
        }

        # Render trade advisor page
        try:
            trade_advisor_page.render_trade_advisor_page(
                market_data=market_data,
                options_chains=options_chains,
                global_sentiment=gs.get("score", 0) if gs else 0,
                fii_dii=fii_dii,
                breadth=breadth_data,
            )
        except Exception as e:
            st.error(f"Trade Advisor Error: {str(e)[:200]}")
    else:
        st.error("❌ Trade Advisor modules not available. Check imports.")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 0 — Morning Checklist
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("## 🌅 Morning Market Checklist")
    st.caption("Run this every morning before 9:15 AM to prepare your trading plan for the day.")

    # ── Fetch all data upfront ────────────────────────────────────────────────
    def safe_nested_get(d, key, subkey, default=0):
        """Safely get nested dict values."""
        val = d.get(key) if d else None
        return val.get(subkey, default) if val and isinstance(val, dict) else default

    nq_m       = quotes.get("Nifty 50",   {}) or {}
    bnq_m      = quotes.get("Bank Nifty", {}) or {}
    vix_m      = safe_nested_get(quotes, "India VIX", "ltp", 0)
    sp_m       = {n: get_quote(t) for n, t in {"S&P 500":"^GSPC","Crude Oil":"CL=F","USD/INR":"USDINR=X"}.items()}
    nifty_df_m = get_candles("^NSEI", period="5d", interval="15m")
    nifty_df_m = add_indicators(nifty_df_m)
    g_quotes_m = {n: get_quote(t) for n, t in GLOBAL.items()}
    gs_m       = compute_global_sentiment(g_quotes_m)
    nifty_pct  = nq_m.get("pct", 0)
    sp_pct     = safe_nested_get(sp_m, "S&P 500",  "pct", 0)
    crude_pct  = safe_nested_get(sp_m, "Crude Oil", "pct", 0)
    usdinr_ltp = safe_nested_get(sp_m, "USD/INR",  "ltp", 84)

    last_m   = nifty_df_m.iloc[-1] if not nifty_df_m.empty else {}
    ema9_m   = last_m.get("ema9",  0) if not nifty_df_m.empty else 0
    ema21_m  = last_m.get("ema21", 0) if not nifty_df_m.empty else 0
    vwap_m   = last_m.get("vwap",  0) if not nifty_df_m.empty else 0
    ltp_m    = nq_m.get("ltp", 0)
    st_dir_m = last_m.get("supertrend_dir", 0) if not nifty_df_m.empty else 0

    # ── Helper: card item ─────────────────────────────────────────────────────
    def ci(label, value, status, msg):
        colors = {"ok": ("#0d2618","#089981","✅"), "warn": ("#2a1f0d","#ffa500","⚠️"), "bad": ("#2a0d0d","#f23645","❌")}
        bg, border, icon = colors.get(status, colors["warn"])
        st.markdown(
            f'<div style="background:{bg};border-left:4px solid {border};border-radius:8px;'
            f'padding:10px 12px;margin:4px 0">'
            f'<div style="color:{border};font-weight:700;font-size:14px">{icon} {label}</div>'
            f'<div style="color:#e0e0e0;font-weight:700;font-size:16px;margin:3px 0">{value}</div>'
            f'<div style="color:#b2b5be;font-size:12px">{msg}</div></div>',
            unsafe_allow_html=True,
        )

    def sec_title(n, title):
        st.markdown(f'<div style="font-size:13px;font-weight:800;color:#b2b5be;'
                    f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">{n} {title}</div>',
                    unsafe_allow_html=True)

    # ── 6 columns — widths proportional to content ────────────────────────────
    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns([1, 1.2, 1.6, 1.6, 1.5, 1.4])

    # 1. Volatility
    with mc1:
        sec_title("1️⃣", "VOLATILITY")
        if vix_m:
            if vix_m < 14:
                ci("India VIX", f"{vix_m:.2f}", "ok", "Low — good for trades")
            elif vix_m < 18:
                ci("India VIX", f"{vix_m:.2f}", "warn", "Moderate — normal size")
            else:
                ci("India VIX", f"{vix_m:.2f}", "bad", "High — reduce size 50%")

    # 2. Gap Analysis
    with mc2:
        sec_title("2️⃣", "GAP")
        if abs(nifty_pct) < 0.3:
            ci("Nifty", f"{nifty_pct:+.2f}%", "ok", "Flat — wait for 9:30 AM")
        elif nifty_pct > 0.3:
            ci("Nifty", f"{nifty_pct:+.2f}%", "warn", "Gap up — continuation?")
        else:
            ci("Nifty", f"{nifty_pct:+.2f}%", "warn", "Gap down — bounce?")
        bpct = bnq_m.get("pct", 0)
        ci("BankNifty", f"{bpct:+.2f}%",
           "ok" if abs(bpct) < 0.3 else ("warn" if bpct > 0 else "bad"),
           "Flat" if abs(bpct) < 0.3 else ("Gap up" if bpct > 0 else "Gap down"))

    # 3. Global Cues
    with mc3:
        sec_title("3️⃣", "GLOBAL CUES")
        ci("S&P 500", f"{sp_pct:+.2f}%",
           "ok" if sp_pct > 0.3 else ("bad" if sp_pct < -0.3 else "warn"),
           "US positive — bull bias" if sp_pct > 0.3 else ("US negative — caution" if sp_pct < -0.3 else "US flat — neutral"))
        ci("Crude Oil", f"{crude_pct:+.2f}%",
           "bad" if crude_pct > 1.5 else ("ok" if crude_pct < -1.0 else "warn"),
           "Spike — negative India" if crude_pct > 1.5 else ("Down — positive India" if crude_pct < -1.0 else "Stable — neutral"))
        ci("USD/INR", f"₹{usdinr_ltp:.2f}",
           "bad" if usdinr_ltp > 85 else ("ok" if usdinr_ltp < 83.5 else "warn"),
           "Rupee weak — FII sell" if usdinr_ltp > 85 else ("Rupee strong — FII buy" if usdinr_ltp < 83.5 else "Rupee stable"))

    # 4. Trend Direction
    with mc4:
        sec_title("4️⃣", "TREND")
        if not nifty_df_m.empty:
            ci("EMA Stack",
               "EMA9 > EMA21 ▲" if ema9_m > ema21_m else "EMA9 < EMA21 ▼",
               "ok" if ema9_m > ema21_m else "bad",
               "Bullish — prefer CE" if ema9_m > ema21_m else "Bearish — prefer PE")
            if ltp_m and vwap_m:
                ci("VWAP",
                   f"{'Above' if ltp_m > vwap_m else 'Below'} {vwap_m:,.0f}",
                   "ok" if ltp_m > vwap_m else "bad",
                   "Price above VWAP — bullish" if ltp_m > vwap_m else "Price below VWAP — bearish")
            ci("Supertrend",
               "Bullish 🟢" if st_dir_m == 1 else ("Bearish 🔴" if st_dir_m == -1 else "N/A"),
               "ok" if st_dir_m == 1 else ("bad" if st_dir_m == -1 else "warn"),
               "Uptrend confirmed" if st_dir_m == 1 else ("Downtrend confirmed" if st_dir_m == -1 else "Calculating..."))

    # 5. Global Intelligence
    with mc5:
        sec_title("5️⃣", "GLOBAL INTEL")
        gs_status = "ok" if gs_m["score"] >= 2 else ("bad" if gs_m["score"] <= -2 else "warn")
        gs_bg = "#0d2618" if gs_status == "ok" else ("#2a0d0d" if gs_status == "bad" else "#2a1f0d")
        factors_html = "".join([
            f'<div style="color:{"#089981" if f[2]=="bull" else ("#f23645" if f[2]=="bear" else "#6b7280")};font-size:12px">'
            f'{"▲" if f[2]=="bull" else ("▼" if f[2]=="bear" else "—")} {f[0]}: {f[1]}</div>'
            for f in gs_m["factors"][:6]
        ])
        st.markdown(
            f'<div style="background:{gs_bg};border-left:4px solid {gs_m["color"]};'
            f'border-radius:8px;padding:12px;margin:4px 0">'
            f'<div style="font-size:28px;font-weight:900;color:{gs_m["color"]};line-height:1">'
            f'{gs_m["score"]:+d}<span style="font-size:13px;color:#b2b5be"> /10</span></div>'
            f'<div style="font-size:14px;font-weight:700;color:{gs_m["color"]};margin:4px 0">{gs_m["label"]}</div>'
            f'{factors_html}</div>',
            unsafe_allow_html=True,
        )

    # 6. Trading Decision
    with mc6:
        sec_title("6️⃣", "DECISION")
        bull_checks = 0
        bear_checks = 0
        if vix_m and vix_m < 18:              bull_checks += 1
        if nifty_pct > 0:                     bull_checks += 1
        if sp_pct > 0:                        bull_checks += 1
        if gs_m["score"] >= 2:                bull_checks += 1
        elif gs_m["score"] <= -2:             bear_checks += 1
        if ema9_m > ema21_m:                  bull_checks += 1
        if st_dir_m == 1:                     bull_checks += 1
        elif st_dir_m == -1:                  bear_checks += 1
        if ltp_m and vwap_m and ltp_m > vwap_m: bull_checks += 1
        bear_checks = max(7 - bull_checks, bear_checks)

        if vix_m and vix_m > 20:
            verdict, vc = "⛔ NO TRADE",  "#f23645"
            advice = "VIX > 20\nSit out today."
        elif gs_m["score"] <= -4:
            verdict, vc = "⛔ NO TRADE",  "#f23645"
            advice = "Strong global\nheadwinds."
        elif bull_checks >= 4:
            verdict, vc = "🟢 BULLISH",   "#089981"
            advice = f"{bull_checks}/7 bullish\nBuy CE near VWAP\nTrail SL on ST"
        elif bear_checks >= 4:
            verdict, vc = "🔴 BEARISH",   "#f23645"
            advice = f"{bear_checks}/7 bearish\nBuy PE near VWAP\nTrail SL on ST"
        else:
            verdict, vc = "🟡 NEUTRAL",   "#ffa500"
            advice = f"{bull_checks}B / {bear_checks}Be out of 7\nWait for breakout\nafter 10 AM"

        vd_bg = "#0d2618" if vc == "#089981" else ("#2a0d0d" if vc == "#f23645" else "#2a1f0d")
        st.markdown(
            f'<div style="background:{vd_bg};border-left:4px solid {vc};border-radius:8px;'
            f'padding:14px 12px;margin:4px 0;text-align:center">'
            f'<div style="font-size:20px;font-weight:900;color:{vc}">{verdict}</div>'
            f'<div style="font-size:13px;color:#b2b5be;margin-top:8px;white-space:pre-line;line-height:1.8">{advice}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
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
with tab1:
    st.markdown("## 🎯 Intraday Trade Command Center")
    st.caption("Professional options trading signals — acts as your intraday mentor. Refresh for latest data.")

    # Load data if not already loaded
    intra_nifty_df = get_candles("^NSEI",    period="5d", interval="15m")
    intra_bank_df  = get_candles("^NSEBANK", period="5d", interval="15m")
    intra_nifty_df = add_indicators(intra_nifty_df)
    intra_bank_df  = add_indicators(intra_bank_df)

    nq_i   = quotes.get("Nifty 50",    {}) or {}
    bnq_i  = quotes.get("Bank Nifty",  {}) or {}
    vix_i  = safe_quote_get(quotes, "India VIX", "ltp", 0)
    n_ltp  = nq_i.get("ltp",  0) if nq_i else 0
    bn_ltp = bnq_i.get("ltp", 0) if bnq_i else 0

    # ── Market condition banner ───────────────────────────────────────────────
    ic1, ic2, ic3, _ = st.columns([1, 1, 1, 2])
    with ic1:
        vix_color = "#f23645" if vix_i > 18 else "#089981"
        st.markdown(f'<div class="metric-card" style="border-left-color:{vix_color}">'
                    f'<div class="trade-label">India VIX</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{vix_color}">{vix_i:.2f}</div>'
                    f'<div style="font-size:12px;color:#b2b5be">{"⚠️ High — reduce size" if vix_i > 18 else "✅ Normal range"}</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic2:
        n_color = "#089981" if nq_i.get("chg",0)>=0 else "#f23645"
        st.markdown(f'<div class="metric-card" style="border-left-color:{n_color}">'
                    f'<div class="trade-label">Nifty 50</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{n_color}">{n_ltp:,.2f}</div>'
                    f'<div style="font-size:12px;color:#b2b5be">{nq_i.get("pct",0):+.2f}% today</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic3:
        b_color = "#089981" if bnq_i.get("chg",0)>=0 else "#f23645"
        st.markdown(f'<div class="metric-card" style="border-left-color:{b_color}">'
                    f'<div class="trade-label">Bank Nifty</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{b_color}">{bn_ltp:,.2f}</div>'
                    f'<div style="font-size:12px;color:#b2b5be">{bnq_i.get("pct",0):+.2f}% today</div>'
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
                    orb_cls    = "#089981"
                elif ltp_orb < orb_l:
                    orb_signal = "🔴 BREAKDOWN — PE bias"
                    orb_cls    = "#f23645"
                else:
                    orb_signal = "🟡 Inside range — wait"
                    orb_cls    = "#ffa500"
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{orb_cls}">
                  <div style="font-size:12px;color:#b2b5be;margin-bottom:6px"><b>{name_orb} ORB</b></div>
                  <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <div><div class="trade-label">ORB High</div>
                         <div style="color:#f23645;font-weight:700;font-size:15px">{orb_h:,.2f}</div></div>
                    <div><div class="trade-label">ORB Low</div>
                         <div style="color:#089981;font-weight:700;font-size:15px">{orb_l:,.2f}</div></div>
                    <div><div class="trade-label">Range</div>
                         <div style="font-weight:700;font-size:15px">{orb_r:,.0f} pts</div></div>
                    <div><div class="trade-label">LTP</div>
                         <div style="font-weight:700;font-size:15px">{ltp_orb:,.2f}</div></div>
                  </div>
                  <div style="color:{orb_cls};font-weight:700;font-size:14px">{orb_signal}</div>
                  <div style="color:#b2b5be;font-size:12px;margin-top:4px">
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

    # ── Also fetch pivots for signal engine ──────────────────────────────────
    nifty_pivots_i = get_pivots("^NSEI")
    bank_pivots_i  = get_pivots("^NSEBANK")

    def _level_chip(label, val, color):
        return (f'<div style="background:#1e222d;border:1px solid {color};border-radius:6px;'
                f'padding:6px 10px;text-align:center;min-width:80px">'
                f'<div style="color:#b2b5be;font-size:12px;font-weight:700">{label}</div>'
                f'<div style="color:{color};font-size:14px;font-weight:800">{val}</div></div>')

    def show_intraday_signals(df, ltp, vix, name, step, orb=None, pivots=None):
        setup = intraday_option_setup(df, ltp, vix, name, step, orb, pivots)
        direction  = setup.get("direction", "CE")
        dir_color  = "#089981" if direction == "CE" else "#f23645"
        dir_emoji  = "📈" if direction == "CE" else "📉"
        atm        = setup.get("atm", nearest_strike(ltp, step))
        vix_f      = float(vix) if vix else 15
        lot_sz     = 75 if "Bank" not in name else 30
        days_left   = setup.get("days_left", 3)
        expiry_date = setup.get("expiry_date", "—")

        # Live option chain from Upstox (falls back to {} if token missing)
        exp_info_live = next_expiry_info()
        if "Bank" in name:
            _ikey   = "NSE_INDEX|Nifty Bank"
            _expstr = exp_info_live["banknifty"]["date_str"]
        else:
            _ikey   = "NSE_INDEX|Nifty 50"
            _expstr = exp_info_live["nifty"]["date_str"]
        live_chain = get_live_chain(_ikey, _expstr)

        st.markdown(f"### {name} — Trade Setup")

        # ── KEY LEVELS ROW ────────────────────────────────────────────────────
        st.markdown("**Key Levels**")
        kl_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">'
        if orb and orb.get("high"):
            kl_html += _level_chip("ORB High", f"{orb['high']:,.0f}", "#f23645")
            kl_html += _level_chip("ORB Low",  f"{orb['low']:,.0f}",  "#089981")
        vwap_val = setup.get("vwap", 0)
        if vwap_val and not (isinstance(vwap_val, float) and np.isnan(vwap_val)):
            kl_html += _level_chip("VWAP", f"{vwap_val:,.0f}", "#a78bfa")
        if pivots:
            if pivots.get("P"):  kl_html += _level_chip("Pivot P", f"{pivots['P']:,}", "#ffa500")
            if pivots.get("R1"): kl_html += _level_chip("R1", f"{pivots['R1']:,}", "#f23645")
            if pivots.get("R2"): kl_html += _level_chip("R2", f"{pivots['R2']:,}", "#f23645")
            if pivots.get("S1"): kl_html += _level_chip("S1", f"{pivots['S1']:,}", "#089981")
            if pivots.get("S2"): kl_html += _level_chip("S2", f"{pivots['S2']:,}", "#089981")
        kl_html += _level_chip("ATM", f"{atm:,}", "#9ca3af")
        kl_html += '</div>'
        st.markdown(kl_html, unsafe_allow_html=True)

        # ── NO TRADE / WAIT BANNER ────────────────────────────────────────────
        if setup.get("no_trade"):
            reason = setup["reason"]
            st.markdown(
                f'<div style="background:#2a1f0d;border-left:4px solid #ffa500;border-radius:8px;'
                f'padding:14px 16px;margin:8px 0">'
                f'<div style="color:#ffa500;font-weight:800;font-size:16px">⏳ WAIT — No Trade Yet</div>'
                f'<div style="color:#e0e0e0;font-size:13px;margin-top:6px">{reason}</div></div>',
                unsafe_allow_html=True)
            # Show confirmations even in wait state
            if setup.get("confirmations"):
                with st.expander("Current indicator readings", expanded=False):
                    for c in setup["confirmations"]:
                        st.markdown(f"• {c}")
            return

        # ── MAIN SIGNAL BANNER ────────────────────────────────────────────────
        bg_color = "#0d2618" if direction == "CE" else "#2a0d0d"
        st.markdown(
            f'<div style="background:{bg_color};border:2px solid {dir_color};border-radius:10px;'
            f'padding:16px 20px;margin:8px 0">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
            f'<div>'
            f'<div style="color:{dir_color};font-size:22px;font-weight:900">'
            f'{dir_emoji} BUY {direction} — {setup["conf_label"]} CONFIDENCE</div>'
            f'<div style="color:#e0e0e0;font-size:13px;margin-top:4px">{setup["entry_cond"]}</div>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<div style="color:#b2b5be;font-size:12px">VWAP</div>'
            f'<div style="color:#a78bfa;font-weight:700;font-size:15px">{vwap_val:,.0f}</div>'
            f'</div></div>'
            f'<div style="color:#b2b5be;font-size:12px;margin-top:8px">'
            f'{setup.get("vix_advice","")}</div>'
            f'</div>', unsafe_allow_html=True)

        # ── SIGNAL CONFIRMATIONS ──────────────────────────────────────────────
        with st.expander(f"Signal factors (Bull {setup['bull_score']} | Bear {setup['bear_score']})",
                         expanded=False):
            for c in setup["confirmations"]:
                icon = "🟢" if any(w in c for w in ["bullish","above","BREAKOUT","rising","buying"]) else \
                       ("🔴" if any(w in c for w in ["bearish","below","BREAKDOWN","falling","selling"]) else "🟡")
                st.markdown(f"{icon} {c}")

        st.markdown("---")

        # ── INDEX-LEVEL SL / TARGETS (primary reference) ──────────────────────
        sl_lbl = setup["idx_sl_label"]
        t1_lbl = setup["idx_t1_label"]
        t2_lbl = setup["idx_t2_label"]
        idx_move_t1 = abs(setup["idx_t1"] - ltp)
        idx_move_sl = abs(setup["idx_sl"] - ltp)
        rr_idx = round(idx_move_t1 / max(idx_move_sl, 1), 1)

        lv1, lv2, lv3, lv4 = st.columns(4)
        for col, label, val, color, note in [
            (lv1, "Entry (LTP)", f"{ltp:,.2f}", dir_color, "Current market price"),
            (lv2, "Index SL",    sl_lbl,        "#f23645", f"Exit if {name} crosses this"),
            (lv3, "Index T1",    t1_lbl,        "#089981", "Book 50-60% qty here"),
            (lv4, "Index T2",    t2_lbl,        "#089981", "Trail rest to T2"),
        ]:
            with col:
                st.markdown(
                    f'<div style="background:#1e222d;border-left:3px solid {color};border-radius:6px;'
                    f'padding:10px 12px">'
                    f'<div style="color:#b2b5be;font-size:12px">{label}</div>'
                    f'<div style="color:{color};font-weight:800;font-size:15px">{val}</div>'
                    f'<div style="color:#b2b5be;font-size:12px">{note}</div></div>',
                    unsafe_allow_html=True)

        st.markdown(
            f'<div style="color:#b2b5be;font-size:12px;margin:6px 0 14px">'
            f'Index needs to move <b style="color:{dir_color}">{idx_move_t1:,.0f} pts</b> to T1 '
            f'vs <b style="color:#f23645">{idx_move_sl:,.0f} pts</b> risk — '
            f'<b>R:R = 1:{rr_idx}</b></div>', unsafe_allow_html=True)

        # ── STRIKE LADDER ─────────────────────────────────────────────────────
        st.markdown("#### Strike Selection")
        st.caption("Premiums are estimates based on VIX + days to expiry. CHECK ACTUAL PRICE ON YOUR BROKER before entering.")

        days_safe  = max(float(days_left), 0.5)
        vix_ann    = max(vix_f, 8) / 100
        bs_factor  = 0.40 if "Bank" in name else 0.308
        base_mid   = ltp * vix_ann * np.sqrt(days_safe / 252) * bs_factor
        # Show ±20% range to acknowledge real-world bid-ask spread
        def prem_range(mult):
            mid = base_mid * mult
            return f"~{max(int(mid*0.80),5)}–{int(mid*1.20)}"

        # OTM multipliers calibrated from live market data:
        # Nifty 23650 CE ATM=104 | 23350 PE (6-step OTM)=24.65 (ratio 0.24)
        # Extrapolated for 1/2/3 steps: ~0.72 / 0.45 / 0.27
        OTM_LEVELS = [
            ("ATM",      0, 1.00, "Best for strong breakouts. Highest premium, highest delta."),
            ("OTM 1",    1, 0.72, "Recommended — good delta, manageable cost. Needs ~1 step move."),
            ("OTM 2",    2, 0.45, "Lower cost. Needs ~2x the index move to profit."),
            ("Deep OTM", 3, 0.27, "High risk. Needs a large sustained move — avoid near expiry."),
        ]

        # Recommended direction gets full opacity; opposite is dimmed
        for opt_dir, sign in [(direction, +1 if direction=="CE" else -1),
                               ("PE" if direction=="CE" else "CE",
                                -1 if direction=="CE" else +1)]:
            is_rec = (opt_dir == direction)
            oc     = "#089981" if opt_dir == "CE" else "#f23645"
            hdr    = f'{"★ RECOMMENDED" if is_rec else "OPPOSITE SIDE"}  {opt_dir}'
            st.markdown(
                f'<div style="color:{oc};font-weight:700;font-size:14px;'
                f'margin:14px 0 4px;opacity:{"1" if is_rec else "0.4"}">{hdr}</div>',
                unsafe_allow_html=True)

            for label, offset, mult, note in OTM_LEVELS:
                strike      = atm + sign * offset * step
                # Use live Upstox premium if available, else fall back to BS estimate
                chain_row   = live_chain.get(int(strike), {})
                live_ltp    = chain_row.get("ce" if opt_dir == "CE" else "pe", 0)
                live_iv     = chain_row.get("ce_iv" if opt_dir == "CE" else "pe_iv", 0)
                if live_ltp and live_ltp > 0:
                    pr          = f"₹{live_ltp:.0f}"
                    prem_source = "LIVE"
                    mid_prem    = live_ltp
                else:
                    pr          = f"~{prem_range(mult)}"
                    prem_source = "EST"
                    mid_prem    = base_mid * mult
                cost_lo     = int(max(mid_prem * 0.90, 5) * lot_sz)
                cost_hi     = int(mid_prem * 1.10 * lot_sz)
                affordable  = cost_lo <= user_budget
                max_lots    = int(user_budget // max(cost_lo, 1))
                # premium SL = -30%, T1 = +60%, T2 = +120%
                prem_sl_pct = "−30%"
                prem_t1_pct = "+60%"
                prem_t2_pct = "+120%"
                idx_pts_needed = offset * step * 1.0  # rough: each OTM step needs ~step pts more

                row_bg     = f"rgba({'38,166,154' if opt_dir=='CE' else '239,83,80'},0.07)" if is_rec and affordable else "rgba(255,255,255,0.02)"
                row_border = oc if (is_rec and affordable) else "#374151"
                op         = "1" if is_rec else "0.4"
                rec_badge  = ' <span style="background:#ffa500;color:#000;padding:1px 6px;border-radius:4px;font-size:12px">REC</span>' if is_rec and label == "OTM 1" else ""

                st.markdown(f"""
                <div style="background:{row_bg};border:1px solid {row_border};border-radius:8px;
                            padding:10px 14px;margin:4px 0;opacity:{op}">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px">
                    <div>
                      <span style="color:{oc};font-weight:800;font-size:16px">{strike} {opt_dir}</span>{rec_badge}<span style="color:#b2b5be;font-size:12px;margin-left:8px">{label}</span>
                    </div>
                    <div style="background:#1e2130;border-radius:6px;padding:3px 10px;font-size:12px">
                      📅 <span style="color:#b2b5be">Expiry:</span> <span style="color:#e0e0e0;font-weight:700">{expiry_date}</span> <span style="color:#9598a1">({days_left}d)</span>
                    </div>
                  </div>
                  <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12px">
                    <div><div style="color:#9598a1">{'Premium 🟢 LIVE' if prem_source=='LIVE' else 'Premium 🟡 EST'}</div>
                         <div style="color:{oc};font-weight:700">{pr}</div>
                         {'<div style="color:#b2b5be;font-size:12px">IV: '+f"{live_iv:.1f}%</div>" if live_iv else ''}</div>
                    <div><div style="color:#9598a1">1-lot cost</div>
                         <div style="font-weight:700">₹{cost_lo:,}–{cost_hi:,}</div></div>
                    <div><div style="color:#9598a1">Max lots</div>
                         <div style="color:{'#089981' if affordable else '#6b7280'};font-weight:800;font-size:14px">{max_lots if affordable else '—'}</div></div>
                    <div><div style="color:#9598a1">Prem SL / T1 / T2</div>
                         <div style="font-weight:700"><span style="color:#f23645">{prem_sl_pct}</span> &nbsp;
                         <span style="color:#089981">{prem_t1_pct}</span> &nbsp;
                         <span style="color:#089981">{prem_t2_pct}</span></div></div>
                    <div><div style="color:#9598a1">Index SL</div>
                         <div style="color:#f23645;font-weight:700">{setup['idx_sl_label']}</div></div>
                    <div><div style="color:#9598a1">Index T1</div>
                         <div style="color:#089981;font-weight:700">{setup['idx_t1_label']}</div></div>
                  </div>
                  <div style="color:#b2b5be;font-size:12px;margin-top:6px">💡 {note}</div>
                </div>""", unsafe_allow_html=True)

        live_label = "🟢 LIVE from Upstox" if live_chain else "🟡 Estimated (add token for live)"
        st.caption(f"Lot sizes: Nifty=75 | BankNifty=30 | Expiry in {days_left} day(s) | Premiums: {live_label}")

        # ── RISK RULES ────────────────────────────────────────────────────────
        st.markdown("""
        <div style="background:#1e222d;border-left:4px solid #ffa500;border-radius:8px;
                    padding:12px 16px;margin-top:12px;font-size:13px">
        <b style="color:#ffa500">Risk Rules (Non-negotiable)</b><br>
        <span style="color:#b2b5be">
        • Risk only 1–2% of capital per trade &nbsp;|&nbsp;
        • Exit at premium SL (−30%) without hesitation &nbsp;|&nbsp;
        • Exit if index crosses your SL level — do NOT average down &nbsp;|&nbsp;
        • Book 50% at T1, trail rest for T2 &nbsp;|&nbsp;
        • No new entries after 1:30 PM &nbsp;|&nbsp;
        • Exit ALL positions by 3:00 PM
        </span></div>""", unsafe_allow_html=True)

    nifty_pivs_for_signal = {k: float(v) for k, v in nifty_pivots_i.items()} if nifty_pivots_i else {}
    bank_pivs_for_signal  = {k: float(v) for k, v in bank_pivots_i.items()}  if bank_pivots_i  else {}

    # ══════════════════════════════════════════════════════════════════════════════
    #  LIVE OPTIONS CHAIN VIEWER
    # ══════════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("## 📊 Live Options Chain")
    st.caption("Real-time strike prices, premiums (CE/PE), IV, and Open Interest — refreshes every 12 seconds")

    if _OPTIONS_VIEWER_OK and _UPSTOX_AVAILABLE:
        # Fetch live option chains
        exp_info_chains = next_expiry_info()

        options_index = st.radio(
            "View options for:",
            ["Nifty 50", "Bank Nifty"],
            horizontal=True,
            key="options_chain_index"
        )

        if options_index == "Nifty 50":
            ikey_opt = "NSE_INDEX|Nifty 50"
            expiry_str = exp_info_chains["nifty"]["date_str"]
            ltp_opt = n_ltp
            step_opt = 50
            name_opt = "Nifty 50"
        else:
            ikey_opt = "NSE_INDEX|Nifty Bank"
            expiry_str = exp_info_chains["banknifty"]["date_str"]
            ltp_opt = bn_ltp
            step_opt = 100
            name_opt = "Bank Nifty"

        # Fetch live chain (12s TTL)
        live_chain_data = OptionChainCache.get_chain(ikey_opt, expiry_str, get_live_chain) if _CACHE_OK else get_live_chain(ikey_opt, expiry_str)

        if live_chain_data and isinstance(live_chain_data, dict) and len(live_chain_data) > 0:
            # Build display dataframe
            df_chain = ov.build_chain_dataframe(live_chain_data, ltp_opt, step_opt)

            if not df_chain.empty:
                # Display options chain table
                ov.render_option_chain_table(df_chain, ltp_opt, name_opt)

                st.markdown("---")

                # Strike selector
                oc1, oc2 = st.columns(2)
                with oc1:
                    selected_ce_strike = ov.render_strike_selector(df_chain, ltp_opt, "CE")
                    if selected_ce_strike:
                        ce_row = df_chain[df_chain["Strike"] == selected_ce_strike].iloc[0]
                        st.success(f"✅ Selected CE {selected_ce_strike} @ ₹{ce_row['CE_LTP']:.2f}")

                with oc2:
                    selected_pe_strike = ov.render_strike_selector(df_chain, ltp_opt, "PE")
                    if selected_pe_strike:
                        pe_row = df_chain[df_chain["Strike"] == selected_pe_strike].iloc[0]
                        st.success(f"✅ Selected PE {selected_pe_strike} @ ₹{pe_row['PE_LTP']:.2f}")

                st.markdown("---")

                # IV Heatmap
                with st.expander("🔥 IV Heatmap (Volatility Surface)", expanded=False):
                    ov.show_iv_heatmap(df_chain)
            else:
                st.warning("Option chain data empty. Try refreshing.")
        else:
            st.info("📊 Fetching live option chain... Make sure your Upstox token is active.")
    elif not _OPTIONS_VIEWER_OK:
        st.error("❌ Options viewer module not loaded. Check your installation.")
    else:
        st.warning("⚠️ Upstox token not available. Add UPSTOX_ACCESS_TOKEN to Streamlit secrets for live option data.")

    # ── OLD signals (kept for existing users, shown below new section) ────────
    st.divider()
    st.markdown("#### 📊 Technical Signals (Legacy View)")
    with st.expander("Show detailed technical signals", expanded=False):
        if sel_index == "Nifty 50":
            show_intraday_signals(intra_nifty_df, n_ltp, vix_i, "Nifty 50",   50,  orb_n,  nifty_pivs_for_signal)
        elif sel_index == "Bank Nifty":
            show_intraday_signals(intra_bank_df,  bn_ltp, vix_i, "Bank Nifty", 100, orb_bn, bank_pivs_for_signal)
        else:
            show_intraday_signals(intra_nifty_df, n_ltp, vix_i, "Nifty 50",   50,  orb_n,  nifty_pivs_for_signal)
            st.divider()
            show_intraday_signals(intra_bank_df,  bn_ltp, vix_i, "Bank Nifty", 100, orb_bn, bank_pivs_for_signal)

    # ═══════════════════════════════════════════════════════════════════════════
    # NEW: PROFESSIONAL TRADE COMMAND CENTER
    # ═══════════════════════════════════════════════════════════════════════════
    if not _TRADE_ENGINE_OK:
        st.warning("Trade engine not loaded. Check trade_engine.py.")
    else:
        st.markdown("---")
        st.markdown("## 🎯 Professional Trade Recommendations")

        # ── Full market intelligence (cached 5 min) ───────────────────────────
        @st.cache_data(ttl=300)
        def _get_market_intel(vix_val, nifty_pct_val):
            if _MI_OK:
                return mi.get_full_intelligence(vix_india=vix_val, nifty_pct=nifty_pct_val)
            return {}

        nifty_pct_now = quotes.get("Nifty 50", {}).get("pct", 0)
        intel = _get_market_intel(vix_i, nifty_pct_now)

        # Legacy global sentiment (kept for fallback)
        global_quotes_tc = {}
        for gname, gticker in GLOBAL.items():
            gq = get_quote(gticker)
            if gq:
                global_quotes_tc[gname] = gq
        g_sentiment  = compute_global_sentiment(global_quotes_tc)
        g_score      = intel.get("macro_score", g_sentiment.get("score", 0)) // 2  # scale -20→-10
        fii_dii_data = intel.get("fii_dii",  te.fetch_fii_dii() if not intel else {})
        breadth_data = intel.get("breadth",  te.fetch_market_breadth() if not intel else {})

        # ── Market Context Banner ─────────────────────────────────────────────
        st.markdown("### 🌐 Market Context")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)

        with mc1:
            g_color = "#089981" if g_score >= 2 else ("#f23645" if g_score <= -2 else "#ffa500")
            g_arrow = "🟢" if g_score >= 2 else ("🔴" if g_score <= -2 else "🟡")
            st.markdown(f"""<div class="metric-card" style="border-left-color:{g_color}">
            <div class="trade-label">Global Cues</div>
            <div style="font-size:18px;font-weight:800;color:{g_color}">{g_arrow} {g_sentiment.get('label','—')[:20]}</div>
            <div style="font-size:12px;color:#b2b5be">Score: {g_score:+d}/10</div>
            </div>""", unsafe_allow_html=True)

        with mc2:
            vcolor = "#f23645" if vix_i > 20 else ("#ffa500" if vix_i > 16 else "#089981")
            st.markdown(f"""<div class="metric-card" style="border-left-color:{vcolor}">
            <div class="trade-label">India VIX</div>
            <div style="font-size:22px;font-weight:800;color:{vcolor}">{vix_i:.2f}</div>
            <div style="font-size:12px;color:#b2b5be">{"⚠️ High" if vix_i>20 else ("⚠️ Watch" if vix_i>16 else "✅ Normal")}</div>
            </div>""", unsafe_allow_html=True)

        with mc3:
            if fii_dii_data:
                fii_n   = fii_dii_data.get("fii_net", 0)
                dii_n   = fii_dii_data.get("dii_net", 0)
                fc = "#089981" if fii_n > 0 else "#f23645"
                dc = "#089981" if dii_n > 0 else "#f23645"
                st.markdown(f"""<div class="metric-card">
                <div class="trade-label">FII / DII (₹Cr)</div>
                <div style="font-size:14px;font-weight:700;color:{fc}">FII: {fii_n:+,.0f}</div>
                <div style="font-size:14px;font-weight:700;color:{dc}">DII: {dii_n:+,.0f}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""<div class="metric-card">
                <div class="trade-label">FII / DII</div>
                <div style="font-size:13px;color:#9598a1">Data unavailable</div>
                <div style="font-size:12px;color:#9598a1">NSE updates after 4 PM</div>
                </div>""", unsafe_allow_html=True)

        with mc4:
            if breadth_data:
                bc = "#089981" if breadth_data.get("bias") == "bullish" else (
                     "#f23645" if breadth_data.get("bias") == "bearish" else "#ffa500")
                st.markdown(f"""<div class="metric-card" style="border-left-color:{bc}">
                <div class="trade-label">Market Breadth</div>
                <div style="font-size:13px;font-weight:700;color:{bc}">{breadth_data.get('label','—')}</div>
                <div style="font-size:12px;color:#b2b5be">A/D Ratio: {breadth_data.get('ratio',0):.1f}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""<div class="metric-card">
                <div class="trade-label">Market Breadth</div>
                <div style="font-size:13px;color:#9598a1">Unavailable</div>
                </div>""", unsafe_allow_html=True)

        with mc5:
            now_ist  = datetime.now(IST)
            mkt_time = now_ist.strftime("%H:%M")
            is_open  = is_market_open()
            mins_e   = te._market_minutes_elapsed()
            hold_str = te._max_hold_till(mins_e)
            tc = "#089981" if is_open else "#6b7280"
            st.markdown(f"""<div class="metric-card" style="border-left-color:{tc}">
            <div class="trade-label">Session</div>
            <div style="font-size:16px;font-weight:800;color:{tc}">{'🟢 OPEN' if is_open else '🔴 CLOSED'} {mkt_time}</div>
            <div style="font-size:12px;color:#b2b5be">Max hold: {hold_str[:20]}</div>
            </div>""", unsafe_allow_html=True)

        # ── Full Market Intelligence Panel ────────────────────────────────────
        if intel:
            macro_score  = intel.get("macro_score", 0)
            regime       = intel.get("market_regime", "NEUTRAL")
            risk_level   = intel.get("risk_level", "MEDIUM")
            summary      = intel.get("summary", "")
            geo_alert    = intel.get("geo_alert")
            policy_alert = intel.get("policy_alert")
            eco_events   = intel.get("eco_events", [])
            news_intel   = intel.get("news", {})
            drivers      = intel.get("drivers", [])

            regime_color = {"RISK_ON": "#089981", "RISK_OFF": "#f23645", "NEUTRAL": "#ffa500"}.get(regime, "#ffa500")
            risk_color   = {"LOW": "#089981", "MEDIUM": "#ffa500", "HIGH": "#f97316", "EXTREME": "#f23645"}.get(risk_level, "#ffa500")

            # Regime summary bar
            score_bar_w = int((macro_score + 20) / 40 * 100)
            st.markdown(f"""
            <div style="background:#1e222d;border-radius:12px;padding:16px 20px;margin:8px 0">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
                <div>
                  <span style="color:{regime_color};font-size:18px;font-weight:800">{regime.replace('_',' ')} MODE</span>
                  <span style="background:{risk_color}33;color:{risk_color};font-size:12px;font-weight:700;
                        padding:2px 8px;border-radius:10px;margin-left:10px;border:1px solid {risk_color}">
                    {risk_level} RISK
                  </span>
                </div>
                <div style="color:#b2b5be;font-size:12px">Macro Score: <b style="color:{regime_color}">{macro_score:+d}/20</b></div>
              </div>
              <div style="background:#131722;border-radius:6px;height:6px;margin-bottom:10px">
                <div style="background:{regime_color};width:{score_bar_w}%;height:100%;border-radius:6px"></div>
              </div>
              <div style="color:#d1d5db;font-size:13px">📋 {summary}</div>
            </div>""", unsafe_allow_html=True)

            # Alerts
            if geo_alert:
                st.markdown(f'<div style="background:#1f0d0f;border:1px solid #f23645;border-radius:8px;padding:10px 16px;margin:4px 0;font-size:13px;color:#f23645">{geo_alert}</div>', unsafe_allow_html=True)
            if policy_alert:
                st.markdown(f'<div style="background:#1a1d0d;border:1px solid #ffa500;border-radius:8px;padding:10px 16px;margin:4px 0;font-size:13px;color:#ffa500">{policy_alert}</div>', unsafe_allow_html=True)
            if eco_events:
                ev_html = " &nbsp;|&nbsp; ".join(
                    [f"<b style='color:{'#f23645' if e['impact']=='High' else '#ffa500'}'>{e['currency']}</b> {e['event']} @ {e['time']}"
                     for e in eco_events[:5]])
                st.markdown(f'<div style="background:#0d1a2e;border:1px solid #3b82f6;border-radius:8px;padding:10px 16px;margin:4px 0;font-size:12px;color:#d1d5db">📅 <b style="color:#2962ff">TODAY\'S EVENTS:</b> {ev_html}</div>', unsafe_allow_html=True)

            # Key market drivers (collapsible)
            with st.expander("📊 Full Market Intelligence — Global Indices, Macro, News, Sectors", expanded=False):
                d1, d2 = st.columns(2)
                with d1:
                    # Driver table
                    st.markdown("**🌐 Key Market Drivers**")
                    drv_html = ""
                    for d in drivers:
                        bc = "#089981" if d["bull"] is True else ("#f23645" if d["bull"] is False else "#6b7280")
                        drv_html += (f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
                                     f'border-bottom:1px solid #1e2130;font-size:12px">'
                                     f'<span style="color:#b2b5be">{d["factor"]}</span>'
                                     f'<span style="color:{bc};font-weight:600">{d["signal"]}</span>'
                                     f'</div>')
                    st.markdown(f'<div style="background:#1e222d;border-radius:8px;padding:12px">{drv_html}</div>',
                                unsafe_allow_html=True)

                    # News intelligence
                    st.markdown("**📰 News Intelligence**")
                    if news_intel.get("top_bull"):
                        for h in news_intel["top_bull"][:2]:
                            st.markdown(f'<div style="font-size:12px;color:#089981;padding:2px 0">🟢 {h[:90]}</div>', unsafe_allow_html=True)
                    if news_intel.get("top_bear"):
                        for h in news_intel["top_bear"][:2]:
                            st.markdown(f'<div style="font-size:12px;color:#f23645;padding:2px 0">🔴 {h[:90]}</div>', unsafe_allow_html=True)
                    if news_intel.get("earnings_headlines"):
                        for h in news_intel["earnings_headlines"][:2]:
                            st.markdown(f'<div style="font-size:12px;color:#ffa500;padding:2px 0">📊 {h[:90]}</div>', unsafe_allow_html=True)

                with d2:
                    # Global indices table
                    st.markdown("**🗺️ Global Indices**")
                    gidx = intel.get("global_indices", {})
                    gi_html = ""
                    for gname, gq in gidx.items():
                        pct  = gq.get("pct", 0)
                        ltp  = gq.get("ltp", 0)
                        clr  = "#089981" if pct > 0 else "#f23645"
                        gi_html += (f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
                                    f'border-bottom:1px solid #1e2130;font-size:12px">'
                                    f'<span style="color:#b2b5be">{gname}</span>'
                                    f'<span style="color:{clr};font-weight:600">{pct:+.2f}%</span>'
                                    f'</div>')
                    st.markdown(f'<div style="background:#1e222d;border-radius:8px;padding:12px">{gi_html}</div>',
                                unsafe_allow_html=True)

                    # Sector performance
                    st.markdown("**🏭 NSE Sectors (Today)**")
                    sec = intel.get("sectors", {})
                    sec_html = ""
                    for sname, sq in list(sec.items())[:8]:
                        pct = sq.get("pct", 0)
                        clr = "#089981" if pct > 0 else "#f23645"
                        bar_w = min(abs(pct) * 20, 100)
                        sec_html += (f'<div style="display:flex;justify-content:space-between;align-items:center;'
                                     f'padding:4px 0;border-bottom:1px solid #1e2130;font-size:12px">'
                                     f'<span style="color:#b2b5be;min-width:90px">{sname}</span>'
                                     f'<div style="flex:1;margin:0 8px;background:#1e2130;border-radius:3px;height:4px">'
                                     f'<div style="background:{clr};width:{bar_w}%;height:100%;border-radius:3px;'
                                     f'{"margin-left:auto" if pct < 0 else ""}"></div></div>'
                                     f'<span style="color:{clr};font-weight:700;min-width:50px;text-align:right">{pct:+.2f}%</span>'
                                     f'</div>')
                    st.markdown(f'<div style="background:#1e222d;border-radius:8px;padding:12px">{sec_html}</div>',
                                unsafe_allow_html=True)

                # Macro data row
                st.markdown("**💱 Macro Snapshot**")
                mac = intel.get("macro_data", {})
                mac_items = [
                    ("USD/INR",      mac.get("USD/INR",{})),
                    ("Crude Oil",    mac.get("Crude Oil",{})),
                    ("Gold",         mac.get("Gold",{})),
                    ("US 10Y",       mac.get("US 10Y Yield",{})),
                    ("US VIX",       mac.get("US VIX",{})),
                    ("Dollar Index", mac.get("Dollar Index",{})),
                ]
                mac_cols = st.columns(6)
                for col, (mname, mq) in zip(mac_cols, mac_items):
                    pct = mq.get("pct", 0)
                    ltp = mq.get("ltp", 0)
                    clr = "#089981" if pct < 0 and mname in ("USD/INR","Crude Oil","US VIX","US 10Y","Dollar Index") else (
                          "#089981" if pct > 0 else "#f23645")
                    with col:
                        st.markdown(f"""<div style="background:#1e222d;border-radius:6px;padding:8px;text-align:center">
                        <div style="color:#b2b5be;font-size:12px">{mname}</div>
                        <div style="color:{clr};font-size:14px;font-weight:700">{ltp:.2f}</div>
                        <div style="color:{clr};font-size:12px">{pct:+.2f}%</div>
                        </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Per-index recommendation cards ────────────────────────────────────
        exp_info_tc = next_expiry_info()

        INDICES_TC = [
            ("Nifty 50",   "^NSEI",    intra_nifty_df, n_ltp,  50,  75,
             exp_info_tc["nifty"],     "NSE_INDEX|Nifty 50",     orb_n,  nifty_pivs_for_signal),
            ("Bank Nifty", "^NSEBANK", intra_bank_df,  bn_ltp, 100, 30,
             exp_info_tc["banknifty"],"NSE_INDEX|Nifty Bank",    orb_bn, bank_pivs_for_signal),
        ]

        # Fin Nifty
        intra_fin_df = add_indicators(get_candles("^CNXFIN", period="5d", interval="15m"))
        fn_ltp  = quotes.get("Fin Nifty", {}).get("ltp", 0)
        fn_orb  = get_orb("^CNXFIN")
        fn_pivs = {k: float(v) for k, v in get_pivots("^CNXFIN").items()} if get_pivots("^CNXFIN") else {}

        # Fin Nifty expiry = Tuesday same as Nifty
        INDICES_TC.append(
            ("Fin Nifty", "^CNXFIN", intra_fin_df, fn_ltp, 50, 40,
             exp_info_tc["nifty"], "NSE_INDEX|Nifty Fin Service", fn_orb, fn_pivs)
        )

        for (iname, iticker, idf, iltp, istep, ilot,
             iexp, iupstox_key, iorb, ipivots) in INDICES_TC:

            expiry_label_tc   = f"{iexp['date']} ({iexp['days']}d)"
            expiry_date_str   = iexp["date_str"]
            live_chain_tc     = get_live_chain(iupstox_key, expiry_date_str)

            rec = te.generate_recommendation(
                name=iname, df=idf, ltp=iltp, vix=vix_i,
                orb=iorb, pivots=ipivots,
                live_chain=live_chain_tc,
                global_score=g_score,
                step=istep, lot_size=ilot,
                expiry_label=expiry_label_tc,
                expiry_date_str=expiry_date_str,
                fii_dii=fii_dii_data,
                breadth=breadth_data,
            )

            # ── Status color & badge ──────────────────────────────────────────
            status = rec.get("status", "AVOID")
            direction = rec.get("direction", "")
            conf = rec.get("confidence", 0)

            STATUS_META = {
                "HIGH_CONVICTION": ("#089981", "🔥 HIGH CONVICTION"),
                "MODERATE":        ("#ffa500", "✅ MODERATE CONVICTION"),
                "WATCHLIST":       ("#3b82f6", "👀 WATCHLIST"),
                "AVOID":           ("#f23645", "🚫 AVOID — STAY OUT"),
            }
            s_color, s_label = STATUS_META.get(status, ("#6b7280", "—"))
            dir_emoji = "📈" if direction == "CALL" else ("📉" if direction == "PUT" else "")
            dir_color = "#089981" if direction == "CALL" else "#f23645"

            with st.container():
                # Header bar
                st.markdown(f"""
                <div style="background:linear-gradient(90deg,{s_color}22,transparent);
                border-left:5px solid {s_color};border-radius:10px;
                padding:14px 20px;margin:8px 0 4px">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                    <div>
                      <span style="font-size:20px;font-weight:900;color:{s_color}">{s_label}</span>
                      <span style="font-size:16px;font-weight:700;color:#e0e0e0;margin-left:12px">{iname}</span>
                      {'<span style="font-size:15px;font-weight:800;color:'+dir_color+';margin-left:8px">'+dir_emoji+' '+direction+' OPTION</span>' if direction else ''}
                    </div>
                    <div style="text-align:right">
                      <div style="font-size:22px;font-weight:900;color:{s_color}">{conf:.0f}%</div>
                      <div style="font-size:12px;color:#b2b5be">Confidence</div>
                    </div>
                  </div>
                  {'<div style="margin-top:8px;background:#1e222d;border-radius:6px;height:8px;overflow:hidden"><div style="background:'+s_color+';width:'+str(conf)+'%;height:100%;border-radius:6px"></div></div>' if status != 'AVOID' else ''}
                </div>""", unsafe_allow_html=True)

                if status == "AVOID":
                    st.markdown(f"""
                    <div style="background:#1f0d0f;border:1px solid #f23645;border-radius:8px;
                    padding:16px 20px;margin:4px 0 16px">
                      <div style="font-size:14px;font-weight:700;color:#f23645;margin-bottom:6px">
                        ⛔ Why to stay out:
                      </div>
                      <div style="font-size:13px;color:#d1d5db">{rec.get('reason','—')}</div>
                    </div>""", unsafe_allow_html=True)

                elif status == "WATCHLIST":
                    st.markdown(f"""
                    <div style="background:#0d1a2e;border:1px solid #3b82f6;border-radius:8px;
                    padding:16px 20px;margin:4px 0 16px">
                      <div style="font-size:14px;font-weight:700;color:#2962ff;margin-bottom:6px">
                        👀 Monitor — conditions not fully met yet:
                      </div>
                      <div style="font-size:13px;color:#d1d5db">{rec.get('avoid_note',rec.get('reason','—'))}</div>
                    </div>""", unsafe_allow_html=True)

                else:
                    # Full trade card
                    iltp_v = rec.get("ltp", iltp)
                    c1, c2 = st.columns([3, 2])

                    with c1:
                        # Option setup
                        strike   = rec.get("strike", 0)
                        sl_lbl   = rec.get("strike_label", "")
                        exp_lbl  = rec.get("expiry_label", "")
                        e_lo     = rec.get("entry_prem_low",  0)
                        e_hi     = rec.get("entry_prem_high", 0)
                        e_mid    = rec.get("entry_prem_mid",  0)
                        psl      = rec.get("prem_sl", 0)
                        psl_pct  = rec.get("prem_sl_pct", -30)
                        pt1      = rec.get("prem_t1", 0)
                        pt1_pct  = rec.get("prem_t1_pct", 60)
                        pt2      = rec.get("prem_t2", 0)
                        pt2_pct  = rec.get("prem_t2_pct", 100)
                        pt3      = rec.get("prem_t3", 0)
                        pt3_pct  = rec.get("prem_t3_pct", 150)
                        i_sl_lbl = rec.get("idx_sl_label", "")
                        i_t1_lbl = rec.get("idx_t1_label", "")
                        i_t2_lbl = rec.get("idx_t2_label", "")
                        i_t3_lbl = rec.get("idx_t3_label", "")
                        rr       = rec.get("rr_ratio", 0)
                        mh       = rec.get("max_hold", "—")
                        ei_lo    = rec.get("entry_idx_low", 0)
                        ei_hi    = rec.get("entry_idx_high", 0)
                        lot      = rec.get("lot_size", 75)

                        st.markdown(f"""
                        <div style="background:#1e222d;border:2px solid {dir_color};border-radius:12px;
                             padding:18px;margin:6px 0">
                          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                            <div>
                              <span style="color:{dir_color};font-size:22px;font-weight:900">
                                {strike:,} {direction}
                              </span>
                              <span style="color:#b2b5be;font-size:12px;margin-left:8px">{sl_lbl}</span>
                            </div>
                            <div style="background:#131722;border-radius:6px;padding:4px 12px;font-size:12px">
                              📅 {exp_lbl}
                            </div>
                          </div>
                          <div style="background:#131722;border-radius:8px;padding:10px 14px;margin-bottom:10px">
                            <div style="color:#b2b5be;font-size:12px;margin-bottom:4px">ENTRY ZONE</div>
                            <div style="color:#e0e0e0;font-size:16px;font-weight:700">
                              Premium: ₹{e_lo}–₹{e_hi}
                              &nbsp;<span style="color:#b2b5be;font-size:12px">(live: ~₹{e_mid:.0f})</span>
                            </div>
                            <div style="color:#b2b5be;font-size:12px;margin-top:2px">
                              Index entry zone: {ei_lo:,} – {ei_hi:,}
                            </div>
                          </div>
                          <table style="width:100%;border-collapse:collapse;font-size:13px">
                            <tr style="color:#b2b5be;font-size:12px;text-transform:uppercase">
                              <td>Level</td><td>Premium</td><td>Index Level</td><td>P&L / lot</td>
                            </tr>
                            <tr style="color:#f23645;border-top:1px solid #374151">
                              <td style="padding:5px 0;font-weight:700">🛑 Stop Loss</td>
                              <td>₹{psl} <span style="color:#b2b5be;font-size:12px">({psl_pct:+d}%)</span></td>
                              <td style="color:#b2b5be">{i_sl_lbl}</td>
                              <td style="color:#f23645">−₹{int((e_mid-psl)*lot):,}</td>
                            </tr>
                            <tr style="color:#089981;border-top:1px solid #1e2130">
                              <td style="padding:5px 0;font-weight:700">🎯 Target 1</td>
                              <td>₹{pt1} <span style="color:#b2b5be;font-size:12px">({pt1_pct:+d}%)</span></td>
                              <td style="color:#b2b5be">{i_t1_lbl}</td>
                              <td style="color:#089981">+₹{int((pt1-e_mid)*lot):,}</td>
                            </tr>
                            <tr style="color:#089981;border-top:1px solid #1e2130">
                              <td style="padding:5px 0;font-weight:700">🎯 Target 2</td>
                              <td>₹{pt2} <span style="color:#b2b5be;font-size:12px">({pt2_pct:+d}%)</span></td>
                              <td style="color:#b2b5be">{i_t2_lbl}</td>
                              <td style="color:#089981">+₹{int((pt2-e_mid)*lot):,}</td>
                            </tr>
                            <tr style="color:#ffa500;border-top:1px solid #1e2130">
                              <td style="padding:5px 0;font-weight:700">🏆 Target 3</td>
                              <td>₹{pt3} <span style="color:#b2b5be;font-size:12px">({pt3_pct:+d}%)</span></td>
                              <td style="color:#b2b5be">{i_t3_lbl}</td>
                              <td style="color:#ffa500">+₹{int((pt3-e_mid)*lot):,}</td>
                            </tr>
                          </table>
                          <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap">
                            <div style="background:#131722;border-radius:6px;padding:6px 14px;font-size:12px">
                              ⚖️ R:R = <b style="color:#ffa500">1:{rr}</b>
                            </div>
                            <div style="background:#131722;border-radius:6px;padding:6px 14px;font-size:12px">
                              ⏱️ Hold till: <b style="color:#b2b5be">{mh}</b>
                            </div>
                            <div style="background:#131722;border-radius:6px;padding:6px 14px;font-size:12px">
                              📦 Lot: <b>{lot} units</b>
                            </div>
                          </div>
                        </div>""", unsafe_allow_html=True)

                    with c2:
                        # Why this trade
                        reasons = rec.get("reasons", [])
                        st.markdown(f"""
                        <div style="background:#1e222d;border-radius:10px;padding:14px;
                             border:1px solid #374151;height:100%">
                          <div style="color:#ffa500;font-weight:700;font-size:13px;margin-bottom:10px">
                            🧠 ANALYSIS
                          </div>
                          {''.join([f'<div style="font-size:12px;padding:3px 0;border-bottom:1px solid #1e2130;color:#d1d5db">{r}</div>' for r in reasons[:10]])}
                          <div style="color:#b2b5be;font-size:12px;margin-top:8px">
                            VIX: {rec.get('vix_note','—')}
                          </div>
                        </div>""", unsafe_allow_html=True)

                    # Exit conditions
                    exits = rec.get("exits", [])
                    exit_html = "".join([
                        f'<div style="font-size:12px;padding:5px 8px;border-left:3px solid '
                        f'{"#f23645" if "Exit" in e or "⏰" in e else "#374151"};margin:3px 0;'
                        f'color:#d1d5db;background:#1e222d;border-radius:0 6px 6px 0">{e}</div>'
                        for e in exits
                    ])
                    st.markdown(f"""
                    <div style="margin:8px 0 4px">
                      <div style="color:#f23645;font-weight:700;font-size:13px;margin-bottom:6px">
                        ❌ EXIT CONDITIONS (follow strictly)
                      </div>
                      {exit_html}
                    </div>""", unsafe_allow_html=True)

                    # OI & PCR snapshot
                    pcr_d  = rec.get("pcr_data", {})
                    oid    = rec.get("oi_data",  {})
                    if pcr_d.get("ce_oi", 0) > 0:
                        st.markdown(f"""
                        <div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0">
                          <div style="background:#1e222d;border-radius:6px;padding:6px 12px;font-size:12px">
                            📊 PCR: <b style="color:{'#089981' if pcr_d['bias']=='bullish' else '#f23645'}">{pcr_d['pcr']:.2f}</b>
                            <span style="color:#9598a1"> ({pcr_d['label'][:25]})</span>
                          </div>
                          <div style="background:#1e222d;border-radius:6px;padding:6px 12px;font-size:12px">
                            🏋️ Max Pain: <b style="color:#ffa500">{rec.get('max_pain',0):,}</b>
                          </div>
                          <div style="background:#1e222d;border-radius:6px;padding:6px 12px;font-size:12px">
                            🧱 CE Wall: <b style="color:#f23645">{rec.get('ce_wall',0):,}</b>
                            &nbsp;|&nbsp; PE Wall: <b style="color:#089981">{rec.get('pe_wall',0):,}</b>
                          </div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)


# ── TAB 2: AI Expert ─────────────────────────────────────────────────────────
with tab2:
    st.markdown("## 🤖 AI Options Trading Expert")
    st.caption("Powered by Claude AI · Analyzes live market data before every response · Acts as your personal derivatives strategist")

    if not _AI_OK or not ai_expert.is_available():
        st.warning("⚠️ **AI Expert not configured.** Add your `ANTHROPIC_API_KEY` to Streamlit secrets to enable this feature.")
        st.code("""
# In Streamlit Cloud → Settings → Secrets, add:
ANTHROPIC_API_KEY = "sk-ant-..."

# Get your key at: https://console.anthropic.com
        """)
    else:
        # ── Build live market context ─────────────────────────────────────────
        _ai_exp_info  = next_expiry_info()
        _ai_n_chain   = get_live_chain("NSE_INDEX|Nifty 50",
                                       _ai_exp_info["nifty"]["date_str"])
        _ai_b_chain   = get_live_chain("NSE_INDEX|Nifty Bank",
                                       _ai_exp_info["banknifty"]["date_str"])
        _ai_n_df      = add_indicators(get_candles("^NSEI",    "5d", "15m"))
        _ai_b_df      = add_indicators(get_candles("^NSEBANK", "5d", "15m"))
        _ai_n_orb     = get_orb("^NSEI")
        _ai_b_orb     = get_orb("^NSEBANK")
        _ai_n_pivots  = {k: float(v) for k, v in get_pivots("^NSEI").items()}    if get_pivots("^NSEI")    else {}
        _ai_b_pivots  = {k: float(v) for k, v in get_pivots("^NSEBANK").items()} if get_pivots("^NSEBANK") else {}
        _ai_g_quotes  = {n: get_quote(t) for n, t in GLOBAL.items()}
        _ai_fii       = intel.get("fii_dii",  {}) if "intel" in dir() else {}
        _ai_breadth   = intel.get("breadth",  {}) if "intel" in dir() else {}
        _ai_intel     = intel if "intel" in dir() else {}

        _market_ctx = ai_expert.build_market_context(
            quotes       = quotes,
            nifty_df     = _ai_n_df,
            bank_df      = _ai_b_df,
            vix          = vix_i if "vix_i" in dir() else 15.0,
            nifty_orb    = _ai_n_orb,
            bank_orb     = _ai_b_orb,
            nifty_pivots = _ai_n_pivots,
            bank_pivots  = _ai_b_pivots,
            nifty_chain  = _ai_n_chain,
            bank_chain   = _ai_b_chain,
            global_quotes= _ai_g_quotes,
            fii_dii      = _ai_fii,
            breadth      = _ai_breadth,
            intel        = _ai_intel,
            exp_info     = _ai_exp_info,
        )

        # ── Quick question buttons ────────────────────────────────────────────
        st.markdown("**⚡ Quick Analysis**")
        q_cols = st.columns(5)
        for i, (label, _) in enumerate(ai_expert.QUICK_QUESTIONS[:5]):
            with q_cols[i]:
                if st.button(label, key=f"qq_{i}", use_container_width=True):
                    st.session_state.setdefault("ai_messages", [])
                    st.session_state["ai_pending"] = ai_expert.QUICK_QUESTIONS[i][1]

        q_cols2 = st.columns(5)
        for i, (label, _) in enumerate(ai_expert.QUICK_QUESTIONS[5:10]):
            with q_cols2[i]:
                if st.button(label, key=f"qq_{i+5}", use_container_width=True):
                    st.session_state.setdefault("ai_messages", [])
                    st.session_state["ai_pending"] = ai_expert.QUICK_QUESTIONS[i+5][1]

        st.markdown("---")

        # ── Chat history ──────────────────────────────────────────────────────
        if "ai_messages" not in st.session_state:
            st.session_state["ai_messages"] = []

        # ── Pause auto-refresh while AI is active to prevent interruptions ────
        # If last message is from user (AI response was cut off by a refresh),
        # mark it as needing a response so we re-trigger automatically.
        _msgs         = st.session_state["ai_messages"]
        _needs_retry  = bool(_msgs and _msgs[-1]["role"] == "user")
        _ai_busy      = st.session_state.get("_ai_busy", False)

        # Display message history
        for msg in _msgs:
            with st.chat_message(msg["role"],
                                  avatar="🤖" if msg["role"] == "assistant" else "👤"):
                st.markdown(msg["content"])

        # ── Handle pending quick-question ─────────────────────────────────────
        pending = st.session_state.pop("ai_pending", None)

        # ── Chat input ────────────────────────────────────────────────────────
        user_input = st.chat_input(
            "Ask about NIFTY/BANKNIFTY options... e.g. 'Should I buy a Call right now?'"
        ) or pending

        # If auto-refresh cut off the previous response, retry with saved question
        if not user_input and _needs_retry:
            retry_q = _msgs[-1]["content"]
            st.info(f"⟳ Auto-retrying interrupted response for: *\"{retry_q[:60]}\"*")
            user_input = None   # will be handled in the retry block below
            _do_retry  = True
        else:
            _do_retry = False

        def _run_ai(question: str):
            """Show user bubble (if new), stream AI response, save both."""
            # Only add user message if it's a NEW question (not a retry)
            msgs_now = st.session_state["ai_messages"]
            if not msgs_now or msgs_now[-1]["content"] != question or msgs_now[-1]["role"] != "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(question)
                st.session_state["ai_messages"].append({"role": "user", "content": question})

            # Build API context (last 10 turns)
            api_msgs = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["ai_messages"][-10:]
            ]

            # Mark busy so autorefresh is paused
            st.session_state["_ai_busy"] = True
            try:
                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("🧠 Analyzing live market data..."):
                        response = st.write_stream(
                            ai_expert.stream_response(api_msgs, _market_ctx)
                        )
                if response:
                    st.session_state["ai_messages"].append(
                        {"role": "assistant", "content": response}
                    )
                else:
                    st.session_state["ai_messages"].append(
                        {"role": "assistant",
                         "content": "⚠️ Empty response received. Please try again."}
                    )
            except Exception as e:
                st.error(f"❌ AI error: {e}")
            finally:
                st.session_state["_ai_busy"] = False

        if user_input:
            _run_ai(user_input)
        elif _do_retry:
            _run_ai(_msgs[-1]["content"])

        # ── Clear chat button ─────────────────────────────────────────────────
        if st.session_state.get("ai_messages"):
            cc1, cc2 = st.columns([1, 5])
            with cc1:
                if st.button("🗑️ Clear conversation", key="clear_ai"):
                    st.session_state["ai_messages"] = []
                    st.session_state["_ai_busy"] = False
                    st.rerun()

        # ── Market context preview (collapsible) ──────────────────────────────
        with st.expander("🔍 View market data injected into AI context", expanded=False):
            st.code(_market_ctx, language="")

# ── TAB 3: Nifty ─────────────────────────────────────────────────────────────
with tab4:
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
                color = "#f23645" if level.startswith("R") else ("#089981" if level.startswith("S") else "#ffa500")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 0">'
                            f'<span style="color:{color};font-weight:700;font-size:13px">{level}</span>'
                            f'<span style="font-size:13px">{val:,}</span></div>', unsafe_allow_html=True)

# ── TAB 3: Bank Nifty ────────────────────────────────────────────────────────
with tab5:
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
                color = "#f23645" if level.startswith("R") else ("#089981" if level.startswith("S") else "#ffa500")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:2px 0">'
                            f'<span style="color:{color};font-weight:700;font-size:13px">{level}</span>'
                            f'<span style="font-size:13px">{val:,}</span></div>', unsafe_allow_html=True)

# ── TAB 4: Global Cues ───────────────────────────────────────────────────────
with tab6:
    global_quotes = {name: get_quote(ticker) for name, ticker in GLOBAL.items()}
    gs = compute_global_sentiment(global_quotes)

    # ── Composite Sentiment Banner ────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.3);border:2px solid {gs['color']};border-radius:14px;
                padding:16px 24px;margin-bottom:16px;display:flex;align-items:center;gap:24px">
      <div>
        <div style="font-size:12px;color:#b2b5be;text-transform:uppercase;letter-spacing:.06em">
          Global Sentiment for India</div>
        <div style="font-size:22px;font-weight:800;color:{gs['color']}">{gs['label']}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #374151;padding-left:24px">
        <div style="font-size:12px;color:#b2b5be">Score</div>
        <div style="font-size:36px;font-weight:900;color:{gs['color']}">{gs['score']:+d}</div>
        <div style="font-size:12px;color:#9598a1">out of ±10</div>
      </div>
      <div style="font-size:12px;color:#b2b5be;flex:1">
        {'  ·  '.join([f"<span style='color:{'#089981' if f[2]=='bull' else ('#f23645' if f[2]=='bear' else '#9ca3af')}'>{f[0]}: {f[1]}</span>" for f in gs['factors']])}
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
                <div class="metric-card" style="border-left-color:{'#089981' if q['chg']>=0 else '#f23645'}">
                  <div style="font-size:12px;color:#b2b5be">{name}</div>
                  <div style="font-size:18px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
                  <div style="font-size:12px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
                </div>""", unsafe_allow_html=True)

    # ── Macro Impact Matrix ───────────────────────────────────────────────────
    st.markdown('<div class="section-title" style="margin-top:16px">Macro Impact on India</div>',
                unsafe_allow_html=True)

    def safe_nested_get_macro(d, key, subkey, default=0):
        """Safely get nested dict values for macro section."""
        val = d.get(key) if d else None
        return val.get(subkey, default) if val and isinstance(val, dict) else default

    crude_pct  = safe_nested_get_macro(global_quotes, "Crude Oil",    "pct", 0)
    gold_pct   = safe_nested_get_macro(global_quotes, "Gold",         "pct", 0)
    dxy_pct    = safe_nested_get_macro(global_quotes, "Dollar Index", "pct", 0)
    usdinr_pct = safe_nested_get_macro(global_quotes, "USD/INR",      "pct", 0)
    tnx_ltp    = safe_nested_get_macro(global_quotes, "US 10Y Yield", "ltp", 4.2)

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
            s_color = "#089981" if h["sentiment"] == "bullish" else \
                      ("#f23645" if h["sentiment"] == "bearish" else "#9ca3af")
            s_icon  = "▲" if h["sentiment"] == "bullish" else \
                      ("▼" if h["sentiment"] == "bearish" else "—")
            st.markdown(
                f'<div style="padding:7px 0;border-bottom:1px solid #1e2130;font-size:13px">'
                f'<span style="color:{s_color};font-weight:700;margin-right:6px">{s_icon}</span>'
                f'<span style="color:#e0e0e0">{h["title"]}</span>'
                f'<span style="color:#b2b5be;font-size:12px;margin-left:8px">[{h["source"]}]</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("News feed temporarily unavailable. Check internet connection.")

    st.caption("⚠️ News sentiment uses keyword analysis — not financial advice. Verify before acting.")

# ── TAB 5: Trade Plan ────────────────────────────────────────────────────────
with tab7:
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
            <div class="metric-card" style="border-left-color:#2962ff;margin-top:8px">
              <div style="display:flex;gap:40px;flex-wrap:wrap">
                <div><div class="trade-label">Max Risk Amount</div>
                     <div style="color:#ffa500;font-weight:800;font-size:18px">₹{max_risk_amt:,.0f}</div></div>
                <div><div class="trade-label">Loss per Lot</div>
                     <div style="color:#f23645;font-weight:800;font-size:18px">₹{max_loss_per_lot:,.0f}</div></div>
                <div><div class="trade-label">Max Lots to Trade</div>
                     <div style="color:#089981;font-weight:800;font-size:28px">{max_lots}</div></div>
                <div><div class="trade-label">Premium Required</div>
                     <div style="font-weight:700;font-size:18px">₹{premium_needed:,.0f}</div></div>
              </div>
              <div style="font-size:12px;color:#9598a1;margin-top:8px">
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

with tab8:
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
                Current: <b style="color:#f23645">{cur_price:,.2f}</b> &nbsp;|&nbsp;
                <span style="color:#b2b5be">{row.get('note','')}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="alert-box">
                🔔 <b>{row['index']}</b> {row['condition']} <b>{row['price']:,.2f}</b> &nbsp;|&nbsp;
                Current: {cur_price:,.2f} &nbsp;|&nbsp;
                Gap: {abs(cur_price - row['price']):,.2f} pts &nbsp;|&nbsp;
                <span style="color:#b2b5be">{row.get('note','')}</span>
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

with tab9:
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
                    line=dict(color="#089981" if stats["total_pnl"] >= 0 else "#f23645", width=2),
                    fillcolor="rgba(8,153,129,0.1)" if stats["total_pnl"] >= 0 else "rgba(242,54,69,0.1)",
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
                    marker_colors=["#089981", "#f23645", "#ffa500"],
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
                    marker_color=["#089981" if v >= 0 else "#f23645" for v in by_index["pnl"]],
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
                    marker_color=["#089981" if v >= 0 else "#f23645" for v in by_strat["pnl"]],
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
                  <div style="color:#089981;font-weight:700;font-size:16px">🏆 Best Trade</div>
                  <div style="font-size:24px;font-weight:800;color:#089981">₹{best_row['pnl']:,.0f}</div>
                  <div style="color:#b2b5be;font-size:13px">{best_row['date'].date() if pd.notna(best_row['date']) else ''} &nbsp;|&nbsp; {best_row['index']} &nbsp;|&nbsp; {best_row['direction']}</div>
                  <div style="color:#b2b5be;font-size:12px;margin-top:6px">{best_row['notes'][:120] if best_row['notes'] else ''}...</div>
                </div>""", unsafe_allow_html=True)
            with bc2:
                worst_row = jdf.loc[jdf["pnl"].idxmin()]
                st.markdown(f"""
                <div class="trade-card-put">
                  <div style="color:#f23645;font-weight:700;font-size:16px">📉 Worst Trade</div>
                  <div style="font-size:24px;font-weight:800;color:#f23645">₹{worst_row['pnl']:,.0f}</div>
                  <div style="color:#b2b5be;font-size:13px">{worst_row['date'].date() if pd.notna(worst_row['date']) else ''} &nbsp;|&nbsp; {worst_row['index']} &nbsp;|&nbsp; {worst_row['direction']}</div>
                  <div style="color:#b2b5be;font-size:12px;margin-top:6px">{worst_row['notes'][:120] if worst_row['notes'] else ''}...</div>
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
                    if v > 0:   return "color: #089981; font-weight: 700"
                    if v < 0:   return "color: #f23645; font-weight: 700"
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
with tab10:
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
                sig_color = "#089981" if row["Signal"] == "BUY" else "#ffa500"
                chg_color = "#089981" if row["Chg%"] >= 0 else "#f23645"
                rsi_color = "#089981" if 50 < row["RSI"] < 70 else ("#ffa500" if row["RSI"] <= 35 else "#e0e0e0")
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{sig_color}">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                    <div>
                      <div style="font-size:18px;font-weight:800;color:{sig_color}">{row['Stock']}</div>
                      <div style="font-size:12px;color:#9598a1">{row['Sector']} &nbsp;|&nbsp;
                        <span style="background:{sig_color};color:#000;padding:1px 8px;border-radius:10px;font-weight:700;font-size:12px">{row['Signal']}</span>
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
                  <div style="margin-top:8px;font-size:12px;color:#b2b5be">📋 {row['Reasons']}</div>
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
            if val == "BUY":    return "background-color:#0d2618;color:#089981;font-weight:700"
            if val == "WATCH":  return "background-color:#2a1f0d;color:#ffa500;font-weight:700"
            if val == "AVOID":  return "background-color:#2a0d0d;color:#f23645;font-weight:700"
            return ""

        def color_score(val):
            try:
                v = float(val)
                if v >= 4:  return "color:#089981;font-weight:700"
                if v >= 2:  return "color:#ffa500;font-weight:700"
                if v <= -2: return "color:#f23645;font-weight:700"
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
        <div style="background:#1e222d;border-radius:8px;padding:12px 16px;margin-top:8px;
                    border-left:4px solid #ffa500;font-size:12px;color:#b2b5be">
        ⚠️ <b style="color:#ffa500">Disclaimer:</b>
        These scores use technical indicators on daily data. They are for research and swing trade ideas only —
        not financial advice. Always do your own analysis before investing. Past performance does not guarantee future returns.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 10 — Mutual Funds
# ══════════════════════════════════════════════════════════════════════════════
with tab11:
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
        "Very Low": "#3b82f6", "Low": "#089981", "Moderate": "#ffa500",
        "Moderate-High": "#f97316", "High": "#f23645", "Very High": "#dc2626",
    }
    star_map = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐"}

    for i, fund in enumerate(top_funds):
        rc = risk_colors.get(fund["risk"], "#9ca3af")
        ret_color_1y = "#089981" if fund["ret_1y"] > 15 else ("#ffa500" if fund["ret_1y"] > 10 else "#f23645")
        corpus_10y = round(mf_sip * (((1 + fund["ret_5y"]/100/12) ** 120 - 1) / (fund["ret_5y"]/100/12)), 0)

        # Live NAV lookup
        nav_data = lookup_nav(amfi_navs, fund.get("amfi_search", []))
        if nav_data:
            nav_html = f"""
              <div style="text-align:center;border:1px solid {rc};border-radius:8px;padding:6px 14px">
                <div class="trade-label">Live NAV</div>
                <div style="font-size:20px;font-weight:800;color:{rc}">₹{nav_data['nav']:,.2f}</div>
                <div style="font-size:12px;color:#9598a1">as of {nav_data['date']}</div>
              </div>"""
        else:
            nav_html = '<div style="text-align:center"><div class="trade-label">NAV</div><div style="color:#b2b5be;font-size:12px">N/A</div></div>'

        st.markdown(f"""
        <div class="metric-card" style="border-left-color:{rc};margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
            <div style="flex:1;min-width:200px">
              <div style="font-size:16px;font-weight:800;color:#e0e0e0">#{i+1} {fund['name']}</div>
              <div style="font-size:12px;color:#b2b5be;margin-top:2px">
                {fund['category']} &nbsp;|&nbsp;
                <span style="color:{rc};font-weight:700">{fund['risk']} Risk</span> &nbsp;|&nbsp;
                {star_map.get(fund['stars'], '⭐⭐⭐')} &nbsp;|&nbsp;
                Min SIP: ₹{fund['min_sip']:,} &nbsp;|&nbsp; AUM: {fund['aum']}
              </div>
              <div style="font-size:12px;color:#9598a1;margin-top:4px">🕐 Horizon: {fund['horizon']}</div>
            </div>
            <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
              {nav_html}
              <div style="text-align:center">
                <div class="trade-label">1Y Return</div>
                <div style="font-size:18px;font-weight:800;color:{ret_color_1y}">{fund['ret_1y']}%</div>
              </div>
              <div style="text-align:center">
                <div class="trade-label">3Y Return</div>
                <div style="font-size:16px;font-weight:700;color:#089981">{fund['ret_3y']}%</div>
              </div>
              <div style="text-align:center">
                <div class="trade-label">5Y Return</div>
                <div style="font-size:16px;font-weight:700;color:#089981">{fund['ret_5y']}%</div>
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
    <div style="background:#1e222d;border-radius:8px;padding:14px 18px;margin-top:12px;
                border-left:4px solid #3b82f6;font-size:13px;color:#b2b5be">
    ⚠️ <b style="color:#2962ff">Disclaimer:</b>
    Returns shown are approximate historical figures for reference only.
    Mutual fund investments are subject to market risks. Past returns do not guarantee future performance.
    Please read the Scheme Information Document (SID) carefully before investing.
    Consider consulting a SEBI-registered financial advisor for personalised advice.
    </div>""", unsafe_allow_html=True)


st.divider()
st.caption("📡 Dashboard auto-refreshes every 30 seconds during market hours (9:15 AM – 3:30 PM IST) via browser meta-refresh.")
