"""
Market Events & Intelligence Dashboard
Displays economic calendar, political news, geopolitical alerts, and sector analysis.
Integrated with Trade Advisor for dynamic recommendation adjustments.
"""

import streamlit as st
from datetime import datetime, timedelta
import pytz

try:
    from market_events import (
        get_full_market_intelligence,
        get_economic_calendar,
        get_upcoming_events_today,
        get_political_news,
        get_geopolitical_news,
        get_sector_news,
        analyze_market_sentiment_from_news,
        get_market_risk_score,
    )
    _EVENTS_OK = True
except Exception:
    _EVENTS_OK = False

IST = pytz.timezone("Asia/Kolkata")


def render_market_events_dashboard():
    """Render complete market events and intelligence dashboard."""

    if not _EVENTS_OK:
        st.error("❌ Market Events module not available")
        return

    st.markdown("# 📊 Market Events & Intelligence Dashboard")
    st.caption("Real-time economic calendar, political news, geopolitical alerts, and sector analysis")

    # Get all market intelligence
    try:
        market_intel = get_full_market_intelligence()
    except Exception as e:
        st.error(f"Error fetching market intelligence: {str(e)[:100]}")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 1: MARKET RISK & ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## ⚠️ Market Risk Assessment")

    risk_data = market_intel.get("risk_assessment", {})
    risk_score = risk_data.get("risk_score", 50)
    risk_level = risk_data.get("risk_level", "MODERATE")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        risk_color = "🔴" if risk_level == "CRITICAL" else "🟠" if risk_level == "HIGH" else "🟡" if risk_level == "MODERATE" else "🟢"
        st.metric("Risk Level", f"{risk_color} {risk_level}", f"{risk_score:.0f}/100")

    with col2:
        condition = risk_data.get("market_condition", "Normal")
        st.write(f"**Market Condition**  \n{condition}")

    with col3:
        recommendation = risk_data.get("trading_recommendation", "Trade normally")
        st.write(f"**Trading Recommendation**  \n{recommendation[:50]}")

    with col4:
        advisories = risk_data.get("position_management", [])
        if advisories:
            st.write(f"**Position Advice**  \n{advisories[0][:40]}")

    # Show detailed alerts
    advisories = risk_data.get("position_management", [])
    if advisories:
        st.warning("📌 " + " | ".join(advisories))

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 2: UPCOMING EVENTS TODAY (CRITICAL)
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 📅 Upcoming Events Today (Next 6 Hours)")

    events_today = market_intel.get("events_today", [])

    if events_today:
        for i, event in enumerate(events_today, 1):
            minutes_until = event.get("minutes_until", 0)
            impact = event.get("impact", 0)
            event_name = event.get("event", "Event")

            # Color code by proximity and impact
            if minutes_until < 30 and impact > 200:
                icon = "🔴"
                severity = "CRITICAL"
            elif minutes_until < 60 and impact > 150:
                icon = "🟠"
                severity = "HIGH"
            elif minutes_until < 120:
                icon = "🟡"
                severity = "MEDIUM"
            else:
                icon = "🟢"
                severity = "LOW"

            col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])

            with col1:
                st.write(icon)
            with col2:
                st.write(f"**{event_name}**")
            with col3:
                st.write(f"{minutes_until} min")
            with col4:
                st.write(f"Impact: ±{impact}")
            with col5:
                st.write(f"{severity}")

    else:
        st.info("✅ No major events in next 6 hours")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 3: ECONOMIC CALENDAR
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 📆 Economic Calendar (Next 7 Days)")

    calendar = market_intel.get("economic_calendar", [])

    if calendar:
        cal_tab1, cal_tab2 = st.tabs(["Upcoming Events", "By Impact"])

        with cal_tab1:
            for event in calendar[:10]:  # Show first 10
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                with col1:
                    st.write(f"**{event.get('event', 'Event')}**  \n{event.get('date')}")
                with col2:
                    st.write(f"**Time**  \n{event.get('time', 'TBD')}")
                with col3:
                    impact = event.get("impact", 0)
                    impact_emoji = "🔴" if impact > 300 else "🟠" if impact > 200 else "🟡" if impact > 100 else "🟢"
                    st.write(f"{impact_emoji} ±{impact}")
                with col4:
                    days = event.get("days_away", 0)
                    st.write(f"{days} days away")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 4: MARKET SENTIMENT
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 🎯 Market Sentiment Analysis")

    sentiment = market_intel.get("sentiment_analysis", {})
    overall = sentiment.get("overall_sentiment", 0.5)
    political = sentiment.get("political_sentiment", 0.5)
    geo = sentiment.get("geopolitical_sentiment", 0.5)

    col1, col2, col3 = st.columns(3)

    with col1:
        sentiment_label = "Very Bullish" if overall > 0.7 else "Bullish" if overall > 0.6 else "Neutral" if overall > 0.4 else "Bearish"
        sentiment_color = "🟢" if overall > 0.6 else "🟡" if overall > 0.4 else "🔴"
        st.metric("Overall Sentiment", f"{sentiment_color} {sentiment_label}", f"{overall:.0%}")

    with col2:
        st.metric("Political Sentiment", f"{political:.0%}", delta=f"{(political - 0.5):.0%}")

    with col3:
        st.metric("Geopolitical Sentiment", f"{geo:.0%}", delta=f"{(geo - 0.5):.0%}")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 5: POLITICAL NEWS
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 🏛️ Political News")

    political_news = market_intel.get("political_news", [])

    if political_news:
        for news in political_news[:5]:
            impact = "positive" if news.get("impact") == "positive" else "negative" if news.get("impact") == "negative" else "neutral"
            impact_icon = "🟢" if impact == "positive" else "🔴" if impact == "negative" else "🟡"

            with st.container():
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    st.write(impact_icon)
                with col2:
                    st.write(f"**{news.get('headline', 'News')}**")
                    st.caption(f"{news.get('category', 'News')} | {news.get('date', 'Today')} | Impact: ±{news.get('market_impact', 0)}")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 6: GEOPOLITICAL NEWS
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 🌍 Geopolitical News")

    geo_news = market_intel.get("geopolitical_news", [])

    if geo_news:
        for news in geo_news[:5]:
            severity = news.get("severity", "low")
            severity_icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"

            with st.container():
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    st.write(severity_icon)
                with col2:
                    st.write(f"**{news.get('headline', 'News')}**")
                    st.caption(f"{news.get('region', 'Global')} | Impact: ±{news.get('market_impact', 0)} | {severity.upper()}")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 7: SECTOR NEWS
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 📈 Sector-Specific News")

    sector_news = market_intel.get("sector_news", {})

    if sector_news:
        sector_tabs = st.tabs(list(sector_news.keys()))

        for tab, (sector, news_list) in zip(sector_tabs, sector_news.items()):
            with tab:
                if news_list:
                    for news in news_list:
                        impact = news.get("impact", "neutral")
                        impact_icon = "🟢" if impact == "positive" else "🔴" if impact in ["negative", "negative_for_oil"] else "🟡"

                        col1, col2 = st.columns([0.1, 0.9])
                        with col1:
                            st.write(impact_icon)
                        with col2:
                            st.write(f"**{news.get('headline', 'News')}**")
                            affected = ", ".join(news.get("stocks_affected", [])[:3])
                            st.caption(f"Affected: {affected} | {news.get('date', 'Today')}")
                else:
                    st.info(f"No recent news for {sector}")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 8: KEY RISKS & OPPORTUNITIES
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## ⚡ Key Risks & Opportunities")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🚨 Key Risks")
        risks = sentiment.get("key_risks", [])
        if risks:
            for risk in risks:
                st.warning(f"• {risk}")
        else:
            st.info("No major risks identified")

    with col2:
        st.markdown("### 💡 Opportunities")
        opps = sentiment.get("key_opportunities", [])
        if opps:
            for opp in opps:
                st.success(f"• {opp}")
        else:
            st.info("Limited clear opportunities")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 9: TRADING ADVISORIES
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("## 📊 Trading Advisories")

    trading_advisories = market_intel.get("trading_advisories", {})

    col1, col2, col3 = st.columns(3)

    with col1:
        can_trade = trading_advisories.get("can_trade", True)
        trade_status = "✅ Safe to Trade" if can_trade else "❌ Avoid Trading"
        st.metric("Trading Status", trade_status)

    with col2:
        pos_recs = trading_advisories.get("position_recommendations", {})
        size_mult = pos_recs.get("size_multiplier", 1.0)
        st.metric("Position Size Multiplier", f"{size_mult:.0%}")

    with col3:
        max_trades = pos_recs.get("max_concurrent_trades", 3)
        st.metric("Max Concurrent Trades", max_trades)

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # FOOTER
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.caption(
        "💡 Use this intelligence to adjust your Trade Advisor recommendations. "
        "High risk periods warrant smaller positions and tighter stops. "
        "Green periods allow normal trading. Always respect upcoming events!"
    )
    st.caption(f"Last updated: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
