"""
Professional Intraday Options Trade Recommendation Engine
For NIFTY 50, BANK NIFTY, FIN NIFTY

Scoring methodology:
  Each factor scores +/- against a 50-point base.
  Final score 0-100 maps to confidence %.
  Direction (CALL/PUT) chosen by whichever scores higher.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytz
import requests
import logging

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# OPTION CHAIN ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_pcr(live_chain: dict) -> dict:
    """Put-Call Ratio from option chain OI."""
    ce_oi = sum(v.get("ce_oi", 0) for v in live_chain.values())
    pe_oi = sum(v.get("pe_oi", 0) for v in live_chain.values())
    if ce_oi == 0:
        return {"pcr": 1.0, "label": "No OI data", "bias": "neutral", "ce_oi": 0, "pe_oi": 0}
    pcr = round(pe_oi / ce_oi, 2)
    if pcr >= 1.5:
        label, bias = "Extreme fear / Contrarian Bullish", "bullish"
    elif pcr >= 1.2:
        label, bias = "Bearish sentiment", "bearish"
    elif pcr >= 0.9:
        label, bias = "Neutral", "neutral"
    elif pcr >= 0.7:
        label, bias = "Bullish sentiment", "bullish"
    else:
        label, bias = "Extreme greed / Contrarian Bearish", "bearish"
    return {"pcr": pcr, "label": label, "bias": bias, "ce_oi": ce_oi, "pe_oi": pe_oi}


def compute_oi_analysis(live_chain: dict, ltp: float, step: int) -> dict:
    """
    Identify key OI support/resistance and max pain from the option chain.
    Returns:
      max_pain    : strike with min total premium loss for market makers
      ce_wall     : strike with highest CE OI (resistance / call writing)
      pe_wall     : strike with highest PE OI (support / put writing)
      ce_unwinding: strikes where CE OI is falling (bearish signal)
      pe_unwinding: strikes where PE OI is falling (bullish signal)
    """
    if not live_chain:
        return {}

    atm = round(int(round(ltp / step) * step))
    # Focus on ±10 strikes from ATM
    relevant = {k: v for k, v in live_chain.items()
                if atm - step * 10 <= k <= atm + step * 10}
    if not relevant:
        relevant = live_chain

    # Max pain
    strikes = sorted(relevant.keys())
    min_pain, max_pain_strike = float("inf"), strikes[0]
    for test_strike in strikes:
        pain = 0
        for s, v in relevant.items():
            ce_ltp = v.get("ce", 0)
            pe_ltp = v.get("pe", 0)
            ce_oi  = v.get("ce_oi", 0)
            pe_oi  = v.get("pe_oi", 0)
            if test_strike > s:
                pain += (test_strike - s) * ce_oi
            elif test_strike < s:
                pain += (s - test_strike) * pe_oi
        if pain < min_pain:
            min_pain, max_pain_strike = pain, test_strike

    # Highest OI strikes (call wall = resistance, put wall = support)
    ce_wall = max(relevant, key=lambda k: relevant[k].get("ce_oi", 0), default=atm)
    pe_wall = max(relevant, key=lambda k: relevant[k].get("pe_oi", 0), default=atm)

    # Net OI bias above/below ATM
    ce_above = sum(v.get("ce_oi", 0) for k, v in relevant.items() if k > atm)
    pe_below  = sum(v.get("pe_oi", 0) for k, v in relevant.items() if k < atm)

    return {
        "max_pain":    max_pain_strike,
        "ce_wall":     ce_wall,
        "pe_wall":     pe_wall,
        "ce_above_oi": ce_above,
        "pe_below_oi": pe_below,
        "atm":         atm,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTERNAL DATA — FII/DII & MARKET BREADTH
# ─────────────────────────────────────────────────────────────────────────────

def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except Exception:
        pass
    return s


def fetch_fii_dii() -> dict:
    """
    Fetch FII/DII provisional cash market data from NSE India.
    Returns {fii_net, dii_net, fii_buy, fii_sell, dii_buy, dii_sell, date}
    Falls back to {} on error.
    """
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
    except Exception as e:
        log.debug("FII/DII fetch failed: %s", e)
        return {}


def fetch_market_breadth() -> dict:
    """
    Fetch advance/decline data from NSE India.
    Returns {advances, declines, unchanged, ratio, label}
    """
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
                if pct > 0.5:
                    advances += 1
                elif pct < -0.5:
                    declines += 1
                else:
                    unchanged += 1
        total = advances + declines + unchanged or 1
        ratio = round(advances / max(declines, 1), 2)
        if ratio >= 2.0:
            label, bias = f"Strong breadth ({advances}A/{declines}D)", "bullish"
        elif ratio >= 1.2:
            label, bias = f"Moderate breadth ({advances}A/{declines}D)", "bullish"
        elif ratio >= 0.8:
            label, bias = f"Mixed breadth ({advances}A/{declines}D)", "neutral"
        else:
            label, bias = f"Weak breadth ({advances}A/{declines}D)", "bearish"
        return {
            "advances": advances, "declines": declines,
            "unchanged": unchanged, "ratio": ratio,
            "label": label, "bias": bias,
        }
    except Exception as e:
        log.debug("Market breadth fetch failed: %s", e)
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# CURRENT TIME UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _market_minutes_elapsed() -> int:
    """Minutes since market open (9:15 AM IST). Negative if pre-open."""
    now = datetime.now(IST)
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    return int((now - open_t).total_seconds() / 60)


def _max_hold_till(entry_minutes_from_open: int) -> str:
    """Given minutes from open, return latest safe exit time string."""
    if entry_minutes_from_open < 0:
        return "Wait — market not open"
    if entry_minutes_from_open < 30:    # before 9:45
        return "2:30 PM (full session)"
    if entry_minutes_from_open < 105:   # before 11:00
        return "2:00 PM"
    if entry_minutes_from_open < 165:   # before 12:00
        return "1:30 PM"
    if entry_minutes_from_open < 225:   # before 1:00
        return "12:30 PM – 1:00 PM max"
    return "⚠️ TOO LATE — avoid new entries after 1:30 PM"


# ─────────────────────────────────────────────────────────────────────────────
# CORE RECOMMENDATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def generate_recommendation(
    name: str,
    df: pd.DataFrame,
    ltp: float,
    vix: float,
    orb: dict,
    pivots: dict,
    live_chain: dict,
    global_score: int,       # -10 to +10 from compute_global_sentiment
    step: int = 50,
    lot_size: int = 75,
    expiry_label: str = "",
    expiry_date_str: str = "",
    fii_dii: dict = None,
    breadth: dict = None,
) -> dict:
    """
    Generate a complete professional trade recommendation.
    Returns a rich dict consumed by the UI renderer.
    """
    fii_dii  = fii_dii  or {}
    breadth  = breadth  or {}
    mins_open = _market_minutes_elapsed()

    # ── Hard no-trade conditions ──────────────────────────────────────────────
    if df.empty or len(df) < 20 or ltp == 0:
        return {"status": "AVOID", "reason": "Insufficient data — market may not be open yet."}
    if vix and vix > 28:
        return {"status": "AVOID",
                "reason": f"VIX at {vix:.1f} — extreme volatility. Buying options is very risky today. Stay out."}
    if mins_open > 255:   # after 1:30 PM
        return {"status": "AVOID",
                "reason": "After 1:30 PM — no new intraday entries. Exit existing positions by 3:00 PM."}

    last    = df.iloc[-1]
    prev    = df.iloc[-2] if len(df) > 2 else last

    # ── Extract indicators ────────────────────────────────────────────────────
    rsi      = float(last.get("rsi",   50) or 50)
    macd     = float(last.get("macd",   0) or 0)
    macd_s   = float(last.get("macd_s", 0) or 0)
    ema9     = float(last.get("ema9",  ltp) or ltp)
    ema21    = float(last.get("ema21", ltp) or ltp)
    ema50    = float(last.get("ema50", ltp) or ltp)
    vwap     = float(last.get("vwap",  ltp) or ltp)
    st_dir   = int(last.get("supertrend_dir", 0) or 0)
    obv      = float(last.get("obv",     0) or 0)
    obv_ema  = float(last.get("obv_ema", 0) or 0)
    vol      = float(last.get("volume",  0) or 0)
    avg_vol  = float(df["volume"].tail(20).mean() or 1) if "volume" in df.columns else 1
    vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0

    orb_high = float(orb["high"]) if orb and orb.get("high") else None
    orb_low  = float(orb["low"])  if orb and orb.get("low")  else None
    piv_p    = float(pivots.get("P",  0) or 0)
    piv_r1   = float(pivots.get("R1", 0) or 0)
    piv_r2   = float(pivots.get("R2", 0) or 0)
    piv_r3   = float(pivots.get("R3", 0) or 0)
    piv_s1   = float(pivots.get("S1", 0) or 0)
    piv_s2   = float(pivots.get("S2", 0) or 0)
    piv_s3   = float(pivots.get("S3", 0) or 0)

    # ── Option chain analytics ────────────────────────────────────────────────
    pcr_data = compute_pcr(live_chain)
    oi_data  = compute_oi_analysis(live_chain, ltp, step)
    pcr      = pcr_data["pcr"]
    atm      = oi_data.get("atm", round(int(round(ltp / step) * step)))
    max_pain = oi_data.get("max_pain", atm)
    ce_wall  = oi_data.get("ce_wall",  atm + step * 5)
    pe_wall  = oi_data.get("pe_wall",  atm - step * 5)

    # ── Score each factor for CALL and PUT separately ─────────────────────────
    # We score the CALL direction; PUT score = invert sign of directional factors
    reasons_call = []
    reasons_put  = []
    bull = 0
    bear = 0

    # 1. ORB (±25) — primary signal
    orb_status = "inside"
    if orb_high and orb_low:
        if ltp > orb_high:
            bull += 25
            orb_status = "bull_break"
            reasons_call.append(f"✅ ORB breakout UP — price above {orb_high:,.0f}")
            reasons_put.append(f"❌ Price above ORB — bearish setup invalid")
        elif ltp < orb_low:
            bear += 25
            orb_status = "bear_break"
            reasons_put.append(f"✅ ORB breakdown — price below {orb_low:,.0f}")
            reasons_call.append(f"❌ Price below ORB — bullish setup invalid")
        else:
            bull -= 15
            bear -= 15
            orb_status = "inside"
            reasons_call.append(f"⚠️ Price inside ORB ({orb_low:,.0f}–{orb_high:,.0f}) — wait for breakout")
            reasons_put.append(f"⚠️ Price inside ORB ({orb_low:,.0f}–{orb_high:,.0f}) — wait for breakdown")
    else:
        reasons_call.append("ℹ️ ORB not yet formed (pre 9:30 AM)")
        reasons_put.append("ℹ️ ORB not yet formed (pre 9:30 AM)")

    # 2. VWAP (±15)
    if ltp > vwap * 1.001:
        bull += 15
        reasons_call.append(f"✅ Price above VWAP ({vwap:,.0f}) — buyers in control")
        reasons_put.append(f"❌ Price above VWAP — bearish pressure absent")
    elif ltp < vwap * 0.999:
        bear += 15
        reasons_put.append(f"✅ Price below VWAP ({vwap:,.0f}) — sellers in control")
        reasons_call.append(f"❌ Price below VWAP — bullish momentum weak")
    else:
        reasons_call.append(f"⚠️ Price at VWAP — no directional edge yet")
        reasons_put.append(f"⚠️ Price at VWAP — no directional edge yet")

    # 3. EMA Stack (±12)
    if ema9 > ema21 > ema50 and ltp > ema9:
        bull += 12
        reasons_call.append(f"✅ EMA stack bullish (9>{ema21:.0f}>50) — strong uptrend")
    elif ema9 < ema21 < ema50 and ltp < ema9:
        bear += 12
        reasons_put.append(f"✅ EMA stack bearish — strong downtrend confirmed")
    elif ema9 > ema21:
        bull += 6
        reasons_call.append(f"✅ EMA9 > EMA21 — short-term momentum up")
    elif ema9 < ema21:
        bear += 6
        reasons_put.append(f"✅ EMA9 < EMA21 — short-term momentum down")

    # 4. Supertrend (±10)
    if st_dir == 1:
        bull += 10
        reasons_call.append("✅ Supertrend BULLISH — trend confirmation")
        reasons_put.append("❌ Supertrend bullish — against put setup")
    elif st_dir == -1:
        bear += 10
        reasons_put.append("✅ Supertrend BEARISH — trend confirmation")
        reasons_call.append("❌ Supertrend bearish — against call setup")

    # 5. MACD (±8)
    if macd > macd_s and macd > 0:
        bull += 8
        reasons_call.append("✅ MACD bullish cross above zero — strong momentum")
    elif macd > macd_s:
        bull += 4
        reasons_call.append("✅ MACD bullish cross (below zero) — early signal")
    elif macd < macd_s and macd < 0:
        bear += 8
        reasons_put.append("✅ MACD bearish cross below zero — strong downward momentum")
    elif macd < macd_s:
        bear += 4
        reasons_put.append("✅ MACD bearish cross — early downward signal")

    # 6. RSI (±7)
    if 52 < rsi <= 65:
        bull += 7
        reasons_call.append(f"✅ RSI {rsi:.0f} — bullish zone, room to run")
    elif rsi > 65 and rsi <= 75:
        bull += 3
        reasons_call.append(f"⚠️ RSI {rsi:.0f} — strong but watch for exhaustion")
    elif rsi > 75:
        bear += 4
        reasons_call.append(f"⚠️ RSI {rsi:.0f} — overbought, tighten SL on calls")
    elif 35 <= rsi < 48:
        bear += 7
        reasons_put.append(f"✅ RSI {rsi:.0f} — bearish zone, downward pressure")
    elif rsi < 35:
        bear += 3
        reasons_put.append(f"⚠️ RSI {rsi:.0f} — oversold, watch for bounce (tighten put SL)")

    # 7. Volume (±5)
    if vol_ratio > 1.5 and ltp > float(prev.get("close", ltp) or ltp):
        bull += 5
        reasons_call.append(f"✅ Volume surge {vol_ratio:.1f}x with price up — conviction buying")
    elif vol_ratio > 1.5 and ltp < float(prev.get("close", ltp) or ltp):
        bear += 5
        reasons_put.append(f"✅ Volume surge {vol_ratio:.1f}x with price down — conviction selling")

    # 8. OBV (±4)
    if obv > obv_ema:
        bull += 4
        reasons_call.append("✅ OBV rising — accumulation by smart money")
    elif obv < obv_ema:
        bear += 4
        reasons_put.append("✅ OBV falling — distribution detected")

    # 9. PCR (±5)
    if pcr_data.get("ce_oi", 0) > 0:
        pcr_bias = pcr_data["bias"]
        if pcr_bias == "bullish":
            bull += 5
            reasons_call.append(f"✅ PCR {pcr:.2f} — bullish option positioning")
            reasons_put.append(f"❌ PCR {pcr:.2f} — not supportive of put setup")
        elif pcr_bias == "bearish":
            bear += 5
            reasons_put.append(f"✅ PCR {pcr:.2f} — bearish option positioning")
            reasons_call.append(f"❌ PCR {pcr:.2f} — not supportive of call setup")
        else:
            reasons_call.append(f"⚠️ PCR {pcr:.2f} — neutral, no directional bias")
            reasons_put.append(f"⚠️ PCR {pcr:.2f} — neutral, no directional bias")

    # 10. OI Wall Analysis (±4)
    if oi_data:
        if ltp < ce_wall and ltp > pe_wall:
            reasons_call.append(f"ℹ️ CE wall at {ce_wall:,} (resistance) | PE wall at {pe_wall:,} (support)")
            reasons_put.append(f"ℹ️ PE wall at {pe_wall:,} (support) | CE wall at {ce_wall:,} (resistance)")
        if max_pain:
            mp_diff = ltp - max_pain
            if abs(mp_diff) < step * 2:
                reasons_call.append(f"ℹ️ Max pain: {max_pain:,} — price near max pain zone (expect pinning)")
            elif mp_diff > 0:
                bear += 3
                reasons_put.append(f"✅ Price above max pain ({max_pain:,}) — gravity pull down")
            else:
                bull += 3
                reasons_call.append(f"✅ Price below max pain ({max_pain:,}) — gravity pull up")

    # 11. Global cues (±5)
    if global_score >= 3:
        bull += 5
        reasons_call.append(f"✅ Global cues positive (score: {global_score:+d}) — risk-on environment")
        reasons_put.append(f"❌ Global markets positive — headwind for puts")
    elif global_score <= -3:
        bear += 5
        reasons_put.append(f"✅ Global cues negative (score: {global_score:+d}) — risk-off environment")
        reasons_call.append(f"❌ Global markets negative — headwind for calls")
    else:
        reasons_call.append(f"⚠️ Global cues mixed (score: {global_score:+d})")
        reasons_put.append(f"⚠️ Global cues mixed (score: {global_score:+d})")

    # 12. FII/DII (±5)
    if fii_dii:
        fii_net = fii_dii.get("fii_net", 0)
        dii_net = fii_dii.get("dii_net", 0)
        if fii_net > 500:
            bull += 4
            reasons_call.append(f"✅ FII buying ₹{fii_net:,.0f} Cr — institutional support")
        elif fii_net < -500:
            bear += 4
            reasons_put.append(f"✅ FII selling ₹{abs(fii_net):,.0f} Cr — institutional exit")
        if dii_net > 500:
            bull += 1
            reasons_call.append(f"✅ DII buying ₹{dii_net:,.0f} Cr — domestic support")
        elif dii_net < -500:
            bear += 1
            reasons_put.append(f"✅ DII selling ₹{abs(dii_net):,.0f} Cr — domestic exit")
    else:
        reasons_call.append("ℹ️ FII/DII data unavailable for today")

    # 13. Market Breadth (±5)
    if breadth:
        b_bias = breadth.get("bias", "neutral")
        if b_bias == "bullish":
            bull += 5
            reasons_call.append(f"✅ {breadth['label']} — broad market rally supporting calls")
        elif b_bias == "bearish":
            bear += 5
            reasons_put.append(f"✅ {breadth['label']} — broad market weakness supporting puts")
        else:
            reasons_call.append(f"⚠️ {breadth.get('label','Mixed breadth')}")

    # 14. VIX adjustment
    vix_f = float(vix) if vix else 15
    vix_note = ""
    if vix_f > 20:
        bull -= 8; bear -= 8
        vix_note = f"⚠️ VIX {vix_f:.1f} — elevated. Use ATM only, smaller size, wider SL"
    elif vix_f > 18:
        bull -= 4; bear -= 4
        vix_note = f"⚠️ VIX {vix_f:.1f} — slightly elevated. OTM1 max, manage risk carefully"
    else:
        vix_note = f"✅ VIX {vix_f:.1f} — normal range, comfortable for buying options"

    # ── Determine direction and confidence ───────────────────────────────────
    base = 50
    call_conf = max(5, min(97, base + bull - bear))
    put_conf  = max(5, min(97, base + bear - bull))

    net = bull - bear
    if net > 0:
        direction = "CALL"
        confidence = call_conf
        reasons = reasons_call
    elif net < 0:
        direction = "PUT"
        confidence = put_conf
        reasons = reasons_put
    else:
        return {
            "status": "AVOID",
            "reason": "Indicators are perfectly balanced — no directional edge. Stay out.",
            "confidence": 50,
        }

    # ── Status classification ─────────────────────────────────────────────────
    if orb_status == "inside" and orb_high and orb_low:
        status = "WATCHLIST"
        avoid_note = (f"Wait for ORB breakout above {orb_high:,.0f} (CALL) "
                      f"or breakdown below {orb_low:,.0f} (PUT) on 15-min candle close.")
    elif confidence >= 72:
        status = "HIGH_CONVICTION"
        avoid_note = ""
    elif confidence >= 58:
        status = "MODERATE"
        avoid_note = ""
    elif confidence >= 45:
        status = "WATCHLIST"
        avoid_note = "Setup not yet confirmed. Watch for additional confirmation before entering."
    else:
        return {
            "status": "AVOID",
            "reason": f"Confidence too low ({confidence:.0f}%) — indicators conflicting. Do not trade.",
            "confidence": confidence,
        }

    # ── Strike & premium ─────────────────────────────────────────────────────
    sign = 1 if direction == "CALL" else -1
    strike = atm + sign * step   # OTM1 (best risk-reward for intraday)
    atm_strike = atm

    # Live premium from chain
    chain_atm  = live_chain.get(atm_strike, {})
    chain_otm1 = live_chain.get(strike, {})
    key = "ce" if direction == "CALL" else "pe"

    entry_prem_atm  = float(chain_atm.get(key, 0)  or 0)
    entry_prem_otm1 = float(chain_otm1.get(key, 0) or 0)

    # Use ATM if high conviction, OTM1 if moderate (better R:R)
    if status == "HIGH_CONVICTION":
        rec_strike = atm_strike
        entry_mid  = entry_prem_atm if entry_prem_atm > 0 else _bs_estimate(ltp, atm_strike, vix_f, 5, direction)
        strike_label = "ATM"
    else:
        rec_strike = strike
        entry_mid  = entry_prem_otm1 if entry_prem_otm1 > 0 else _bs_estimate(ltp, strike, vix_f, 5, direction)
        strike_label = "OTM 1"

    entry_low  = max(int(entry_mid * 0.95), 5)
    entry_high = int(entry_mid * 1.05)

    # ── Targets & SL ─────────────────────────────────────────────────────────
    prem_sl   = max(int(entry_mid * 0.70), 5)   # -30%
    prem_t1   = int(entry_mid * 1.60)           # +60%
    prem_t2   = int(entry_mid * 2.00)           # +100%
    prem_t3   = int(entry_mid * 2.50)           # +150%

    # Index-level SL and targets
    if direction == "CALL":
        idx_sl = orb_low   if orb_low  else (piv_s1 if piv_s1 else ltp * 0.995)
        idx_t1 = piv_r1    if piv_r1   else (orb_high * 1.01 if orb_high else ltp * 1.005)
        idx_t2 = piv_r2    if piv_r2   else ltp * 1.010
        idx_t3 = piv_r3    if piv_r3   else ltp * 1.018
        idx_sl_label = f"{idx_sl:,.0f} (ORB Low)" if orb_low else f"{idx_sl:,.0f} (S1)"
        idx_t1_label = f"{idx_t1:,.0f} (Pivot R1)"
        idx_t2_label = f"{idx_t2:,.0f} (Pivot R2)"
        idx_t3_label = f"{idx_t3:,.0f} (Pivot R3)"
    else:
        idx_sl = orb_high  if orb_high else (piv_r1 if piv_r1 else ltp * 1.005)
        idx_t1 = piv_s1    if piv_s1   else (orb_low  * 0.99 if orb_low  else ltp * 0.995)
        idx_t2 = piv_s2    if piv_s2   else ltp * 0.990
        idx_t3 = piv_s3    if piv_s3   else ltp * 0.982
        idx_sl_label = f"{idx_sl:,.0f} (ORB High)" if orb_high else f"{idx_sl:,.0f} (R1)"
        idx_t1_label = f"{idx_t1:,.0f} (Pivot S1)"
        idx_t2_label = f"{idx_t2:,.0f} (Pivot S2)"
        idx_t3_label = f"{idx_t3:,.0f} (Pivot S3)"

    # R:R (using T1)
    risk   = max(entry_mid - prem_sl, 1)
    reward = max(prem_t1 - entry_mid, 1)
    rr     = round(reward / risk, 1)

    # ── Exit conditions ───────────────────────────────────────────────────────
    exits = []
    exits.append(f"Book 50% quantity at T1 (₹{prem_t1}) — move SL to breakeven")
    exits.append(f"Book 30% more at T2 (₹{prem_t2}) — trail remaining with 15-pt SL")
    exits.append(f"Exit remaining at T3 (₹{prem_t3}) or 3:00 PM — whichever comes first")
    exits.append(f"Exit ALL if {name} {('falls' if direction=='CALL' else 'rises')} below/above {idx_sl:,.0f} (index SL)")
    exits.append(f"Exit if premium drops below ₹{prem_sl} (−30%)")
    if orb_high and orb_low:
        exits.append(f"Exit if price re-enters ORB range — breakout failure signal")
    exits.append(f"Exit if price {'crosses' if direction=='CALL' else 'crosses'} VWAP ({vwap:,.0f}) against your direction")
    exits.append("Exit immediately if VIX spikes above 20 mid-session")
    exits.append("⏰ MANDATORY exit of ALL positions by 3:00 PM")

    # ── Max hold time ─────────────────────────────────────────────────────────
    max_hold = _max_hold_till(mins_open)

    # ── Entry validity zone (index level) ────────────────────────────────────
    entry_idx_low  = round(ltp - step * 0.4)
    entry_idx_high = round(ltp + step * 0.4)

    return {
        "status":         status,
        "direction":      direction,
        "confidence":     confidence,
        "name":           name,
        "ltp":            ltp,
        "vix":            vix_f,
        "vix_note":       vix_note,
        "orb_status":     orb_status,
        "orb_high":       orb_high,
        "orb_low":        orb_low,

        # Option details
        "strike":         rec_strike,
        "strike_label":   strike_label,
        "atm":            atm_strike,
        "expiry_label":   expiry_label,
        "entry_prem_mid": entry_mid,
        "entry_prem_low": entry_low,
        "entry_prem_high":entry_high,

        # Premium targets
        "prem_sl":   prem_sl,
        "prem_t1":   prem_t1,
        "prem_t2":   prem_t2,
        "prem_t3":   prem_t3,

        # Index targets
        "idx_sl":        idx_sl,
        "idx_sl_label":  idx_sl_label,
        "idx_t1":        idx_t1,
        "idx_t1_label":  idx_t1_label,
        "idx_t2":        idx_t2,
        "idx_t2_label":  idx_t2_label,
        "idx_t3":        idx_t3,
        "idx_t3_label":  idx_t3_label,

        "entry_idx_low":  entry_idx_low,
        "entry_idx_high": entry_idx_high,

        "rr_ratio":    rr,
        "max_hold":    max_hold,
        "exits":       exits,
        "reasons":     [r for r in reasons if r],   # filter blanks
        "pcr_data":    pcr_data,
        "oi_data":     oi_data,
        "max_pain":    max_pain,
        "ce_wall":     ce_wall,
        "pe_wall":     pe_wall,
        "lot_size":    lot_size,
        "avoid_note":  avoid_note if status in ("WATCHLIST",) else "",

        # Score breakdown for display
        "score_bull":  bull,
        "score_bear":  bear,
    }


def _bs_estimate(spot: float, strike: float, vix: float, days: int, direction: str) -> float:
    """Simplified Black-Scholes estimate when live premium unavailable."""
    sigma = max(vix, 8) / 100
    T = max(days, 0.5) / 252
    d = (spot - strike) / spot
    atm_prem = spot * sigma * np.sqrt(T) * 0.4
    if direction == "CALL":
        if strike <= spot:
            return round(atm_prem + max(spot - strike, 0) * 0.5, 0)
        else:
            return round(atm_prem * np.exp(-abs(d) * 5), 0)
    else:
        if strike >= spot:
            return round(atm_prem + max(strike - spot, 0) * 0.5, 0)
        else:
            return round(atm_prem * np.exp(-abs(d) * 5), 0)
