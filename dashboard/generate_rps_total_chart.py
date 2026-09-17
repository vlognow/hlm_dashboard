"""Overall RPS posted $ recovered per month (stacked: Subro + Pharmacy + COB), last 12 complete months."""
import os, json, pandas as pd, plotly.graph_objects as go
OUT = os.path.dirname(os.path.abspath(__file__))
GRAY, DARK = "#9CA3AF", "#1F2933"
COLORS = {"Subrogation": "#1F5AA6", "Pharmacy programs": "#178A5A", "COB (Medical)": "#7A3E9D"}
def lab(ym): return pd.Period(ym).strftime("%b %Y")

subro = pd.read_parquet(os.path.join(OUT, "data", "subro_monthly_total.parquet")).rename(columns={"YearMonth": "ym", "GrossRecovery": "v"})[["ym", "v"]]
rx = pd.read_csv(os.path.join(OUT, "dmg_PRT_monthly.csv"))
rx_ym = [c for c in rx.columns if c.lower() in ("ym", "yearmonth", "month")][0]
rx_v = [c for c in rx.columns if c.lower() in ("recovery", "total", "applied", "amount", "posted", "recovered")][0]
rx = rx.rename(columns={rx_ym: "ym", rx_v: "v"})[["ym", "v"]]; rx["ym"] = rx["ym"].astype(str).str[:7]
cob = pd.read_csv(os.path.join(OUT, "cob_act_monthly.csv")).rename(columns={"applied": "v"})[["ym", "v"]]
cob_months = sorted(cob.ym); last12 = cob_months[:-1][-12:]
wide = pd.DataFrame({"Subrogation": subro.set_index("ym")["v"], "Pharmacy programs": rx.groupby("ym")["v"].sum(), "COB (Medical)": cob.set_index("ym")["v"]}).reindex(last12)
assert wide.notna().all().all(), wide
tot = wide.sum(axis=1)
fig = go.Figure()
for col in wide.columns:
    fig.add_trace(go.Bar(name=col, x=[lab(m) for m in last12], y=wide[col]/1e6, marker_color=COLORS[col],
                         hovertemplate=col + " %{x}: $%{y:,.2f}M<extra></extra>"))
fig.add_trace(go.Scatter(x=[lab(m) for m in last12], y=tot/1e6, mode="text", text=[f"${v/1e6:,.1f}M" for v in tot],
                         textposition="top center", textfont=dict(size=11, color=DARK), showlegend=False, hoverinfo="skip"))
fig.update_layout(barmode="stack", template="plotly_white", height=500, width=1280, margin=dict(l=60, r=30, t=90, b=60),
                  legend=dict(orientation="h", y=1.02, x=1, xanchor="right"), font=dict(family="Segoe UI, Arial, sans-serif", size=12),
                  title=dict(text=f"RPS — Total posted $ recovered per month, {lab(last12[0])} – {lab(last12[-1])}"
                                  f"<br><span style='font-size:12px;color:{GRAY}'>Subrogation (SubroReports) + Pharmacy programs (DMG ledger) + COB medical (ACT Remit); each net of reversals</span>",
                             x=0.02, font=dict(size=16, color=DARK)))
fig.update_yaxes(tickprefix="$", ticksuffix="M", showgrid=True, gridcolor="#EEF0F3", rangemode="tozero")
p = os.path.join(OUT, "exec_chart_rps_total_monthly.png"); fig.write_image(p, scale=2); print("wrote", p)
wide["Total"] = tot; wide.to_csv(os.path.join(OUT, "rps_total_monthly.csv"))
last, prev = last12[-1], last12[-2]
summ = dict(month=last, total=float(tot[last]), prior=float(tot[prev]), mom=float((tot[last]-tot[prev])/tot[prev]), t12=float(tot.sum()),
            high=float(tot.max()), high_month=tot.idxmax(), low=float(tot.min()), low_month=tot.idxmin(),
            pillars={c: dict(current=float(wide.loc[last, c]), prior=float(wide.loc[prev, c]), t12=float(wide[c].sum()), share=float(wide.loc[last, c]/tot[last])) for c in COLORS})
json.dump(summ, open(os.path.join(OUT, "rps_total_summary.json"), "w"), indent=1, default=str)
print(json.dumps(summ, indent=1, default=str)); print((wide/1e6).round(2).to_string())
