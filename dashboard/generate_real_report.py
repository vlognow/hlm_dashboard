"""
Generates a markdown report + static PNG chart from REAL data only.
No synthetic/placeholder rows are included anywhere in this script's output.
"""
import os
import json
import pandas as pd
import plotly.graph_objects as go

import rps_data_real as data
import rps_measures as m

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    fact, files, anchor = data.load_all()
    cob = json.load(open(os.path.join(data.DATA_DIR, "cob_summary.json")))
    cob_by_client = pd.read_parquet(os.path.join(data.DATA_DIR, "cob_by_client.parquet")) \
        .sort_values("total_invoiced", ascending=False)

    lines = []
    lines.append("# RPS $ Recovered — Real-Data Snapshot\n")
    lines.append(f"_Generated {pd.Timestamp.now(tz='US/Eastern').strftime('%Y-%m-%d %H:%M %Z')} "
                 f"from Machinify Studio. No synthetic or placeholder rows anywhere below._\n")

    l30, cases = m.l30(fact, anchor, Pillar="Subrogation")
    p30, _ = m.p30(fact, anchor, Pillar="Subrogation")
    delta = m.delta_pct(l30, p30)
    lines.append("## Subrogation (full real time series)")
    lines.append(f"- **Recovered, last 30 days:** {m.fmt_millions(l30)}")
    lines.append(f"- **Prior 30 days:** {m.fmt_millions(p30)} ({m.fmt_pct(delta)})")
    lines.append(f"- **Files with a posting in the window:** {int(cases):,}")
    lines.append(f"- **Data through:** {anchor.strftime('%b %d, %Y')}")
    lines.append("- **Source:** `SubroReports.rpt.RecoveriesbyLOBTableau` "
                 "(Machinify Studio project 0010z / TRGDMGREP1)\n")

    lines.append("## COB (real, but all-time invoiced — no date field exists)")
    lines.append(f"- **Total invoiced (all-time):** {m.fmt_millions(cob['total_invoiced'])}")
    lines.append(f"- **Investigations:** {cob['n_investigations']:,} "
                 f"({cob['n_positive']:,} with a positive invoice amount)")
    lines.append("- **Source:** `overlap_detection.InvestigationInvoices` joined to "
                 "`CEMOverlapsAndSmartIIResults` for client code "
                 "(Machinify Studio project 0012k / TRGACAP3)")
    lines.append("- **Caveat:** this table has no date column, so no 30-day figure can be computed. "
                 "Separately, 8 other tables with the right shape for a dated recovered-$ figure "
                 "(`OverpaymentReceivedAmount` + `PayDate`/`ReceivedDate`, across 7 Aetna HMO/HRP MSP "
                 "audit 'Final' tables and a Cigna Professional Claims extract) were checked and every "
                 "one has that column entirely NULL.\n")
    lines.append("**Top 10 clients by invoiced $ (all-time, real):**\n")
    lines.append("| Client Code | Investigations | Invoiced $ |")
    lines.append("|---|---|---|")
    for _, r in cob_by_client.head(10).iterrows():
        lines.append(f"| {r['ClientCode']} | {int(r['n_investigations']):,} | ${r['total_invoiced']:,.0f} |")
    lines.append("")

    lines.append("## Pharma")
    lines.append("- **No reachable data source.** RXP/RxTra are not registered as a Studio data "
                 "source in any project this session can access. No number is shown because none "
                 "exists to show — not because a real figure was omitted.\n")

    # Chart: real Subro daily totals, last 90 days
    daily, idx = m.daily_series(fact, anchor, days=90, Pillar="Subrogation")
    pv = daily.pivot(index="RecoveryDate", columns="Pillar", values="GrossAmount").reindex(idx).fillna(0)
    fig = go.Figure()
    fig.add_bar(x=idx, y=pv.get("Subrogation", pd.Series(0, index=idx)),
                name="Subrogation (real)", marker_color="#1F5AA6")
    fig.update_layout(
        template="plotly_white", height=380, width=900,
        title="Subrogation — $ Recovered per day, last 90 days (real data, Machinify Studio)",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12),
        yaxis=dict(title="$", tickprefix="$", tickformat=",.2s"),
        margin=dict(l=60, r=20, t=50, b=60),
    )
    png_path = os.path.join(OUT_DIR, "real_data_chart.png")
    fig.write_image(png_path)
    lines.append("## Chart\n")
    lines.append("![Subrogation $ Recovered per day, last 90 days](real_data_chart.png)\n")

    # Secondary chart: COB by client (real)
    fig2 = go.Figure(go.Bar(x=cob_by_client.head(15)["ClientCode"],
                             y=cob_by_client.head(15)["total_invoiced"], marker_color="#0F8B6E"))
    fig2.update_layout(
        template="plotly_white", height=380, width=900,
        title="COB — Invoiced $ by client, all-time (real data, no date field available)",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12),
        yaxis=dict(title="$ invoiced", tickprefix="$", tickformat=",.2s"),
        xaxis=dict(tickangle=-45),
        margin=dict(l=60, r=20, t=50, b=100),
    )
    png_path2 = os.path.join(OUT_DIR, "real_data_chart_cob.png")
    fig2.write_image(png_path2)
    lines.append("![COB invoiced $ by client, all-time](real_data_chart_cob.png)\n")

    with open(os.path.join(OUT_DIR, "REAL_DATA_REPORT.md"), "w") as f:
        f.write("\n".join(lines))
    print("wrote REAL_DATA_REPORT.md, real_data_chart.png, real_data_chart_cob.png")


if __name__ == "__main__":
    main()
