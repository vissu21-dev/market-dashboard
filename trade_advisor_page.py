"""
Trade Advisor Page - Professional Intraday Options Trading Recommendations
Main Streamlit page for the Trade Advisor tab with all integrated features.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional

from trade_engine import generate_recommendation
from trade_advisor import generate_professional_trade_recommendation, analyze_confidence_breakdown
from risk_manager import calculate_position_size, check_trading_guardrails, INSTRUMENT_CONFIG
from trade_journal import (
    init_database, log_trade, close_trade, get_daily_pnl, get_period_pnl,
    get_performance_by_index, get_best_setups, get_worst_setups, export_journal_csv
)
import ui_components

IST = pytz.timezone("Asia/Kolkata")


def render_trade_advisor_page(
    market_data: Dict,
    options_chains: Dict,
    global_sentiment: int,
    fii_dii: Dict = None,
    breadth: Dict = None,
):
    """
    Main Trade Advisor page renderer.

    Args:
        market_data: Dict with NIFTY, BANKNIFTY, FINNIFTY quotes and intraday data
        options_chains: Dict with live option chains for each index
        global_sentiment: Global sentiment score (-10 to +10)
        fii_dii: FII/DII data dict
        breadth: Market breadth dict
    """

    st.set_page_config(page_title="🎯 Trade Advisor", layout="wide")

    st.markdown("# 🎯 Trade Advisor — Professional Intraday Options Mentor")
    st.markdown("Real-time trade recommendations with entry zones, targets, risk management, and exit strategy.")

    # Initialize database
    init_database()

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 1: RISK MANAGEMENT SETUP
    # ──────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## ⚙️ Risk Management Setup")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        account_size = st.number_input(
            "Account Size (₹)",
            min_value=10000,
            max_value=10000000,
            value=st.session_state.get("account_size", 100000),
            step=10000,
            key="account_size_input"
        )
        st.session_state.account_size = account_size

    with col2:
        risk_percent = st.slider(
            "Risk per Trade (%)",
            min_value=0.5,
            max_value=5.0,
            value=st.session_state.get("risk_percent", 1.0),
            step=0.5,
            key="risk_percent_input"
        )
        st.session_state.risk_percent = risk_percent

    with col3:
        max_concurrent = st.selectbox(
            "Max Concurrent Trades",
            [1, 2, 3, 4, 5],
            index=2,
            key="max_concurrent_input"
        )

    with col4:
        leverage = st.selectbox(
            "Leverage Preference",
            ["Conservative (1x)", "Moderate (1.5x)", "Aggressive (2x)"],
            index=1,
            key="leverage_input"
        )

    # Display guardrails
    guardrails = check_trading_guardrails(
        daily_pnl=st.session_state.get("daily_pnl", 0),
        account_size=account_size,
        num_active_trades=st.session_state.get("active_trades_count", 0),
        total_daily_risk=st.session_state.get("total_daily_risk", 0),
        vix=market_data.get("NIFTY", {}).get("vix", 15)
    )

    # Show warnings
    if guardrails.get("warnings"):
        for warning in guardrails["warnings"]:
            if "🛑" in warning:
                st.error(warning)
            else:
                st.warning(warning)

    status_color = "#f23645" if guardrails["status"] == "🛑 STOP" else "#ffa500" if "CAUTION" in guardrails["status"] else "#089981"
    st.markdown(f"**Status:** <span style='color: {status_color}; font-weight: 700;'>{guardrails['status']}</span>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 2: TRADE RECOMMENDATIONS
    # ──────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## 🎯 Live Trade Recommendations")

    # Tabs for each index
    tab_nifty, tab_banknifty, tab_finnifty = st.tabs(["NIFTY 50", "BANK NIFTY", "FIN NIFTY"])

    indices_config = {
        "NIFTY": {
            "tab": tab_nifty,
            "key": "NIFTY 50",
            "step": 50,
            "lot_size": 75,
        },
        "BANKNIFTY": {
            "tab": tab_banknifty,
            "key": "BANK NIFTY",
            "step": 100,
            "lot_size": 40,
        },
        "FINNIFTY": {
            "tab": tab_finnifty,
            "key": "FIN NIFTY",
            "step": 50,
            "lot_size": 30,
        },
    }

    recommendations = {}

    for idx_name, config in indices_config.items():
        with config["tab"]:
            quote = market_data.get(config["key"], {})
            if not quote or quote.get("ltp") == 0:
                st.warning(f"No data available for {config['key']} yet. Check market hours (9:15 AM - 3:30 PM IST).")
                continue

            ltp = quote.get("ltp", 0)
            vix = quote.get("vix", 15)

            # Get candle data and generate recommendation
            df = st.session_state.get(f"{idx_name}_candles", pd.DataFrame())

            if df.empty or len(df) < 20:
                st.info(f"Loading {config['key']} data...")
                continue

            # Get options chain
            live_chain = options_chains.get(idx_name, {})

            # Get ORB and pivots from market data
            orb = quote.get("orb", {})
            pivots = quote.get("pivots", {})

            # Generate recommendation from trade_engine
            engine_result = generate_recommendation(
                name=config["key"],
                df=df,
                ltp=ltp,
                vix=vix,
                orb=orb,
                pivots=pivots,
                live_chain=live_chain,
                global_score=global_sentiment,
                step=config["step"],
                lot_size=config["lot_size"],
                expiry_label="Weekly",
                fii_dii=fii_dii,
                breadth=breadth,
            )

            # Convert to professional trade
            if engine_result.get("status") == "AVOID":
                st.warning(f"🛑 {engine_result.get('reason', 'No trade available')}")
            else:
                pro_trade = generate_professional_trade_recommendation(
                    trade_engine_result=engine_result,
                    live_chain=live_chain,
                    ltp=ltp,
                    account_size=account_size,
                    risk_percent=risk_percent,
                    instrument=idx_name,
                    step=config["step"],
                )

                if pro_trade:
                    recommendations[idx_name] = pro_trade.to_dict()

                    # Render the professional card
                    ui_components.render_trade_recommendation_card(
                        recommendations[idx_name],
                        account_size=account_size
                    )

                    # Confidence gauge
                    col1, col2 = st.columns(2)
                    with col1:
                        ui_components.render_confidence_gauge(recommendations[idx_name])
                    with col2:
                        ui_components.render_risk_reward_visual(recommendations[idx_name])

                    st.divider()

                    # Position sizing suggestion
                    st.markdown("**Position Sizing Recommendation:**")
                    entry_mid = recommendations[idx_name].get("entry_price_mid", 0)
                    sl = recommendations[idx_name].get("stop_loss", 0)

                    pos_size = calculate_position_size(
                        account_size=account_size,
                        risk_percent=risk_percent,
                        entry_price=entry_mid,
                        sl_price=sl,
                        instrument=idx_name,
                    )

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Recommended Lots", pos_size.get("lots", 0))
                    with col2:
                        st.metric("Units", pos_size.get("units", 0))
                    with col3:
                        st.metric("Max Loss", f"Rs {pos_size.get('max_loss_inr', 0):,.0f}")
                    with col4:
                        st.metric("Account Risk", f"{pos_size.get('max_loss_pct', 0):.2f}%")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 3: ACTIVE TRADES MONITORING
    # ──────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## 📊 Active Trades Monitoring")

    active_trades = st.session_state.get("active_trades", [])

    if active_trades:
        ui_components.render_active_trades_table(active_trades)
        st.session_state.active_trades_count = len(active_trades)
    else:
        st.info("No active trades. Use recommendations above to enter trades.")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 4: TRADE JOURNAL & ANALYTICS
    # ──────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## 📈 Trade Journal & Performance Analytics")

    analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs([
        "Daily P&L", "By Index", "Setup Analysis"
    ])

    with analytics_tab1:
        st.markdown("### Daily P&L Summary")

        col1, col2 = st.columns(2)

        with col1:
            date_selected = st.date_input("Select Date", value=datetime.now(IST).date())
        with col2:
            if st.button("Refresh P&L", key="refresh_pnl"):
                st.rerun()

        daily_pnl = get_daily_pnl(date_selected)

        if daily_pnl.get("total_trades", 0) > 0:
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Total Trades", daily_pnl.get("total_trades", 0))
            with col2:
                st.metric("Winning Trades", daily_pnl.get("winning_trades", 0))
            with col3:
                st.metric(
                    "Win Rate",
                    f"{daily_pnl.get('win_rate', 0):.1f}%"
                )
            with col4:
                pnl = daily_pnl.get("total_pnl", 0)
                st.metric(
                    "Total P&L",
                    f"Rs {pnl:,.0f}",
                    delta="Profit" if pnl > 0 else "Loss"
                )
            with col5:
                st.metric("Best Trade", f"Rs {daily_pnl.get('largest_win', 0):,.0f}")

            # Daily P&L chart
            period_pnl = get_period_pnl(
                date_selected - timedelta(days=7),
                date_selected
            )

            if period_pnl.get("total_trades", 0) > 0:
                daily_summaries = []
                for i in range(8):
                    d = date_selected - timedelta(days=i)
                    d_pnl = get_daily_pnl(d)
                    if d_pnl.get("total_trades", 0) > 0:
                        daily_summaries.append(d_pnl)

                if daily_summaries:
                    ui_components.render_daily_pnl_chart(daily_summaries)
        else:
            st.info("No trades on this date")

    with analytics_tab2:
        st.markdown("### Performance by Index")

        perf_by_index = get_performance_by_index(date_selected)

        if perf_by_index:
            perf_df = pd.DataFrame([
                {
                    "Index": k,
                    "Total Trades": v["total_trades"],
                    "Winning": v["winning_trades"],
                    "Win Rate": f"{v['win_rate']:.1f}%",
                    "Total P&L": f"Rs {v['total_pnl']:,.0f}",
                    "Avg P&L": f"Rs {v['avg_pnl']:,.0f}",
                }
                for k, v in perf_by_index.items()
            ])
            st.dataframe(perf_df, use_container_width=True)
        else:
            st.info("No performance data for this date")

    with analytics_tab3:
        st.markdown("### Best & Worst Performing Setups (Last 7 Days)")

        best_setups = get_best_setups(min_trades=2, date_range_days=7)
        worst_setups = get_worst_setups(min_trades=2, date_range_days=7)

        ui_components.render_best_worst_setups(best_setups, worst_setups)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 5: EXPORT & ADMIN
    # ──────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## 💾 Export & Administration")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 Export Trade Journal (CSV)", key="export_journal"):
            export_df = export_journal_csv(date_range_days=30)
            if export_df is not None:
                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Download Journal",
                    data=csv,
                    file_name=f"trade_journal_{datetime.now(IST).strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No trades to export")

    with col2:
        if st.button("🗑️ Clear Database (⚠️ Careful!)", key="clear_db"):
            if st.checkbox("Confirm deletion of all trade data"):
                try:
                    import sqlite3
                    from pathlib import Path
                    db_path = Path(__file__).parent / "trade_journal.db"
                    if db_path.exists():
                        db_path.unlink()
                        st.success("Database cleared")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error clearing database: {e}")

    st.markdown("---")
    st.caption("© 2026 Professional Trade Advisor | Trading carries risk. Always use stop losses.")
