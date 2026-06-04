"""
Zerodha Kite Connect data fetcher for the India Market Dashboard.
Provides real-time quotes, OHLC and historical candles via kiteconnect.

Setup:
  1. pip install kiteconnect
  2. Add ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN to your .env file
  3. Refresh ZERODHA_ACCESS_TOKEN daily after login
"""
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

try:
    from kiteconnect import KiteConnect
    _KITE_LIB = True
except ImportError:
    _KITE_LIB = False

# ── yfinance ticker → Zerodha instrument symbol ───────────────────────────────
YF_TO_ZERODHA = {
    "^NSEI":     "NSE:NIFTY 50",
    "^NSEBANK":  "NSE:NIFTY BANK",
    "^INDIAVIX": "NSE:INDIA VIX",
    "^BSESN":    "BSE:SENSEX",
    "^CNXIT":    "NSE:NIFTY IT",
}

# ── Instrument tokens for historical candle API ───────────────────────────────
INDEX_TOKENS = {
    "NSE:NIFTY 50":   256265,
    "BSE:SENSEX":     265,
    "NSE:NIFTY BANK": 260105,
    "NSE:INDIA VIX":  264969,
    "NSE:NIFTY IT":   259849,
}

# ── Nifty 50 stocks: display name → Zerodha symbol + instrument token ─────────
NIFTY50 = {
    "Reliance":         ("NSE:RELIANCE",   738561),
    "TCS":              ("NSE:TCS",        2953217),
    "HDFC Bank":        ("NSE:HDFCBANK",   341249),
    "Infosys":          ("NSE:INFY",       408065),
    "ICICI Bank":       ("NSE:ICICIBANK",  1270529),
    "HUL":              ("NSE:HINDUNILVR", 356865),
    "ITC":              ("NSE:ITC",        424961),
    "SBI":              ("NSE:SBIN",       779521),
    "Bajaj Finance":    ("NSE:BAJFINANCE", 81153),
    "Bharti Airtel":    ("NSE:BHARTIARTL", 2714625),
    "Kotak Bank":       ("NSE:KOTAKBANK",  492033),
    "L&T":              ("NSE:LT",         2939649),
    "Axis Bank":        ("NSE:AXISBANK",   1510401),
    "Asian Paints":     ("NSE:ASIANPAINT", 60417),
    "Maruti":           ("NSE:MARUTI",     2815745),
    "Titan":            ("NSE:TITAN",      897537),
    "Sun Pharma":       ("NSE:SUNPHARMA",  857857),
    "UltraTech Cement": ("NSE:ULTRACEMCO", 2952193),
    "Wipro":            ("NSE:WIPRO",      969473),
    "ONGC":             ("NSE:ONGC",       633601),
    "Power Grid":       ("NSE:POWERGRID",  3834113),
    "NTPC":             ("NSE:NTPC",       2977281),
    "Tech Mahindra":    ("NSE:TECHM",      3465729),
    "Nestle":           ("NSE:NESTLEIND",  4598529),
    "HCL Tech":         ("NSE:HCLTECH",    1850625),
    "Tata Motors":      ("NSE:TMPV",       884737),    # post-demerger PV entity
    "Tata Steel":       ("NSE:TATASTEEL",  895745),
    "JSW Steel":        ("NSE:JSWSTEEL",   3001089),
    "Hindalco":         ("NSE:HINDALCO",   348929),
    "M&M":              ("NSE:M&M",        519937),
    "Dr Reddy's":       ("NSE:DRREDDY",    225537),
    "Cipla":            ("NSE:CIPLA",      177665),
    "Bajaj Auto":       ("NSE:BAJAJ-AUTO", 4267265),
    "Eicher Motors":    ("NSE:EICHERMOT",  232961),
    "Coal India":       ("NSE:COALINDIA",  5215745),
    "Hero MotoCorp":    ("NSE:HEROMOTOCO", 345089),
    "Apollo Hospitals": ("NSE:APOLLOHOSP", 40193),
    "Tata Consumer":    ("NSE:TATACONSUM", 878593),
    "Britannia":        ("NSE:BRITANNIA",  140033),
    "IndusInd Bank":    ("NSE:INDUSINDBK", 1346049),
    "SBI Life":         ("NSE:SBILIFE",    5582849),
    "HDFC Life":        ("NSE:HDFCLIFE",   119553),
    "Adani Ports":      ("NSE:ADANIPORTS", 3861249),
    "Adani Ent.":       ("NSE:ADANIENT",   6401),
    "Grasim":           ("NSE:GRASIM",     315393),
    "Divi's Labs":      ("NSE:DIVISLAB",   2800641),
    "Bajaj Finserv":    ("NSE:BAJAJFINSV", 4268801),
    "UPL":              ("NSE:UPL",        2889473),
    "Shree Cement":     ("NSE:SHREECEM",   794369),
}

# ── Interval mapping: yfinance style → Zerodha style ─────────────────────────
INTERVAL_MAP = {
    "1m":  "minute",
    "2m":  "3minute",
    "5m":  "5minute",
    "15m": "15minute",
    "30m": "30minute",
    "1h":  "60minute",
    "60m": "60minute",
    "1d":  "day",
    "1wk": "day",   # use daily and resample if needed
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_kite():
    """Return an authenticated KiteConnect instance, or None if unavailable."""
    if not _KITE_LIB:
        return None
    api_key      = os.getenv("ZERODHA_API_KEY", "")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")
    if not api_key or not access_token:
        return None
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        return kite
    except Exception as e:
        log.warning("Zerodha KiteConnect init failed: %s", e)
        return None


def is_available() -> bool:
    """True if kiteconnect is installed and credentials are configured."""
    return _get_kite() is not None


def _parse_quote(v: dict) -> dict:
    """Convert a raw Zerodha quote dict into the dashboard's common format."""
    ltp  = float(v.get("last_price") or 0)
    ohlc = v.get("ohlc") or {}
    prev = float(ohlc.get("close") or ltp)   # ohlc.close = prev day official close ✓
    chg  = round(ltp - prev, 2)
    pct  = round((chg / prev * 100) if prev else 0, 2)
    return {
        "ltp":    ltp,
        "open":   float(ohlc.get("open") or ltp),
        "high":   float(ohlc.get("high") or ltp),
        "low":    float(ohlc.get("low")  or ltp),
        "prev":   prev,
        "chg":    chg,
        "pct":    pct,
        "volume": int(v.get("volume") or 0),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_quotes(instruments: list) -> dict:
    """
    Full market snapshot for a list of Zerodha-format symbols.
    Returns {symbol: {ltp, open, high, low, prev, chg, pct, volume}}
    Max 500 instruments per call (Zerodha limit).
    """
    kite = _get_kite()
    if not kite:
        return {}
    try:
        raw = kite.quote(instruments)
        return {sym: _parse_quote(v) for sym, v in raw.items()}
    except Exception as e:
        log.warning("Zerodha get_quotes failed: %s", e)
        return {}


def get_index_quotes() -> dict:
    """
    Fetch all 5 Indian index quotes.
    Returns {yf_ticker: quote_dict}  e.g. {"^NSEI": {...}, "^BSESN": {...}}
    """
    syms = list(YF_TO_ZERODHA.values())
    raw  = get_quotes(syms)
    inv  = {v: k for k, v in YF_TO_ZERODHA.items()}
    return {inv[sym]: q for sym, q in raw.items() if sym in inv}


def get_stock_quotes() -> dict:
    """
    Fetch real-time quotes for all Nifty 50 stocks.
    Returns {display_name: quote_dict}
    """
    syms  = [sym for sym, _ in NIFTY50.values()]
    raw   = get_quotes(syms)
    inv   = {sym: name for name, (sym, _) in NIFTY50.items()}
    return {inv[sym]: q for sym, q in raw.items() if sym in inv}


def get_candles(instrument_key: str, interval: str, from_date: str, to_date: str) -> pd.DataFrame:
    """
    Fetch OHLCV candle history from Zerodha.

    instrument_key : Zerodha symbol ('NSE:NIFTY 50') or yf ticker ('^NSEI')
    interval       : yfinance-style ('1m', '5m', '15m', '1h', '1d')
    from_date      : 'YYYY-MM-DD'
    to_date        : 'YYYY-MM-DD'

    Returns DataFrame with columns: timestamp, open, high, low, close, volume
    (empty DataFrame on error or if credentials missing)
    """
    kite = _get_kite()
    if not kite:
        return pd.DataFrame()
    try:
        # Resolve yfinance ticker → Zerodha symbol
        if instrument_key.startswith("^"):
            instrument_key = YF_TO_ZERODHA.get(instrument_key, "")
        token = INDEX_TOKENS.get(instrument_key)
        if not token:
            log.debug("No Zerodha token for %s", instrument_key)
            return pd.DataFrame()

        z_interval  = INTERVAL_MAP.get(interval, "15minute")
        is_intraday = z_interval not in ("day", "week", "month")
        fmt = "%Y-%m-%d %H:%M:%S"

        if is_intraday:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").strftime(fmt)
            to_dt   = (datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)).strftime(fmt)
        else:
            from_dt = from_date
            to_dt   = to_date

        records = kite.historical_data(token, from_dt, to_dt, z_interval)
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.rename(columns={"date": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    except Exception as e:
        log.warning("Zerodha get_candles failed: %s", e)
        return pd.DataFrame()
