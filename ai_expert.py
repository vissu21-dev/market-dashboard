"""
AI Options Trading Expert — powered by Claude (Anthropic)

Injects real-time market context (Nifty/BankNifty LTP, technicals, option chain,
VIX, FII/DII, global cues) into every conversation so the AI always has
current market data before answering.
"""

import os
import logging
from datetime import datetime
import pytz

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

try:
    import anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

MODEL = "claude-opus-4-5"
MAX_TOKENS = 3000

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

_BASE_SYSTEM = """You are an elite derivatives trading expert with 25+ years specializing in Indian F&O markets — specifically NIFTY 50 and BANK NIFTY options on NSE.

Your profile:
• Ex-institutional derivatives desk at a leading Indian bank
• Deep expertise in NSE options structure, expiry mechanics, margin requirements
• Mastery of Greeks: Delta, Gamma, Theta, Vega — and their intraday behaviour
• Options strategies: directional buys, selling premium, spreads, straddles, iron condors
• OI-based market analysis, max pain theory, institutional flow reading
• Quantitative signals: ORB, VWAP, EMA stacks, Supertrend, PCR trends
• Risk management for retail traders with ₹10,000–₹5,00,000 capital

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 LIVE MARKET DATA (auto-updated before each response)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{market_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESPONSE RULES:
0. A "DASHBOARD ENGINE VERDICT" may appear at the very top of the live data. That
   is the house quant view the user already sees on screen. Treat it as your
   anchor: if you agree, reinforce it and explain why; if you genuinely disagree
   based on the data, say so explicitly and justify the divergence. Never give a
   recommendation that silently contradicts the verdict — the user must understand
   any difference. If the verdict is WAIT/STAND DOWN, default to NO TRADE unless
   the user describes a materially different setup.
1. Always reference the live data above before recommending anything
2. Every trade recommendation MUST include:
   Direction | Index | Strike | Expiry | Premium | Entry Range | SL | T1 | T2 | T3 | R:R | Max Hold
3. Calculate P&L in ₹ using: NIFTY lot = 75 units, BANK NIFTY lot = 30 units
4. When risk/reward is unfavorable or signals are conflicting → recommend NO TRADE clearly
5. For position monitoring → give one of: HOLD | PARTIAL BOOK | TRAIL SL | EXIT NOW | REVERSE
6. Always explain your reasoning (technicals + macro + options flow)
7. Warn about high VIX, low liquidity, or event risk before entries
8. Never encourage over-leveraging. Suggest 1-2% capital risk per trade max
9. Format with clear sections, tables, and emojis for readability
10. Distinguish between BUY options (limited risk) and SELL options (unlimited risk)

TRADE FORMAT TEMPLATE:
```
🎯 RECOMMENDATION: [BUY CALL / BUY PUT / SELL CALL / SELL PUT / NO TRADE]
📊 CONFIDENCE: [XX]% | [HIGH / MODERATE / LOW] CONVICTION

INDEX:        [NIFTY 50 / BANK NIFTY]
STRIKE:       [XXXXX CE/PE]  ([ATM/OTM1/OTM2])
EXPIRY:       [Date]
CURRENT PREM: ₹[XXX]
ENTRY ZONE:   ₹[low]–₹[high]  (Index: [X]–[X])

🛑 STOP LOSS:  ₹[XX] ([-%]%)   → Index: [level]
🎯 TARGET 1:   ₹[XX] ([+%]%)   → Index: [level]
🎯 TARGET 2:   ₹[XX] ([+%]%)   → Index: [level]
🏆 TARGET 3:   ₹[XX] ([+%]%)   → Index: [level]
⚖️ R:R RATIO:  1:[X.X]
⏱️ MAX HOLD:   [time]
📦 LOT SIZE:   [N] units | 1 lot P&L: SL=-₹[X] | T1=+₹[X]

🧠 RATIONALE:
[Detailed explanation of why this trade, what signals confirm it]

❌ TRADE INVALID IF:
[Specific conditions that would cancel the trade thesis]

💰 EXIT PLAN:
[Step by step exit strategy]
```

⚠️ DISCLAIMER: This is for educational purposes only. Options trading involves substantial risk of loss. Not SEBI-registered investment advice. Always use your own judgment.
"""


# ─────────────────────────────────────────────────────────────────────────────
# MARKET CONTEXT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_market_context(
    quotes: dict,
    nifty_df,
    bank_df,
    vix: float,
    nifty_orb: dict,
    bank_orb: dict,
    nifty_pivots: dict,
    bank_pivots: dict,
    nifty_chain: dict,
    bank_chain: dict,
    global_quotes: dict,
    fii_dii: dict,
    breadth: dict,
    intel: dict,
    exp_info: dict,
    decision: dict = None,
) -> str:
    """
    Build a comprehensive market context string to inject into the system prompt.
    If `decision` (from decision_engine.build_trade_decision) is supplied, its
    verdict is placed at the TOP so the AI anchors to the same call the
    dashboard shows the user.
    """
    now = datetime.now(IST).strftime("%d %b %Y %H:%M IST")
    lines = [f"📅 Data as of: {now}", ""]

    # ── House verdict from the Decision Engine (anchor) ───────────────────────
    if decision:
        try:
            from decision_engine import format_decision_for_ai
            block = format_decision_for_ai(decision)
            if block:
                lines.append(block)
        except Exception:
            pass

    # ── Indian Indices ────────────────────────────────────────────────────────
    lines.append("🇮🇳 INDIAN INDICES")
    for name in ["Nifty 50", "Bank Nifty", "India VIX", "Sensex", "Fin Nifty"]:
        q = quotes.get(name, {})
        if q:
            arrow = "▲" if q.get("chg", 0) >= 0 else "▼"
            lines.append(f"  {name}: {q.get('ltp',0):,.2f}  {arrow}{abs(q.get('chg',0)):,.2f} ({q.get('pct',0):+.2f}%)  H:{q.get('high',0):,.0f} L:{q.get('low',0):,.0f}")
    lines.append("")

    # ── Technical Indicators ──────────────────────────────────────────────────
    def _tech(df, name):
        if df is None or df.empty or len(df) < 5:
            return f"  {name}: Data unavailable"
        last = df.iloc[-1]
        rsi   = last.get("rsi",   50)
        macd  = last.get("macd",   0)
        macds = last.get("macd_s", 0)
        ema9  = last.get("ema9",   0)
        ema21 = last.get("ema21",  0)
        ema50 = last.get("ema50",  0)
        vwap  = last.get("vwap",   0)
        std   = int(last.get("supertrend_dir", 0))
        ltp   = float(last.get("close", 0))
        t = []
        t.append(f"RSI:{rsi:.0f}({'Overbought' if rsi>70 else 'Oversold' if rsi<30 else 'Bullish zone' if rsi>55 else 'Bearish zone' if rsi<45 else 'Neutral'})")
        t.append(f"MACD:{'Bullish' if macd>macds else 'Bearish'}({'above0' if macd>0 else 'below0'})")
        t.append(f"EMA:{'Bull stack' if ema9>ema21>ema50 else 'Bear stack' if ema9<ema21<ema50 else 'Mixed'}")
        t.append(f"VWAP:{vwap:,.0f}({'above' if ltp>vwap else 'below'})")
        t.append(f"Supertrend:{'BULL' if std==1 else 'BEAR' if std==-1 else 'N/A'}")
        return f"  {name} (15m): " + " | ".join(t)

    lines.append("📊 TECHNICAL INDICATORS (15-min chart)")
    lines.append(_tech(nifty_df,  "Nifty 50"))
    lines.append(_tech(bank_df, "Bank Nifty"))
    lines.append("")

    # ── ORB ───────────────────────────────────────────────────────────────────
    lines.append("📐 OPENING RANGE BREAKOUT (ORB)")
    n_ltp = quotes.get("Nifty 50",  {}).get("ltp", 0)
    b_ltp = quotes.get("Bank Nifty",{}).get("ltp", 0)
    for iname, iorb, iltp in [("Nifty 50", nifty_orb, n_ltp), ("Bank Nifty", bank_orb, b_ltp)]:
        if iorb and iorb.get("high"):
            if iltp > iorb["high"]:
                status = f"BREAKOUT UP above {iorb['high']:,.0f}"
            elif iltp < iorb["low"]:
                status = f"BREAKDOWN below {iorb['low']:,.0f}"
            else:
                status = f"INSIDE ORB ({iorb['low']:,.0f}–{iorb['high']:,.0f}) — wait"
            lines.append(f"  {iname}: H={iorb['high']:,.0f} L={iorb['low']:,.0f} Range={iorb.get('range',0):,.0f} → {status}")
        else:
            lines.append(f"  {iname}: ORB not yet formed")
    lines.append("")

    # ── Pivots ────────────────────────────────────────────────────────────────
    lines.append("📍 PIVOT LEVELS")
    for iname, ipivs in [("Nifty 50", nifty_pivots), ("Bank Nifty", bank_pivots)]:
        if ipivs:
            pstr = "  ".join([f"{k}:{v:,.0f}" for k, v in ipivs.items()])
            lines.append(f"  {iname}: {pstr}")
    lines.append("")

    # ── Option Chain ──────────────────────────────────────────────────────────
    lines.append("⛓️ OPTION CHAIN ANALYSIS")
    n_exp = exp_info.get("nifty",    {})
    b_exp = exp_info.get("banknifty",{})

    def _chain_summary(chain, ltp, step, iname, exp):
        if not chain:
            return f"  {iname}: Chain data unavailable"
        atm = round(int(round(ltp / step) * step))
        ce_oi = sum(v.get("ce_oi", 0) for v in chain.values())
        pe_oi = sum(v.get("pe_oi", 0) for v in chain.values())
        pcr   = round(pe_oi / ce_oi, 2) if ce_oi else 0
        ce_wall = max(chain, key=lambda k: chain[k].get("ce_oi", 0), default=atm)
        pe_wall = max(chain, key=lambda k: chain[k].get("pe_oi", 0), default=atm)
        atm_ce  = chain.get(atm, {}).get("ce", 0)
        atm_pe  = chain.get(atm, {}).get("pe", 0)
        atm_iv  = chain.get(atm, {}).get("ce_iv", 0)
        # Max pain
        strikes = sorted(chain.keys())
        min_pain, mp = float("inf"), atm
        for ts in strikes:
            pain = sum((ts-s)*chain[s].get("ce_oi",0) if ts>s else (s-ts)*chain[s].get("pe_oi",0)
                       for s in strikes)
            if pain < min_pain:
                min_pain, mp = pain, ts
        pcr_lbl = "Bullish" if 0.7<=pcr<=1.0 else ("Bearish" if pcr>1.2 else "Neutral")
        return (f"  {iname} (Expiry: {exp.get('date','?')} | {exp.get('days','?')}d left):\n"
                f"    ATM={atm} | ATM CE=₹{atm_ce:.0f} PE=₹{atm_pe:.0f} | IV={atm_iv:.1f}%\n"
                f"    PCR={pcr:.2f} ({pcr_lbl}) | Max Pain={mp:,}\n"
                f"    CE Wall (resistance)={ce_wall:,} | PE Wall (support)={pe_wall:,}")

    n_ltp = quotes.get("Nifty 50",  {}).get("ltp", 23400)
    b_ltp = quotes.get("Bank Nifty",{}).get("ltp", 54000)
    lines.append(_chain_summary(nifty_chain, n_ltp, 50,  "Nifty 50",   n_exp))
    lines.append(_chain_summary(bank_chain,  b_ltp, 100, "Bank Nifty", b_exp))
    lines.append("")

    # ── India VIX ─────────────────────────────────────────────────────────────
    vix_label = "Normal ✅" if vix < 16 else ("Elevated ⚠️" if vix < 20 else "HIGH 🔴")
    lines.append(f"📈 INDIA VIX: {vix:.2f} — {vix_label}")
    lines.append("")

    # ── FII/DII ───────────────────────────────────────────────────────────────
    if fii_dii:
        fii_n = fii_dii.get("fii_net", 0)
        dii_n = fii_dii.get("dii_net", 0)
        lines.append(f"💰 FII/DII FLOWS: FII={fii_n:+,.0f}Cr {'🟢 Buying' if fii_n>0 else '🔴 Selling'} | DII={dii_n:+,.0f}Cr {'🟢' if dii_n>0 else '🔴'}")
    else:
        lines.append("💰 FII/DII: Not yet available (NSE updates after 4 PM)")
    lines.append("")

    # ── Market Breadth ────────────────────────────────────────────────────────
    if breadth:
        lines.append(f"📊 MARKET BREADTH: {breadth.get('label','')} | A/D Ratio: {breadth.get('ratio',0):.1f}")
    lines.append("")

    # ── Global Cues ───────────────────────────────────────────────────────────
    lines.append("🌍 GLOBAL MARKETS")
    for gname, gq in global_quotes.items():
        if gq:
            arrow = "▲" if gq.get("pct", 0) >= 0 else "▼"
            lines.append(f"  {gname}: {gq.get('ltp',0):,.2f}  {arrow}{gq.get('pct',0):+.2f}%")
    lines.append("")

    # ── Macro Intelligence ────────────────────────────────────────────────────
    if intel:
        regime = intel.get("market_regime", "NEUTRAL")
        score  = intel.get("macro_score", 0)
        risk   = intel.get("risk_level", "MEDIUM")
        lines.append(f"🧠 MACRO INTELLIGENCE: {regime} | Score: {score:+d}/20 | Risk: {risk}")
        lines.append(f"   Summary: {intel.get('summary','')}")
        if intel.get("geo_alert"):
            lines.append(f"   ⚠️ GEO: {intel['geo_alert']}")
        if intel.get("policy_alert"):
            lines.append(f"   📢 POLICY: {intel['policy_alert']}")
        news = intel.get("news", {})
        if news.get("top_bull"):
            lines.append(f"   📰 Positive news: {news['top_bull'][0][:80]}")
        if news.get("top_bear"):
            lines.append(f"   📰 Negative news: {news['top_bear'][0][:80]}")
    lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# STREAMING RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

def stream_response(messages: list, market_context: str):
    """
    Stream Claude's response token-by-token.
    Yields text chunks for use with st.write_stream().
    """
    if not _ANTHROPIC_OK:
        yield "❌ `anthropic` library not installed. Run: `pip install anthropic`"
        return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield "❌ `ANTHROPIC_API_KEY` not set. Add it to your `.env` file and Streamlit secrets."
        return

    system_prompt = _BASE_SYSTEM.format(market_context=market_context)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
    except anthropic.AuthenticationError:
        yield "❌ Invalid Anthropic API key. Check your `ANTHROPIC_API_KEY` in Streamlit secrets."
    except anthropic.RateLimitError:
        yield "⚠️ Rate limit reached. Please wait a moment and try again."
    except Exception as e:
        yield f"❌ AI error: {str(e)}"


def is_available() -> bool:
    return _ANTHROPIC_OK and bool(os.getenv("ANTHROPIC_API_KEY", ""))


# ─────────────────────────────────────────────────────────────────────────────
# QUICK QUESTION PRESETS
# ─────────────────────────────────────────────────────────────────────────────

QUICK_QUESTIONS = [
    ("📊 Best trade right now?",     "Analyze current market conditions and give me the best NIFTY or BANK NIFTY options trade available right now. Include full trade details with entry, SL, and targets."),
    ("📈 Buy NIFTY Call?",           "Should I buy a NIFTY 50 Call option right now? Analyze the technicals, option chain, global cues and give me a complete trade plan if the setup is valid."),
    ("📉 Buy BANK NIFTY Put?",       "Should I buy a BANK NIFTY Put option right now? Give me a complete analysis and trade recommendation with strike, entry, SL and targets."),
    ("⏸️ Hold or exit position?",    "I have an open options position. Based on current market conditions, should I hold, partially book profits, trail my stop loss, or exit immediately?"),
    ("🧱 Where is max pain today?",  "What is the current max pain level for NIFTY and BANK NIFTY? How does it impact where the market is likely to settle at expiry?"),
    ("🌍 Global cues impact?",       "How are global markets (US, Europe, Asia) impacting NIFTY and BANK NIFTY today? Should I be bullish or bearish based on the global setup?"),
    ("📉 What is VIX saying?",       "Interpret the current India VIX level and tell me what it means for options buying vs selling strategy today."),
    ("💡 Safest trade today?",       "What is the lowest-risk options trade available today on NIFTY or BANK NIFTY? Prioritize capital preservation and high-probability setups."),
    ("🔄 Sell options strategy?",    "Based on current VIX and option chain, is today suitable for selling options (straddle/strangle/credit spread)? Give me a complete setup if valid."),
    ("❓ No trade conditions?",      "Are there any reasons I should completely avoid trading options today? Evaluate all risk factors and tell me if staying on the sidelines is the best call."),
]
