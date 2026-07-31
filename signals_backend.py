"""
Vijaya Power — signals generator (for GitHub Actions)
--------------------------------------------------------
Same free (yfinance) logic as before, but this version writes its
output to signals.json instead of printing a table. GitHub Actions
runs this on a schedule and commits the updated signals.json back
to the repo — the dashboard (index.html) then fetches that file
directly, so it shows real data with no server needed.

Data note: Yahoo Finance intraday data for NSE stocks is typically
~15 minutes delayed. Fine for spotting patterns, not for
split-second entries. Not investment advice.
"""

import json
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Run: pip install yfinance pandas")

WATCHLIST = [
    {"name": "Kalyan Jewellers",     "ticker": "KALYANKJIL.NS"},
    {"name": "Eternal (Zomato)",     "ticker": "ETERNAL.NS"},
    {"name": "City Union Bank",      "ticker": "CUB.NS"},
    {"name": "Apollo Micro Systems", "ticker": "APOLLO.NS"},
    {"name": "Advance Agrolife",     "ticker": "ADVANCEAGRO.NS"},
    {"name": "Nuvoco Vistas",        "ticker": "NUVOCO.NS"},
    {"name": "Birlasoft",            "ticker": "BSOFT.NS"},
    {"name": "PhysicsWallah",        "ticker": "PHYSICSWALLAH.NS"},
]

INTERVAL = "5m"
PERIOD = "1d"


def sma(values, period):
    if len(values) < period:
        period = len(values)
    return sum(values[-period:]) / period


def compute_signal(closes, highs, lows, vols):
    if len(closes) < 21:
        return {"signal": "watch", "reasons": ["not enough candles yet this session"],
                 "last": closes[-1] if closes else 0, "vwap": 0, "ma9": 0, "ma21": 0,
                 "recent_high": 0, "recent_low": 0, "last_vol": 0, "avg_vol20": 0,
                 "closes": closes}

    cum_pv = sum(c * v for c, v in zip(closes, vols))
    cum_v = sum(vols)
    vwap = cum_pv / cum_v if cum_v else closes[-1]

    ma9 = sma(closes, 9)
    ma21 = sma(closes, 21)
    prev_ma9 = sma(closes[:-1], 9)
    prev_ma21 = sma(closes[:-1], 21)
    cross_up = prev_ma9 <= prev_ma21 and ma9 > ma21
    cross_down = prev_ma9 >= prev_ma21 and ma9 < ma21

    avg_vol20 = sma(vols, 20)
    last_vol = vols[-1]
    vol_spike = last_vol > avg_vol20 * 1.6

    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    last = closes[-1]
    near_high = last > recent_high * 0.997
    near_low = last < recent_low * 1.003

    score = 0
    reasons = []
    if last > vwap:
        score += 1
        reasons.append("trading above VWAP")
    else:
        score -= 1
        reasons.append("trading below VWAP")
    if cross_up:
        score += 2
        reasons.append("9/21 MA bullish crossover")
    if cross_down:
        score -= 2
        reasons.append("9/21 MA bearish crossover")
    if vol_spike:
        score += 1 if last > vwap else -1
        reasons.append("volume spike vs 20-period avg")
    if near_high:
        score += 1
        reasons.append("pressing session high — breakout zone")
    if near_low:
        score -= 1
        reasons.append("pressing session low — breakdown zone")

    signal = "watch"
    if score >= 2:
        signal = "buy"
    elif score <= -2:
        signal = "sell"

    return {
        "signal": signal,
        "last": round(last, 2),
        "vwap": round(vwap, 2),
        "ma9": round(ma9, 2),
        "ma21": round(ma21, 2),
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
        "last_vol": int(last_vol),
        "avg_vol20": int(avg_vol20),
        "reasons": reasons,
        "closes": [round(c, 2) for c in closes],
    }


def fetch_and_score(stock):
    try:
        df = yf.Ticker(stock["ticker"]).history(period=PERIOD, interval=INTERVAL)
        if df.empty:
            return {"name": stock["name"], "ticker": stock["ticker"],
                     "signal": "error", "reasons": ["no data returned — check ticker symbol"],
                     "closes": []}
        closes = df["Close"].tolist()
        highs = df["High"].tolist()
        lows = df["Low"].tolist()
        vols = df["Volume"].tolist()
        sig = compute_signal(closes, highs, lows, vols)
    except Exception as e:
        sig = {"signal": "error", "reasons": [str(e)], "closes": []}
    return {"name": stock["name"], "ticker": stock["ticker"], **sig}


def main():
    results = [fetch_and_score(s) for s in WATCHLIST]
    output = {"updated_at": datetime.utcnow().isoformat() + "Z", "stocks": results}
    with open("signals.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote signals.json with {len(results)} stocks at {output['updated_at']}")


if __name__ == "__main__":
    main()
