"""
Trade Journal & Performance Analytics
SQLite-based logging of all trades for tracking, analysis, and performance feedback.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# Database file location
DB_PATH = Path(__file__).parent / "trade_journal.db"


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE INITIALIZATION & SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

def init_database():
    """Initialize SQLite database with trade journal schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Main trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            index_name TEXT,
            direction TEXT,
            strike INTEGER,
            expiry TEXT,

            entry_price REAL,
            entry_time DATETIME,
            entry_quantity INTEGER,
            confidence_pct INTEGER,
            conviction_level TEXT,

            exit_price REAL,
            exit_time DATETIME,
            exit_reason TEXT,
            exit_quantity INTEGER,

            pnl_rupees REAL,
            pnl_percent REAL,
            max_pnl_reached REAL,
            targets_hit INTEGER,

            time_in_trade_minutes INTEGER,
            market_snapshot TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Daily summary table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_trades INTEGER,
            winning_trades INTEGER,
            losing_trades INTEGER,
            win_rate REAL,
            total_pnl REAL,
            largest_win REAL,
            largest_loss REAL,
            avg_win REAL,
            avg_loss REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Setup analytics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS setup_analytics (
            setup_name TEXT PRIMARY KEY,
            total_trades INTEGER,
            winning_trades INTEGER,
            win_rate REAL,
            avg_pnl REAL,
            best_pnl REAL,
            worst_pnl REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# TRADE LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def log_trade(
    trade_id: str,
    index_name: str,
    direction: str,
    strike: int,
    expiry: str,
    entry_price: float,
    entry_quantity: int,
    confidence_pct: int,
    conviction_level: str,
    market_snapshot: Dict = None,
) -> bool:
    """
    Log a new trade recommendation to journal.
    Called when trade is first recommended (before entry).

    Returns:
        Success status
    """
    try:
        init_database()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (
                id, index_name, direction, strike, expiry,
                entry_price, entry_quantity, confidence_pct, conviction_level,
                market_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id, index_name, direction, strike, expiry,
            entry_price, entry_quantity, confidence_pct, conviction_level,
            json.dumps(market_snapshot or {})
        ))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f"Failed to log trade: {e}")
        return False


def update_trade_entry(
    trade_id: str,
    entry_price: float,
    entry_time: datetime,
    entry_quantity: int,
) -> bool:
    """
    Update trade with actual entry details (when entry is confirmed).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE trades
            SET entry_price = ?, entry_time = ?, entry_quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (entry_price, entry_time.isoformat(), entry_quantity, trade_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f"Failed to update trade entry: {e}")
        return False


def close_trade(
    trade_id: str,
    exit_price: float,
    exit_time: datetime,
    exit_reason: str,
    exit_quantity: int = None,
    targets_hit: int = 0,
) -> bool:
    """
    Close a trade and calculate final P&L.
    Called when trade is exited (target hit, SL hit, etc).

    Args:
        trade_id: Unique trade identifier
        exit_price: Exit premium
        exit_time: Timestamp of exit
        exit_reason: "Target 1", "Target 2", "Stop Loss", "Trend Reversal", "Time Decay"
        exit_quantity: Quantity exited
        targets_hit: Number of targets hit (0-3)

    Returns:
        Success status
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Fetch entry price for P&L calculation
        cursor.execute("SELECT entry_price, entry_quantity FROM trades WHERE id = ?", (trade_id,))
        result = cursor.fetchone()

        if not result:
            log.warning(f"Trade {trade_id} not found")
            conn.close()
            return False

        entry_price, qty = result
        qty = exit_quantity or qty

        # Calculate P&L
        pnl_rupees = (exit_price - entry_price) * qty
        pnl_percent = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        time_in_trade = None
        cursor.execute("SELECT entry_time FROM trades WHERE id = ?", (trade_id,))
        entry_time_str = cursor.fetchone()
        if entry_time_str and entry_time_str[0]:
            entry_dt = datetime.fromisoformat(entry_time_str[0])
            time_in_trade = int((exit_time - entry_dt).total_seconds() / 60)

        # Update trade
        cursor.execute("""
            UPDATE trades
            SET exit_price = ?, exit_time = ?, exit_reason = ?, exit_quantity = ?,
                pnl_rupees = ?, pnl_percent = ?, targets_hit = ?,
                time_in_trade_minutes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            exit_price, exit_time.isoformat(), exit_reason, exit_quantity,
            pnl_rupees, pnl_percent, targets_hit,
            time_in_trade, trade_id
        ))

        conn.commit()
        conn.close()

        # Update daily summary
        _update_daily_summary(exit_time.date())

        return True
    except Exception as e:
        log.error(f"Failed to close trade: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS & REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def get_trade_by_id(trade_id: str) -> Optional[Dict]:
    """Fetch a specific trade from journal."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        cols = [description[0] for description in cursor.description]
        result = cursor.fetchone()
        conn.close()

        if result:
            return dict(zip(cols, result))
        return None
    except Exception as e:
        log.error(f"Failed to fetch trade: {e}")
        return None


def get_daily_pnl(date: datetime.date = None) -> Dict:
    """
    Get P&L summary for a specific date.
    Default is today.
    """
    if date is None:
        date = datetime.now(IST).date()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Fetch all closed trades for the day
        cursor.execute("""
            SELECT * FROM trades
            WHERE DATE(exit_time) = ? AND exit_price IS NOT NULL
            ORDER BY exit_time DESC
        """, (date.isoformat(),))

        cols = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

        trades = [dict(zip(cols, row)) for row in results]

        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl_rupees'] and t['pnl_rupees'] > 0])
        losing_trades = len([t for t in trades if t['pnl_rupees'] and t['pnl_rupees'] <= 0])

        total_pnl = sum(t['pnl_rupees'] or 0 for t in trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        wins = [t['pnl_rupees'] for t in trades if t['pnl_rupees'] and t['pnl_rupees'] > 0]
        losses = [t['pnl_rupees'] for t in trades if t['pnl_rupees'] and t['pnl_rupees'] <= 0]

        return {
            "date": date.isoformat(),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "largest_win": round(max(wins), 2) if wins else 0,
            "largest_loss": round(min(losses), 2) if losses else 0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "trades": trades,
        }
    except Exception as e:
        log.error(f"Failed to get daily P&L: {e}")
        return {}


def get_period_pnl(start_date: datetime.date, end_date: datetime.date = None) -> Dict:
    """Get P&L summary for a date range."""
    if end_date is None:
        end_date = datetime.now(IST).date()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trades
            WHERE DATE(exit_time) BETWEEN ? AND ? AND exit_price IS NOT NULL
            ORDER BY exit_time DESC
        """, (start_date.isoformat(), end_date.isoformat()))

        cols = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

        trades = [dict(zip(cols, row)) for row in results]

        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl_rupees'] and t['pnl_rupees'] > 0])
        losing_trades = total_trades - winning_trades

        total_pnl = sum(t['pnl_rupees'] or 0 for t in trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        wins = [t['pnl_rupees'] for t in trades if t['pnl_rupees'] and t['pnl_rupees'] > 0]
        losses = [t['pnl_rupees'] for t in trades if t['pnl_rupees'] and t['pnl_rupees'] <= 0]

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_traded": (end_date - start_date).days + 1,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "largest_win": round(max(wins), 2) if wins else 0,
            "largest_loss": round(min(losses), 2) if losses else 0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "avg_trade": round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 0,
        }
    except Exception as e:
        log.error(f"Failed to get period P&L: {e}")
        return {}


def get_performance_by_index(date: datetime.date = None) -> Dict[str, Dict]:
    """Get performance breakdown by index (NIFTY, BANKNIFTY, FINNIFTY)."""
    if date is None:
        date = datetime.now(IST).date()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT index_name, COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as winning_trades,
                   SUM(pnl_rupees) as total_pnl,
                   AVG(pnl_rupees) as avg_pnl
            FROM trades
            WHERE DATE(exit_time) = ? AND exit_price IS NOT NULL
            GROUP BY index_name
        """, (date.isoformat(),))

        cols = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

        performance = {}
        for row in results:
            data = dict(zip(cols, row))
            index = data['index_name']
            total = data['total_trades']
            win_rate = (data['winning_trades'] / total * 100) if total > 0 else 0

            performance[index] = {
                "total_trades": total,
                "winning_trades": data['winning_trades'],
                "win_rate": round(win_rate, 2),
                "total_pnl": round(data['total_pnl'] or 0, 2),
                "avg_pnl": round(data['avg_pnl'] or 0, 2),
            }

        return performance
    except Exception as e:
        log.error(f"Failed to get performance by index: {e}")
        return {}


def get_best_setups(min_trades: int = 3, date_range_days: int = 7) -> List[Dict]:
    """
    Identify best-performing trade setups (combination of signals that worked).
    Ranks by win rate and avg P&L.
    """
    start_date = datetime.now(IST).date() - timedelta(days=date_range_days)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT index_name || "_" || direction as setup,
                   COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as winning_trades,
                   AVG(pnl_rupees) as avg_pnl,
                   MAX(pnl_rupees) as best_pnl,
                   MIN(pnl_rupees) as worst_pnl
            FROM trades
            WHERE DATE(exit_time) >= ? AND exit_price IS NOT NULL
            GROUP BY setup
            HAVING COUNT(*) >= ?
            ORDER BY AVG(pnl_rupees) DESC
        """, (start_date.isoformat(), min_trades))

        cols = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

        setups = []
        for row in results:
            data = dict(zip(cols, row))
            total = data['total_trades']
            win_rate = (data['winning_trades'] / total * 100) if total > 0 else 0

            setups.append({
                "setup": data['setup'],
                "total_trades": total,
                "winning_trades": data['winning_trades'],
                "win_rate": round(win_rate, 2),
                "avg_pnl": round(data['avg_pnl'] or 0, 2),
                "best_pnl": round(data['best_pnl'] or 0, 2),
                "worst_pnl": round(data['worst_pnl'] or 0, 2),
            })

        return setups
    except Exception as e:
        log.error(f"Failed to get best setups: {e}")
        return []


def get_worst_setups(min_trades: int = 3, date_range_days: int = 7) -> List[Dict]:
    """
    Identify worst-performing setups (to avoid or refine).
    """
    start_date = datetime.now(IST).date() - timedelta(days=date_range_days)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT index_name || "_" || direction as setup,
                   COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl_rupees > 0 THEN 1 ELSE 0 END) as winning_trades,
                   AVG(pnl_rupees) as avg_pnl,
                   MAX(pnl_rupees) as best_pnl,
                   MIN(pnl_rupees) as worst_pnl
            FROM trades
            WHERE DATE(exit_time) >= ? AND exit_price IS NOT NULL
            GROUP BY setup
            HAVING COUNT(*) >= ?
            ORDER BY AVG(pnl_rupees) ASC
        """, (start_date.isoformat(), min_trades))

        cols = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

        setups = []
        for row in results:
            data = dict(zip(cols, row))
            total = data['total_trades']
            win_rate = (data['winning_trades'] / total * 100) if total > 0 else 0

            setups.append({
                "setup": data['setup'],
                "total_trades": total,
                "winning_trades": data['winning_trades'],
                "win_rate": round(win_rate, 2),
                "avg_pnl": round(data['avg_pnl'] or 0, 2),
                "best_pnl": round(data['best_pnl'] or 0, 2),
                "worst_pnl": round(data['worst_pnl'] or 0, 2),
            })

        return setups
    except Exception as e:
        log.error(f"Failed to get worst setups: {e}")
        return []


def export_journal_csv(date_range_days: int = 30) -> Optional[pd.DataFrame]:
    """
    Export trade journal to pandas DataFrame (can be saved as CSV).
    Useful for external analysis (TradingView, Excel, etc).
    """
    start_date = datetime.now(IST).date() - timedelta(days=date_range_days)

    try:
        conn = sqlite3.connect(DB_PATH)

        df = pd.read_sql_query("""
            SELECT * FROM trades
            WHERE DATE(exit_time) >= ? AND exit_price IS NOT NULL
            ORDER BY exit_time DESC
        """, conn, params=(start_date.isoformat(),))

        conn.close()
        return df if not df.empty else None
    except Exception as e:
        log.error(f"Failed to export journal: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _update_daily_summary(date: datetime.date):
    """Update daily summary table after a trade closes."""
    daily = get_daily_pnl(date)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO daily_summary
            (date, total_trades, winning_trades, losing_trades, win_rate,
             total_pnl, largest_win, largest_loss, avg_win, avg_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.isoformat(),
            daily.get('total_trades', 0),
            daily.get('winning_trades', 0),
            daily.get('losing_trades', 0),
            daily.get('win_rate', 0),
            daily.get('total_pnl', 0),
            daily.get('largest_win', 0),
            daily.get('largest_loss', 0),
            daily.get('avg_win', 0),
            daily.get('avg_loss', 0),
        ))

        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Failed to update daily summary: {e}")
