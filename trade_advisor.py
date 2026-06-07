"""
Professional Trade Recommendation Advisor
Wraps trade_engine.py and provides institutional-grade trade recommendations
with multi-strike options, entry zone analysis, and confidence scoring.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Tuple
import logging
from risk_manager import calculate_position_size, INSTRUMENT_CONFIG

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────────────────────────────────────
# PROFESSIONAL TRADE RECOMMENDATION OBJECT
# ─────────────────────────────────────────────────────────────────────────────

class ProfessionalTrade:
    """
    Represents a complete professional trade recommendation with all details
    needed for execution and monitoring.
    """

    def __init__(
        self,
        index: str,
        direction: str,
        trade_id: str,
        timestamp: datetime,
        strike: int,
        expiry: str,
    ):
        self.index = index
        self.direction = direction  # CALL or PUT
        self.trade_id = trade_id
        self.timestamp = timestamp
        self.strike = strike
        self.expiry = expiry

        # Entry
        self.entry_price_low = 0
        self.entry_price_high = 0
        self.entry_price_mid = 0
        self.entry_zone_reasoning = ""

        # Risk Management
        self.stop_loss = 0
        self.ideal_sl_index_level = 0
        self.stop_loss_pct = 0
        self.max_loss_inr = 0

        # Targets
        self.target_1 = 0
        self.target_2 = 0
        self.target_3 = 0
        self.target_1_index = 0
        self.target_2_index = 0
        self.target_3_index = 0

        # Time & Position Sizing
        self.max_holding_minutes = 60
        self.risk_to_reward = 0
        self.lot_size = 1
        self.max_gain_t1 = 0
        self.max_gain_t2 = 0
        self.max_gain_t3 = 0

        # Confidence & Status
        self.confidence_pct = 0
        self.conviction_level = "LOW"  # AVOID / LOW / MODERATE / HIGH
        self.confidence_breakdown = {}

        # Exit Strategy
        self.exit_conditions = []

        # Market Snapshot
        self.market_snapshot = {}

        # Invalidation Rules
        self.invalid_if = []

    def to_dict(self) -> Dict:
        """Serialize for storage/display."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "index": self.index,
            "direction": self.direction,
            "strike": self.strike,
            "expiry": self.expiry,
            "trade_id": self.trade_id,
            # Entry
            "entry_price_low": round(self.entry_price_low, 2),
            "entry_price_high": round(self.entry_price_high, 2),
            "entry_price_mid": round(self.entry_price_mid, 2),
            "entry_zone_reasoning": self.entry_zone_reasoning,
            # Risk
            "stop_loss": round(self.stop_loss, 2),
            "ideal_sl_index_level": round(self.ideal_sl_index_level, 2),
            "stop_loss_pct": round(self.stop_loss_pct, 2),
            "max_loss_inr": round(self.max_loss_inr, 2),
            # Targets
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "target_3": round(self.target_3, 2),
            "target_1_index": round(self.target_1_index, 2),
            "target_2_index": round(self.target_2_index, 2),
            "target_3_index": round(self.target_3_index, 2),
            # Time & Sizing
            "max_holding_minutes": self.max_holding_minutes,
            "risk_to_reward": round(self.risk_to_reward, 2),
            "lot_size": self.lot_size,
            "max_gain_t1": round(self.max_gain_t1, 2),
            "max_gain_t2": round(self.max_gain_t2, 2),
            "max_gain_t3": round(self.max_gain_t3, 2),
            # Confidence
            "confidence_pct": self.confidence_pct,
            "conviction_level": self.conviction_level,
            "confidence_breakdown": self.confidence_breakdown,
            # Exit & Invalidation
            "exit_conditions": self.exit_conditions,
            "invalid_if": self.invalid_if,
            "market_snapshot": self.market_snapshot,
        }

    def is_valid(self) -> Tuple[bool, str]:
        """Check if trade is still valid given current market conditions."""
        if self.direction not in ["CALL", "PUT"]:
            return False, "Invalid direction"
        if self.stop_loss <= 0 or self.target_1 <= 0:
            return False, "SL or targets not set"
        if self.entry_price_mid <= 0:
            return False, "Entry price not set"
        return True, "Trade is valid"


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY ZONE CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

def analyze_entry_zones(
    live_chain: Dict,
    ltp: float,
    direction: str,
    step: int = 50,
    pcr: float = 1.0,
    volatility_percentile: int = 50
) -> Dict:
    """
    Analyze entry zones for both ATM and OTM1 strikes.
    Returns pricing and affordability analysis for each zone.

    Returns:
        Dict with ATM and OTM1 zone analysis
    """
    atm = round(int(round(ltp / step) * step))
    otm1 = atm + (step if direction == "CALL" else -step)

    zones = {}

    for strike in [atm, otm1]:
        chain_data = live_chain.get(strike, {})
        key = "ce" if direction == "CALL" else "pe"

        premium = float(chain_data.get(key, 0) or 0)
        iv = float(chain_data.get(f"{key}_iv", 0) or 0)
        oi = float(chain_data.get(f"{key}_oi", 0) or 0)
        volume = float(chain_data.get(f"{key}_volume", 0) or 0)

        # Entry zone: ±5% of premium
        zone_low = int(premium * 0.95) if premium > 0 else 0
        zone_high = int(premium * 1.05) if premium > 0 else 0

        # Affordability by lot size
        affordability = {}
        for lot_size in [30, 40, 75, 100]:
            budget_needed = premium * lot_size
            affordability[f"{lot_size}_lot"] = {
                "budget_needed": round(budget_needed, 2),
                "affordable": True
            }

        zone_label = "ATM (Lower risk, lower reward)" if strike == atm else "OTM1 (Better R:R)"

        zones[strike] = {
            "strike": strike,
            "label": zone_label,
            "premium_mid": premium,
            "premium_low": zone_low,
            "premium_high": zone_high,
            "iv": iv,
            "oi": oi,
            "volume": volume,
            "affordability": affordability,
            "liquidity_quality": "High" if oi > 500000 and volume > 100 else "Medium" if oi > 100000 else "Low",
        }

    return zones


# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE BREAKDOWN ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

def analyze_confidence_breakdown(
    trade_engine_result: Dict,
) -> Dict:
    """
    Analyze and structure the confidence breakdown from trade_engine result.
    Returns detailed breakdown by category with score and reasoning.
    """
    reasons = trade_engine_result.get("reasons", [])
    bull_score = trade_engine_result.get("score_bull", 0)
    bear_score = trade_engine_result.get("score_bear", 0)
    net_score = bull_score - bear_score
    confidence = trade_engine_result.get("confidence", 50)

    # Categorize reasons
    technical_reasons = [r for r in reasons if any(x in r for x in ["ORB", "EMA", "VWAP", "RSI", "MACD", "Volume", "OBV", "Supertrend"])]
    options_reasons = [r for r in reasons if any(x in r for x in ["PCR", "OI", "max pain"])]
    macro_reasons = [r for r in reasons if any(x in r for x in ["FII", "DII", "breadth", "Global", "VIX"])]
    structure_reasons = [r for r in reasons if any(x in r for x in ["price", "Pivot", "wall", "Max pain"])]

    # Calculate subscores
    tech_score = len([r for r in technical_reasons if "✅" in r]) / max(len(technical_reasons), 1) * 10
    opt_score = len([r for r in options_reasons if "✅" in r]) / max(len(options_reasons), 1) * 10
    macro_score = len([r for r in macro_reasons if "✅" in r]) / max(len(macro_reasons), 1) * 10
    struct_score = len([r for r in structure_reasons if "✅" in r]) / max(len(structure_reasons), 1) * 10

    breakdown = {
        "overall": {
            "confidence_pct": confidence,
            "net_signal_strength": net_score,
            "bull_signals": bull_score,
            "bear_signals": bear_score,
        },
        "technical": {
            "score": round(tech_score, 1),
            "weight": 30,
            "reasons": technical_reasons[:3],  # Top 3
        },
        "options_flow": {
            "score": round(opt_score, 1),
            "weight": 25,
            "reasons": options_reasons[:3],
        },
        "macro_context": {
            "score": round(macro_score, 1),
            "weight": 20,
            "reasons": macro_reasons[:3],
        },
        "market_structure": {
            "score": round(struct_score, 1),
            "weight": 25,
            "reasons": structure_reasons[:3],
        },
    }

    return breakdown


# ─────────────────────────────────────────────────────────────────────────────
# INVALIDATION TRIGGER ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def identify_invalidation_triggers(
    direction: str,
    entry_level: float,
    orb_high: Optional[float],
    orb_low: Optional[float],
    pcr: float,
    vix: float,
    rsi: float
) -> List[str]:
    """
    Identify specific conditions that would invalidate the trade setup.
    Returns list of invalidation triggers to watch for.
    """
    triggers = []

    if direction == "CALL":
        if orb_low:
            triggers.append(f"Closes below ORB low ({orb_low:,.0f}) — structural breakdown")
        triggers.append(f"Closes below {entry_level * 0.995:,.0f} (2-15m chart) — loses momentum")
        if rsi > 65:
            triggers.append(f"RSI above 70 and rolling over — momentum loss")
    else:  # PUT
        if orb_high:
            triggers.append(f"Closes above ORB high ({orb_high:,.0f}) — structural breakdown")
        triggers.append(f"Closes above {entry_level * 1.005:,.0f} (2-15m chart) — loses momentum")
        if rsi < 35:
            triggers.append(f"RSI below 30 and rolling over — momentum loss")

    if pcr > 1.3:
        triggers.append(f"PCR spikes above 1.3 (extreme) — contrarian signal fading")

    if vix > 20:
        triggers.append(f"VIX spikes >20 (macro shock) — fast exit if hit")

    triggers.append("Premium drops >60% from entry without hitting target (bleeding out)")

    return triggers


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RECOMMENDATION WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

def generate_professional_trade_recommendation(
    trade_engine_result: Dict,
    live_chain: Dict,
    ltp: float,
    account_size: float = 100000,
    risk_percent: float = 1.0,
    instrument: str = "NIFTY",
    step: int = 50,
) -> Optional[ProfessionalTrade]:
    """
    Convert trade_engine output into a professional ProfessionalTrade object.
    This is the main wrapper that enhances trade_engine recommendations.

    Args:
        trade_engine_result: Dict from generate_recommendation()
        live_chain: Options chain dict
        ltp: Current index price
        account_size: Trading account size for position sizing
        risk_percent: Risk per trade as % of account
        instrument: NIFTY, BANKNIFTY, FINNIFTY
        step: Strike interval (50 for NIFTY)

    Returns:
        ProfessionalTrade object or None if AVOID status
    """

    # Check if trade_engine recommended AVOID
    status = trade_engine_result.get("status", "AVOID")
    if status in ["AVOID"]:
        return None

    direction = trade_engine_result.get("direction", "CALL")
    confidence = int(trade_engine_result.get("confidence", 50))
    name = trade_engine_result.get("name", "INDEX")

    # Create trade object
    trade_id = f"{name}_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}_{direction}"
    trade = ProfessionalTrade(
        index=name,
        direction=direction,
        trade_id=trade_id,
        timestamp=datetime.now(IST),
        strike=int(trade_engine_result.get("strike", 0)),
        expiry=trade_engine_result.get("expiry_label", "Current"),
    )

    # ── ENTRY ZONE ANALYSIS ──────────────────────────────────────────────────
    entry_low = int(trade_engine_result.get("entry_prem_low", 0))
    entry_high = int(trade_engine_result.get("entry_prem_high", 0))
    entry_mid = int(trade_engine_result.get("entry_prem_mid", 0))

    trade.entry_price_low = entry_low
    trade.entry_price_high = entry_high
    trade.entry_price_mid = entry_mid
    trade.entry_zone_reasoning = (
        f"Premium {entry_mid} Rs at current IV (±5% = {entry_low}-{entry_high} zone). "
        f"Enter on dips towards {entry_low}, avoid above {entry_high}."
    )

    # ── RISK MANAGEMENT ──────────────────────────────────────────────────────
    trade.stop_loss = int(trade_engine_result.get("prem_sl", 0))
    trade.ideal_sl_index_level = float(trade_engine_result.get("idx_sl", 0))
    trade.stop_loss_pct = int(trade_engine_result.get("prem_sl_pct", 0))

    # Calculate max loss
    risk_per_point = abs(entry_mid - trade.stop_loss)
    config = INSTRUMENT_CONFIG.get(instrument, INSTRUMENT_CONFIG["NIFTY"])
    lot_size = config["lot_size"]
    trade.max_loss_inr = risk_per_point * lot_size

    # ── TARGETS ──────────────────────────────────────────────────────────────
    trade.target_1 = int(trade_engine_result.get("prem_t1", 0))
    trade.target_2 = int(trade_engine_result.get("prem_t2", 0))
    trade.target_3 = int(trade_engine_result.get("prem_t3", 0))

    trade.target_1_index = float(trade_engine_result.get("idx_t1", 0))
    trade.target_2_index = float(trade_engine_result.get("idx_t2", 0))
    trade.target_3_index = float(trade_engine_result.get("idx_t3", 0))

    trade.max_gain_t1 = (trade.target_1 - entry_mid) * lot_size if trade.target_1 > 0 else 0
    trade.max_gain_t2 = (trade.target_2 - entry_mid) * lot_size if trade.target_2 > 0 else 0
    trade.max_gain_t3 = (trade.target_3 - entry_mid) * lot_size if trade.target_3 > 0 else 0

    # ── RISK/REWARD & POSITION SIZING ────────────────────────────────────────
    trade.risk_to_reward = trade_engine_result.get("rr_ratio", 1.0)
    trade.max_holding_minutes = 60  # Default 1 hour for intraday

    # Position sizing
    pos_size = calculate_position_size(
        account_size=account_size,
        risk_percent=risk_percent,
        entry_price=entry_mid,
        sl_price=trade.stop_loss,
        instrument=instrument,
    )
    trade.lot_size = pos_size.get("lots", 1)

    # ── CONFIDENCE & STATUS ──────────────────────────────────────────────────
    trade.confidence_pct = confidence

    if confidence >= 72:
        trade.conviction_level = "HIGH"
    elif confidence >= 58:
        trade.conviction_level = "MODERATE"
    elif confidence >= 45:
        trade.conviction_level = "LOW"
    else:
        trade.conviction_level = "AVOID"

    # Detailed breakdown
    trade.confidence_breakdown = analyze_confidence_breakdown(trade_engine_result)

    # ── EXIT CONDITIONS ──────────────────────────────────────────────────────
    exit_conds = [
        {
            "type": "target_1",
            "level": trade.target_1,
            "action": "book_50_pct",
            "description": f"Book 50% at T1 ({trade.target_1}), move SL to breakeven"
        },
        {
            "type": "target_2",
            "level": trade.target_2,
            "action": "book_30_pct",
            "description": f"Book 30% more at T2 ({trade.target_2}), trail SL"
        },
        {
            "type": "target_3",
            "level": trade.target_3,
            "action": "book_remaining",
            "description": f"Book remaining at T3 ({trade.target_3}) or 3:00 PM"
        },
        {
            "type": "stop_loss",
            "level": trade.stop_loss,
            "action": "exit_all",
            "description": f"Exit ALL if SL hit ({trade.stop_loss})"
        },
        {
            "type": "time_decay",
            "minutes": trade.max_holding_minutes,
            "action": "exit_all",
            "description": f"Exit by {trade.max_holding_minutes}min or 3:00 PM, theta eats profits"
        },
    ]
    trade.exit_conditions = exit_conds

    # ── INVALIDATION RULES ───────────────────────────────────────────────────
    trade.invalid_if = identify_invalidation_triggers(
        direction=direction,
        entry_level=ltp,
        orb_high=trade_engine_result.get("orb_high"),
        orb_low=trade_engine_result.get("orb_low"),
        pcr=trade_engine_result.get("pcr_data", {}).get("pcr", 1.0),
        vix=trade_engine_result.get("vix", 15),
        rsi=trade_engine_result.get("reasons", []),
    )

    # ── MARKET SNAPSHOT AT RECOMMENDATION TIME ───────────────────────────────
    trade.market_snapshot = {
        "index_ltp": ltp,
        "index_open": trade_engine_result.get("ltp", ltp),
        "vix": trade_engine_result.get("vix", 15),
        "fii_net": trade_engine_result.get("fii_net", 0),
        "pcr": trade_engine_result.get("pcr_data", {}).get("pcr", 1.0),
        "iv_percentile": 50,
        "breadth": trade_engine_result.get("breadth_label", "neutral"),
        "orb_high": trade_engine_result.get("orb_high"),
        "orb_low": trade_engine_result.get("orb_low"),
        "max_pain": trade_engine_result.get("max_pain"),
    }

    return trade


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-STRIKE RECOMMENDATION GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_multi_strike_recommendations(
    trade_engine_results: List[Dict],
    live_chain: Dict,
    ltp: float,
    account_size: float = 100000,
) -> Dict:
    """
    Generate recommendations for multiple strikes (ATM, OTM1, OTM2).

    Returns:
        Dict with recommendations for each strike level
    """
    recommendations = {}

    for result in trade_engine_results:
        direction = result.get("direction", "CALL")
        strike_label = result.get("strike_label", "UNKNOWN")

        trade = generate_professional_trade_recommendation(
            trade_engine_result=result,
            live_chain=live_chain,
            ltp=ltp,
            account_size=account_size,
        )

        if trade:
            recommendations[strike_label] = trade.to_dict()
        else:
            recommendations[strike_label] = None

    return recommendations
