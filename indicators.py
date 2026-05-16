"""
Technical indicator calculations using pure pandas/numpy — no external TA library needed.
"""
import pandas as pd
import numpy as np


def add_ema(df: pd.DataFrame, periods: list = [20, 50, 200]) -> pd.DataFrame:
    for p in periods:
        df[f"ema_{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"]        = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]
    return df


def add_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    hl2 = (df["high"] + df["low"]) / 2

    # True Range
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)

    # ATR via Wilder smoothing
    atr = tr.ewm(com=period - 1, min_periods=period).mean()

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=float)

    for i in range(1, len(df)):
        prev_upper = upper_band.iloc[i - 1]
        prev_lower = lower_band.iloc[i - 1]
        prev_close = df["close"].iloc[i - 1]

        upper_band.iloc[i] = upper_band.iloc[i] if upper_band.iloc[i] < prev_upper or prev_close > prev_upper else prev_upper
        lower_band.iloc[i] = lower_band.iloc[i] if lower_band.iloc[i] > prev_lower or prev_close < prev_lower else prev_lower

        if i == 1:
            direction.iloc[i] = 1
        elif supertrend.iloc[i - 1] == prev_upper:
            direction.iloc[i] = -1 if df["close"].iloc[i] > upper_band.iloc[i] else 1
        else:
            direction.iloc[i] =  1 if df["close"].iloc[i] < lower_band.iloc[i] else -1

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == -1 else upper_band.iloc[i]

    df["supertrend"]     = supertrend
    df["supertrend_dir"] = direction * -1   # 1 = bullish (price above), -1 = bearish
    return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = df["close"].rolling(window=period).mean()
    sd  = df["close"].rolling(window=period).std()
    df["bb_mid"]   = mid
    df["bb_upper"] = mid + std * sd
    df["bb_lower"] = mid - std * sd
    return df


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    if "volume" in df.columns and df["volume"].sum() > 0:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return df


def add_all_indicators(df: pd.DataFrame, ema_periods: list = [20, 50, 200]) -> pd.DataFrame:
    if df.empty or len(df) < 30:
        return df
    df = add_ema(df, periods=ema_periods)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_supertrend(df)
    df = add_bollinger_bands(df)
    df = add_vwap(df)
    return df


def get_signal_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    last = df.iloc[-1]
    signals = {}

    rsi = last.get("rsi")
    if pd.notna(rsi):
        if rsi < 30:
            signals["RSI"] = ("Oversold", "green")
        elif rsi > 70:
            signals["RSI"] = ("Overbought", "red")
        else:
            signals["RSI"] = (f"{rsi:.1f} Neutral", "gray")

    macd = last.get("macd")
    sig  = last.get("macd_signal")
    if pd.notna(macd) and pd.notna(sig):
        signals["MACD"] = ("Bullish crossover", "green") if macd > sig else ("Bearish crossover", "red")

    st_dir = last.get("supertrend_dir")
    if pd.notna(st_dir):
        signals["Supertrend"] = ("Uptrend", "green") if st_dir == 1 else ("Downtrend", "red")

    ema20 = last.get("ema_20")
    close = last.get("close")
    if pd.notna(ema20) and pd.notna(close):
        signals["EMA20"] = ("Price above EMA20", "green") if close > ema20 else ("Price below EMA20", "red")

    return signals
