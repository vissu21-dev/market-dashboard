"""
Market Analysis Dashboard — powered by Upstox API
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

import config
import data_fetcher as df_api
import indicators
import charts

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  body, .stApp {{ background-color: {config.BG_COLOR}; color: {config.TEXT_COLOR}; }}
  .metric-card {{
    background: #1a1d2e; border-radius: 10px; padding: 16px 20px;
    border-left: 4px solid #3b82f6;
  }}
  .metric-label {{ font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }}
  .metric-value {{ font-size: 26px; font-weight: 700; }}
  .metric-change {{ font-size: 14px; margin-top: 2px; }}
  .bull {{ color: {config.BULL_COLOR}; }}
  .bear {{ color: {config.BEAR_COLOR}; }}
  .signal-pill {{
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 600; margin: 2px;
  }}
  .pill-green {{ background: rgba(38,166,154,0.2); color: {config.BULL_COLOR}; border: 1px solid {config.BULL_COLOR}; }}
  .pill-red   {{ background: rgba(239,83,80,0.2);  color: {config.BEAR_COLOR}; border: 1px solid {config.BEAR_COLOR}; }}
  .pill-gray  {{ background: rgba(156,163,175,0.2); color: #9ca3af; border: 1px solid #9ca3af; }}
  div[data-testid="stMetricValue"] {{ font-size: 1.6rem !important; font-weight: 700; }}
</style>
""", unsafe_allow_html=True)

IST = pytz.timezone("Asia/Kolkata")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/48/combo-chart.png", width=40)
    st.title("Market Dashboard")
    st.caption("Powered by Upstox API")

    page = st.radio(
        "Navigation",
        ["📊 Live Index Dashboard", "🕯️ Candlestick Chart", "🔗 Option Chain", "ℹ️ Setup Guide"],
        label_visibility="collapsed",
    )

    st.divider()
    market_open = df_api.is_market_open()
    status_col = config.BULL_COLOR if market_open else config.BEAR_COLOR
    st.markdown(
        f'<span style="color:{status_col}; font-weight:600;">● Market {"OPEN" if market_open else "CLOSED"}</span>',
        unsafe_allow_html=True,
    )
    now_ist = datetime.now(IST).strftime("%d %b %Y  %H:%M:%S IST")
    st.caption(now_ist)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.toggle("Auto-refresh (30s)", value=False)


# ── Helper: render index metric card ─────────────────────────────────────────
def render_index_card(name: str, quote: dict):
    ltp    = quote.get("last_price", 0)
    chg    = quote.get("net_change", 0)
    pct    = quote.get("net_change_percentage", 0)
    high   = quote.get("ohlc", {}).get("high", 0)
    low    = quote.get("ohlc", {}).get("low", 0)
    cls    = "bull" if chg >= 0 else "bear"
    arrow  = "▲" if chg >= 0 else "▼"
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{name}</div>
      <div class="metric-value {cls}">{ltp:,.2f}</div>
      <div class="metric-change {cls}">{arrow} {abs(chg):,.2f}  ({pct:+.2f}%)</div>
      <div style="font-size:11px; color:#6b7280; margin-top:6px;">
        H: {high:,.2f} &nbsp;|&nbsp; L: {low:,.2f}
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — Live Index Dashboard
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Live Index Dashboard":
    st.header("Live Index Dashboard")

    keys = list(config.INSTRUMENTS.values())
    with st.spinner("Fetching live quotes…"):
        quotes = df_api.get_market_quotes(keys)

    if not quotes:
        st.warning("No data returned. Check your Upstox access token in the .env file.")
    else:
        cols = st.columns(len(config.INSTRUMENTS))
        for col, (name, key) in zip(cols, config.INSTRUMENTS.items()):
            # Upstox returns data with the key as dict key (dot-separated)
            q = quotes.get(key, quotes.get(key.replace("|", ":"), {}))
            with col:
                if q:
                    render_index_card(name, q)
                else:
                    st.metric(name, "N/A")

    st.divider()

    # Intraday mini-charts for all indices
    st.subheader("Today's Intraday Move (5-min)")
    chart_cols = st.columns(2)
    for idx, (name, key) in enumerate(config.INSTRUMENTS.items()):
        today = datetime.now(IST).date()
        candles = df_api.get_historical_candles(key, "5minute", str(today), str(today))
        with chart_cols[idx % 2]:
            if candles.empty:
                st.info(f"No intraday data for {name}")
            else:
                import plotly.graph_objects as go
                color = config.BULL_COLOR if candles["close"].iloc[-1] >= candles["open"].iloc[0] else config.BEAR_COLOR
                fig = go.Figure(go.Scatter(
                    x=candles["timestamp"], y=candles["close"],
                    fill="tozeroy",
                    line=dict(color=color, width=2),
                    fillcolor=f"rgba({'38,166,154' if color == config.BULL_COLOR else '239,83,80'},0.1)",
                ))
                fig.update_layout(
                    title=name,
                    paper_bgcolor=config.BG_COLOR, plot_bgcolor=config.BG_COLOR,
                    font=dict(color=config.TEXT_COLOR),
                    margin=dict(l=10, r=10, t=40, b=10), height=200,
                    showlegend=False, xaxis_rangeslider_visible=False,
                )
                fig.update_xaxes(gridcolor=config.GRID_COLOR)
                fig.update_yaxes(gridcolor=config.GRID_COLOR)
                st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — Candlestick Chart
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🕯️ Candlestick Chart":
    st.header("Candlestick Chart & Technical Indicators")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        symbol = st.selectbox("Index", list(config.INSTRUMENTS.keys()))
    with c2:
        interval_label = st.selectbox("Timeframe", list(config.INTERVALS.keys()), index=4)  # 15 min default
    with c3:
        days_back = st.number_input("Days back", min_value=1, max_value=365, value=30)

    interval = config.INTERVALS[interval_label]
    instrument_key = config.INSTRUMENTS[symbol]

    today      = datetime.now(IST).date()
    from_date  = str(today - timedelta(days=days_back))
    to_date    = str(today)

    # Indicator toggles
    st.markdown("**Overlays & Indicators**")
    t1, t2, t3, t4, t5 = st.columns(5)
    show_ema20  = t1.toggle("EMA 20",      value=True)
    show_ema50  = t2.toggle("EMA 50",      value=True)
    show_ema200 = t3.toggle("EMA 200",     value=False)
    show_bb     = t4.toggle("Bollinger",   value=False)
    show_st     = t5.toggle("Supertrend",  value=True)

    ema_periods = ([20] if show_ema20 else []) + ([50] if show_ema50 else []) + ([200] if show_ema200 else [])

    with st.spinner("Loading candles…"):
        candles = df_api.get_historical_candles(instrument_key, interval, from_date, to_date)

    if candles.empty:
        st.warning("No candle data returned. Check your access token or try a different timeframe.")
    else:
        candles = indicators.add_all_indicators(candles, ema_periods=ema_periods if ema_periods else [20, 50])

        fig = charts.candlestick_chart(
            candles,
            title=f"{symbol} — {interval_label}",
            show_ema=ema_periods if ema_periods else [],
            show_bb=show_bb,
            show_supertrend=show_st,
            show_volume=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        # MACD chart
        if "macd" in candles.columns:
            st.subheader("MACD")
            st.plotly_chart(charts.macd_chart(candles), use_container_width=True)

        # Signal summary
        st.subheader("Signal Summary")
        sigs = indicators.get_signal_summary(candles)
        if sigs:
            sig_html = ""
            for name, (label, color) in sigs.items():
                pill_cls = {"green": "pill-green", "red": "pill-red", "gray": "pill-gray"}.get(color, "pill-gray")
                sig_html += f'<span class="signal-pill {pill_cls}">{name}: {label}</span>'
            st.markdown(sig_html, unsafe_allow_html=True)

        # Raw data expander
        with st.expander("Raw OHLCV Data"):
            st.dataframe(
                candles[["timestamp", "open", "high", "low", "close", "volume"]].tail(50),
                use_container_width=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — Option Chain
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔗 Option Chain":
    st.header("Option Chain Analyzer")

    oc1, oc2 = st.columns(2)
    with oc1:
        oc_symbol = st.selectbox("Index", ["Nifty 50", "Bank Nifty"])
    with oc2:
        if oc_symbol == "Nifty 50":
            default_expiry = config.NIFTY_EXPIRY
            oc_key = config.INSTRUMENTS["Nifty 50"]
        else:
            default_expiry = config.BANKNIFTY_EXPIRY
            oc_key = config.INSTRUMENTS["Bank Nifty"]

        expiry = st.date_input("Expiry Date", value=pd.to_datetime(default_expiry))

    # Get spot price
    spot_data = df_api.get_ltp([oc_key])
    spot = spot_data.get(oc_key, 0)

    with st.spinner("Fetching option chain…"):
        oc_df = df_api.get_option_chain(oc_key, str(expiry))

    if oc_df.empty:
        st.warning("No option chain data. Verify expiry date and access token.")
    else:
        if spot:
            st.metric("Spot Price", f"{spot:,.2f}")

        # Filter around ATM
        atm_range = st.slider(
            "Show strikes (ATM ± N)",
            min_value=5, max_value=50, value=20, step=5,
        )
        if spot:
            oc_df = oc_df[
                (oc_df["strike"] >= spot - atm_range * 50) &
                (oc_df["strike"] <= spot + atm_range * 50)
            ]

        # OI chart
        st.subheader("Open Interest — CE vs PE")
        st.plotly_chart(charts.option_chain_oi_chart(oc_df, spot=spot), use_container_width=True)

        # Max pain
        oc_df["total_oi"] = oc_df["ce_oi"] + oc_df["pe_oi"]
        max_pain_row = oc_df.loc[oc_df["total_oi"].idxmax()] if not oc_df.empty else None

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if max_pain_row is not None:
                st.metric("Max Pain Strike", f"{max_pain_row['strike']:,.0f}")
        with col_b:
            pcr = oc_df["pe_oi"].sum() / oc_df["ce_oi"].sum() if oc_df["ce_oi"].sum() > 0 else 0
            st.metric("PCR (OI)", f"{pcr:.2f}", help="Put-Call Ratio > 1 = bearish sentiment")
        with col_c:
            total = oc_df["ce_oi"].sum() + oc_df["pe_oi"].sum()
            st.metric("Total OI", f"{total:,.0f}")

        # Full table
        st.subheader("Option Chain Table")
        display_cols = ["strike", "ce_oi", "ce_volume", "ce_iv", "ce_ltp", "pe_ltp", "pe_iv", "pe_volume", "pe_oi"]
        available = [c for c in display_cols if c in oc_df.columns]

        def highlight_atm(row):
            if spot and abs(row["strike"] - spot) < 50:
                return ["background-color: rgba(59,130,246,0.2)"] * len(row)
            return [""] * len(row)

        st.dataframe(
            oc_df[available].style.apply(highlight_atm, axis=1),
            use_container_width=True,
            height=400,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — Setup Guide
# ══════════════════════════════════════════════════════════════════════════════
elif page == "ℹ️ Setup Guide":
    st.header("Setup Guide")
    st.markdown("""
    ### Step 1 — Create Upstox Developer App
    1. Go to [developer.upstox.com](https://developer.upstox.com) and sign in with your Upstox account.
    2. Click **My Apps → Create New App**.
    3. Set the **Redirect URL** to `http://localhost:8501`.
    4. Copy your **API Key** and **API Secret**.

    ### Step 2 — Add credentials to `.env`
    Open the `.env` file in this folder and fill in:
    ```
    UPSTOX_API_KEY=your_api_key_here
    UPSTOX_API_SECRET=your_api_secret_here
    UPSTOX_REDIRECT_URI=http://localhost:8501
    UPSTOX_ACCESS_TOKEN=   ← leave blank for now
    ```

    ### Step 3 — Get a daily access token
    Run this once every morning before the market opens:
    ```bash
    python upstox_auth.py
    ```
    It will open your browser → log in with Upstox → paste the code → you get a token.
    Copy the token into `.env` as `UPSTOX_ACCESS_TOKEN=...`.

    ### Step 4 — Update expiry dates weekly
    In `config.py`, update these every Thursday evening:
    ```python
    NIFTY_EXPIRY    = "YYYY-MM-DD"   # Thursday expiry
    BANKNIFTY_EXPIRY = "YYYY-MM-DD"  # Wednesday expiry
    ```

    ### Step 5 — Run the dashboard
    ```bash
    streamlit run app.py
    ```

    ---
    **Note:** Upstox access tokens are valid only for the current trading day (expire at midnight).
    """)

    st.subheader("Current Config Status")
    import config as cfg
    checks = {
        "API Key set":      bool(cfg.API_KEY and cfg.API_KEY != "your_api_key_here"),
        "API Secret set":   bool(cfg.API_SECRET and cfg.API_SECRET != "your_api_secret_here"),
        "Access Token set": bool(cfg.ACCESS_TOKEN and cfg.ACCESS_TOKEN != "your_access_token_here"),
    }
    for label, ok in checks.items():
        icon = "✅" if ok else "❌"
        st.markdown(f"{icon} **{label}**")


# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
