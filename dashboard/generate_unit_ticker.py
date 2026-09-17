"""
Stock-ticker style strip for the Subro units (LRU / RCU / SRU):
last complete month $, MoM % change, 12-month sparkline, 12-month high/low range bar.
Real data: data/subro_monthly_team.parquet (SubroReports.rpt.RecoveriesbyLOBTableau by team+month).
"""
import os, json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import rps_data_real as data
import rps_measures as m

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
GREEN, RED, GRAY, DARK = "#178A5A", "#C0392B", "#9CA3AF", "#1F2933"
UNIT_COLORS = {"LRU": "#1F5AA6", "RCU": "#5B8DEF", "SRU": "#9DBEF5"}


def unit_of_team(t):
    return "SRU" if t in (41, 42) else ("RCU" if t == 45 else "LRU")


def build():
    t = pd.read_parquet(os.path.join(data.DATA_DIR, "subro_monthly_team.parquet"))
    t["Unit"] = t["Team"].fillna(-1).astype(int).map(unit_of_team)
    mu = t.groupby(["YearMonth", "Unit"], as_index=False)["GrossRecovery"].sum()
    months = sorted(mu["YearMonth"].unique())
    complete = months[:-1]                     # drop current partial month (2026-09)
    last12 = complete[-12:]
    last, prev = complete[-1], complete[-2]
    rows = []
    for u in ["LRU", "RCU", "SRU"]:
        s = mu[mu["Unit"] == u].set_index("YearMonth")["GrossRecovery"].reindex(last12).fillna(0)
        cur, pv = s[last], s[prev]
        rows.append(dict(Unit=u, Month=last, Current=cur, Prior=pv, MoM=(cur - pv) / pv if pv else None,
                         High=s.max(), HighMonth=s.idxmax(), Low=s.min(), LowMonth=s.idxmin(),
                         Series=s))
    return rows, last12


def label_month(ym):
    return pd.Period(ym).strftime("%b %Y")


def render(rows, last12):
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.06,
                        specs=[[{"secondary_y": False}] * 3])
    for i, r in enumerate(rows, start=1):
        s = r["Series"] / 1e6
        x = [label_month(ym) for ym in s.index]
        fig.add_trace(go.Scatter(x=x, y=s.values, mode="lines", line=dict(color=UNIT_COLORS[r["Unit"]], width=2.5),
                                 fill="tozeroy", fillcolor=UNIT_COLORS[r["Unit"]] + "22", showlegend=False,
                                 hovertemplate="%{x}: $%{y:,.2f}M<extra></extra>"), row=1, col=i)
        # high / low markers
        fig.add_trace(go.Scatter(x=[label_month(r["HighMonth"])], y=[r["High"] / 1e6], mode="markers+text",
                                 marker=dict(color=GREEN, size=9), text=[f"H {m.fmt_millions(r['High'])}"],
                                 textposition="top center", textfont=dict(size=10, color=GREEN), showlegend=False), row=1, col=i)
        fig.add_trace(go.Scatter(x=[label_month(r["LowMonth"])], y=[r["Low"] / 1e6], mode="markers+text",
                                 marker=dict(color=RED, size=9), text=[f"L {m.fmt_millions(r['Low'])}"],
                                 textposition="bottom center", textfont=dict(size=10, color=RED), showlegend=False), row=1, col=i)
        fig.update_yaxes(tickprefix="$", ticksuffix="M", tickformat=",.2f", showgrid=True, gridcolor="#EEF0F3",
                         rangemode="tozero", row=1, col=i)
        fig.update_xaxes(tickangle=-45, nticks=6, showgrid=False, row=1, col=i)

        up = r["MoM"] is not None and r["MoM"] >= 0
        arrow, color = ("▲", GREEN) if up else ("▼", RED)
        mom_txt = m.fmt_pct(r["MoM"]) if r["MoM"] is not None else "—"
        xdom = fig.layout[f"xaxis{'' if i == 1 else i}"].domain
        xc = (xdom[0] + xdom[1]) / 2
        # ticker header: UNIT   $XX.XXM   ▲ +x.x% MoM
        fig.add_annotation(x=xdom[0], y=1.30, xref="paper", yref="paper", xanchor="left", showarrow=False,
                           text=f"<b>{r['Unit']}</b>", font=dict(size=20, color=DARK))
        fig.add_annotation(x=xdom[0], y=1.17, xref="paper", yref="paper", xanchor="left", showarrow=False,
                           text=f"<b>{m.fmt_millions(r['Current'])}</b>  <span style='color:{color}'>{arrow} {mom_txt}</span>",
                           font=dict(size=17, color=DARK))
        fig.add_annotation(x=xdom[0], y=1.07, xref="paper", yref="paper", xanchor="left", showarrow=False,
                           text=f"{label_month(r['Month'])} vs {label_month(list(r['Series'].index)[-2])} ({m.fmt_millions(r['Prior'])})",
                           font=dict(size=11, color=GRAY))
        # 12-month range bar (52-week-style) under the sparkline
        lo, hi, cur = r["Low"], r["High"], r["Current"]
        pos = 0 if hi == lo else (cur - lo) / (hi - lo)
        bar_x0, bar_x1, bar_y = xdom[0], xdom[1], -0.42
        fig.add_shape(type="line", x0=bar_x0, x1=bar_x1, y0=bar_y, y1=bar_y, xref="paper", yref="paper",
                      line=dict(color="#D1D5DB", width=6))
        fig.add_shape(type="line", x0=bar_x0, x1=bar_x0 + pos * (bar_x1 - bar_x0), y0=bar_y, y1=bar_y,
                      xref="paper", yref="paper", line=dict(color=UNIT_COLORS[r["Unit"]], width=6))
        fig.add_annotation(x=bar_x0 + pos * (bar_x1 - bar_x0), y=bar_y, xref="paper", yref="paper", showarrow=False,
                           text="●", font=dict(size=16, color=DARK))
        fig.add_annotation(x=bar_x0, y=bar_y - 0.10, xref="paper", yref="paper", xanchor="left", showarrow=False,
                           text=f"12M low {m.fmt_millions(lo)} ({label_month(r['LowMonth'])})", font=dict(size=10, color=RED))
        fig.add_annotation(x=bar_x1, y=bar_y - 0.10, xref="paper", yref="paper", xanchor="right", showarrow=False,
                           text=f"12M high {m.fmt_millions(hi)} ({label_month(r['HighMonth'])})", font=dict(size=10, color=GREEN))
        fig.add_annotation(x=xc, y=bar_y + 0.10, xref="paper", yref="paper", showarrow=False,
                           text=f"current sits at {pos*100:.0f}% of 12-month range", font=dict(size=10, color=GRAY))

    fig.update_layout(template="plotly_white", height=560, width=1280,
                      margin=dict(l=60, r=30, t=170, b=170),
                      font=dict(family="Segoe UI, Arial, sans-serif", size=12),
                      title=dict(text=f"Subrogation Units — {label_month(rows[0]['Month'])} vs prior month, with 12-month range "
                                      f"({label_month(last12[0])} – {label_month(last12[-1])})",
                                 x=0.02, y=0.99, font=dict(size=15, color=GRAY)))
    return fig


if __name__ == "__main__":
    rows, last12 = build()
    fig = render(rows, last12)
    png = os.path.join(OUT_DIR, "exec_chart_subro_unit_ticker.png")
    fig.write_image(png, scale=2)
    summary = [{k: (v if k != "Series" else None) for k, v in r.items()} for r in rows]
    for r in summary:
        print(f"{r['Unit']}: {label_month(r['Month'])} {m.fmt_millions(r['Current'])}  MoM {m.fmt_pct(r['MoM'])}  "
              f"12M high {m.fmt_millions(r['High'])} ({label_month(r['HighMonth'])})  low {m.fmt_millions(r['Low'])} ({label_month(r['LowMonth'])})")
    json.dump(summary, open(os.path.join(OUT_DIR, "unit_ticker_summary.json"), "w"), default=str, indent=1)
    print("wrote", png)
