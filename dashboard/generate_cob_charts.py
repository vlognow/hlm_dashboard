"""COB (medical) exec charts from ACT.dbo.Remit pulls (cob_act_*.csv). Same visual system as the Subro/Rx charts."""
import os, json
import pandas as pd
import plotly.graph_objects as go

OUT = os.path.dirname(os.path.abspath(__file__))
GREEN, RED, GRAY, DARK, COB = "#178A5A", "#C0392B", "#9CA3AF", "#1F2933", "#7A3E9D"

def fmt_m(v): return f"${v/1e6:,.2f}M" if abs(v) >= 1e6 else f"${v/1e3:,.2f}K"
def fmt_pct(p): return ("+" if p >= 0 else "") + f"{p*100:.1f}%"
def lab(ym): return pd.Period(ym).strftime("%b %Y")

def build():
    m = pd.read_csv(os.path.join(OUT, "cob_act_monthly.csv"))
    months = sorted(m.ym.unique()); complete = months[:-1]; last12 = complete[-12:]
    s = m.set_index("ym")["applied"].reindex(last12)
    last, prev = complete[-1], complete[-2]
    summ = dict(month=last, current=float(s[last]), prior=float(s[prev]), mom=float((s[last]-s[prev])/s[prev]),
                high=float(s.max()), high_month=s.idxmax(), low=float(s.min()), low_month=s.idxmin(),
                t12=float(s.sum()), last12=last12, series={k: float(v) for k, v in s.items()},
                n_remits_last=int(m.set_index("ym").loc[last, "n_remits"]), n_claims_last=int(m.set_index("ym").loc[last, "n_claims"]),
                reversals_last=float(m.set_index("ym").loc[last, "reversals"]))
    cat = pd.read_csv(os.path.join(OUT, "cob_act_month_category.csv"))
    cli = pd.read_csv(os.path.join(OUT, "cob_act_month_client.csv"))
    def split(df, key):
        cur = df[df.ym == last].groupby(key)["applied"].sum()
        pv = df[df.ym == prev].groupby(key)["applied"].sum()
        t12 = df[df.ym.isin(last12)].groupby(key)["applied"].sum()
        out = pd.DataFrame({"current": cur, "prior": pv, "t12": t12}).fillna(0).sort_values("current", ascending=False)
        out["mom"] = (out.current - out.prior) / out.prior.where(out.prior != 0)
        return out
    return summ, split(cat, "category"), split(cli, "parent")

def chart_monthly(summ):
    x = [lab(k) for k in summ["last12"]]; y = [v/1e6 for v in summ["series"].values()]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=y, marker_color=COB, text=[f"${v:,.1f}M" for v in y], textposition="outside",
                         hovertemplate="%{x}: $%{y:,.2f}M<extra></extra>"))
    fig.update_yaxes(tickprefix="$", ticksuffix="M", showgrid=True, gridcolor="#EEF0F3", rangemode="tozero")
    fig.update_layout(template="plotly_white", height=460, width=1280, margin=dict(l=60, r=30, t=90, b=60),
                      font=dict(family="Segoe UI, Arial, sans-serif", size=12),
                      title=dict(text=f"COB (Medical) — Posted $ recovered per month, {lab(summ['last12'][0])} – {lab(summ['last12'][-1])}"
                                      f"<br><span style='font-size:12px;color:{GRAY}'>ACT.dbo.Remit, Payment Integrity book, AppliedAmt net of reversals</span>",
                                 x=0.02, font=dict(size=16, color=DARK)))
    p = os.path.join(OUT, "exec_chart_cob_monthly.png"); fig.write_image(p, scale=2); return p

def chart_category(cat, summ):
    c = cat[~cat.index.str.startswith("(")].head(8).iloc[::-1]
    fig = go.Figure(go.Bar(x=c.current/1e6, y=c.index, orientation="h", marker_color=COB,
                           text=[fmt_m(v) for v in c.current], textposition="outside"))
    fig.update_xaxes(tickprefix="$", ticksuffix="M", showgrid=True, gridcolor="#EEF0F3")
    fig.update_layout(template="plotly_white", height=420, width=1280, margin=dict(l=180, r=80, t=80, b=50),
                      font=dict(family="Segoe UI, Arial, sans-serif", size=12),
                      title=dict(text=f"COB (Medical) — By audit category, {lab(summ['month'])}", x=0.02, font=dict(size=16, color=DARK)))
    p = os.path.join(OUT, "exec_chart_cob_by_category.png"); fig.write_image(p, scale=2); return p

if __name__ == "__main__":
    summ, cat, cli = build()
    print(chart_monthly(summ)); print(chart_category(cat, summ))
    json.dump(dict(summary=summ, category=cat.reset_index().to_dict("records"), client=cli.reset_index().head(12).to_dict("records")),
              open(os.path.join(OUT, "cob_act_summary.json"), "w"), default=str, indent=1)
    print(f"{lab(summ['month'])}: {fmt_m(summ['current'])}  MoM {fmt_pct(summ['mom'])} (prior {fmt_m(summ['prior'])})  "
          f"12M high {fmt_m(summ['high'])} ({lab(summ['high_month'])}) low {fmt_m(summ['low'])} ({lab(summ['low_month'])})  T12 {fmt_m(summ['t12'])}")
    print(cat.head(10).to_string()); print(cli.head(10).to_string())
