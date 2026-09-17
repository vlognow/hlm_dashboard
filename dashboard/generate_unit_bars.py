"""Subro units (LRU / RCU / SRU) as ONE grouped bar chart on a shared $ scale, last 12 complete months.
Replaces the three-panel sparkline ticker (generate_unit_ticker.py) after reviewer feedback."""
import os, pandas as pd, plotly.graph_objects as go
import rps_data_real as data

OUT = os.path.dirname(os.path.abspath(__file__))
GRAY, DARK = "#9CA3AF", "#1F2933"
UNIT_COLORS = {"LRU": "#1F5AA6", "RCU": "#5B8DEF", "SRU": "#9DBEF5"}
def unit_of_team(t): return "SRU" if t in (41, 42) else ("RCU" if t == 45 else "LRU")
def lab(ym): return pd.Period(ym).strftime("%b %Y")
def fmt(v): return f"${v/1e6:,.1f}M" if v >= 1e6 else f"${v/1e3:,.0f}K"

t = pd.read_parquet(os.path.join(data.DATA_DIR, "subro_monthly_team.parquet"))
t["Unit"] = t["Team"].fillna(-1).astype(int).map(unit_of_team)
mu = t.groupby(["YearMonth", "Unit"], as_index=False)["GrossRecovery"].sum()
months = sorted(mu["YearMonth"].unique()); last12 = months[:-1][-12:]
wide = mu.pivot(index="YearMonth", columns="Unit", values="GrossRecovery").reindex(last12).fillna(0)

fig = go.Figure()
for u in ["LRU", "RCU", "SRU"]:
    fig.add_trace(go.Bar(name=u, x=[lab(m) for m in last12], y=wide[u]/1e6, marker_color=UNIT_COLORS[u],
                         text=[fmt(v) for v in wide[u]], textposition="outside", textfont=dict(size=10),
                         cliponaxis=False, hovertemplate=u + " %{x}: $%{y:,.2f}M<extra></extra>"))
fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05, template="plotly_white", height=520, width=1280,
                  margin=dict(l=60, r=30, t=90, b=60), legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
                  font=dict(family="Segoe UI, Arial, sans-serif", size=12),
                  title=dict(text=f"Subrogation Units — Posted $ recovered per month, {lab(last12[0])} – {lab(last12[-1])}"
                                  f"<br><span style='font-size:12px;color:{GRAY}'>One shared scale. LRU = all teams except 41/42 (SRU) and 45 (RCU). Counted by recovery posting date.</span>",
                             x=0.02, font=dict(size=16, color=DARK)))
fig.update_yaxes(tickprefix="$", ticksuffix="M", showgrid=True, gridcolor="#EEF0F3", rangemode="tozero")
p = os.path.join(OUT, "exec_chart_subro_unit_bars.png"); fig.write_image(p, scale=2); print("wrote", p)
print((wide/1e6).round(2).to_string())
