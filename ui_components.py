"""
Professional UI Components for Trade Advisor
Reusable Streamlit rendering functions for trade cards, charts, and analytics.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List, Optional
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────────────────────────────────────
# TRADE RECOMMENDATION CARD
# ─────────────────────────────────────────────────────────────────────────────

def render_trade_recommendation_card(trade: Dict, account_size: float = 100000):
    """
    Render a professional trade recommendation card with all details.
    Shows entry zone, targets, SL, conviction, exit conditions.
    """
    direction = trade.get("direction", "CALL")
    confidence = trade.get("confidence_pct", 0)
    conviction = trade.get("conviction_level", "LOW")
    index = trade.get("index", "INDEX")

    # Color scheme based on conviction
    color_map = {
        "HIGH": "#089981",      # Green
        "MODERATE": "#ffa500",  # Orange
        "LOW": "#f23645",       # Red
        "AVOID": "#666666",     # Gray
    }
    color = color_map.get(conviction, "#9598a1")

    # Main card header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {color}20 0%, {color}05 100%);
        border-left: 4px solid {color};
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin: 0; color: #fff;">{index} {direction}</h3>
                <p style="margin: 4px 0; color: #b2b5be; font-size: 12px;">Strike {trade.get('strike', '—')}</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 28px; font-weight: 700; color: {color};">{confidence}%</div>
                <div style="font-size: 12px; color: #b2b5be;">{conviction}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Entry zone section
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📍 ENTRY ZONE**")
        entry_low = trade.get("entry_price_low", 0)
        entry_high = trade.get("entry_price_high", 0)
        entry_mid = trade.get("entry_price_mid", 0)
        st.write(f"Range: Rs {entry_low} - {entry_high}")
        st.write(f"Mid: Rs {entry_mid}")
        st.caption(trade.get("entry_zone_reasoning", ""))

    with col2:
        st.markdown("**🛑 STOP LOSS**")
        sl = trade.get("stop_loss", 0)
        sl_pct = trade.get("stop_loss_pct", 0)
        sl_idx = trade.get("ideal_sl_index_level", 0)
        st.write(f"Premium: Rs {sl} ({sl_pct:+d}%)")
        st.write(f"Index: {sl_idx:,.0f}")

    st.divider()

    # Targets section
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🎯 TARGET 1**")
        t1 = trade.get("target_1", 0)
        t1_pct = trade.get("target_1_pct", 0) if "target_1_pct" in trade else int((t1 - trade.get("entry_price_mid", 1)) / max(trade.get("entry_price_mid", 1), 1) * 100)
        st.write(f"Rs {t1} ({t1_pct:+d}%)")
        st.caption(f"Index: {trade.get('target_1_index', 0):,.0f}")
        st.info("📊 Book 50% here")

    with col2:
        st.markdown("**🎯 TARGET 2**")
        t2 = trade.get("target_2", 0)
        t2_pct = trade.get("target_2_pct", 0) if "target_2_pct" in trade else int((t2 - trade.get("entry_price_mid", 1)) / max(trade.get("entry_price_mid", 1), 1) * 100)
        st.write(f"Rs {t2} ({t2_pct:+d}%)")
        st.caption(f"Index: {trade.get('target_2_index', 0):,.0f}")
        st.info("📊 Book 30% more")

    with col3:
        st.markdown("**🎯 TARGET 3**")
        t3 = trade.get("target_3", 0)
        t3_pct = trade.get("target_3_pct", 0) if "target_3_pct" in trade else int((t3 - trade.get("entry_price_mid", 1)) / max(trade.get("entry_price_mid", 1), 1) * 100)
        st.write(f"Rs {t3} ({t3_pct:+d}%)")
        st.caption(f"Index: {trade.get('target_3_index', 0):,.0f}")
        st.info("📊 Book remaining")

    st.divider()

    # Risk metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("R:R Ratio", f"{trade.get('risk_to_reward', 0):.2f}x")

    with col2:
        max_loss = trade.get("max_loss_inr", 0)
        st.metric("Max Loss", f"Rs {max_loss:,.0f}")

    with col3:
        max_holding = trade.get("max_holding_minutes", 60)
        st.metric("Max Hold", f"{max_holding} min")

    with col4:
        lot_size = trade.get("lot_size", 1)
        st.metric("Lots", f"{lot_size}")

    st.divider()

    # Exit conditions
    st.markdown("**📤 EXIT CONDITIONS**")
    exits = trade.get("exit_conditions", [])
    for i, exit_cond in enumerate(exits[:5], 1):
        if isinstance(exit_cond, dict):
            st.write(f"{i}. {exit_cond.get('description', exit_cond)}")
        else:
            st.write(f"{i}. {exit_cond}")

    if len(exits) > 5:
        st.caption(f"... and {len(exits) - 5} more conditions")


# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE GAUGE
# ─────────────────────────────────────────────────────────────────────────────

def render_confidence_gauge(trade: Dict):
    """Render a radial confidence gauge with breakdown by category."""
    confidence = trade.get("confidence_pct", 50)
    breakdown = trade.get("confidence_breakdown", {})

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=confidence,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Trade Confidence", 'font': {'size': 20}},
        delta={'reference': 50, 'increasing': {'color': "#089981"}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#089981" if confidence >= 70 else "#ffa500" if confidence >= 50 else "#f23645"},
            'steps': [
                {'range': [0, 30], 'color': "#f2364520"},
                {'range': [30, 50], 'color': "#ffa50020"},
                {'range': [50, 70], 'color': "#ffa50020"},
                {'range': [70, 100], 'color': "#08998120"},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 50
            }
        }
    ))

    fig.update_layout(
        height=300,
        font={'color': "#b2b5be"},
        paper_bgcolor="#131722",
        plot_bgcolor="#131722",
        margin=dict(l=0, r=0, t=50, b=0)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Breakdown by category
    if breakdown:
        st.markdown("**Confidence Breakdown:**")
        overall = breakdown.get("overall", {})
        bull_score = overall.get("bull_signals", 0)
        bear_score = overall.get("bear_signals", 0)

        col1, col2, col3, col4 = st.columns(4)

        categories = [
            ("Technical", breakdown.get("technical", {})),
            ("Options", breakdown.get("options_flow", {})),
            ("Macro", breakdown.get("macro_context", {})),
            ("Structure", breakdown.get("market_structure", {})),
        ]

        for col, (label, cat_data) in zip([col1, col2, col3, col4], categories):
            with col:
                score = cat_data.get("score", 0)
                weight = cat_data.get("weight", 0)
                st.metric(label, f"{score:.1f}/10", f"{weight}% weight")


# ─────────────────────────────────────────────────────────────────────────────
# RISK/REWARD VISUALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def render_risk_reward_visual(trade: Dict):
    """Render visual entry zone vs targets."""
    entry_low = trade.get("entry_price_low", 0)
    entry_high = trade.get("entry_price_high", 0)
    entry_mid = trade.get("entry_price_mid", 0)
    sl = trade.get("stop_loss", 0)
    t1 = trade.get("target_1", 0)
    t2 = trade.get("target_2", 0)
    t3 = trade.get("target_3", 0)

    if entry_mid == 0:
        st.warning("No entry price set")
        return

    # Create zones
    zones = {
        "SL": sl,
        "Entry Low": entry_low,
        "Entry Mid": entry_mid,
        "Entry High": entry_high,
        "T1": t1,
        "T2": t2,
        "T3": t3,
    }

    # Normalize for display
    min_price = sl * 0.95
    max_price = t3 * 1.05

    fig = go.Figure()

    # Add zones as bars
    fig.add_trace(go.Bar(
        y=[zones[k] for k in zones],
        x=list(zones.keys()),
        marker=dict(
            color=["#f23645", "#ffa500", "#ffa500", "#ffa500", "#089981", "#089981", "#089981"],
            line=dict(color="#b2b5be", width=1),
        ),
        text=[f"Rs {v:.0f}" for v in zones.values()],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Rs %{y:.0f}<extra></extra>",
    ))

    fig.update_layout(
        title="Entry Zone vs Targets",
        yaxis_title="Premium (Rs)",
        xaxis_title="",
        height=300,
        font={'color': "#b2b5be"},
        paper_bgcolor="#131722",
        plot_bgcolor="#131722",
        showlegend=False,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVE TRADES TABLE
# ─────────────────────────────────────────────────────────────────────────────

def render_active_trades_table(active_trades: List[Dict]):
    """Render table of active/monitored trades."""
    if not active_trades:
        st.info("📊 No active trades being monitored")
        return

    data = []
    for trade in active_trades:
        data.append({
            "Index": trade.get("index", "—"),
            "Direction": trade.get("direction", "—"),
            "Strike": trade.get("strike", "—"),
            "Entry": f"Rs {trade.get('entry_price', 0):.0f}",
            "Current": f"Rs {trade.get('current_price', 0):.0f}",
            "Target 1": f"Rs {trade.get('target_1', 0):.0f}",
            "P&L": f"Rs {trade.get('current_pnl_inr', 0):.0f}",
            "Status": trade.get("status", "—"),
            "Time": f"{trade.get('time_in_trade_minutes', 0)}m",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=300)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO HEAT MAP
# ─────────────────────────────────────────────────────────────────────────────

def render_portfolio_heatmap(portfolio: Dict):
    """Render portfolio exposure by index and direction."""
    if not portfolio or portfolio.get("num_active_trades", 0) == 0:
        st.info("📊 No active positions")
        return

    fig = go.Figure()

    indices = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    directions = ["CALL", "PUT"]
    z_data = []

    # Create heatmap data (would need actual trade data)
    st.write("**Portfolio Exposure:**")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Active Trades", portfolio.get("num_active_trades", 0))

    with col2:
        pnl = portfolio.get("total_pnl_inr", 0)
        color = "green" if pnl > 0 else "red"
        st.metric("Portfolio P&L", f"Rs {pnl:,.0f}", delta=f"{portfolio.get('total_pnl_pct', 0):.2f}%")

    with col3:
        st.metric("Max Drawdown Risk", f"{portfolio.get('max_drawdown_pct', 0):.2f}%")


# ─────────────────────────────────────────────────────────────────────────────
# DAILY P&L CHART
# ─────────────────────────────────────────────────────────────────────────────

def render_daily_pnl_chart(daily_summaries: List[Dict]):
    """Render daily P&L chart."""
    if not daily_summaries:
        st.info("📊 No trading history yet")
        return

    df = pd.DataFrame(daily_summaries)
    df['date'] = pd.to_datetime(df['date'])

    fig = go.Figure()

    # P&L bars
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['total_pnl'],
        marker=dict(
            color=['#089981' if x > 0 else '#f23645' for x in df['total_pnl']],
            line=dict(color="#b2b5be", width=1),
        ),
        name="Daily P&L",
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>P&L: Rs %{y:,.0f}<extra></extra>",
    ))

    # Win rate line
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['win_rate'],
        mode='lines+markers',
        name="Win Rate %",
        yaxis='y2',
        line=dict(color="#ffa500", width=2),
        marker=dict(size=6),
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Win Rate: %{y:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title="Daily P&L & Win Rate",
        xaxis_title="Date",
        yaxis_title="P&L (Rs)",
        yaxis2=dict(
            title="Win Rate %",
            overlaying='y',
            side='right',
        ),
        height=350,
        font={'color': "#b2b5be"},
        paper_bgcolor="#131722",
        plot_bgcolor="#131722",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# BEST/WORST SETUPS
# ─────────────────────────────────────────────────────────────────────────────

def render_best_worst_setups(best_setups: List[Dict], worst_setups: List[Dict]):
    """Render best and worst performing setups."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ✅ Best Performing Setups")
        if best_setups:
            for setup in best_setups[:3]:
                with st.container():
                    st.write(f"**{setup['setup']}**")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Win Rate", f"{setup['win_rate']:.0f}%")
                    with col_b:
                        st.metric("Avg P&L", f"Rs {setup['avg_pnl']:.0f}")
                    with col_c:
                        st.metric("Trades", setup['total_trades'])
                    st.divider()
        else:
            st.info("No data yet")

    with col2:
        st.markdown("### ❌ Worst Performing Setups")
        if worst_setups:
            for setup in worst_setups[:3]:
                with st.container():
                    st.write(f"**{setup['setup']}**")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Win Rate", f"{setup['win_rate']:.0f}%")
                    with col_b:
                        st.metric("Avg P&L", f"Rs {setup['avg_pnl']:.0f}")
                    with col_c:
                        st.metric("Trades", setup['total_trades'])
                    st.divider()
        else:
            st.info("No data yet")


# ─────────────────────────────────────────────────────────────────────────────
# MARKET CONTEXT SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def render_market_snapshot(market_snapshot: Dict):
    """Render current market conditions snapshot."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Index LTP", f"{market_snapshot.get('index_ltp', 0):,.0f}")

    with col2:
        vix = market_snapshot.get('vix', 15)
        vix_color = "🔴" if vix > 20 else "🟡" if vix > 18 else "🟢"
        st.metric("VIX", f"{vix:.1f}", delta=vix_color)

    with col3:
        pcr = market_snapshot.get('pcr', 1.0)
        st.metric("PCR", f"{pcr:.2f}")

    with col4:
        fii = market_snapshot.get('fii_net', 0)
        fii_color = "green" if fii > 0 else "red"
        st.metric("FII Net", f"Rs {fii:,.0f} Cr")
