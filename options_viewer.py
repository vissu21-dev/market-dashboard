"""
Live Options Chain Viewer
Displays real-time option strikes, premiums, IV, OI, volume with live updates.
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import requests

def format_number(val, decimals=0):
    """Format numbers with K/M suffix."""
    if pd.isna(val) or val == 0:
        return "—"
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.1f}K"
    return f"{val:.{decimals}f}"


def build_chain_dataframe(live_chain: dict, ltp: float, step: int) -> pd.DataFrame:
    """
    Convert Upstox option chain dict to display-ready DataFrame.
    live_chain format: {strike: {ce: ltp, pe: ltp, ce_iv: val, pe_iv: val, ...}}
    """
    if not live_chain:
        return pd.DataFrame()

    rows = []
    atm = round(int(round(ltp / step) * step))

    # Get all strikes, sort descending (show ITM to OTM)
    strikes = sorted(live_chain.keys(), reverse=True)

    for strike in strikes:
        data = live_chain[strike]
        ce_ltp = float(data.get("ce", 0) or 0)
        pe_ltp = float(data.get("pe", 0) or 0)
        ce_iv = float(data.get("ce_iv", 0) or 0)
        pe_iv = float(data.get("pe_iv", 0) or 0)
        ce_oi = float(data.get("ce_oi", 0) or 0)
        pe_oi = float(data.get("pe_oi", 0) or 0)
        ce_vol = float(data.get("ce_volume", 0) or 0)
        pe_vol = float(data.get("pe_volume", 0) or 0)

        # Calculate Greeks (simplified delta approximation if not available)
        ce_delta = estimate_delta(ce_ltp, strike, ltp, 0.2)  # Rough estimate
        pe_delta = -estimate_delta(pe_ltp, strike, ltp, 0.2)

        rows.append({
            "Strike": strike,
            "CE_LTP": ce_ltp,
            "CE_IV": ce_iv,
            "CE_OI": ce_oi,
            "CE_Vol": ce_vol,
            "CE_Delta": ce_delta,
            "PE_LTP": pe_ltp,
            "PE_IV": pe_iv,
            "PE_OI": pe_oi,
            "PE_Vol": pe_vol,
            "PE_Delta": pe_delta,
            "Distance": abs(strike - ltp),
            "Type": "ATM" if strike == atm else ("ITM" if strike > ltp else "OTM"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Distance").reset_index(drop=True)
    return df


def estimate_delta(premium: float, strike: int, ltp: float, iv: float) -> float:
    """Quick delta estimate (not exact BS, but good enough for display)."""
    if premium == 0:
        return 0.0
    moneyness = (ltp - strike) / (ltp + strike)  # Rough moneyness
    delta = 0.5 + 0.3 * moneyness  # Smoothed curve
    return np.clip(delta, 0, 1)


def render_option_chain_table(df: pd.DataFrame, ltp: float, name: str = "Nifty 50"):
    """
    Render beautiful live options chain table.
    Highlights ATM, shows color gradients for IV/OI.
    """
    if df.empty:
        st.info("📊 No option chain data available. Check Upstox token status.")
        return

    # Filter to relevant strikes (ATM ± 10)
    atm_approx = round(ltp / 50) * 50
    df_display = df.copy()
    df_display = df_display[
        (df_display["Strike"] >= atm_approx - 500) &
        (df_display["Strike"] <= atm_approx + 500)
    ].reset_index(drop=True)

    if df_display.empty:
        st.warning("No strikes near ATM in available data.")
        return

    # Build HTML table with custom styling
    html = f"""
    <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #2a2e39;">
    <table style="width:100%; border-collapse: collapse; font-family: monospace; font-size: 12px;">
        <thead>
            <tr style="background: #1e222d; border-bottom: 2px solid #2a2e39;">
                <th style="padding: 10px; color: #9598a1; text-align: center; font-weight: 700;">
                    📈 CALL OPTIONS
                </th>
                <th style="padding: 10px; color: #9598a1; text-align: center; border-left: 2px solid #2a2e39; border-right: 2px solid #2a2e39; font-weight: 700;">
                    🎯 STRIKE
                </th>
                <th style="padding: 10px; color: #9598a1; text-align: center; font-weight: 700;">
                    📉 PUT OPTIONS
                </th>
            </tr>
            <tr style="background: #131722; border-bottom: 1px solid #2a2e39;">
                <th colspan="3" style="padding: 6px; text-align: center; color: #b2b5be; font-weight: 600;">
                    {name} — LTP: ₹{ltp:,.2f}
                </th>
            </tr>
            <tr style="background: #1e222d; border-bottom: 2px solid #2a2e39;">
                <td style="padding: 8px; color: #9598a1; text-align: center; font-weight: 600;">LTP | IV% | OI | Vol</td>
                <td style="padding: 8px; color: #9598a1; text-align: center; border-left: 2px solid #2a2e39; border-right: 2px solid #2a2e39; font-weight: 600;">Strike | Δ</td>
                <td style="padding: 8px; color: #9598a1; text-align: center; font-weight: 600;">LTP | IV% | OI | Vol</td>
            </tr>
        </thead>
        <tbody>
    """

    for idx, row in df_display.iterrows():
        strike = int(row["Strike"])
        is_atm = strike == round(ltp / 50) * 50

        # Cell background: ATM highlighted, ITM/OTM dimmed
        row_bg = "#0d2618" if is_atm else "#131722"
        strike_bg = "#1a3a2a" if is_atm else "#1e222d"
        border_color = "#089981" if is_atm else "#2a2e39"

        # CE side
        ce_ltp_color = "#089981" if row["CE_LTP"] > 0 else "#9598a1"
        ce_oi_color = "#a78bfa" if row["CE_OI"] > 100000 else "#9598a1"

        # PE side
        pe_ltp_color = "#f23645" if row["PE_LTP"] > 0 else "#9598a1"
        pe_oi_color = "#a78bfa" if row["PE_OI"] > 100000 else "#9598a1"

        html += f"""
        <tr style="background: {row_bg}; border-bottom: 1px solid {border_color};">
            <!-- CALL SIDE -->
            <td style="padding: 8px; text-align: right; border-right: 1px solid #2a2e39;">
                <div style="color: {ce_ltp_color}; font-weight: 700;">₹{row['CE_LTP']:.2f}</div>
                <div style="color: #ffa500; font-size: 11px;">{row['CE_IV']:.1f}%</div>
                <div style="color: {ce_oi_color}; font-size: 11px;">{format_number(row['CE_OI'])}</div>
                <div style="color: #9598a1; font-size: 11px;">{int(row['CE_Vol'])}</div>
            </td>
            <!-- STRIKE SIDE -->
            <td style="padding: 8px; text-align: center; border-left: 2px solid {border_color}; border-right: 2px solid {border_color}; background: {strike_bg}; font-weight: 700;">
                <div style="color: #d1d4dc; font-size: 14px;">{strike}</div>
                <div style="color: #b2b5be; font-size: 11px;">Δ {row['CE_Delta']:.2f} | Δ {row['PE_Delta']:.2f}</div>
            </td>
            <!-- PUT SIDE -->
            <td style="padding: 8px; text-align: left; border-left: 1px solid #2a2e39;">
                <div style="color: {pe_ltp_color}; font-weight: 700;">₹{row['PE_LTP']:.2f}</div>
                <div style="color: #ffa500; font-size: 11px;">{row['PE_IV']:.1f}%</div>
                <div style="color: {pe_oi_color}; font-size: 11px;">{format_number(row['PE_OI'])}</div>
                <div style="color: #9598a1; font-size: 11px;">{int(row['PE_Vol'])}</div>
            </td>
        </tr>
        """

    html += """
        </tbody>
    </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)

    # Legend
    st.markdown("""
    <div style="margin-top: 12px; padding: 10px; background: #1e222d; border-radius: 6px; font-size: 12px;">
        <span style="color: #089981; margin-right: 20px;">🟢 ATM Strike (Highlighted)</span>
        <span style="color: #ffa500; margin-right: 20px;">📊 IV% (Implied Volatility)</span>
        <span style="color: #a78bfa; margin-right: 20px;">📍 OI (Open Interest)</span>
        <span style="color: #9598a1;">Δ (Delta: sensitivity to price move)</span>
    </div>
    """, unsafe_allow_html=True)


def render_strike_selector(df: pd.DataFrame, ltp: float, direction: str = "CE") -> Optional[int]:
    """
    Interactive strike selector with budget calculator.
    Returns selected strike or None.
    """
    if df.empty:
        return None

    st.subheader(f"💰 {direction} Strike Selector")

    col1, col2, col3 = st.columns(3)

    with col1:
        budget = st.number_input(
            "Your budget (₹)", min_value=500, max_value=500000,
            value=10000, step=500, key=f"budget_{direction}"
        )

    with col2:
        lot_size = st.selectbox(
            "Lot size",
            [30, 40, 75, 100],
            index=2,
            key=f"lot_{direction}"
        )

    with col3:
        max_premium = budget / lot_size
        st.metric("Max premium", f"₹{max_premium:.2f}")

    st.markdown("---")

    # Affordable strikes
    df_afford = df.copy()
    if direction == "CE":
        df_afford = df_afford[df_afford["CE_LTP"] <= max_premium].copy()
        df_afford = df_afford.sort_values("Strike", ascending=True)
    else:
        df_afford = df_afford[df_afford["PE_LTP"] <= max_premium].copy()
        df_afford = df_afford.sort_values("Strike", ascending=False)

    if df_afford.empty:
        st.warning(f"❌ No {direction} strikes available with ₹{budget} budget")
        return None

    # Create selection columns
    sc1, sc2, sc3, sc4 = st.columns(4)

    with sc1:
        st.markdown("**ATM (Safest)**")
        atm_row = df_afford[
            df_afford["Strike"] == round(ltp / 50) * 50
        ]
        if not atm_row.empty:
            premium = atm_row.iloc[0]["CE_LTP"] if direction == "CE" else atm_row.iloc[0]["PE_LTP"]
            if st.button(f"ATM\n₹{premium:.2f}", key=f"atm_{direction}", use_container_width=True):
                return int(atm_row.iloc[0]["Strike"])
        else:
            st.caption("No ATM available")

    with sc2:
        st.markdown("**OTM1 (Good Risk/Reward)**")
        if direction == "CE":
            otm_row = df_afford[df_afford["Strike"] > ltp].head(1)
        else:
            otm_row = df_afford[df_afford["Strike"] < ltp].tail(1)

        if not otm_row.empty:
            premium = otm_row.iloc[0]["CE_LTP"] if direction == "CE" else otm_row.iloc[0]["PE_LTP"]
            if st.button(f"OTM1\n₹{premium:.2f}", key=f"otm1_{direction}", use_container_width=True):
                return int(otm_row.iloc[0]["Strike"])
        else:
            st.caption("No OTM1 available")

    with sc3:
        st.markdown("**OTM2 (Risky but cheap)**")
        if direction == "CE":
            otm2_row = df_afford[df_afford["Strike"] > ltp].tail(1)
        else:
            otm2_row = df_afford[df_afford["Strike"] < ltp].head(1)

        if not otm2_row.empty:
            premium = otm2_row.iloc[0]["CE_LTP"] if direction == "CE" else otm2_row.iloc[0]["PE_LTP"]
            if st.button(f"OTM2\n₹{premium:.2f}", key=f"otm2_{direction}", use_container_width=True):
                return int(otm2_row.iloc[0]["Strike"])
        else:
            st.caption("No OTM2 available")

    with sc4:
        st.markdown("**Custom**")
        custom_strike = st.selectbox(
            "Pick strike manually",
            df_afford["Strike"].unique(),
            key=f"custom_{direction}"
        )
        return int(custom_strike)

    return None


def show_iv_heatmap(df: pd.DataFrame):
    """Display IV surface heatmap — shows which strikes have highest/lowest IV."""
    if df.empty or "CE_IV" not in df.columns:
        return

    st.markdown("### 🔥 IV Heatmap (Volatility Surface)")

    df_iv = df[["Strike", "CE_IV", "PE_IV"]].copy()
    df_iv.columns = ["Strike", "Call IV", "Put IV"]

    # Normalize for color intensity (0-100 scale)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Call IV** (higher = expensive calls)")
        iv_data = df_iv[["Strike", "Call IV"]].set_index("Strike")
        st.bar_chart(iv_data, color="#089981", height=250)

    with col2:
        st.markdown("**Put IV** (higher = expensive puts)")
        iv_data = df_iv[["Strike", "Put IV"]].set_index("Strike")
        st.bar_chart(iv_data, color="#f23645", height=250)
