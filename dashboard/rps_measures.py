"""Measure helpers mirroring the DAX in the design doc (§1.6), computed in pandas."""
import pandas as pd
import numpy as np


def window_sum(fact, anchor, days_back_start, days_back_end, **filters):
    d = fact
    for k, v in filters.items():
        if v is None:
            continue
        d = d[d[k] == v] if not isinstance(v, (list, tuple, set)) else d[d[k].isin(v)]
    lo = anchor - pd.Timedelta(days=days_back_start)
    hi = anchor - pd.Timedelta(days=days_back_end)
    win = d[(d["RecoveryDate"] >= lo) & (d["RecoveryDate"] <= hi)]
    return win["GrossAmount"].sum(), win["Cases"].sum() if "Cases" in win else len(win)


def l30(fact, anchor, **filters):
    g, c = window_sum(fact, anchor, 29, 0, **filters)
    return g, c


def p30(fact, anchor, **filters):
    g, c = window_sum(fact, anchor, 59, 30, **filters)
    return g, c


def delta_pct(l30_val, p30_val):
    if not p30_val:
        return None
    return (l30_val - p30_val) / p30_val


def last_complete_month(fact, anchor, **filters):
    d = fact
    for k, v in filters.items():
        if v is not None:
            d = d[d[k] == v]
    period = (anchor - pd.offsets.MonthBegin(1)).to_period("M") if anchor.day < 28 else anchor.to_period("M") - 1
    # last COMPLETE calendar month strictly before the anchor's month
    this_month = anchor.to_period("M")
    lc_month = this_month - 1
    win = d[d["RecoveryDate"].dt.to_period("M") == lc_month]
    return win["GrossAmount"].sum(), str(lc_month)


def daily_series(fact, anchor, days=30, **filters):
    d = fact
    for k, v in filters.items():
        if v is not None:
            d = d[d[k] == v]
    lo = anchor - pd.Timedelta(days=days - 1)
    win = d[(d["RecoveryDate"] >= lo) & (d["RecoveryDate"] <= anchor)]
    g = win.groupby(["RecoveryDate", "Pillar"], as_index=False)["GrossAmount"].sum()
    full_idx = pd.date_range(lo, anchor, freq="D")
    return g, full_idx


def rolling7(daily_totals):
    """daily_totals: Series indexed by date -> $"""
    return daily_totals.rolling(7, min_periods=1).mean()


def monthly_series(fact, anchor, months=12, **filters):
    d = fact
    for k, v in filters.items():
        if v is not None:
            d = d[d[k] == v]
    this_m = anchor.to_period("M")
    lo_m = this_m - months  # exclude current partial month -> last `months` complete months
    win = d[(d["RecoveryDate"].dt.to_period("M") >= lo_m) & (d["RecoveryDate"].dt.to_period("M") < this_m)]
    g = win.groupby([win["RecoveryDate"].dt.to_period("M"), "Pillar"])["GrossAmount"].sum().reset_index()
    g.columns = ["YearMonth", "Pillar", "GrossAmount"]
    g["YearMonth"] = g["YearMonth"].astype(str)
    return g


def business_days_and_batch_days(fact, anchor, pillar=None):
    d = fact if pillar is None else fact[fact["Pillar"] == pillar]
    lo = anchor - pd.Timedelta(days=29)
    daily = d[(d["RecoveryDate"] >= lo) & (d["RecoveryDate"] <= anchor)].groupby("RecoveryDate")["GrossAmount"].sum()
    bdays = pd.bdate_range(lo, anchor)
    n_bdays = len(bdays)
    if len(daily) == 0:
        return n_bdays, 0
    med = daily[daily > 0].median() if (daily > 0).any() else 0
    batch_days = int((daily > 3 * med).sum()) if med else 0
    return n_bdays, batch_days


def fmt_millions(x):
    """$ with 2 decimal places, scaled to M or K (M for |x| >= 1,000,000, else K)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "$0.00M"
    sign = "-" if x < 0 else ""
    ax = abs(x)
    if ax >= 1e6:
        return f"{sign}${ax/1e6:,.2f}M"
    return f"{sign}${ax/1e3:,.2f}K"


def fmt_pct(x):
    if x is None:
        return "—"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x*100:.1f}%"
