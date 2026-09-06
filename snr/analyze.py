"""SNR（Support & Resistance）綜合版分析。

方法：
  1. 用 fractal 找 4H / 日線的擺盪高低點（swing pivot）
  2. 依價格排序後聚類成「區帶」：相鄰點價差 <= tol 且區帶寬度 <= maxW
  3. 每個區帶給分：日線點權重較高、越近期權重越高，再加上量價共振加分
  4. 用成交量分布（POC / VAH / VAL）與日樞紐點做輔助與命名依據
"""
from __future__ import annotations
import math

# --------------------------------------------------------------------------- #
# 指標
# --------------------------------------------------------------------------- #
def atr(bars, n=14):
    tr = []
    for i in range(1, len(bars)):
        p, b = bars[i - 1], bars[i]
        tr.append(max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])))
    if len(tr) < n:
        return sum(tr) / max(len(tr), 1)
    v = sum(tr[:n]) / n
    for x in tr[n:]:
        v = (v * (n - 1) + x) / n
    return v


def ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(vals, n=14):
    if len(vals) < n + 2:
        return 50.0
    g = l = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        g += max(d, 0)
        l += max(-d, 0)
    g /= n
    l /= n
    for i in range(n + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
    return 100 - 100 / (1 + g / (l or 1e-9))


def pivots(bars, w, weight):
    """fractal 擺盪點：左右各 w 根都不超過自己。"""
    out = []
    n = len(bars)
    for i in range(w, n - w):
        hi = lo = True
        for j in range(i - w, i + w + 1):
            if j == i:
                continue
            if bars[j]["h"] >= bars[i]["h"]:
                hi = False
            if bars[j]["l"] <= bars[i]["l"]:
                lo = False
        r = i / n  # 近期權重
        if hi:
            out.append({"p": bars[i]["h"], "w": weight, "r": r})
        if lo:
            out.append({"p": bars[i]["l"], "w": weight, "r": r})
    return out


def volume_profile(bars, nbins=60, va=0.70):
    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    if hi <= lo:
        return {"poc": lo, "val": lo, "vah": hi}
    bw = (hi - lo) / nbins
    bins = [0.0] * nbins
    for b in bars:
        a = max(0, int((b["l"] - lo) / bw))
        z = min(nbins - 1, int((b["h"] - lo) / bw))
        share = b["v"] / (z - a + 1)
        for i in range(a, z + 1):
            bins[i] += share
    total = sum(bins) or 1.0
    p = bins.index(max(bins))
    a, z, acc = p, p, bins[p]
    while acc < total * va and (a > 0 or z < nbins - 1):
        left = bins[a - 1] if a > 0 else -1
        right = bins[z + 1] if z < nbins - 1 else -1
        if right >= left:
            z += 1
            acc += bins[z]
        else:
            a -= 1
            acc += bins[a]
    return {"poc": lo + (p + 0.5) * bw, "val": lo + a * bw, "vah": lo + (z + 1) * bw}


# --------------------------------------------------------------------------- #
# 區帶聚類
# --------------------------------------------------------------------------- #
def cluster(pts, tol, max_width):
    pts = sorted(pts, key=lambda x: x["p"])
    if not pts:
        return []
    groups, cur = [], [pts[0]]
    for pt in pts[1:]:
        if pt["p"] - cur[-1]["p"] <= tol and pt["p"] - cur[0]["p"] <= max_width:
            cur.append(pt)
        else:
            groups.append(cur)
            cur = [pt]
    groups.append(cur)
    zones = []
    min_w = tol * 0.5          # 單點也要有厚度，才是「區」而不是「線」
    for g in groups:
        lo = min(x["p"] for x in g)
        hi = max(x["p"] for x in g)
        if hi - lo < min_w:
            mid = (lo + hi) / 2
            lo, hi = mid - min_w / 2, mid + min_w / 2
        zones.append({
            "lo": lo, "hi": hi, "mid": (lo + hi) / 2, "n": len(g),
            "score": round(sum(x["w"] * (0.4 + 0.6 * x["r"]) for x in g), 2),
        })
    return zones


def _label(z, ctx):
    """依共振條件替區帶產生說明文字。"""
    if z.get("proj"):
        return "ATR 投射（該方向無歷史點位）"
    tags = []
    a4 = ctx["atr4"]
    for name, val in (("7日POC", ctx["vp42"]["poc"]), ("7日VAH", ctx["vp42"]["vah"]),
                      ("7日VAL", ctx["vp42"]["val"]), ("15日POC", ctx["vp90"]["poc"])):
        if z["lo"] - a4 * 0.35 <= val <= z["hi"] + a4 * 0.35:
            tags.append(f"{name} {val:,.0f}")
            break
    for name, val in ctx["pivot"].items():
        if z["lo"] - a4 * 0.25 <= val <= z["hi"] + a4 * 0.25:
            tags.append(f"日樞紐{name}")
            break
    for name, val in (("前日高", ctx["pd"]["h"]), ("前日低", ctx["pd"]["l"]),
                      ("30日高", ctx["hi30"]), ("30日低", ctx["lo30"])):
        if z["lo"] - a4 * 0.2 <= val <= z["hi"] + a4 * 0.2:
            tags.append(name)
            break
    for name, val in (("4H EMA20", ctx["e20"]), ("4H EMA50", ctx["e50"]),
                      ("4H EMA200", ctx["e200"])):
        if z["lo"] - a4 * 0.2 <= val <= z["hi"] + a4 * 0.2:
            tags.append(name)
            break
    tags.insert(0, f"{z['n']}次觸碰")
    return "・".join(tags[:3])


def _stars(score, best):
    ratio = score / best if best else 0
    return "★★★" if ratio >= 0.6 else ("★★☆" if ratio >= 0.3 else "★☆☆")


def analyze(md: dict) -> dict:
    h4, d1 = md["h4"], md["d1"]
    price = md["last"]
    c4 = [b["c"] for b in h4]
    cd = [b["c"] for b in d1]
    a4, ad = atr(h4, 14), atr(d1, 14)

    vp42 = volume_profile(h4[-42:], 40)
    vp90 = volume_profile(h4[-90:], 60)
    pd = d1[-2]
    pv = (pd["h"] + pd["l"] + pd["c"]) / 3
    pivot = {"P": pv, "R1": 2 * pv - pd["l"], "R2": pv + (pd["h"] - pd["l"]),
             "S1": 2 * pv - pd["h"], "S2": pv - (pd["h"] - pd["l"])}

    ctx = {
        "atr4": a4, "vp42": vp42, "vp90": vp90, "pivot": pivot,
        "pd": pd, "hi30": max(b["h"] for b in d1[-30:]),
        "lo30": min(b["l"] for b in d1[-30:]),
        "e20": ema(c4[-120:], 20), "e50": ema(c4[-200:], 50), "e200": ema(c4, 200),
    }

    pts = pivots(h4[-180:], 3, 1.0) + pivots(d1[-90:], 2, 2.4)
    zones = cluster(pts, tol=a4 * 0.35, max_width=a4 * 1.0)

    sup = [z for z in zones if z["hi"] < price * 0.999 and z["mid"] > price * 0.85]
    res = [z for z in zones if z["lo"] > price * 1.001 and z["mid"] < price * 1.18]
    sup = sorted(sorted(sup, key=lambda z: -z["score"])[:4], key=lambda z: -z["mid"])
    res = sorted(sorted(res, key=lambda z: -z["score"])[:4], key=lambda z: z["mid"])

    # 上方（或下方）沒有歷史點位時，用 ATR 投射補一層，並誠實標註
    def _proj(base, direction, k):
        w = a4 * 0.3
        mid = base + direction * a4 * k
        return {"lo": mid - w / 2, "hi": mid + w / 2, "mid": mid, "n": 0,
                "score": 0.5, "proj": True}

    while len(res) < 2:
        base = res[-1]["hi"] if res else price
        res.append(_proj(base, +1, 1.6))
    while len(sup) < 2:
        base = sup[-1]["lo"] if sup else price
        sup.append(_proj(base, -1, 1.6))

    best = max([z["score"] for z in sup + res] or [1])
    for i, z in enumerate(sup):
        z["tag"], z["star"], z["name"] = _label(z, ctx), _stars(z["score"], best), f"S{i+1}"
    for i, z in enumerate(res):
        z["tag"], z["star"], z["name"] = _label(z, ctx), _stars(z["score"], best), f"R{i+1}"

    d_e50, d_e200 = ema(cd[-150:], 50), ema(cd, 200)
    r = rsi(c4[-120:], 14)

    return {
        "price": price, "atr4": a4, "atr1d": ad, "rsi": r,
        "e20": ctx["e20"], "e50": ctx["e50"], "e200": ctx["e200"],
        "d50": d_e50, "d200": d_e200,
        "vp42": vp42, "vp90": vp90, "pivot": pivot,
        "hi30": ctx["hi30"], "lo30": ctx["lo30"], "pd": pd,
        "sup": sup, "res": res,
        "trend_daily": "多頭" if d_e50 > d_e200 else "空頭",
    }
