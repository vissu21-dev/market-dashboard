"""
AI Options Trading Decision Engine
═══════════════════════════════════════════════════════════════════════════════
The synthesis brain that turns raw market data into ONE clear, actionable
trade decision — the "What should I do right now?" answer.

It does NOT re-implement analysis. It orchestrates the existing layers:
  • trade_engine.generate_recommendation()  → technical + options-flow signal
  • market_events.get_full_market_intelligence() → event-risk overlay
  • market_intelligence.get_full_intelligence()   → macro / global overlay

…then adjusts confidence, ranks every index, and picks the single best setup
(or confidently says WAIT — NO TRADE).

Returned object is UI-agnostic so it can feed a Streamlit card, the AI Expert
prompt, or an alert.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Dict, List, Optional

import pytz

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

try:
    from trade_engine import generate_recommendation
    _ENGINE_OK = True
except Exception:                                    # pragma: no cover
    _ENGINE_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Conviction / traffic-light mapping
# ─────────────────────────────────────────────────────────────────────────────

def _conviction_label(conf: float) -> str:
    if conf >= 78:
        return "Very High"
    if conf >= 68:
        return "High"
    if conf >= 58:
        return "Moderate"
    if conf >= 48:
        return "Low"
    return "Very Low"


def _traffic_light(conf: float, actionable: bool, blocked_by_event: bool) -> str:
    """green = take it, yellow = caution, red = stand down."""
    if blocked_by_event or not actionable:
        return "red"
    if conf >= 68:
        return "green"
    if conf >= 58:
        return "yellow"
    return "red"


# ─────────────────────────────────────────────────────────────────────────────
# Confidence overlay — events + macro
# ─────────────────────────────────────────────────────────────────────────────

def _event_adjustment(direction: str, events_intel: Optional[Dict]) -> Dict:
    """
    Reduce confidence when high-impact events are imminent.
    Returns {delta, warnings[], blocked(bool), size_mult}.
    """
    out = {"delta": 0.0, "warnings": [], "blocked": False, "size_mult": 1.0}
    if not events_intel:
        return out

    risk = events_intel.get("risk_assessment", {}) or {}
    risk_score = float(risk.get("risk_score", 50) or 50)
    advisories = events_intel.get("trading_advisories", {}) or {}
    pos = advisories.get("position_recommendations", {}) or {}
    out["size_mult"] = float(pos.get("size_multiplier", advisories.get("size_multiplier", 1.0)) or 1.0)

    for ev in events_intel.get("events_today", []) or []:
        mins = float(ev.get("minutes_until", 999) or 999)
        impact = float(ev.get("impact", 0) or 0)
        ename = ev.get("event", "Event")
        if mins < 30 and impact >= 200:
            out["blocked"] = True
            out["warnings"].append(f"🛑 {ename} in {int(mins)}m (±{int(impact)} pts) — do NOT enter, exit open trades")
        elif mins < 60 and impact >= 200:
            out["delta"] -= 25
            out["warnings"].append(f"⚠️ {ename} in {int(mins)}m (±{int(impact)} pts) — size down / exit by {int(mins-15)}m")
        elif mins < 120 and impact >= 150:
            out["delta"] -= 12
            out["warnings"].append(f"⏳ {ename} in {int(mins)}m — keep size light, plan early exit")

    if risk_score >= 75:
        out["delta"] -= 15
        out["warnings"].append(f"⚠️ Market event-risk HIGH ({int(risk_score)}/100) — reduce exposure")
    elif risk_score >= 60:
        out["delta"] -= 7

    if advisories.get("can_trade") is False:
        out["blocked"] = True
        out["warnings"].append("🛑 Event layer flags NO-TRADE conditions right now")

    return out


def _macro_adjustment(direction: str, macro_intel: Optional[Dict]) -> Dict:
    """Nudge confidence when macro/global regime aligns or conflicts with direction."""
    out = {"delta": 0.0, "notes": []}
    if not macro_intel:
        return out

    score = float(macro_intel.get("macro_score", 0) or 0)        # roughly -20..+20
    regime = (macro_intel.get("market_regime") or "").lower()
    bull = direction == "CALL"

    aligned = (bull and score > 3) or (not bull and score < -3)
    against = (bull and score < -3) or (not bull and score > 3)

    if aligned:
        out["delta"] += 5
        out["notes"].append(f"Macro tailwind (score {score:+.0f}, {regime or 'regime'})")
    elif against:
        out["delta"] -= 8
        out["notes"].append(f"Macro headwind (score {score:+.0f}) — fighting global flow")
    else:
        out["notes"].append(f"Macro neutral (score {score:+.0f})")

    if macro_intel.get("geo_alert"):
        out["delta"] -= 4
        out["notes"].append(macro_intel["geo_alert"][:70])

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Position sizing
# ─────────────────────────────────────────────────────────────────────────────

def _position_size(entry_mid: float, prem_sl: float, lot_size: int,
                   account_size: float, risk_pct: float, size_mult: float) -> Dict:
    """Lots to buy so that hitting premium-SL loses ≈ risk_pct of account."""
    risk_per_lot = max((entry_mid - prem_sl) * lot_size, 1)
    max_risk = account_size * (risk_pct / 100.0)
    raw_lots = max_risk / risk_per_lot
    lots = max(0, int(math.floor(raw_lots * max(size_mult, 0.0))))
    capital = lots * entry_mid * lot_size
    return {
        "lots": lots,
        "units": lots * lot_size,
        "risk_per_lot": round(risk_per_lot),
        "capital_required": round(capital),
        "max_loss": round(lots * risk_per_lot),
        "size_mult": size_mult,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evaluate one index
# ─────────────────────────────────────────────────────────────────────────────

_ACTIONABLE = {"HIGH_CONVICTION", "MODERATE"}


def evaluate_index(cfg: Dict, events_intel: Optional[Dict],
                   macro_intel: Optional[Dict],
                   account_size: float, risk_pct: float) -> Optional[Dict]:
    """
    Run the engine for one index and enrich with overlays.
    `cfg` keys: name, df, ltp, vix, orb, pivots, live_chain, global_score,
                step, lot_size, expiry_label, expiry_date_str, fii_dii, breadth
    Returns an enriched evaluation dict (always non-None unless engine missing).
    """
    if not _ENGINE_OK:
        return None

    try:
        rec = generate_recommendation(
            name=cfg["name"], df=cfg["df"], ltp=cfg["ltp"], vix=cfg["vix"],
            orb=cfg.get("orb", {}), pivots=cfg.get("pivots", {}),
            live_chain=cfg.get("live_chain", {}), global_score=cfg.get("global_score", 0),
            step=cfg.get("step", 50), lot_size=cfg.get("lot_size", 75),
            expiry_label=cfg.get("expiry_label", ""),
            expiry_date_str=cfg.get("expiry_date_str", ""),
            fii_dii=cfg.get("fii_dii", {}), breadth=cfg.get("breadth", {}),
        )
    except Exception as e:                                       # pragma: no cover
        log.error(f"engine failed for {cfg.get('name')}: {e}")
        return None

    status = rec.get("status", "AVOID")
    base_conf = float(rec.get("confidence", 0) or 0)
    direction = rec.get("direction", "")

    # Non-actionable (AVOID / WATCHLIST) — keep for context but flag
    if status not in _ACTIONABLE or not direction:
        return {
            "index": cfg["name"],
            "actionable": False,
            "status": status,
            "reason": rec.get("reason") or rec.get("avoid_note") or "No confirmed setup",
            "base_confidence": base_conf,
            "adj_confidence": base_conf,
            "direction": direction,
            "raw": rec,
        }

    ev = _event_adjustment(direction, events_intel)
    mc = _macro_adjustment(direction, macro_intel)
    adj_conf = max(5.0, min(97.0, base_conf + ev["delta"] + mc["delta"]))

    entry_mid = float(rec.get("entry_prem_mid", 0) or 0)
    prem_sl = float(rec.get("prem_sl", 0) or 0)
    lot_size = int(rec.get("lot_size", cfg.get("lot_size", 75)))
    sizing = _position_size(entry_mid, prem_sl, lot_size, account_size, risk_pct, ev["size_mult"])

    opt_type = "CE" if direction == "CALL" else "PE"

    return {
        "index": cfg["name"],
        "actionable": not ev["blocked"],
        "blocked_by_event": ev["blocked"],
        "status": status,
        "direction": direction,
        "option_type": opt_type,
        "strike": rec.get("strike"),
        "strike_label": rec.get("strike_label", ""),
        "expiry": rec.get("expiry_label", ""),
        "base_confidence": round(base_conf),
        "adj_confidence": round(adj_conf),
        "conviction": _conviction_label(adj_conf),
        "premium": entry_mid,
        "entry_low": rec.get("entry_prem_low"),
        "entry_high": rec.get("entry_prem_high"),
        "sl": prem_sl,
        "sl_pct": rec.get("prem_sl_pct"),
        "t1": rec.get("prem_t1"), "t1_pct": rec.get("prem_t1_pct"),
        "t2": rec.get("prem_t2"), "t2_pct": rec.get("prem_t2_pct"),
        "t3": rec.get("prem_t3"), "t3_pct": rec.get("prem_t3_pct"),
        "idx_sl_label": rec.get("idx_sl_label"),
        "idx_t1_label": rec.get("idx_t1_label"),
        "idx_t2_label": rec.get("idx_t2_label"),
        "rr": rec.get("rr_ratio"),
        "max_hold": rec.get("max_hold", ""),
        "exits": rec.get("exits", []),
        "reasons": rec.get("reasons", []),
        "invalidation": rec.get("idx_sl_label", ""),
        "lot_size": lot_size,
        "sizing": sizing,
        "event_warnings": ev["warnings"],
        "macro_notes": mc["notes"],
        "pcr": rec.get("pcr_data", {}),
        "max_pain": rec.get("max_pain"),
        "raw": rec,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build the single decision
# ─────────────────────────────────────────────────────────────────────────────

def build_trade_decision(indices: List[Dict],
                         events_intel: Optional[Dict] = None,
                         macro_intel: Optional[Dict] = None,
                         account_size: float = 100000,
                         risk_pct: float = 1.0) -> Dict:
    """
    Top-level entry point. Evaluate every index, pick the best actionable setup,
    and return the decision-first object that drives the UI.
    """
    now_str = datetime.now(IST).strftime("%H:%M:%S IST")

    if not _ENGINE_OK:
        return {
            "verdict": "WAIT", "traffic_light": "red",
            "headline_action": "ENGINE UNAVAILABLE",
            "no_trade_reason": "Trade engine module failed to load.",
            "best": None, "alternatives": [], "as_of": now_str,
        }

    evals = []
    for cfg in indices:
        ev = evaluate_index(cfg, events_intel, macro_intel, account_size, risk_pct)
        if ev:
            evals.append(ev)

    actionable = [e for e in evals if e.get("actionable") and e.get("direction")]
    actionable.sort(key=lambda e: e["adj_confidence"], reverse=True)

    # Global event block (e.g. major announcement < 30 min away)
    any_blocked = any(e.get("blocked_by_event") for e in evals)
    block_warnings = []
    for e in evals:
        block_warnings.extend(e.get("event_warnings", []))
    block_warnings = list(dict.fromkeys(block_warnings))   # de-dup, keep order

    # ── No actionable setup → confident WAIT ─────────────────────────────────
    if not actionable or actionable[0]["adj_confidence"] < 58:
        # Build an honest reason
        if any_blocked:
            reason = "Major event risk imminent — preserve capital, do not enter fresh positions."
        elif actionable:
            top = actionable[0]
            reason = (f"Best available setup ({top['index']} {top['option_type']}) is only "
                      f"{top['adj_confidence']}% — below the 58% actionable threshold. "
                      f"No high-probability edge right now. Wait for confirmation.")
        else:
            why = "; ".join(f"{e['index']}: {e.get('reason','no setup')}" for e in evals[:3]) or "Indicators conflicting across indices."
            reason = f"No confirmed directional edge. {why}"
        return {
            "verdict": "WAIT",
            "traffic_light": "red",
            "headline_action": "WAIT — NO TRADE",
            "no_trade_reason": reason,
            "best": None,
            "alternatives": [
                {"index": e["index"], "direction": e.get("direction", "—"),
                 "confidence": e.get("adj_confidence", 0),
                 "status": e.get("status", "")} for e in evals
            ],
            "event_warnings": block_warnings,
            "macro_context": macro_intel.get("summary", "") if macro_intel else "",
            "all_evaluations": evals,
            "as_of": now_str,
        }

    best = actionable[0]
    conf = best["adj_confidence"]
    light = _traffic_light(conf, True, best.get("blocked_by_event", False))

    headline = f"BUY {best['index']} {best['strike']} {best['option_type']}"

    return {
        "verdict": "TRADE",
        "traffic_light": light,
        "headline_action": headline,
        "best": best,
        "alternatives": [
            {"index": e["index"], "direction": e["direction"],
             "option_type": e.get("option_type", ""),
             "strike": e.get("strike"),
             "confidence": e["adj_confidence"],
             "conviction": e.get("conviction", "")}
            for e in actionable[1:]
        ],
        "event_warnings": block_warnings,
        "macro_context": macro_intel.get("summary", "") if macro_intel else "",
        "all_evaluations": evals,
        "as_of": now_str,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Text rendering for the AI Expert prompt
# ─────────────────────────────────────────────────────────────────────────────

def format_decision_for_ai(decision: Optional[Dict]) -> str:
    """
    Render the decision object as a compact text block to inject at the TOP of
    the AI Expert's market context, so the chatbot anchors to the same verdict
    the dashboard shows the user. One brain, two surfaces.
    """
    if not decision:
        return ""

    L = ["🎯 DASHBOARD ENGINE VERDICT (the house view — align with this)"]
    light = decision.get("traffic_light", "red").upper()
    L.append(f"  Signal: {light}  |  Verdict: {decision.get('verdict','WAIT')}  "
             f"|  Action: {decision.get('headline_action','WAIT — NO TRADE')}")
    L.append(f"  As of: {decision.get('as_of','')}")

    best = decision.get("best")
    if decision.get("verdict") == "TRADE" and best:
        sz = best.get("sizing", {})
        L.append(f"  BEST TRADE: {best['index']} {best['strike']} {best['option_type']} "
                 f"({best.get('strike_label','')}) exp {best.get('expiry','')}")
        L.append(f"    Confidence {best['adj_confidence']}% (base {best['base_confidence']}%) "
                 f"· {best['conviction']} conviction")
        L.append(f"    Entry ₹{best.get('entry_low','?')}–₹{best.get('entry_high','?')} "
                 f"| SL ₹{best.get('sl','?')} | T1 ₹{best.get('t1','?')} "
                 f"T2 ₹{best.get('t2','?')} T3 ₹{best.get('t3','?')} | R:R 1:{best.get('rr','?')}")
        L.append(f"    Position {sz.get('lots',0)} lot(s) / {sz.get('units',0)} units "
                 f"· capital ₹{sz.get('capital_required',0):,} · max loss ₹{sz.get('max_loss',0):,}")
        L.append(f"    Max hold {best.get('max_hold','—')} | "
                 f"Invalidate if index crosses {best.get('invalidation','SL')}")
        if best.get("reasons"):
            L.append("    Why: " + "; ".join(best["reasons"][:4]))
    else:
        L.append(f"  NO-TRADE REASON: {decision.get('no_trade_reason','No edge right now.')}")

    alts = decision.get("alternatives", [])
    if alts:
        a_str = ", ".join(
            f"{a['index']} {a.get('strike','')}{a.get('option_type','')} {a.get('confidence',0)}%"
            for a in alts[:3] if a.get('strike'))
        if a_str:
            L.append(f"  Other setups: {a_str}")

    warns = decision.get("event_warnings", [])
    if warns:
        L.append("  Event flags: " + " | ".join(warns[:3]))

    L.append("")
    return "\n".join(L)
