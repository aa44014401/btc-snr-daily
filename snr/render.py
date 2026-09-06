# -*- coding: utf-8 -*-
"""把分析結果畫成一張 PNG 圖卡。"""
from __future__ import annotations
import glob
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402
from matplotlib.font_manager import FontProperties    # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

BG, PANEL, LINE = "#0B0E14", "#151A23", "#242B36"
TXT, MUT = "#E8EDF4", "#8A94A6"
UP, DN, GOLD, BLUE = "#0ECB81", "#F6465C", "#F0B90B", "#5B8DEF"
FIG_W, FIG_H, DPI = 6.75, 11.0, 160
ASPECT = FIG_W / FIG_H


# --------------------------------------------------------------------------- #
# 中文字型：不同系統路徑不一，逐一嘗試
# --------------------------------------------------------------------------- #
def _find_font(*keys):
    pats = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK{}.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-{}.ttc",
    ]
    for k in keys:
        for p in pats:
            f = p.format(k)
            if os.path.exists(f):
                return f
    for pat in ("/usr/share/fonts/**/*NotoSansCJK*", "/usr/share/fonts/**/*wqy*",
                "/usr/share/fonts/**/*NotoSansTC*", "/usr/share/fonts/**/*.ttc"):
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            return hits[0]
    return None


_F = {
    "r": _find_font("Regular"),
    "b": _find_font("Bold", "Medium", "Regular"),
    "k": _find_font("Black", "Bold", "Regular"),
}


def fp(size, weight="r"):
    path = _F.get(weight) or _F.get("r")
    return FontProperties(fname=path, size=size) if path else FontProperties(size=size)


def _fmt(x):
    return f"{round(x):,}"


def render(card: dict, out_path: str) -> str:
    a, plans, meta = card["a"], card["plans"], card["meta"]
    h4 = card["h4"][-75:]

    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def panel(x, y, w, h, fc=PANEL, ec=LINE, r=0.012, z=1):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
            fc=fc, ec=ec, lw=1.0, zorder=z, transform=ax.transAxes,
            mutation_aspect=ASPECT))

    def T(x, y, s, size=9, w="r", c=TXT, ha="left", z=5):
        ax.text(x, y, s, fontproperties=fp(size, w), color=c, ha=ha,
                va="center", zorder=z, transform=ax.transAxes)

    M = 0.045
    W = 1 - 2 * M

    # ---------------- 標題 ---------------- #
    T(M, 0.972, meta["symbol"], 20, "k")
    T(M + 0.245, 0.9755, meta["venue"], 8, "b", GOLD)
    T(M + 0.245, 0.9605, "SNR 支撐壓力策略", 8, "r", MUT)
    T(1 - M, 0.975, meta["updated"], 8.5, "r", MUT, ha="right")
    T(1 - M, 0.958, "資料時間 (UTC+8)", 7.5, "r", MUT, ha="right")
    ax.plot([M, 1 - M], [0.9435, 0.9435], color=LINE, lw=1.2,
            transform=ax.transAxes, zorder=3)

    # ---------------- 價格 ---------------- #
    py = 0.895
    ccol = UP if meta["chg"] >= 0 else DN
    T(M, py + 0.012, _fmt(a["price"]), 27, "k")
    T(M + 0.30, py + 0.020, f'{meta["chg"]:+.2f}%', 12, "b", ccol)
    T(M + 0.30, py - 0.002, "24H", 8, "r", MUT)
    stats = [("24H 高", _fmt(meta["h24"])), ("24H 低", _fmt(meta["l24"])),
             ("資金費率", f'{meta["funding"]*100:+.4f}%'),
             ("未平倉", f'{meta["oi"]:,.0f} BTC')]
    for i, (k, v) in enumerate(stats):
        xx = 0.50 + (i % 2) * 0.245
        yy = py + 0.021 - (i // 2) * 0.030
        T(xx, yy, k, 7.5, "r", MUT)
        T(xx + 0.233, yy, v, 8.5, "b", TXT, ha="right")

    # ---------------- K 線 ---------------- #
    cx0, cy0, cw, ch = M, 0.615, W, 0.235
    panel(cx0 - 0.008, cy0 - 0.022, cw + 0.016, ch + 0.040)
    cax = fig.add_axes([cx0 + 0.004, cy0 - 0.008, cw - 0.145, ch + 0.012])
    cax.set_facecolor(PANEL)
    for s in cax.spines.values():
        s.set_visible(False)
    cax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    o = np.array([b["o"] for b in h4]); hh = np.array([b["h"] for b in h4])
    ll = np.array([b["l"] for b in h4]); cc = np.array([b["c"] for b in h4])
    bands = card["bands"]
    lo_p = min(ll.min(), min(b[0] for b in bands)) * 0.995
    hi_p = max(hh.max(), max(b[1] for b in bands)) * 1.005
    n = len(cc)

    for blo, bhi, kind in bands:
        col = DN if kind == "R" else UP
        cax.add_patch(Rectangle((-2, blo), n + 40, bhi - blo, fc=col, alpha=0.13,
                                ec=col, lw=0.7, ls=(0, (3, 2)), zorder=1))
    for i in range(n):
        col = UP if cc[i] >= o[i] else DN
        cax.plot([i, i], [ll[i], hh[i]], color=col, lw=0.75, zorder=3,
                 solid_capstyle="butt")
        cax.add_patch(Rectangle(
            (i - 0.31, min(o[i], cc[i])), 0.62,
            max(abs(cc[i] - o[i]), (hi_p - lo_p) * 0.0012),
            fc=col, ec=col, lw=0.3, zorder=3))

    def _ema(arr, p):
        k = 2 / (p + 1)
        e = [arr[0]]
        for v in arr[1:]:
            e.append(v * k + e[-1] * (1 - k))
        return np.array(e)

    xs = np.arange(n)
    cax.plot(xs, _ema(cc, 20), color=GOLD, lw=1.0, alpha=0.85, zorder=4)
    cax.plot(xs, _ema(cc, 50), color=BLUE, lw=1.0, alpha=0.75, zorder=4)
    cax.axhline(a["price"], color=TXT, lw=0.8, ls=(0, (4, 3)), alpha=0.6, zorder=5)
    cax.set_xlim(-1.5, n + 0.5)
    cax.set_ylim(lo_p, hi_p)

    sx = cx0 + cw - 0.140

    def ypos(v):
        return cy0 - 0.008 + (v - lo_p) / (hi_p - lo_p) * (ch + 0.012)

    labs = [[ypos((b[0] + b[1]) / 2), f"{_fmt(b[0])}–{_fmt(b[1])}",
             DN if b[2] == "R" else UP] for b in bands]
    labs.append([ypos(a["price"]), f"現價 {_fmt(a['price'])}", TXT])
    labs.sort(key=lambda x: x[0])
    GAP = 0.0195
    for i in range(1, len(labs)):
        if labs[i][0] - labs[i - 1][0] < GAP:
            labs[i][0] = labs[i - 1][0] + GAP
    top = cy0 + ch + 0.006
    if labs and labs[-1][0] > top:
        shift = labs[-1][0] - top
        for L in labs:
            L[0] -= shift
    for yy, text, col in labs:
        if yy < cy0 - 0.010 or yy > cy0 + ch + 0.010:
            continue
        ax.add_patch(FancyBboxPatch(
            (sx + 0.004, yy - 0.0085), 0.132, 0.017,
            boxstyle="round,pad=0,rounding_size=0.004", fc=col, ec="none",
            alpha=0.16, zorder=4, transform=ax.transAxes, mutation_aspect=ASPECT))
        T(sx + 0.010, yy, text, 6.6, "b", col, z=6)
    T(cx0 + 0.012, cy0 + ch + 0.008, "4H K線 · 近 12 天", 8, "b", TXT, z=6)
    T(cx0 + 0.165, cy0 + ch + 0.008, "EMA20", 6.8, "b", GOLD, z=6)
    T(cx0 + 0.215, cy0 + ch + 0.008, "EMA50", 6.8, "b", BLUE, z=6)

    # ---------------- 點位表 ---------------- #
    ty = 0.585
    T(M, ty, "SNR 關鍵點位", 11, "k")
    ty -= 0.030
    colw = (W - 0.018) / 2
    rows = max(len(a["res"]), len(a["sup"]), 1)
    hbox = 0.026 + rows * 0.0295 + 0.012
    for ci, (title, col, items) in enumerate(
            [("空方壓力區 RESISTANCE", DN, a["res"]),
             ("多方支撐區 SUPPORT", UP, a["sup"])]):
        x = M + ci * (colw + 0.018)
        panel(x, ty - hbox + 0.014, colw, hbox)
        T(x + 0.014, ty, title, 7.6, "k", col)
        yy = ty - 0.030
        for it in items:
            T(x + 0.014, yy, it["name"], 7.0, "b", col)
            T(x + 0.048, yy + 0.005, f'{_fmt(it["lo"])} – {_fmt(it["hi"])}', 9.0, "b")
            T(x + 0.048, yy - 0.009, it["tag"], 6.4, "r", MUT)
            T(x + colw - 0.014, yy, it["star"], 7.5, "b", GOLD, ha="right")
            yy -= 0.0295
    sy = ty - hbox + 0.010

    # ---------------- 情境 ---------------- #
    sy -= 0.026
    T(M, sy, "4H 情境規劃", 11, "k")
    T(M + 0.175, sy - 0.001, "未來 24–48 小時", 7.5, "r", MUT)
    sy -= 0.026
    kcol = {"range": GOLD, "bull": UP, "bear": DN}
    for sc in plans:
        h = 0.062 if len(sc["lines"]) == 1 else 0.074
        col = kcol[sc["kind"]]
        panel(M, sy - h, W, h)
        ax.add_patch(Rectangle((M, sy - h + 0.006), 0.004, h - 0.012, fc=col,
                               ec="none", zorder=3, transform=ax.transAxes))
        T(M + 0.018, sy - 0.016, sc["title"], 9.0, "k", col)
        T(M + 0.203, sy - 0.016, f'機率 {sc["prob"]}%', 7.5, "b", MUT)
        T(M + 0.018, sy - 0.033, sc["trigger"], 7.3, "r", TXT)
        for i, ln in enumerate(sc["lines"]):
            T(M + 0.018, sy - 0.048 - i * 0.014, ln, 7.3, "r", MUT)
        sy -= h + 0.008

    # ---------------- 指標 ---------------- #
    sy -= 0.010
    panel(M, sy - 0.052, W, 0.052)
    price = a["price"]
    ind = [
        ("RSI (4H)", f'{a["rsi"]:.0f} ' + ("超買" if a["rsi"] > 70 else "超賣" if a["rsi"] < 30 else "中性"), MUT),
        ("ATR (4H)", _fmt(a["atr4"]), TXT),
        ("ATR (1D)", _fmt(a["atr1d"]), TXT),
        ("4H EMA20", _fmt(a["e20"]), UP if price > a["e20"] else DN),
        ("4H EMA50", _fmt(a["e50"]), UP if price > a["e50"] else DN),
        ("4H EMA200", _fmt(a["e200"]), UP if price > a["e200"] else DN),
        ("1D EMA50", _fmt(a["d50"]), UP if price > a["d50"] else DN),
        ("日線結構", a["trend_daily"], UP if a["trend_daily"] == "多頭" else DN),
    ]
    cwid = (W - 0.024) / 4
    for i, (k, v, c) in enumerate(ind):
        xx = M + 0.014 + (i % 4) * cwid
        yy = sy - 0.017 - (i // 4) * 0.021
        T(xx, yy, k, 6.5, "r", MUT)
        T(xx + cwid - 0.016, yy, v, 7.6, "b", c, ha="right")
    sy -= 0.052

    # ---------------- 頁尾 ---------------- #
    T(0.5, sy - 0.020,
      "本圖卡為 SNR 技術面統計結果，非投資建議；加密貨幣波動劇烈，請自行評估風險並嚴設停損。",
      6.4, "r", "#5A6373", ha="center")
    T(0.5, sy - 0.034, f'資料來源：{meta["source"]} · 每日 08:00 (UTC+8) 自動更新',
      6.4, "r", "#5A6373", ha="center")

    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path
