"""
Upstox API data layer — live quotes, historical candles, option chain.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import streamlit as st
import config
import upstox_auth

IST = pytz.timezone("Asia/Kolkata")


def _headers() -> dict:
    return upstox_auth.get_headers()


# ── Live market data ──────────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def get_market_quotes(instrument_keys: list[str]) -> dict:
    """
    Returns full quote for each instrument key.
    Response shape per key:
      { ltp, open, high, low, close, volume, oi, net_change, ... }
    """
    joined = ",".join(instrument_keys)
    url = f"{config.BASE_URL}/market-quote/quotes"
    try:
        r = requests.get(url, params={"instrument_key": joined}, headers=_headers(), timeout=10)
        r.raise_for_status()
        data = r.json().get("data", {})
        return data
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            st.error("Access token expired. Run `python upstox_auth.py` to get a fresh token.")
        else:
            st.error(f"Quote API error: {e}")
        return {}
    except Exception as e:
        st.error(f"Network error: {e}")
        return {}


@st.cache_data(ttl=15)
def get_ltp(instrument_keys: list[str]) -> dict:
    """Returns {instrument_key: ltp} mapping."""
    joined = ",".join(instrument_keys)
    url = f"{config.BASE_URL}/market-quote/ltp"
    try:
        r = requests.get(url, params={"instrument_key": joined}, headers=_headers(), timeout=10)
        r.raise_for_status()
        data = r.json().get("data", {})
        return {k: v.get("last_price", 0) for k, v in data.items()}
    except Exception:
        return {}


# ── Historical candle data ────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_historical_candles(
    instrument_key: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles. Returns DataFrame with columns:
      timestamp, open, high, low, close, volume, oi
    interval: Upstox interval string e.g. "1minute", "day", "week"
    dates: "YYYY-MM-DD"
    """
    # Upstox uses different endpoints for intraday vs historical
    intraday_intervals = {"1minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute"}

    if interval in intraday_intervals:
        url = f"{config.BASE_URL}/historical-candle/intraday/{instrument_key}/{interval}"
        params = {}
    else:
        url = f"{config.BASE_URL}/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        params = {}

    try:
        r = requests.get(url, params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        candles = r.json().get("data", {}).get("candles", [])
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume", "oi"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            st.error("Access token expired. Run `python upstox_auth.py` to get a fresh token.")
        else:
            st.error(f"Candle API error: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Candle fetch error: {e}")
        return pd.DataFrame()


# ── Option chain ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=12)
def get_option_chain(instrument_key: str, expiry_date: str) -> pd.DataFrame:
    """
    Returns option chain DataFrame with columns:
      strike, ce_ltp, ce_iv, ce_oi, ce_volume, ce_delta,
               pe_ltp, pe_iv, pe_oi, pe_volume, pe_delta
    """
    url = f"{config.BASE_URL}/option/chain"
    params = {"instrument_key": instrument_key, "expiry_date": expiry_date}
    try:
        r = requests.get(url, params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()

        rows = []
        for item in data:
            strike = item.get("strike_price", 0)
            ce = item.get("call_options", {}).get("market_data", {})
            pe = item.get("put_options", {}).get("market_data", {})
            ce_greeks = item.get("call_options", {}).get("option_greeks", {})
            pe_greeks = item.get("put_options", {}).get("option_greeks", {})
            rows.append({
                "strike":    strike,
                "ce_ltp":    ce.get("ltp", 0),
                "ce_iv":     ce_greeks.get("iv", 0),
                "ce_oi":     ce.get("oi", 0),
                "ce_volume": ce.get("volume", 0),
                "ce_delta":  ce_greeks.get("delta", 0),
                "pe_ltp":    pe.get("ltp", 0),
                "pe_iv":     pe_greeks.get("iv", 0),
                "pe_oi":     pe.get("oi", 0),
                "pe_volume": pe.get("volume", 0),
                "pe_delta":  pe_greeks.get("delta", 0),
            })
        df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
        return df
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            st.error("Access token expired. Run `python upstox_auth.py` to get a fresh token.")
        else:
            st.error(f"Option chain API error: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Option chain fetch error: {e}")
        return pd.DataFrame()


# ── Utility ───────────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def default_date_range(interval: str) -> tuple[str, str]:
    """Return sensible (from_date, to_date) strings for the given interval."""
    today = datetime.now(IST).date()
    delta_map = {
        "day":   365,
        "week":  365 * 2,
        "month": 365 * 5,
    }
    days = delta_map.get(interval, 30)
    from_date = today - timedelta(days=days)
    return str(from_date), str(today)
