"""
Exec-flash charts: same real data, cleaner presentation.
Amounts pre-divided to $M so axis ticks read like "$85.70M" (2 decimals),
matching the fmt_millions() convention used everywhere else.
"""
import os, json
import pandas as pd
import plotly.graph_objects as go

import rps_data_real as data
import rps_measures as m

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBRO_BLUE = "#1F5AA6"
COB_TEAL = "#0F8B6E"
UNIT_COLORS = {"LRU": "#1F5AA6", "RCU": "#5B8DEF", "SRU": "#9DBEF5"}


def money_axis(title):
    return dict(title=title, tickprefix="$", ticksuffix="M", tickformat=",.2f")


def main():
    fact, files, anchor = data.load_all()
    cob_by_client = pd.read_parquet(os.path.join(data.DATA_DIR, "cob_by_client.parquet")) \
        .sort_values("total_invoiced", ascending=False)

    # 1. Subro daily trend, last 90 days, in $M
    daily, idx = m.daily_series(fact, anchor, days=90, Pillar="Subrogation")
    pv = daily.pivot(index="RecoveryDate", columns="Pillar", values="GrossAmount").reindex(idx).fillna(0)
    y = pv.get("Subrogation", pd.Series(0, index=idx)) / 1e6
    fig = go.Figure()
    fig.add_bar(x=idx, y=y, name="Subrogation", marker_color=SUBRO_BLUE)
    fig.update_layout(
        template="plotly_white", height=380, width=920,
        title="Subrogation — $ Recovered per Day, Last 90 Days",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13),
        yaxis=money_axis("$ Recovered"),
        margin=dict(l=70, r=20, t=50, b=50),
        showlegend=False,
    )
    fig.write_image(os.path.join(OUT_DIR, "exec_chart_subro_trend.png"), scale=2)

    # 2. Subro unit breakdown, last 30 days, in $M
    rows = []
    for unit in ["LRU", "RCU", "SRU"]:
        ul30, ucases = m.l30(fact, anchor, Pillar="Subrogation", UnitKey=unit)
        rows.append({"Unit": unit, "Recovered": ul30 / 1e6, "Files": int(ucases)})
    udf = pd.DataFrame(rows)
    fig2 = go.Figure(go.Bar(
        x=udf["Unit"], y=udf["Recovered"],
        marker_color=[UNIT_COLORS[u] for u in udf["Unit"]],
        text=[f"${v:,.2f}M" for v in udf["Recovered"]], textposition="outside",
    ))
    fig2.update_layout(
        template="plotly_white", height=380, width=560,
        title="Subrogation — $ Recovered by Unit, Last 30 Days",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13),
        yaxis=money_axis("$ Recovered"),
        margin=dict(l=70, r=20, t=50, b=50),
    )
    fig2.write_image(os.path.join(OUT_DIR, "exec_chart_subro_units.png"), scale=2)

    # 3. COB by client, top 12, in $M
    top = cob_by_client.head(12).copy()
    top["total_invoiced_m"] = top["total_invoiced"] / 1e6
    fig3 = go.Figure(go.Bar(
        x=top["ClientCode"], y=top["total_invoiced_m"], marker_color=COB_TEAL,
        text=[f"${v:,.2f}M" for v in top["total_invoiced_m"]], textposition="outside",
    ))
    fig3.update_layout(
        template="plotly_white", height=400, width=920,
        title="COB — $ Invoiced by Client, All-Time (Top 12)",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13),
        yaxis=money_axis("$ Invoiced"),
        xaxis=dict(tickangle=-30),
        margin=dict(l=70, r=20, t=50, b=90),
    )
    fig3.write_image(os.path.join(OUT_DIR, "exec_chart_cob_clients.png"), scale=2)

    print("wrote exec_chart_subro_trend.png, exec_chart_subro_units.png, exec_chart_cob_clients.png")


if __name__ == "__main__":
    main()
