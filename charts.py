"""
Plotly chart builders for the Streamlit dashboard.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import config


def candlestick_chart(
    df: pd.DataFrame,
    title: str = "",
    show_ema: list[int] = [20, 50],
    show_bb: bool = False,
    show_supertrend: bool = True,
    show_volume: bool = True,
) -> go.Figure:
    """Full candlestick chart with optional overlays and volume subplot."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available", template="plotly_dark")
        return fig

    rows = 3 if show_volume else 2
    row_heights = [0.6, 0.2, 0.2] if show_volume else [0.7, 0.3]
    subplot_titles = [title, "Volume", "RSI / MACD"] if show_volume else [title, "RSI / MACD"]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.03,
        subplot_titles=subplot_titles,
    )

    # ── Candlesticks ─────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        increasing_line_color=config.BULL_COLOR,
        decreasing_line_color=config.BEAR_COLOR,
        name="Price",
        showlegend=False,
    ), row=1, col=1)

    # ── EMA overlays ─────────────────────────────────────────────────────────
    ema_colors = {20: "#f59e0b", 50: "#3b82f6", 200: "#a855f7"}
    for p in show_ema:
        col = f"ema_{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df[col],
                line=dict(color=ema_colors.get(p, "#ffffff"), width=1.2),
                name=f"EMA {p}",
            ), row=1, col=1)

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    if show_bb and "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["bb_upper"],
            line=dict(color="rgba(99,102,241,0.5)", width=1, dash="dot"),
            name="BB Upper", showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["bb_lower"],
            line=dict(color="rgba(99,102,241,0.5)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(99,102,241,0.05)",
            name="BB Lower", showlegend=False,
        ), row=1, col=1)

    # ── Supertrend ────────────────────────────────────────────────────────────
    if show_supertrend and "supertrend" in df.columns:
        bull = df[df["supertrend_dir"] == 1]
        bear = df[df["supertrend_dir"] == -1]
        for subset, color, name in [(bull, config.BULL_COLOR, "ST Bull"), (bear, config.BEAR_COLOR, "ST Bear")]:
            if not subset.empty:
                fig.add_trace(go.Scatter(
                    x=subset["timestamp"], y=subset["supertrend"],
                    mode="markers", marker=dict(color=color, size=3),
                    name=name,
                ), row=1, col=1)

    # ── Volume bars ───────────────────────────────────────────────────────────
    if show_volume and "volume" in df.columns:
        colors = [config.BULL_COLOR if c >= o else config.BEAR_COLOR
                  for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(
            x=df["timestamp"], y=df["volume"],
            marker_color=colors, name="Volume", showlegend=False,
        ), row=2, col=1)

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi_row = 3 if show_volume else 2
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["rsi"],
            line=dict(color="#f59e0b", width=1.5),
            name="RSI",
        ), row=rsi_row, col=1)
        for level, color in [(70, "rgba(239,83,80,0.4)"), (30, "rgba(38,166,154,0.4)")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, row=rsi_row, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=config.BG_COLOR,
        plot_bgcolor=config.BG_COLOR,
        font=dict(color=config.TEXT_COLOR, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=40, b=10),
        height=650,
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(
        gridcolor=config.GRID_COLOR,
        showgrid=True,
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor=config.GRID_COLOR,
        showgrid=True,
        zeroline=False,
    )
    return fig


def macd_chart(df: pd.DataFrame) -> go.Figure:
    """Standalone MACD histogram chart."""
    fig = go.Figure()
    if df.empty or "macd" not in df.columns:
        return fig

    colors = [config.BULL_COLOR if v >= 0 else config.BEAR_COLOR
              for v in df["macd_hist"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df["timestamp"], y=df["macd_hist"],
        marker_color=colors, name="MACD Hist",
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["macd"],
        line=dict(color="#3b82f6", width=1.5), name="MACD",
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["macd_signal"],
        line=dict(color="#f59e0b", width=1.5), name="Signal",
    ))
    fig.update_layout(
        paper_bgcolor=config.BG_COLOR,
        plot_bgcolor=config.BG_COLOR,
        font=dict(color=config.TEXT_COLOR),
        legend=dict(orientation="h"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=220,
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(gridcolor=config.GRID_COLOR)
    fig.update_yaxes(gridcolor=config.GRID_COLOR)
    return fig


def option_chain_oi_chart(df: pd.DataFrame, spot: float = 0) -> go.Figure:
    """Bar chart of CE vs PE open interest across strikes."""
    fig = go.Figure()
    if df.empty:
        return fig

    fig.add_trace(go.Bar(
        x=df["strike"], y=df["ce_oi"],
        name="CE OI", marker_color=config.BEAR_COLOR, opacity=0.8,
    ))
    fig.add_trace(go.Bar(
        x=df["strike"], y=df["pe_oi"],
        name="PE OI", marker_color=config.BULL_COLOR, opacity=0.8,
    ))
    if spot:
        fig.add_vline(x=spot, line_dash="dash", line_color="#ffffff",
                      annotation_text=f"Spot {spot:,.0f}", annotation_position="top")

    fig.update_layout(
        barmode="group",
        paper_bgcolor=config.BG_COLOR,
        plot_bgcolor=config.BG_COLOR,
        font=dict(color=config.TEXT_COLOR),
        legend=dict(orientation="h"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=350,
        xaxis_title="Strike",
        yaxis_title="Open Interest",
    )
    fig.update_xaxes(gridcolor=config.GRID_COLOR)
    fig.update_yaxes(gridcolor=config.GRID_COLOR)
    return fig
