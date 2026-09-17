"""
RPS $ Recovered — executive dashboard, REAL DATA ONLY.

Subrogation: full real time-series (SubroReports.rpt.RecoveriesbyLOBTableau,
             Machinify Studio project 0010z / TRGDMGREP1). This is the only
             pillar with a confirmed, dated, populated $-recovered source.

COB: after an exhaustive search of every Studio project this session can
     reach (0010z, 0012k), the only real, non-null dollar figure found is
     an ALL-TIME INVOICED total from overlap_detection.InvestigationInvoices
     (771,151 investigations, $1.65B), broken out by real client code via a
     join to CEMOverlapsAndSmartIIResults. Every other candidate table
     (7 client "Final" MSP/COB audit tables, qryCignaProClaimsPincRepaidStage5)
     has the right-shaped OverpaymentReceivedAmount/PayDate columns but they
     are entirely NULL — the field was never populated. So COB has a real
     number, but it is invoiced (not recovered) and has no date. It is shown
     that way, not smoothed into a fake daily/monthly trend.

Pharma: NO reachable data source at all. RXP/RxTra/SmartII are not
     registered as a Studio data source in any project this session has
     access to. Nothing is shown for Pharma except that fact.

No row anywhere in this file or its data layer is generated/synthetic.
"""
import os
import json
import urllib.parse as up

import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.graph_objects as go
import pandas as pd

import rps_data_real as data
import rps_measures as m

# ---------------------------------------------------------------- data ----
FACT, FILES, ANCHOR = data.load_all()  # Subrogation only (real, dated)

COB_SUMMARY = json.load(open(os.path.join(data.DATA_DIR, "cob_summary.json")))
COB_BY_CLIENT = pd.read_parquet(os.path.join(data.DATA_DIR, "cob_by_client.parquet")) \
    .sort_values("total_invoiced", ascending=False)

PILLARS = ["Subrogation", "COB", "Pharma"]
PILLAR_ACCENT = {"Subrogation": "#1F5AA6", "COB": "#0F8B6E", "Pharma": "#B4571C"}

# ------------------------------------------------------------- Dash app ---
JHUB_PREFIX = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
REQ_PREFIX = f"{JHUB_PREFIX}proxy/8050/"
ROOT = REQ_PREFIX

app = dash.Dash(
    __name__,
    requests_pathname_prefix=REQ_PREFIX,
    routes_pathname_prefix=REQ_PREFIX,
    suppress_callback_exceptions=True,
    title="RPS $ Recovered (real data)",
)
server = app.server

FONT = "Segoe UI, -apple-system, Helvetica, Arial, sans-serif"
BASE_STYLE = {"fontFamily": FONT, "backgroundColor": "#FFFFFF", "color": data.NEUTRAL_TEXT,
              "minHeight": "100vh", "padding": "24px"}


def card_shell(children, accent=None, style=None):
    s = {"border": f"1px solid {data.NEUTRAL_GRID}", "borderRadius": "8px", "padding": "18px",
         "background": "#FFFFFF", "position": "relative"}
    if accent:
        s["borderLeft"] = f"4px solid {accent}"
    if style:
        s.update(style)
    return html.Div(children, style=s)


def delta_span(pct):
    if pct is None:
        return html.Span("—", style={"color": data.NEUTRAL_SUB})
    arrow = "▲" if pct >= 0 else "▼"
    color = data.POS_COLOR if pct >= 0 else data.NEG_COLOR
    return html.Span(f"{arrow} {m.fmt_pct(pct)}", style={"color": color, "fontWeight": 600})


def btn_style():
    return {"background": "#1F2933", "color": "white", "border": "none", "borderRadius": "6px",
            "padding": "8px 14px", "cursor": "pointer", "fontSize": "12px"}


def toggle_style(active):
    s = btn_style()
    if not active:
        s["background"] = "#E5E7EB"
        s["color"] = "#1F2933"
    return s


def real_data_note(text):
    return html.Div(text, style={"background": "#EFF6FF", "border": "1px solid #BFDBFE",
                                  "color": "#1E3A8A", "padding": "8px 14px", "borderRadius": "6px",
                                  "fontSize": "12px", "marginBottom": "16px"})


def build_top_files_records(pillar, client=None, n=25):
    files_p = FILES[FILES["Pillar"] == pillar].copy()
    if client:
        files_p = files_p[files_p["ClientName"] == client]
    files_p = files_p.groupby(["CaseId", "ClientName", "ParentName", "UnitKey"], as_index=False).agg(
        RecentAmount=("GrossAmount", "sum"), LastDate=("RecoveryDate", "max"))
    files_p = files_p.sort_values("RecentAmount", ascending=False).head(n)
    files_p["RecentAmount"] = files_p["RecentAmount"].map(m.fmt_millions)
    files_p["LastDate"] = pd.to_datetime(files_p["LastDate"]).dt.strftime("%Y-%m-%d")
    return files_p.to_dict("records")


# ============================================================ PAGE 1 =====
def page_landing():
    total_l30, total_l30_cases = m.l30(FACT, ANCHOR, Pillar="Subrogation")
    total_p30, _ = m.p30(FACT, ANCHOR, Pillar="Subrogation")
    total_delta = m.delta_pct(total_l30, total_p30)
    lc_amt, lc_label = m.last_complete_month(FACT, ANCHOR, Pillar="Subrogation")
    n_bdays, n_batch = m.business_days_and_batch_days(FACT, ANCHOR, pillar="Subrogation")

    daily, idx = m.daily_series(FACT, ANCHOR, days=30, Pillar="Subrogation")
    pivot = daily.pivot(index="RecoveryDate", columns="Pillar", values="GrossAmount").reindex(idx).fillna(0)
    total_daily = pivot.sum(axis=1)
    roll7 = m.rolling7(total_daily)

    fig = go.Figure()
    fig.add_bar(x=idx, y=pivot.get("Subrogation", pd.Series(0, index=idx)),
                name="Subrogation", marker_color=PILLAR_ACCENT["Subrogation"])
    fig.add_trace(go.Scatter(x=idx, y=roll7, mode="lines", name="7d rolling avg",
                              line=dict(color="#374151", width=1.5)))
    fig.update_layout(
        barmode="stack", template="plotly_white", height=260, font=dict(family=FONT, size=11),
        margin=dict(l=40, r=10, t=10, b=30), legend=dict(orientation="h", y=-0.25),
        yaxis=dict(title="$", tickprefix="$", tickformat=",.2s", gridcolor=data.NEUTRAL_GRID),
        xaxis=dict(gridcolor=data.NEUTRAL_GRID),
    )

    # --- Subrogation card (real, full L30/P30) ---
    subro_card = card_shell([
        html.Div("SUBROGATION", style={"fontSize": "12px", "color": data.NEUTRAL_SUB,
                                        "fontWeight": 700, "letterSpacing": "0.05em"}),
        html.Div(m.fmt_millions(total_l30), style={"fontSize": "30px", "fontWeight": 700}),
        html.Div([delta_span(total_delta), html.Span("  vs prior 30 days", style={"color": data.NEUTRAL_SUB})],
                  style={"fontSize": "13px", "marginTop": "2px"}),
        html.Div(f"{int(total_l30_cases):,} files with a posting in window",
                  style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "marginTop": "6px"}),
        html.Div("REAL DATA — SubroReports.rpt.RecoveriesbyLOBTableau",
                  style={"fontSize": "10px", "color": data.POS_COLOR, "marginTop": "8px", "fontWeight": 600}),
        dcc.Link(html.Button("Drill into Subrogation ›", style={
            "marginTop": "12px", "background": PILLAR_ACCENT["Subrogation"], "color": "white", "border": "none",
            "borderRadius": "6px", "padding": "8px 12px", "cursor": "pointer", "fontSize": "12px"}),
            href=f"{ROOT}drill?pillar=Subrogation"),
    ], accent=PILLAR_ACCENT["Subrogation"])

    # --- COB card (real, but all-time invoiced, no date) ---
    cob_card = card_shell([
        html.Div("COB", style={"fontSize": "12px", "color": data.NEUTRAL_SUB,
                                "fontWeight": 700, "letterSpacing": "0.05em"}),
        html.Div(m.fmt_millions(COB_SUMMARY["total_invoiced"]), style={"fontSize": "30px", "fontWeight": 700}),
        html.Div("ALL-TIME INVOICED — not a 30-day figure", style={"fontSize": "12px", "color": "#B45309", "fontWeight": 600}),
        html.Div(f"{COB_SUMMARY['n_investigations']:,} investigations on record",
                  style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "marginTop": "6px"}),
        html.Div("REAL DATA, but no date field exists in this source — see caveat on drill page",
                  style={"fontSize": "10px", "color": "#B45309", "marginTop": "8px", "fontWeight": 600}),
        dcc.Link(html.Button("View COB detail ›", style={
            "marginTop": "12px", "background": PILLAR_ACCENT["COB"], "color": "white", "border": "none",
            "borderRadius": "6px", "padding": "8px 12px", "cursor": "pointer", "fontSize": "12px"}),
            href=f"{ROOT}drill?pillar=COB"),
    ], accent=PILLAR_ACCENT["COB"])

    # --- Pharma card (no data at all) ---
    pharma_card = card_shell([
        html.Div("PHARMA", style={"fontSize": "12px", "color": data.NEUTRAL_SUB,
                                   "fontWeight": 700, "letterSpacing": "0.05em"}),
        html.Div("No data", style={"fontSize": "30px", "fontWeight": 700, "color": data.NEUTRAL_SUB}),
        html.Div("No reachable source in Machinify Studio", style={"fontSize": "12px", "color": "#B45309", "fontWeight": 600}),
        html.Div("RXP / RxTra are not registered as a Studio data source in any project this "
                 "session has access to (design doc §2.1, open question #1).",
                  style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "marginTop": "6px"}),
        dcc.Link(html.Button("View detail ›", style={
            "marginTop": "12px", "background": "#9CA3AF", "color": "white", "border": "none",
            "borderRadius": "6px", "padding": "8px 12px", "cursor": "pointer", "fontSize": "12px"}),
            href=f"{ROOT}drill?pillar=Pharma"),
    ], accent="#9CA3AF")

    return html.Div([
        html.Div([
            html.H2("RPS RECOVERIES — REAL DATA ONLY", style={"margin": 0, "fontWeight": 700}),
            html.Div(f"Subrogation data through: {ANCHOR.strftime('%b %d, %Y')}",
                      style={"color": data.NEUTRAL_SUB, "fontSize": "13px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline",
                  "borderBottom": f"2px solid {data.NEUTRAL_GRID}", "paddingBottom": "10px", "marginBottom": "18px"}),

        real_data_note(
            "Every number on this dashboard is pulled live from Machinify Studio. Subrogation has a "
            "confirmed dated $-recovered source and is shown as a full 30-day trend. COB has a real "
            "dollar figure but it's an all-time invoiced total with no date field — shown as such, not "
            "smoothed into a fake trend. Pharma has no reachable source at all, so it shows nothing. "
            "Nothing here is synthetic or fabricated."
        ),

        card_shell([
            html.Div("SUBROGATION $ RECOVERED · LAST 30 DAYS", style={"fontSize": "12px", "color": data.NEUTRAL_SUB,
                                                                        "fontWeight": 700, "letterSpacing": "0.05em"}),
            html.Div([
                html.Span(m.fmt_millions(total_l30), style={"fontSize": "42px", "fontWeight": 700, "marginRight": "14px"}),
                delta_span(total_delta),
                html.Span(f"  vs prior 30 days ({m.fmt_millions(total_p30)})", style={"color": data.NEUTRAL_SUB, "fontSize": "14px"}),
            ]),
            html.Div([
                html.Span(f"{(ANCHOR - pd.Timedelta(days=29)).strftime('%b %d')} – {ANCHOR.strftime('%b %d, %Y')}   ·   ",
                          style={"color": data.NEUTRAL_SUB, "fontSize": "12px"}),
                html.Span(f"Last complete month ({lc_label}): {m.fmt_millions(lc_amt)}   ·   ",
                          style={"color": data.NEUTRAL_SUB, "fontSize": "12px"}),
                html.Span(f"{n_bdays} business days, {n_batch} batch day(s) in window",
                          style={"color": data.NEUTRAL_SUB, "fontSize": "12px"}),
            ], style={"marginTop": "4px"}),
        ], style={"marginBottom": "16px"}, accent=PILLAR_ACCENT["Subrogation"]),

        html.Div([subro_card, cob_card, pharma_card], style={"display": "flex", "gap": "16px", "marginBottom": "18px"}),

        card_shell([
            html.Div("SUBROGATION — DAILY $ RECOVERED, LAST 30 DAYS (real data)",
                      style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "fontWeight": 700, "marginBottom": "6px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div([
                dcc.Link(html.Button("Daily / monthly trend ›", style=btn_style()), href=f"{ROOT}trend?mode=daily"),
            ], style={"display": "flex", "gap": "10px", "justifyContent": "flex-end"}),
        ]),
    ], style=BASE_STYLE)


# ============================================================ PAGE 2 =====
def page_drill(pillar):
    if pillar == "Subrogation":
        return page_drill_subro()
    if pillar == "COB":
        return page_drill_cob()
    return page_drill_pharma()


def page_drill_subro():
    pillar = "Subrogation"
    pf = FACT[FACT["Pillar"] == pillar]
    pl30, pcases = m.l30(FACT, ANCHOR, Pillar=pillar)
    pp30, _ = m.p30(FACT, ANCHOR, Pillar=pillar)
    pdelta = m.delta_pct(pl30, pp30)

    units = ["LRU", "RCU", "SRU"]
    unit_cards = []
    for u in units:
        ul30, ucases = m.l30(FACT, ANCHOR, Pillar=pillar, UnitKey=u)
        up30, _ = m.p30(FACT, ANCHOR, Pillar=pillar, UnitKey=u)
        udelta = m.delta_pct(ul30, up30)
        ushare = ul30 / pl30 if pl30 else 0
        unit_cards.append(html.Div(card_shell([
            html.Div(u, style={"fontWeight": 700, "fontSize": "14px"}),
            html.Div(m.fmt_millions(ul30), style={"fontSize": "24px", "fontWeight": 700}),
            html.Div([delta_span(udelta), html.Span(f"  ·  {ushare*100:.0f}%", style={"color": data.NEUTRAL_SUB})],
                      style={"fontSize": "12px"}),
            html.Div(f"{int(ucases):,} files", style={"fontSize": "11px", "color": data.NEUTRAL_SUB}),
        ], accent=PILLAR_ACCENT["Subrogation"]), style={"flex": "1"}))

    clients = sorted(FILES[FILES["Pillar"] == pillar]["ClientName"].dropna().unique().tolist())

    table = dash_table.DataTable(
        id="drill-files-table",
        columns=[
            {"name": "File", "id": "CaseId"}, {"name": "Client", "id": "ClientName"},
            {"name": "Parent", "id": "ParentName"}, {"name": "Unit", "id": "UnitKey"},
            {"name": "Recovered (60d)", "id": "RecentAmount"}, {"name": "Last Recovery", "id": "LastDate"},
        ],
        data=build_top_files_records(pillar),
        style_as_list_view=True,
        style_cell={"fontFamily": FONT, "fontSize": "12px", "padding": "6px 10px", "textAlign": "left"},
        style_header={"fontWeight": 700, "background": "#F9FAFB", "borderBottom": f"2px solid {data.NEUTRAL_GRID}"},
        style_table={"maxHeight": "420px", "overflowY": "auto"},
        page_size=25,
    )

    daily_by_unit = pf[pf["RecoveryDate"] >= ANCHOR - pd.Timedelta(days=29)].groupby(
        ["RecoveryDate", "UnitKey"], as_index=False)["GrossAmount"].sum()
    idx = pd.date_range(ANCHOR - pd.Timedelta(days=29), ANCHOR, freq="D")
    pv2 = daily_by_unit.pivot(index="RecoveryDate", columns="UnitKey", values="GrossAmount").reindex(idx).fillna(0)
    fig2 = go.Figure()
    for u in units:
        if u in pv2.columns:
            fig2.add_bar(x=idx, y=pv2[u], name=u)
    fig2.update_layout(barmode="group", template="plotly_white", height=180, font=dict(family=FONT, size=10),
                        margin=dict(l=40, r=10, t=10, b=20), legend=dict(orientation="h", y=-0.35),
                        yaxis=dict(tickprefix="$", tickformat=",.2s", gridcolor=data.NEUTRAL_GRID),
                        xaxis=dict(gridcolor=data.NEUTRAL_GRID))

    return html.Div([
        html.Div([
            dcc.Link("‹ Back", href=ROOT, style={"color": data.NEUTRAL_SUB, "textDecoration": "none"}),
            html.Span("  SUBROGATION · RECOVERED LAST 30 DAYS", style={"fontWeight": 700, "color": PILLAR_ACCENT["Subrogation"]}),
        ], style={"marginBottom": "6px"}),

        real_data_note("Real data: SubroReports.rpt.RecoveriesbyLOBTableau, pulled via Machinify Studio project 0010z."),

        card_shell([
            html.Span(m.fmt_millions(pl30), style={"fontSize": "28px", "fontWeight": 700, "marginRight": "12px"}),
            delta_span(pdelta),
            html.Span(f"  vs prior 30 days ({m.fmt_millions(pp30)})  ·  {int(pcases):,} files",
                      style={"color": data.NEUTRAL_SUB, "fontSize": "13px"}),
        ], style={"marginBottom": "16px"}),

        html.Div(unit_cards, style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

        dcc.Store(id="drill-pillar", data=pillar),
        html.Div([
            dcc.Dropdown(id="drill-client", options=[{"label": c, "value": c} for c in clients],
                         placeholder="Filter by client (All clients)", clearable=True,
                         style={"width": "300px", "fontSize": "12px"}),
        ], style={"marginBottom": "14px"}),

        card_shell([
            html.Div("TOP FILES BY $ RECOVERED (LAST 60 DAYS)",
                      style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "fontWeight": 700, "marginBottom": "8px"}),
            table,
        ], style={"marginBottom": "16px"}),

        card_shell([
            html.Div("RECOVERED BY UNIT, DAILY (L30)",
                      style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "fontWeight": 700, "marginBottom": "4px"}),
            dcc.Graph(figure=fig2, config={"displayModeBar": False}),
        ]),
    ], style=BASE_STYLE)


def page_drill_cob():
    top = COB_BY_CLIENT.head(25).copy()
    fig = go.Figure(go.Bar(x=top["ClientCode"], y=top["total_invoiced"], marker_color=PILLAR_ACCENT["COB"]))
    fig.update_layout(template="plotly_white", height=380, font=dict(family=FONT, size=11),
                       margin=dict(l=50, r=10, t=10, b=80),
                       yaxis=dict(title="$ invoiced (all-time)", tickprefix="$", tickformat=",.2s",
                                  gridcolor=data.NEUTRAL_GRID),
                       xaxis=dict(tickangle=-45))

    tbl = top.copy()
    tbl["total_invoiced"] = tbl["total_invoiced"].map(m.fmt_millions)
    tbl["n_investigations"] = tbl["n_investigations"].map(lambda x: f"{x:,}")
    table = dash_table.DataTable(
        columns=[{"name": "Client Code", "id": "ClientCode"},
                 {"name": "Investigations", "id": "n_investigations"},
                 {"name": "Invoiced $ (all-time)", "id": "total_invoiced"}],
        data=tbl.to_dict("records"),
        style_as_list_view=True,
        style_cell={"fontFamily": FONT, "fontSize": "12px", "padding": "6px 10px"},
        style_header={"fontWeight": 700, "background": "#F9FAFB"},
        style_table={"maxHeight": "420px", "overflowY": "auto"},
        page_size=25,
    )

    return html.Div([
        html.Div([
            dcc.Link("‹ Back", href=ROOT, style={"color": data.NEUTRAL_SUB, "textDecoration": "none"}),
            html.Span("  COB · INVOICED, ALL-TIME (no date field available)",
                      style={"fontWeight": 700, "color": PILLAR_ACCENT["COB"]}),
        ], style={"marginBottom": "6px"}),

        real_data_note(
            "Real data, but limited: overlap_detection.InvestigationInvoices carries a real dollar "
            "amount per SmartII investigation (771,151 investigations, $1.65B total) with NO date "
            "column at all — it cannot show a 30-day trend. Client codes came from a join to "
            "CEMOverlapsAndSmartIIResults (also real, PHI-free at this grain). Separately, I registered "
            "and checked 8 other candidate tables that DO have the right shape for a dated posted-recovery "
            "figure (OverpaymentReceivedAmount + PayDate/ReceivedDate, across 7 Aetna HMO/HRP MSP audit "
            "'Final' tables plus a Cigna Professional Claims extract) — every one of them has that column "
            "populated as NULL for every row. No dated $-recovered figure for COB exists in any Studio "
            "project this session can reach. This matches design doc open question #1."
        ),

        card_shell([
            html.Span(m.fmt_millions(COB_SUMMARY["total_invoiced"]), style={"fontSize": "28px", "fontWeight": 700, "marginRight": "12px"}),
            html.Span(f"invoiced across {COB_SUMMARY['n_investigations']:,} investigations "
                      f"({COB_SUMMARY['n_positive']:,} with a positive amount)",
                      style={"color": data.NEUTRAL_SUB, "fontSize": "13px"}),
        ], style={"marginBottom": "16px"}, accent=PILLAR_ACCENT["COB"]),

        card_shell([
            html.Div("TOP 25 CLIENTS BY INVOICED $ (ALL-TIME, REAL DATA)",
                      style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "fontWeight": 700, "marginBottom": "6px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ], style={"marginBottom": "16px"}),

        card_shell([table]),
    ], style=BASE_STYLE)


def page_drill_pharma():
    return html.Div([
        html.Div([
            dcc.Link("‹ Back", href=ROOT, style={"color": data.NEUTRAL_SUB, "textDecoration": "none"}),
            html.Span("  PHARMA · NO DATA", style={"fontWeight": 700, "color": "#9CA3AF"}),
        ], style={"marginBottom": "6px"}),
        card_shell([
            html.Div("No reachable data source", style={"fontSize": "20px", "fontWeight": 700, "marginBottom": "10px"}),
            html.P("This session has Machinify Studio access to exactly two projects: "
                   "Internal_RPS_Subro_Assistant (0010z) and COB Overlap Pilot (0012k). Neither has "
                   "RXP, RxTra, or any other pharmacy-recovery system registered as a data source. "
                   "No table, column, or extract with a Pharma $-recovered figure — real or otherwise "
                   "— is reachable from here."),
            html.P("Per the design doc (§2.1, open question #1), getting real Pharma data requires "
                   "either read access to SQLUserRx (RXP/RxTra) provisioned for a pipeline account, "
                   "or an extract from Pharmacy AppDev (Matt Weirich) / Brian Sharp. Nothing on this "
                   "page is a placeholder for a number — there simply is no number to show."),
        ]),
    ], style=BASE_STYLE)


# ============================================================ PAGE 3 =====
def page_trend(mode="daily"):
    daily, idx = m.daily_series(FACT, ANCHOR, days=30, Pillar="Subrogation")
    pv = daily.pivot(index="RecoveryDate", columns="Pillar", values="GrossAmount").reindex(idx).fillna(0)
    fig_daily = go.Figure()
    fig_daily.add_bar(x=idx, y=pv.get("Subrogation", pd.Series(0, index=idx)), name="Subrogation",
                       marker_color=PILLAR_ACCENT["Subrogation"])
    fig_daily.update_layout(barmode="stack", template="plotly_white", height=320, font=dict(family=FONT, size=11),
                             margin=dict(l=50, r=10, t=10, b=30), legend=dict(orientation="h", y=-0.2),
                             yaxis=dict(title="$", tickprefix="$", tickformat=",.2s", gridcolor=data.NEUTRAL_GRID),
                             xaxis=dict(gridcolor=data.NEUTRAL_GRID))

    monthly = m.monthly_series(FACT, ANCHOR, months=12)
    monthly = monthly[monthly["Pillar"] == "Subrogation"]
    fig_month = go.Figure(go.Bar(x=monthly["YearMonth"], y=monthly["GrossAmount"], name="Subrogation",
                                  marker_color=PILLAR_ACCENT["Subrogation"]))
    fig_month.update_layout(template="plotly_white", height=320, font=dict(family=FONT, size=11),
                             margin=dict(l=50, r=10, t=10, b=30), legend=dict(orientation="h", y=-0.2),
                             yaxis=dict(title="$", tickprefix="$", tickformat=",.2s", gridcolor=data.NEUTRAL_GRID),
                             xaxis=dict(gridcolor=data.NEUTRAL_GRID))

    daily_tab = pv.copy()
    daily_tab["Total"] = daily_tab.sum(axis=1)
    daily_tab.index.name = "RecoveryDate"
    daily_tab = daily_tab.reset_index()
    daily_tab["Date"] = pd.to_datetime(daily_tab["RecoveryDate"]).dt.strftime("%Y-%m-%d")
    daily_tab = daily_tab.drop(columns=["RecoveryDate"])
    daily_tab = daily_tab[["Date"] + [c for c in daily_tab.columns if c != "Date"]]
    for c in daily_tab.columns:
        if c != "Date":
            daily_tab[c] = daily_tab[c].map(m.fmt_millions)

    month_tab = monthly[["YearMonth", "GrossAmount"]].rename(columns={"GrossAmount": "Subrogation"})
    month_tab["Subrogation"] = month_tab["Subrogation"].map(m.fmt_millions)

    is_daily = mode != "monthly"

    return html.Div([
        html.Div([
            dcc.Link("‹ Back", href=ROOT, style={"color": data.NEUTRAL_SUB, "textDecoration": "none"}),
            html.Span("  SUBROGATION RECOVERY TREND (real data — COB/Pharma have no dated series to trend)",
                      style={"fontWeight": 700, "marginLeft": "6px"}),
            html.Div([
                dcc.Link(html.Button("Daily · 30d", style=toggle_style(is_daily)), href=f"{ROOT}trend?mode=daily"),
                dcc.Link(html.Button("Monthly · 12m", style=toggle_style(not is_daily)), href=f"{ROOT}trend?mode=monthly"),
            ], style={"float": "right", "display": "flex", "gap": "8px"}),
        ], style={"marginBottom": "16px", "overflow": "hidden"}),

        card_shell([
            html.Div("$ RECOVERED PER DAY (last 30 days)" if is_daily else "$ RECOVERED PER MONTH (last 12 complete months)",
                      style={"fontSize": "12px", "color": data.NEUTRAL_SUB, "fontWeight": 700, "marginBottom": "6px"}),
            dcc.Graph(figure=fig_daily if is_daily else fig_month, config={"displayModeBar": False}),
        ], style={"marginBottom": "16px"}),

        card_shell([
            dash_table.DataTable(
                columns=[{"name": c, "id": c} for c in (daily_tab.columns if is_daily else month_tab.columns)],
                data=(daily_tab if is_daily else month_tab).to_dict("records"),
                style_as_list_view=True,
                style_cell={"fontFamily": FONT, "fontSize": "12px", "padding": "6px 10px"},
                style_header={"fontWeight": 700, "background": "#F9FAFB"},
                style_table={"maxHeight": "360px", "overflowY": "auto"},
                page_size=15, sort_action="native",
            ),
        ]),
    ], style=BASE_STYLE)


# ============================================================ ROUTING ====
app.layout = html.Div([dcc.Location(id="url", refresh=False), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), Input("url", "pathname"), Input("url", "search"))
def route(pathname, search):
    qs = up.parse_qs((search or "").lstrip("?"))
    path = pathname or "/"
    if path.rstrip("/").endswith("/drill"):
        pillar = up.unquote(qs.get("pillar", ["Subrogation"])[0])
        return page_drill(pillar)
    if path.rstrip("/").endswith("/trend"):
        mode = qs.get("mode", ["daily"])[0]
        return page_trend(mode)
    return page_landing()


@app.callback(Output("drill-files-table", "data"), Input("drill-client", "value"),
              State("drill-pillar", "data"))
def filter_drill_table(client, pillar):
    return build_top_files_records(pillar or "Subrogation", client)


if __name__ == "__main__":
    print(f"Serving at prefix: {REQ_PREFIX}")
    app.run(host="0.0.0.0", port=8050, debug=False)
