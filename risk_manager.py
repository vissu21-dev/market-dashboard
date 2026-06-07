"""
Professional Risk Management & Position Sizing Engine
Handles position sizing, P&L tracking, trade lifecycle management, and margin calculations.
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Dict, Optional, Tuple, List
import json
import logging

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# INSTRUMENT CONFIG & LOT SIZES
# ─────────────────────────────────────────────────────────────────────────────

INSTRUMENT_CONFIG = {
    "NIFTY": {
        "lot_size": 75,
        "tick_size": 1,
        "multiplier": 1,
        "margin_percent": 5,  # Approx margin required as % of contract value
        "description": "NIFTY 50 Index Options"
    },
    "BANKNIFTY": {
        "lot_size": 40,
        "tick_size": 1,
        "multiplier": 1,
        "margin_percent": 7,
        "description": "BANK NIFTY Index Options"
    },
    "FINNIFTY": {
        "lot_size": 30,
        "tick_size": 1,
        "multiplier": 1,
        "margin_percent": 8,
        "description": "FIN NIFTY Index Options"
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# POSITION SIZING
# ─────────────────────────────────────────────────────────────────────────────

def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    sl_price: float,
    instrument: str = "NIFTY"
) -> Dict:
    """
    Calculate optimal position size based on account size and risk tolerance.

    Args:
        account_size: Total trading account in INR
        risk_percent: Percent of account willing to risk per trade (typically 1-2%)
        entry_price: Entry price of option (premium)
        sl_price: Stop loss price (premium)
        instrument: NIFTY, BANKNIFTY, or FINNIFTY

    Returns:
        Dict with units, lots, risk_amount, max_loss_inr, etc.
    """
    config = INSTRUMENT_CONFIG.get(instrument, INSTRUMENT_CONFIG["NIFTY"])
    lot_size = config["lot_size"]

    # Calculate account risk in INR
    account_risk_inr = account_size * (risk_percent / 100)

    # Risk per unit of premium (one lot)
    risk_per_unit = abs(entry_price - sl_price)

    if risk_per_unit == 0:
        return {
            "status": "ERROR",
            "message": "Entry and SL cannot be same — risk cannot be zero",
            "units": 0,
            "lots": 0,
        }

    # Units (how many option contracts)
    units_needed = account_risk_inr / risk_per_unit

    # Cap at reasonable max (1-3 lots for intraday)
    max_units = lot_size * 3
    units = min(int(units_needed), max_units)

    # Round down to nearest lot
    lots = max(1, units // lot_size)
    units = lots * lot_size

    # Calculate actual risk
    max_loss_inr = units * risk_per_unit
    max_loss_pct = (max_loss_inr / account_size) * 100 if account_size > 0 else 0

    return {
        "status": "OK",
        "instrument": instrument,
        "account_size": account_size,
        "risk_percent": risk_percent,
        "account_risk_inr": account_risk_inr,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "risk_per_unit": risk_per_unit,
        "units": units,
        "lots": lots,
        "max_loss_inr": max_loss_inr,
        "max_loss_pct": max_loss_pct,
        "lot_size": lot_size,
    }


def calculate_margin_requirement(
    entry_premium: float,
    quantity: int,
    instrument: str = "NIFTY"
) -> float:
    """
    Estimate margin required for the position.
    Returns margin in INR.
    """
    config = INSTRUMENT_CONFIG.get(instrument, INSTRUMENT_CONFIG["NIFTY"])
    lot_size = config["lot_size"]
    margin_percent = config["margin_percent"] / 100

    # Rough estimate: margin = premium × quantity × margin_percent
    # (Real margin depends on Greeks and broker rules)
    margin = entry_premium * quantity * margin_percent

    return round(margin, 0)


def can_afford_trade(
    account_balance: float,
    position_size: int,
    entry_premium: float,
    instrument: str = "NIFTY"
) -> Tuple[bool, str]:
    """
    Check if account has enough balance for the trade.

    Returns:
        (can_afford: bool, message: str)
    """
    margin = calculate_margin_requirement(entry_premium, position_size, instrument)

    if account_balance < margin:
        return (
            False,
            f"Insufficient margin. Need ₹{margin:,.0f} but have ₹{account_balance:,.0f}"
        )

    if account_balance < margin * 1.5:
        return (
            True,
            f"⚠️ Tight margin. Only ₹{account_balance - margin:,.0f} buffer remaining after this trade"
        )

    return (True, "✅ Sufficient balance and margin")


# ─────────────────────────────────────────────────────────────────────────────
# P&L CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

def calculate_pnl(
    entry_price: float,
    current_price: float,
    quantity: int,
    instrument: str = "NIFTY",
    direction: str = "CALL"
) -> Dict:
    """
    Calculate current P&L for a position.

    Args:
        entry_price: Entry premium
        current_price: Current option premium
        quantity: Number of contracts
        instrument: NIFTY, BANKNIFTY, or FINNIFTY
        direction: CALL or PUT

    Returns:
        Dict with pnl_inr, pnl_pct, break_even, etc.
    """
    price_diff = current_price - entry_price
    pnl_inr = price_diff * quantity
    pnl_pct = (price_diff / entry_price * 100) if entry_price > 0 else 0

    break_even = entry_price

    return {
        "entry_price": entry_price,
        "current_price": current_price,
        "quantity": quantity,
        "price_diff": price_diff,
        "pnl_inr": pnl_inr,
        "pnl_pct": round(pnl_pct, 2),
        "break_even": break_even,
        "winning": pnl_inr > 0,
    }


def calculate_theta_decay(
    entry_premium: float,
    current_premium: float,
    time_elapsed_minutes: int,
    quantity: int
) -> Dict:
    """
    Estimate theta decay (time decay) impact on position.

    Returns:
        Dict with decay_per_minute, total_decay, etc.
    """
    if time_elapsed_minutes == 0:
        return {"decay_per_minute": 0, "total_decay": 0, "decay_pct": 0}

    total_decay = (current_premium - entry_premium) * quantity
    decay_per_minute = total_decay / time_elapsed_minutes if time_elapsed_minutes > 0 else 0
    decay_pct = ((current_premium - entry_premium) / entry_premium * 100) if entry_premium > 0 else 0

    return {
        "entry_premium": entry_premium,
        "current_premium": current_premium,
        "time_elapsed_minutes": time_elapsed_minutes,
        "decay_per_minute": round(decay_per_minute, 2),
        "total_decay_inr": round(total_decay, 2),
        "decay_pct": round(decay_pct, 2),
        "daily_extrapolation": round(decay_per_minute * 390, 2),  # 390 mins in trading day
    }


# ─────────────────────────────────────────────────────────────────────────────
# TRADE LIFECYCLE & STATE TRACKING
# ─────────────────────────────────────────────────────────────────────────────

class TradeState:
    """Represents a single active trade."""

    STATUSES = ["WATCHLIST", "ENTRY_ZONE", "ACTIVE", "CLOSED", "CANCELLED"]

    def __init__(self, trade_id: str, index: str, direction: str, strike: int,
                 entry_price: float, sl_price: float, targets: List[float],
                 quantity: int, confidence: int):
        self.trade_id = trade_id
        self.index = index
        self.direction = direction
        self.strike = strike
        self.entry_price = entry_price
        self.sl_price = sl_price
        self.targets = targets  # [T1, T2, T3]
        self.quantity = quantity
        self.confidence = confidence

        # Lifecycle
        self.status = "WATCHLIST"
        self.entry_time = None
        self.current_price = entry_price
        self.current_pnl_inr = 0
        self.current_pnl_pct = 0
        self.max_pnl_reached = 0
        self.targets_hit = []  # [T1, T2, T3] → hit status
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.time_in_trade_minutes = 0

    def to_dict(self) -> Dict:
        """Serialize for storage/display."""
        return {
            "trade_id": self.trade_id,
            "index": self.index,
            "direction": self.direction,
            "strike": self.strike,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "sl_price": self.sl_price,
            "targets": self.targets,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "status": self.status,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "current_pnl_inr": round(self.current_pnl_inr, 2),
            "current_pnl_pct": round(self.current_pnl_pct, 2),
            "max_pnl_reached": round(self.max_pnl_reached, 2),
            "targets_hit": self.targets_hit,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "time_in_trade_minutes": self.time_in_trade_minutes,
        }

    def update_price(self, new_price: float):
        """Update current price and recalculate P&L."""
        self.current_price = new_price
        self.current_pnl_inr = (new_price - self.entry_price) * self.quantity
        self.current_pnl_pct = (
            (new_price - self.entry_price) / self.entry_price * 100
        ) if self.entry_price > 0 else 0

        # Track max profit
        if self.current_pnl_inr > self.max_pnl_reached:
            self.max_pnl_reached = self.current_pnl_inr

    def check_target_hits(self) -> List[int]:
        """Check which targets have been hit. Returns [0,1,2] or empty list."""
        hits = []
        for i, target in enumerate(self.targets):
            if i not in self.targets_hit:  # Not already hit
                if self.direction == "CALL" and self.current_price >= target:
                    hits.append(i)
                    self.targets_hit.append(i)
                elif self.direction == "PUT" and self.current_price <= target:
                    hits.append(i)
                    self.targets_hit.append(i)
        return hits

    def check_sl_hit(self) -> bool:
        """Check if stop loss has been hit."""
        if self.direction == "CALL":
            return self.current_price <= self.sl_price
        else:
            return self.current_price >= self.sl_price

    def activate(self):
        """Mark trade as ACTIVE (entry confirmed)."""
        self.status = "ACTIVE"
        self.entry_time = datetime.now(IST)

    def close(self, exit_price: float, exit_reason: str):
        """Close the trade."""
        self.status = "CLOSED"
        self.exit_price = exit_price
        self.exit_time = datetime.now(IST)
        self.exit_reason = exit_reason

        if self.entry_time:
            self.time_in_trade_minutes = int(
                (self.exit_time - self.entry_time).total_seconds() / 60
            )

        self.update_price(exit_price)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def calculate_portfolio_exposure(
    active_trades: List[TradeState],
    account_size: float
) -> Dict:
    """
    Calculate total portfolio exposure, max drawdown risk, Greeks exposure.
    """
    total_pnl = sum(t.current_pnl_inr for t in active_trades)
    total_risk = sum(
        abs(t.entry_price - t.sl_price) * t.quantity for t in active_trades
    )

    call_exposure = sum(
        t.current_price * t.quantity for t in active_trades if t.direction == "CALL"
    )
    put_exposure = sum(
        t.current_price * t.quantity for t in active_trades if t.direction == "PUT"
    )

    net_delta = sum(
        t.quantity for t in active_trades if t.direction == "CALL"
    ) - sum(
        t.quantity for t in active_trades if t.direction == "PUT"
    )

    drawdown_pct = (total_risk / account_size * 100) if account_size > 0 else 0

    return {
        "num_active_trades": len(active_trades),
        "total_pnl_inr": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl / account_size * 100, 2) if account_size > 0 else 0,
        "total_risk_inr": round(total_risk, 2),
        "max_drawdown_pct": round(drawdown_pct, 2),
        "call_exposure": round(call_exposure, 2),
        "put_exposure": round(put_exposure, 2),
        "net_delta": net_delta,
        "status": "⚠️ CAUTION" if drawdown_pct > 5 else "✅ SAFE" if drawdown_pct <= 2 else "⚡ MODERATE",
    }


def suggest_position_allocation(
    account_size: float,
    daily_loss_limit: float = 0.05,
    max_concurrent_trades: int = 3
) -> Dict:
    """
    Suggest optimal allocation for trading account.

    Args:
        account_size: Total account in INR
        daily_loss_limit: Max loss per day as % (default 5%)
        max_concurrent_trades: Max concurrent active trades

    Returns:
        Dict with recommended allocation
    """
    daily_loss_budget = account_size * daily_loss_limit
    risk_per_trade = daily_loss_budget / max(max_concurrent_trades, 1)

    # Allocate to different instruments
    nifty_alloc = risk_per_trade * 0.5
    banknifty_alloc = risk_per_trade * 0.3
    finnifty_alloc = risk_per_trade * 0.2

    return {
        "account_size": account_size,
        "daily_loss_limit_inr": round(daily_loss_budget, 2),
        "max_concurrent_trades": max_concurrent_trades,
        "risk_per_trade": round(risk_per_trade, 2),
        "allocation": {
            "NIFTY": round(nifty_alloc, 2),
            "BANKNIFTY": round(banknifty_alloc, 2),
            "FINNIFTY": round(finnifty_alloc, 2),
        },
        "cash_buffer_required": round(account_size * 0.30, 2),  # Keep 30% cash
        "recommendations": [
            "Never risk more than 1-2% per trade",
            "Keep 3 max concurrent trades at a time",
            "Always use stop loss",
            "Scale profits (50% at T1, 30% at T2, 20% at T3)",
            "Exit ALL by 3:00 PM — no overnight holds",
            "If down 5% for the day, stop trading",
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# HARD STOP LOSSES & GUARDRAILS
# ─────────────────────────────────────────────────────────────────────────────

def check_trading_guardrails(
    daily_pnl: float,
    account_size: float,
    num_active_trades: int,
    total_daily_risk: float,
    vix: float = 15
) -> Dict:
    """
    Check if we've hit hard stop loss limits and should stop trading.

    Returns:
        Dict with guardrail_status, warnings, should_stop_trading, etc.
    """
    daily_loss_pct = (daily_pnl / account_size * 100) if account_size > 0 else 0
    daily_risk_pct = (total_daily_risk / account_size * 100) if account_size > 0 else 0

    warnings = []
    should_stop = False

    # Hard limit 1: Daily loss exceeds 5%
    if daily_loss_pct < -5:
        warnings.append("🛑 HARD STOP: Daily loss exceeds 5% — STOP ALL TRADING")
        should_stop = True
    elif daily_loss_pct < -3:
        warnings.append("⚠️ Daily loss approaching 5% limit — be cautious")

    # Hard limit 2: Risk exposure >10%
    if daily_risk_pct > 10:
        warnings.append("🛑 Total position risk exceeds 10% of account")
        should_stop = True
    elif daily_risk_pct > 7:
        warnings.append("⚠️ Position risk elevated — reduce size on next trade")

    # Hard limit 3: Too many concurrent trades
    if num_active_trades > 5:
        warnings.append("🛑 Too many concurrent trades (max 3) — close oldest first")
        should_stop = True
    elif num_active_trades > 3:
        warnings.append("⚠️ Approaching max concurrent trades — be selective")

    # Soft warning: VIX elevated
    if vix > 25:
        warnings.append(f"⚠️ VIX {vix:.1f} — very high, reduce size and use only ATM")
    elif vix > 20:
        warnings.append(f"⚠️ VIX {vix:.1f} — elevated, use ATM only")

    return {
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss_pct": round(daily_loss_pct, 2),
        "daily_risk_pct": round(daily_risk_pct, 2),
        "num_active_trades": num_active_trades,
        "vix": vix,
        "warnings": warnings,
        "should_stop_trading": should_stop,
        "status": "🛑 STOP" if should_stop else ("⚠️ CAUTION" if warnings else "✅ OK"),
    }
