#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTCUSDT.P SNR 每日圖卡 — 進入點。

用法:
    python main.py                  # 抓即時行情，輸出到 output/
    python main.py --demo           # 用合成資料跑（離線煙霧測試）
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import shutil

from snr import analyze as A
from snr import plan as P
from snr import render as R

OUT = "output"
TPE = dt.timezone(dt.timedelta(hours=8))


def _bands(a: dict) -> list:
    """挑 2 條壓力 + 2 條支撐畫在 K 線上，太靠近的併掉。"""
    picks = []
    for z in a["res"][:2]:
        picks.append((z["lo"], z["hi"], "R"))
    for z in a["sup"][:2]:
        picks.append((z["lo"], z["hi"], "S"))
    picks.sort(key=lambda b: b[0])
    merged = []
    for b in picks:
        if merged and b[2] == merged[-1][2] and b[0] - merged[-1][1] < a["atr4"] * 0.4:
            merged[-1] = (merged[-1][0], b[1], b[2])
        else:
            merged.append(b)
    return merged


def build(md: dict) -> dict:
    a = A.analyze(md)
    return {
        "a": a,
        "plans": P.build(a),
        "h4": md["h4"],
        "bands": _bands(a),
        "meta": {
            "symbol": md["symbol"], "venue": "BINANCE 永續", "source": md["source"],
            "updated": dt.datetime.now(TPE).strftime("%Y/%m/%d %H:%M"),
            "chg": md["chg"], "h24": md["h24"], "l24": md["l24"],
            "funding": md["funding"], "oi": md["oi"],
        },
    }


def summary(card: dict) -> dict:
    """給 README / Pages / 通知用的機器可讀摘要。"""
    a, m = card["a"], card["meta"]
    return {
        "updated_tpe": m["updated"], "symbol": m["symbol"], "source": m["source"],
        "price": round(a["price"], 1), "change_24h_pct": round(m["chg"], 2),
        "rsi_4h": round(a["rsi"], 1), "atr_4h": round(a["atr4"]),
        "atr_1d": round(a["atr1d"]), "daily_trend": a["trend_daily"],
        "resistance": [{"name": z["name"], "lo": round(z["lo"]), "hi": round(z["hi"]),
                        "touches": z["n"], "note": z["tag"], "strength": z["star"]}
                       for z in a["res"]],
        "support": [{"name": z["name"], "lo": round(z["lo"]), "hi": round(z["hi"]),
                     "touches": z["n"], "note": z["tag"], "strength": z["star"]}
                    for z in a["sup"]],
        "scenarios": [{"title": s["title"], "probability_pct": s["prob"],
                       "trigger": s["trigger"], "plan": s["lines"]} for s in card["plans"]],
        "disclaimer": "SNR 技術面統計結果，非投資建議。",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="用合成資料離線測試")
    ap.add_argument("--symbol", default="BTCUSDT")
    args = ap.parse_args()

    if args.demo:
        from tests.fake import fake_market
        md = fake_market()
    else:
        from snr.fetch import fetch
        md = fetch(args.symbol)

    card = build(md)
    os.makedirs(f"{OUT}/history", exist_ok=True)
    png = f"{OUT}/btc_snr.png"
    R.render(card, png)

    stamp = dt.datetime.now(TPE).strftime("%Y%m%d")
    shutil.copyfile(png, f"{OUT}/history/btc_snr_{stamp}.png")

    s = summary(card)
    with open(f"{OUT}/latest.json", "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    with open(f"{OUT}/history/snr_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

    print(f"價格 {s['price']:,} ({s['change_24h_pct']:+.2f}%) · "
          f"RSI {s['rsi_4h']} · 日線{s['daily_trend']}")
    for z in s["resistance"]:
        print(f"  壓力 {z['name']}: {z['lo']:,}–{z['hi']:,}  {z['note']}")
    for z in s["support"]:
        print(f"  支撐 {z['name']}: {z['lo']:,}–{z['hi']:,}  {z['note']}")
    for sc in s["scenarios"]:
        print(f"  {sc['title']} {sc['probability_pct']}% — {sc['trigger']}")
    print(f"輸出：{png}")


if __name__ == "__main__":
    main()
