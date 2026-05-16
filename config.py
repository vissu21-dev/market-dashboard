import os
from dotenv import load_dotenv

load_dotenv()

# ── Upstox credentials ─────────────────────────────────────────────────────────
API_KEY        = os.getenv("UPSTOX_API_KEY", "")
API_SECRET     = os.getenv("UPSTOX_API_SECRET", "")
REDIRECT_URI   = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8501")
ACCESS_TOKEN   = os.getenv("UPSTOX_ACCESS_TOKEN", "")

# ── Upstox API base ────────────────────────────────────────────────────────────
BASE_URL = "https://api.upstox.com/v2"

# ── Instrument keys (Upstox format) ───────────────────────────────────────────
INSTRUMENTS = {
    "Nifty 50":    "NSE_INDEX|Nifty 50",
    "Bank Nifty":  "NSE_INDEX|Nifty Bank",
    "Fin Nifty":   "NSE_INDEX|Nifty Fin Service",
    "Midcap Nifty":"NSE_INDEX|NIFTY MID SELECT",
}

# ── Timeframe map (Upstox interval → display label) ───────────────────────────
INTERVALS = {
    "1 min":  "1minute",
    "3 min":  "3minute",
    "5 min":  "5minute",
    "10 min": "10minute",
    "15 min": "15minute",
    "30 min": "30minute",
    "1 Hour": "60minute",
    "1 Day":  "day",
    "1 Week": "week",
    "1 Month":"month",
}

# ── Option expiry series (update weekly) ──────────────────────────────────────
NIFTY_EXPIRY    = "2026-05-22"   # nearest weekly expiry
BANKNIFTY_EXPIRY = "2026-05-21"  # nearest weekly expiry

# ── Chart colours ─────────────────────────────────────────────────────────────
BULL_COLOR  = "#26a69a"
BEAR_COLOR  = "#ef5350"
BG_COLOR    = "#0e1117"
GRID_COLOR  = "#1e2130"
TEXT_COLOR  = "#e0e0e0"
