"""由 SNR 區帶自動推導 4H 情境規劃（區間 / 突破 / 破位）。"""
from __future__ import annotations


def _rr(entry, sl, tp):
    risk = abs(entry - sl)
    if risk <= 1e-9:
        return 0.0
    return min(abs(tp - entry) / risk, 9.9)


def _fmt(x):
    return f"{round(x):,}"


def _probs(a):
    """依趨勢與動能給三個情境的機率（合計 100）。"""
    s = 0
    s += 1 if a["price"] > a["e20"] else -1
    s += 1 if a["price"] > a["e50"] else -1
    s += 1 if a["e50"] > a["e200"] else -1
    s += 1 if a["d50"] > a["d200"] else -1
    if a["rsi"] > 58:
        s += 1
    elif a["rsi"] < 42:
        s -= 1
    b = max(15, min(40, 26 + 3 * s))
    c = max(15, min(40, 26 - 3 * s))
    return 100 - b - c, b, c


def build(a: dict) -> list[dict]:
    p, atr = a["price"], a["atr4"]
    sup, res = a["sup"], a["res"]

    s1 = sup[0] if sup else {"lo": p - 2 * atr, "hi": p - 1.5 * atr, "mid": p - 1.75 * atr}
    s2 = sup[1] if len(sup) > 1 else {"lo": s1["lo"] - 2 * atr, "hi": s1["lo"] - 1.5 * atr,
                                      "mid": s1["lo"] - 1.75 * atr}
    r1 = res[0] if res else {"lo": p + 1.5 * atr, "hi": p + 2 * atr, "mid": p + 1.75 * atr}
    r2 = res[1] if len(res) > 1 else {"lo": r1["hi"] + 1.5 * atr, "hi": r1["hi"] + 2 * atr,
                                      "mid": r1["hi"] + 1.75 * atr}

    pA, pB, pC = _probs(a)
    up_trig, dn_trig = r1["hi"], s1["lo"]

    # --- A 區間 ---------------------------------------------------------- #
    le = s1["hi"] + 0.1 * atr          # 多方在支撐上緣附近承接
    lsl = s1["lo"] - 0.5 * atr
    ltp1, ltp2 = r1["lo"], r1["hi"]
    se = r1["lo"] - 0.1 * atr          # 空方在壓力下緣附近試單
    ssl = r1["hi"] + 0.5 * atr
    stp1, stp2 = s1["hi"], s1["lo"]

    # --- B 突破 ---------------------------------------------------------- #
    be = up_trig + 0.25 * atr
    bsl = r1["lo"] - 0.5 * atr
    btp1, btp2 = r2["lo"], r2["hi"]
    if _rr(be, bsl, btp1) < 1.0:                      # R:R 太差就收緊停損
        bsl = be - (btp1 - be) / 1.2
    # --- C 破位 ---------------------------------------------------------- #
    ce = dn_trig - 0.25 * atr
    csl = s1["hi"] + 0.5 * atr
    ctp1, ctp2 = s2["hi"], s2["lo"]
    if _rr(ce, csl, ctp1) < 1.0:
        csl = ce + (ce - ctp1) / 1.2

    return [
        {
            "title": "情境 A｜區間震盪", "prob": pA, "kind": "range",
            "trigger": f"觸發：4H 收盤維持在 {_fmt(dn_trig)} – {_fmt(up_trig)} 之間",
            "lines": [
                f"多方：{_fmt(le)} 進場 · SL {_fmt(lsl)} · TP1 {_fmt(ltp1)} · TP2 {_fmt(ltp2)}"
                f"　（R:R 1:{_rr(le,lsl,ltp1):.1f} · 1:{_rr(le,lsl,ltp2):.1f}）",
                f"空方：{_fmt(se)} 進場 · SL {_fmt(ssl)} · TP1 {_fmt(stp1)} · TP2 {_fmt(stp2)}"
                f"　（R:R 1:{_rr(se,ssl,stp1):.1f} · 1:{_rr(se,ssl,stp2):.1f}）",
            ],
        },
        {
            "title": "情境 B｜向上突破", "prob": pB, "kind": "bull",
            "trigger": f"觸發：4H 收盤站上 {_fmt(up_trig)}（回踩不破再進場，避免假突破）",
            "lines": [
                f"進場 {_fmt(be)} · SL {_fmt(bsl)} · TP1 {_fmt(btp1)} · TP2 {_fmt(btp2)}"
                f"（R:R 1:{_rr(be,bsl,btp1):.1f} · 1:{_rr(be,bsl,btp2):.1f}）",
            ],
        },
        {
            "title": "情境 C｜向下破位", "prob": pC, "kind": "bear",
            "trigger": f"觸發：4H 收盤跌破 {_fmt(dn_trig)}（反抽不過前低再進場）",
            "lines": [
                f"進場 {_fmt(ce)} · SL {_fmt(csl)} · TP1 {_fmt(ctp1)} · TP2 {_fmt(ctp2)}"
                f"（R:R 1:{_rr(ce,csl,ctp1):.1f} · 1:{_rr(ce,csl,ctp2):.1f}）",
            ],
        },
    ]
