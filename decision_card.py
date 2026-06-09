"""
Decision-First UI — renders the "What should I do right now?" card.
Consumes the object produced by decision_engine.build_trade_decision().

Design goals:
  • The verdict (TRADE / WAIT) is the first thing the eye lands on.
  • Traffic-light colour communicates conviction instantly.
  • One single best trade card with the full plan; alternatives collapsed.
  • A confident NO-TRADE state — not a blank or an error.
"""

import streamlit as st

_LIGHT = {
    "green":  {"bg": "#0d2a1a", "border": "#13c27b", "dot": "#13c27b", "word": "GO"},
    "yellow": {"bg": "#2a230d", "border": "#e8b007", "dot": "#e8b007", "word": "CAUTION"},
    "red":    {"bg": "#2a0d0d", "border": "#f23645", "dot": "#f23645", "word": "STAND DOWN"},
}


def _fmt(v, prefix="₹", dash="—"):
    if v is None or v == "":
        return dash
    if isinstance(v, (int, float)):
        return f"{prefix}{v:,.0f}"
    return str(v)


def render_decision_card(decision: dict, *, compact: bool = False):
    """Render the top-of-dashboard decision card."""
    if not decision:
        return

    light = _LIGHT.get(decision.get("traffic_light", "red"), _LIGHT["red"])
    verdict = decision.get("verdict", "WAIT")
    headline = decision.get("headline_action", "WAIT — NO TRADE")
    as_of = decision.get("as_of", "")

    # ── Header banner ────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{light['bg']};border:2px solid {light['border']};
                    border-radius:14px;padding:18px 24px;margin:6px 0 4px">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
            <div style="display:flex;align-items:center;gap:14px">
              <div style="width:16px;height:16px;border-radius:50%;background:{light['dot']};
                          box-shadow:0 0 14px {light['dot']}"></div>
              <div>
                <div style="font-size:11px;letter-spacing:.18em;color:#9aa0aa;font-weight:700">
                  WHAT SHOULD I DO RIGHT NOW?</div>
                <div style="font-size:26px;font-weight:900;color:{light['border']};line-height:1.15">
                  {headline}</div>
              </div>
            </div>
            <div style="text-align:right">
              <div style="font-size:11px;color:#9aa0aa">SIGNAL</div>
              <div style="font-size:18px;font-weight:900;color:{light['border']}">{light['word']}</div>
              <div style="font-size:11px;color:#7d828c;margin-top:2px">as of {as_of}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    best = decision.get("best")
    evals = decision.get("all_evaluations", [])

    if verdict != "TRADE" or not best:
        _render_no_trade(decision)
        # Even on a WAIT, show each index's read so both NIFTY & BANKNIFTY are visible
        _render_per_index_tabs(evals, best_index=None)
        return

    _render_warnings(decision)
    # Per-index plans — NIFTY, BANK NIFTY, FIN NIFTY each with exact strike.
    # Recommended index tab is shown first.
    _render_per_index_tabs(evals, best_index=best.get("index"))


# ─────────────────────────────────────────────────────────────────────────────

def _render_no_trade(decision: dict):
    reason = decision.get("no_trade_reason", "No high-probability setup right now.")
    st.markdown(
        f"""
        <div style="background:#15181f;border-left:4px solid #f23645;border-radius:10px;
                    padding:14px 18px;margin:4px 0 10px">
          <div style="color:#f0a0a0;font-weight:800;font-size:15px;margin-bottom:4px">
            🛑 Preserve capital — stay flat</div>
          <div style="color:#c7ccd4;font-size:13.5px;line-height:1.5">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    warns = decision.get("event_warnings", [])
    if warns:
        for w in warns[:4]:
            st.warning(w)
    alts = decision.get("alternatives", [])
    if alts:
        with st.expander("Why each index is a pass right now", expanded=False):
            for a in alts:
                st.markdown(
                    f"• **{a['index']}** — {a.get('direction') or '—'} · "
                    f"{a.get('confidence',0)}% · _{a.get('status','')}_"
                )


def _render_best_trade(best: dict, light: dict):
    oc = "#13c27b" if best["option_type"] == "CE" else "#f23645"
    conf = best["adj_confidence"]
    sizing = best.get("sizing", {})

    # ── Confidence + conviction strip ────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
    with c1:
        st.markdown(
            f"""<div style="background:#1a1d24;border-radius:10px;padding:12px 14px">
                 <div style="font-size:11px;color:#9aa0aa">CONFIDENCE</div>
                 <div style="font-size:30px;font-weight:900;color:{light['border']}">{conf}%</div>
                 <div style="font-size:12px;color:#c7ccd4">{best['conviction']} conviction</div>
               </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(
            f"""<div style="background:#1a1d24;border-radius:10px;padding:12px 14px">
                 <div style="font-size:11px;color:#9aa0aa">STRIKE</div>
                 <div style="font-size:20px;font-weight:800;color:{oc}">{best['strike']} {best['option_type']}</div>
                 <div style="font-size:12px;color:#c7ccd4">{best.get('strike_label','')} · exp {best.get('expiry','')}</div>
               </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(
            f"""<div style="background:#1a1d24;border-radius:10px;padding:12px 14px">
                 <div style="font-size:11px;color:#9aa0aa">R:R</div>
                 <div style="font-size:20px;font-weight:800;color:#e0e0e0">1:{best.get('rr','—')}</div>
                 <div style="font-size:12px;color:#c7ccd4">max hold {best.get('max_hold','—')}</div>
               </div>""", unsafe_allow_html=True)
    with c4:
        lots = sizing.get("lots", 0)
        st.markdown(
            f"""<div style="background:#1a1d24;border-radius:10px;padding:12px 14px">
                 <div style="font-size:11px;color:#9aa0aa">POSITION</div>
                 <div style="font-size:20px;font-weight:800;color:#e0e0e0">{lots} lot{'s' if lots!=1 else ''}</div>
                 <div style="font-size:12px;color:#c7ccd4">{sizing.get('units',0)} units</div>
               </div>""", unsafe_allow_html=True)

    # ── Entry / SL / Targets ladder ──────────────────────────────────────────
    st.markdown("##### 🎯 Trade Plan (option premium)")
    e1, e2, e3, e4, e5 = st.columns(5)
    ladder = [
        (e1, "ENTRY ZONE", f"{_fmt(best.get('entry_low'))}–{_fmt(best.get('entry_high'),'')}", oc),
        (e2, "STOP LOSS",  f"{_fmt(best.get('sl'))}", "#f23645"),
        (e3, "TARGET 1",   f"{_fmt(best.get('t1'))}", "#13c27b"),
        (e4, "TARGET 2",   f"{_fmt(best.get('t2'))}", "#13c27b"),
        (e5, "TARGET 3",   f"{_fmt(best.get('t3'))}", "#13c27b"),
    ]
    for col, label, val, color in ladder:
        with col:
            st.markdown(
                f"""<div style="background:#15181f;border:1px solid {color}55;border-radius:8px;
                            padding:9px 10px;text-align:center">
                     <div style="font-size:10.5px;color:#9aa0aa;letter-spacing:.05em">{label}</div>
                     <div style="font-size:16px;font-weight:800;color:{color}">{val}</div>
                   </div>""", unsafe_allow_html=True)

    # ── Index reference levels + capital ─────────────────────────────────────
    i1, i2, i3 = st.columns(3)
    with i1:
        st.markdown(f"**Index SL:** <span style='color:#f23645'>{best.get('idx_sl_label','—')}</span>",
                    unsafe_allow_html=True)
    with i2:
        st.markdown(f"**Index T1:** <span style='color:#13c27b'>{best.get('idx_t1_label','—')}</span>",
                    unsafe_allow_html=True)
    with i3:
        st.markdown(f"**Capital:** ₹{sizing.get('capital_required',0):,} · "
                    f"**Max loss:** <span style='color:#f23645'>₹{sizing.get('max_loss',0):,}</span>",
                    unsafe_allow_html=True)

    # ── Why this trade ───────────────────────────────────────────────────────
    reasons = best.get("reasons", [])
    macro_notes = best.get("macro_notes", [])
    with st.expander("🧠 Why this trade — reasoning, exits & invalidation", expanded=True):
        if reasons:
            st.markdown("**Signals confirming the setup:**")
            for r in reasons[:7]:
                st.markdown(f"- {r}")
        if macro_notes:
            st.markdown("**Macro / global context:**")
            for m in macro_notes:
                st.markdown(f"- {m}")
        if best.get("pcr"):
            pcr = best["pcr"]
            st.markdown(f"**Options flow:** PCR {pcr.get('pcr','—')} ({pcr.get('label','')}) · "
                        f"Max Pain {best.get('max_pain','—')}")
        st.markdown(f"**❌ Invalidation:** exit immediately if index crosses "
                    f"<span style='color:#f23645'>{best.get('invalidation','SL level')}</span>",
                    unsafe_allow_html=True)
        exits = best.get("exits", [])
        if exits:
            st.markdown("**💰 Exit plan:**")
            for ex in exits:
                st.markdown(f"- {ex}")


_DISP = {"NIFTY": "NIFTY 50", "BANKNIFTY": "BANK NIFTY", "FINNIFTY": "FIN NIFTY"}


def _light_for(conf: float) -> dict:
    if conf >= 68:
        return _LIGHT["green"]
    if conf >= 58:
        return _LIGHT["yellow"]
    return _LIGHT["red"]


def _render_per_index_tabs(evals: list, best_index=None):
    """One tab per index (NIFTY / BANK NIFTY / FIN NIFTY), each with its full plan."""
    if not evals:
        return

    # Order: recommended index first, then the rest in NIFTY/BANKNIFTY/FINNIFTY order
    order = {"NIFTY": 0, "BANKNIFTY": 1, "FINNIFTY": 2}
    ordered = sorted(evals, key=lambda e: (e.get("index") != best_index, order.get(e.get("index"), 9)))

    st.markdown("#### 📑 Trade plan by index")
    labels = []
    for e in ordered:
        name = _DISP.get(e.get("index"), e.get("index", "—"))
        if e.get("actionable") and e.get("direction"):
            star = "⭐ " if e.get("index") == best_index else ""
            labels.append(f"{star}{name} · {e.get('option_type','')} {e.get('adj_confidence','')}%")
        else:
            labels.append(f"{name} · {e.get('status','—')}")

    tabs = st.tabs(labels)
    for tab, e in zip(tabs, ordered):
        with tab:
            if e.get("actionable") and e.get("direction"):
                _render_best_trade(e, _light_for(e.get("adj_confidence", 0)))
            else:
                _render_index_pass(e)


def _render_index_pass(e: dict):
    """Render a non-actionable index (AVOID / WATCHLIST) with its reason."""
    status = e.get("status", "—")
    color = "#3b82f6" if status == "WATCHLIST" else "#f23645"
    word = "👀 WATCHLIST — wait for confirmation" if status == "WATCHLIST" else "🚫 No trade right now"
    reason = e.get("reason") or "No confirmed directional edge."
    conf = e.get("adj_confidence", e.get("base_confidence", 0))
    st.markdown(
        f"""<div style="background:#15181f;border-left:4px solid {color};border-radius:10px;
                    padding:14px 18px;margin:6px 0">
              <div style="color:{color};font-weight:800;font-size:15px">{word}</div>
              <div style="color:#c7ccd4;font-size:13px;margin-top:4px">{reason}</div>
              <div style="color:#7d828c;font-size:12px;margin-top:6px">Engine read: {conf}% · {status}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def _render_warnings(decision: dict):
    warns = decision.get("event_warnings", [])
    for w in warns[:4]:
        if "🛑" in w:
            st.error(w)
        else:
            st.warning(w)


def _render_alternatives(alts: list):
    if not alts:
        return
    with st.expander(f"📋 Other setups on the radar ({len(alts)})", expanded=False):
        for a in alts:
            oc = "#13c27b" if a.get("option_type") == "CE" else "#f23645"
            st.markdown(
                f"<span style='color:{oc};font-weight:700'>{a['index']} "
                f"{a.get('strike','')} {a.get('option_type','')}</span> · "
                f"{a['confidence']}% · {a.get('conviction','')}",
                unsafe_allow_html=True,
            )
