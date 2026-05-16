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
    return df


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    o = now.replace(hour=9, minute=15, second=0, microsecond=0)
    c = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return o <= now <= c


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


def candlestick_fig(df: pd.DataFrame, title: str) -> go.Figure:
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
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bb_upper"],
            line=dict(color="rgba(99,102,241,0.4)", width=1, dash="dot"),
            name="BB", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bb_lower"],
            line=dict(color="rgba(99,102,241,0.4)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(99,102,241,0.05)",
            name="BB Lower", showlegend=False), row=1, col=1)
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
col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
with col_h1:
    st.markdown("## 📈 India Market Dashboard")
    st.caption(f"Last updated: {now_ist.strftime('%d %b %Y  %H:%M:%S IST')}  |  Data: Yahoo Finance (15-min delay)")
with col_h2:
    status_color = "#26a69a" if market_open else "#ef5350"
    st.markdown(f'<div style="margin-top:20px"><span style="color:{status_color}; font-size:16px; font-weight:700;">● Market {"OPEN" if market_open else "CLOSED"}</span></div>', unsafe_allow_html=True)
with col_h3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

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
            <div class="metric-card">
              <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px">{name}</div>
              <div style="font-size:22px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
              <div style="font-size:13px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
              <div style="font-size:11px;color:#6b7280;margin-top:4px">H:{q['high']:,.0f} L:{q['low']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.metric(name, "Loading…")

st.divider()

# ── Charts + Signals ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["⚡ Intraday Signals", "🕯️ Nifty 50", "🏦 Bank Nifty", "🌍 Global Cues", "📋 Trade Plan", "📓 Trade Journal"])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 0 — Intraday Signals
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
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
        st.markdown(f'<div class="metric-card" style="border-left-color:{vix_color}">'
                    f'<div class="trade-label">India VIX</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{vix_color}">{vix_i:.2f}</div>'
                    f'<div style="font-size:12px;color:#9ca3af">{"⚠️ High — reduce size" if vix_i > 18 else "✅ Normal range"}</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic2:
        st.markdown(f'<div class="metric-card"><div class="trade-label">Nifty 50</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{"#26a69a" if nq_i.get("chg",0)>=0 else "#ef5350"}">'
                    f'{n_ltp:,.2f}</div>'
                    f'<div style="font-size:12px;color:#9ca3af">{nq_i.get("pct",0):+.2f}% today</div>'
                    f'</div>', unsafe_allow_html=True)
    with ic3:
        st.markdown(f'<div class="metric-card"><div class="trade-label">Bank Nifty</div>'
                    f'<div style="font-size:24px;font-weight:800;color:{"#26a69a" if bnq_i.get("chg",0)>=0 else "#ef5350"}">'
                    f'{bn_ltp:,.2f}</div>'
                    f'<div style="font-size:12px;color:#9ca3af">{bnq_i.get("pct",0):+.2f}% today</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Index selector ────────────────────────────────────────────────────────
    sel_index = st.radio("Select Index for Signals", ["Nifty 50", "Bank Nifty", "Both"],
                          horizontal=True)

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


# ── TAB 1: Nifty ─────────────────────────────────────────────────────────────
with tab2:
    c1, c2 = st.columns([3, 1])
    with c1:
        nifty_df = get_candles("^NSEI", period="5d", interval="15m")
        nifty_df = add_indicators(nifty_df)
        if not nifty_df.empty:
            st.plotly_chart(candlestick_fig(nifty_df, "Nifty 50 — 15 Min"), use_container_width=True)
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

# ── TAB 2: Bank Nifty ────────────────────────────────────────────────────────
with tab3:
    bc1, bc2 = st.columns([3, 1])
    with bc1:
        bnf_df = get_candles("^NSEBANK", period="5d", interval="15m")
        bnf_df = add_indicators(bnf_df)
        if not bnf_df.empty:
            st.plotly_chart(candlestick_fig(bnf_df, "Bank Nifty — 15 Min"), use_container_width=True)
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

# ── TAB 3: Global Cues ───────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-title">Global Markets</div>', unsafe_allow_html=True)
    global_quotes = {name: get_quote(ticker) for name, ticker in GLOBAL.items()}
    g1, g2 = st.columns(2)
    items = list(global_quotes.items())
    for i, (name, q) in enumerate(items):
        col = g1 if i % 2 == 0 else g2
        with col:
            if q:
                arrow = "▲" if q["chg"] >= 0 else "▼"
                cls   = "bull" if q["chg"] >= 0 else "bear"
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: {'#26a69a' if q['chg']>=0 else '#ef5350'}">
                  <div style="font-size:11px;color:#9ca3af">{name}</div>
                  <div style="font-size:18px;font-weight:700" class="{cls}">{q['ltp']:,.2f}</div>
                  <div style="font-size:12px" class="{cls}">{arrow} {abs(q['chg']):,.2f} ({q['pct']:+.2f}%)</div>
                </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-title" style="margin-top:20px">Global Sentiment</div>', unsafe_allow_html=True)
    sp_q  = global_quotes.get("S&P 500", {})
    crude = global_quotes.get("Crude Oil", {})
    usdinr= global_quotes.get("USD/INR", {})
    sentiments = []
    if sp_q:
        sentiments.append(("S&P 500", "Risk-ON" if sp_q.get("pct",0) > 0 else "Risk-OFF",
                           "green" if sp_q.get("pct",0) > 0 else "red"))
    if crude:
        sentiments.append(("Crude Oil", "Bearish for India" if crude.get("pct",0) > 1 else "Neutral/Positive",
                           "red" if crude.get("pct",0) > 1 else "green"))
    if usdinr:
        sentiments.append(("USD/INR", "Rupee weak" if usdinr.get("pct",0) > 0 else "Rupee strong",
                           "red" if usdinr.get("pct",0) > 0 else "green"))
    for name, label, color in sentiments:
        pc = "pill-green" if color == "green" else "pill-red"
        st.markdown(f'<span class="pill {pc}">{name}: {label}</span>', unsafe_allow_html=True)

# ── TAB 4: Trade Plan ────────────────────────────────────────────────────────
with tab5:
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
#  TAB 6 — Trade Journal
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

with tab6:
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
                    .style.applymap(color_pnl, subset=["pnl"]),
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

# ── Auto-refresh ──────────────────────────────────────────────────────────────
st.divider()
auto = st.toggle("Auto-refresh every 30 seconds", value=False)
if auto:
    import time
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
