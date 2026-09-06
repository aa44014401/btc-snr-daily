"""行情抓取，含多來源備援。

實測（2026-09，GitHub Actions ubuntu-latest runner）：
    fapi.binance.com          -> 451（幣安封鎖美國 IP）
    api.binance.com           -> 451
    api.bybit.com             -> 403
    api.okx.com               -> 連線失敗
    data-api.binance.vision   -> 200  ← 幣安官方公開資料端點，未封鎖
    api.bitget.com            -> 200  ← BTCUSDT U 本位永續，未封鎖

因此順序為：
    1. Binance 永續 (fapi)          最理想，本機／自架 runner 可用
    2. Binance 現貨 (vision) + Bitget 永續欄位   GitHub Actions 實際會走這條
    3. Bitget 永續                  最後手段
"""
from __future__ import annotations
import time
import requests

UA = {"User-Agent": "btc-snr-daily/1.0"}
TIMEOUT = 20
FAPI_HOSTS = ["https://fapi.binance.com", "https://fapi1.binance.com"]
VISION = "https://data-api.binance.vision"
BITGET = "https://api.bitget.com"


def _get(url, params=None):
    r = requests.get(url, params=params or {}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _bar(t, o, h, l, c, v):
    return {"t": int(t), "o": float(o), "h": float(h), "l": float(l),
            "c": float(c), "v": float(v)}


# --------------------------------------------------------------------------- #
# 1) Binance USDT-M 永續
# --------------------------------------------------------------------------- #
def _fapi(path, params):
    last = None
    for host in FAPI_HOSTS:
        try:
            return _get(host + path, params)
        except Exception as exc:                      # noqa: BLE001
            last = exc
            time.sleep(0.3)
    raise RuntimeError(f"fapi 不可用：{last}")


def _binance_perp(symbol):
    def kl(interval, limit):
        raw = _fapi("/fapi/v1/klines",
                    {"symbol": symbol, "interval": interval, "limit": limit})
        return [_bar(k[0], k[1], k[2], k[3], k[4], k[5]) for k in raw]

    tk = _fapi("/fapi/v1/ticker/24hr", {"symbol": symbol})
    pm = _fapi("/fapi/v1/premiumIndex", {"symbol": symbol})
    oi = _fapi("/fapi/v1/openInterest", {"symbol": symbol})
    return {
        "source": "Binance Futures (BTCUSDT.P)", "symbol": symbol + ".P",
        "h4": kl("4h", 300), "d1": kl("1d", 200),
        "last": float(tk["lastPrice"]), "chg": float(tk["priceChangePercent"]),
        "h24": float(tk["highPrice"]), "l24": float(tk["lowPrice"]),
        "funding": float(pm["lastFundingRate"]), "oi": float(oi["openInterest"]),
    }


# --------------------------------------------------------------------------- #
# 2) Bitget USDT-M 永續（提供永續專屬欄位，也可單獨當來源）
# --------------------------------------------------------------------------- #
def _bitget_kl(symbol, granularity, limit):
    j = _get(BITGET + "/api/v2/mix/market/candles",
             {"symbol": symbol, "granularity": granularity,
              "productType": "USDT-FUTURES", "limit": limit})
    return [_bar(r[0], r[1], r[2], r[3], r[4], r[5]) for r in j["data"]]


def _bitget_extras(symbol):
    tk = _get(BITGET + "/api/v2/mix/market/ticker",
              {"symbol": symbol, "productType": "USDT-FUTURES"})["data"][0]
    fr = _get(BITGET + "/api/v2/mix/market/current-fund-rate",
              {"symbol": symbol, "productType": "USDT-FUTURES"})["data"][0]
    oi = _get(BITGET + "/api/v2/mix/market/open-interest",
              {"symbol": symbol, "productType": "USDT-FUTURES"})["data"]["openInterestList"][0]
    return {
        "last": float(tk["lastPr"]), "chg": float(tk["change24h"]) * 100,
        "h24": float(tk["high24h"]), "l24": float(tk["low24h"]),
        "funding": float(fr["fundingRate"]), "oi": float(oi["size"]),
    }


def _bitget_perp(symbol):
    md = {"source": "Bitget Perp (BTCUSDT.P)", "symbol": symbol + ".P",
          "h4": _bitget_kl(symbol, "4H", 200), "d1": _bitget_kl(symbol, "1D", 200)}
    md.update(_bitget_extras(symbol))
    return md


# --------------------------------------------------------------------------- #
# 3) Binance 現貨（vision）K 線 + Bitget 永續欄位
# --------------------------------------------------------------------------- #
def _vision_mixed(symbol):
    def kl(interval, limit):
        raw = _get(VISION + "/api/v3/klines",
                   {"symbol": symbol, "interval": interval, "limit": limit})
        return [_bar(k[0], k[1], k[2], k[3], k[4], k[5]) for k in raw]

    tk = _get(VISION + "/api/v3/ticker/24hr", {"symbol": symbol})
    md = {
        "source": "Binance 現貨 K 線 + Bitget 永續指標", "symbol": symbol + ".P",
        "h4": kl("4h", 300), "d1": kl("1d", 200),
        "last": float(tk["lastPrice"]), "chg": float(tk["priceChangePercent"]),
        "h24": float(tk["highPrice"]), "l24": float(tk["lowPrice"]),
        "funding": 0.0, "oi": 0.0,
    }
    try:                                   # 永續專屬欄位拿不到就留 0，不讓整包失敗
        ex = _bitget_extras(symbol)
        md["funding"], md["oi"] = ex["funding"], ex["oi"]
    except Exception as exc:               # noqa: BLE001
        print(f"[warn] Bitget 永續欄位不可用：{exc}")
    return md


def fetch(symbol: str = "BTCUSDT") -> dict:
    for name, fn in (("Binance 永續", _binance_perp),
                     ("Binance 現貨+Bitget", _vision_mixed),
                     ("Bitget 永續", _bitget_perp)):
        try:
            md = fn(symbol)
            print(f"[info] 資料來源：{md['source']}")
            return md
        except Exception as exc:           # noqa: BLE001
            print(f"[warn] {name} 不可用：{exc}")
    raise RuntimeError("所有行情來源都不可用")
