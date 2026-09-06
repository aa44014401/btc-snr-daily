"""合成行情資料，供 --demo 離線煙霧測試使用（數字不具任何市場意義）。"""
from __future__ import annotations
import math
import random


def _walk(n, start, vol, seed):
    rnd = random.Random(seed)
    bars, price = [], start
    t0 = 1780000000000
    for i in range(n):
        drift = math.sin(i / 18) * vol * 0.35
        o = price
        c = o + drift + rnd.gauss(0, vol)
        h = max(o, c) + abs(rnd.gauss(0, vol * 0.6))
        l = min(o, c) - abs(rnd.gauss(0, vol * 0.6))
        bars.append({"t": t0 + i * 14_400_000, "o": o, "h": h, "l": l, "c": c,
                     "v": abs(rnd.gauss(20000, 8000)) + 2000})
        price = c
    return bars


def _to_daily(bars):
    """把 4H 聚成日線（每 6 根）。"""
    out = []
    for i in range(0, len(bars) - 5, 6):
        g = bars[i:i + 6]
        out.append({"t": g[0]["t"], "o": g[0]["o"], "h": max(b["h"] for b in g),
                    "l": min(b["l"] for b in g), "c": g[-1]["c"],
                    "v": sum(b["v"] for b in g)})
    return out


def fake_market() -> dict:
    long4h = _walk(1260, 61000, 380, 7)     # 約 210 天
    h4 = long4h[-300:]
    d1 = _to_daily(long4h)[-200:]
    last = h4[-1]["c"]
    return {
        "source": "合成資料（demo）", "symbol": "BTCUSDT.P",
        "h4": h4, "d1": d1, "last": last, "chg": 0.85,
        "h24": max(b["h"] for b in h4[-6:]), "l24": min(b["l"] for b in h4[-6:]),
        "funding": 0.00005, "oi": 110000.0,
    }
