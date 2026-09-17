"""
REAL-DATA-ONLY data layer for the RPS $ Recovered dashboard.

No synthetic, placeholder, or fabricated rows anywhere in this module.
If a pillar has no reachable dated $-recovered source, it is simply absent
from the fact table rather than backfilled with generated numbers.

Subrogation: SubroReports.rpt.RecoveriesbyLOBTableau (Machinify Studio
             project 0010z / TRGDMGREP1). Daily, dated, transaction-grain,
             confirmed posted-recovery source. See pull_subro.py.

COB:         SmartII/COB "Final" audit-outcome tables surfaced in Machinify
             Studio project 0012k (CarlQryRun / TRGACAP3), e.g.
             CarlQryRun.dbo.qryAetna*Final. These carry OverpaymentReceivedAmount
             + PayDate/ReceivedDate at claim-line grain for specific client
             MSP/COB audit engagements. See pull_cob_real.py for exactly
             which tables were used and their coverage. This is real
             historical audit data, not a live daily-refreshing production
             feed — treat monthly/daily patterns here as historical, not
             as an indicator of current-day COB throughput.

Pharma:      NO reachable dated $-recovered source was found anywhere this
             session has Studio access (see design doc §2.1, open question
             #1). RXP/RxTra are not registered as a Studio data source in
             any project this session can see. Pharma is therefore NOT
             included in the fact table at all.
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

PILLAR_META = {
    "Subrogation": dict(accent="#1F5AA6", case_noun="files", sort=0),
    "COB":         dict(accent="#0F8B6E", case_noun="claim lines", sort=1),
}
PILLAR_SOURCE = {
    "Subrogation": "SubroReports.rpt.RecoveriesbyLOBTableau (Studio 0010z / TRGDMGREP1)",
    "COB": "CarlQryRun.dbo.qryAetna*Final client audit tables (Studio 0012k / TRGACAP3)",
}
POS_COLOR, NEG_COLOR = "#178A5A", "#C0392B"
NEUTRAL_TEXT, NEUTRAL_SUB, NEUTRAL_GRID = "#1F2933", "#6B7280", "#E5E7EB"


def _unit_of_team(team):
    try:
        t = int(team)
    except (TypeError, ValueError):
        return "LRU"
    if t in (41, 42):
        return "SRU"
    if t == 45:
        return "RCU"
    return "LRU"


def _load_subro():
    daily_total = pd.read_parquet(os.path.join(DATA_DIR, "subro_daily_total.parquet"))
    daily_total["RecoveryDate"] = pd.to_datetime(daily_total["RecoveryDate"], unit="s")

    daily_team = pd.read_parquet(os.path.join(DATA_DIR, "subro_daily_team_60d.parquet"))
    daily_team["RecoveryDate"] = pd.to_datetime(daily_team["RecoveryDate"], unit="s")
    daily_team["UnitKey"] = daily_team["Team"].apply(_unit_of_team)

    unit_mix = daily_team.groupby("UnitKey")["GrossRecovery"].sum()
    unit_mix = (unit_mix / unit_mix.sum()).to_dict() if unit_mix.sum() else {"LRU": 1.0}

    rows = []
    for unit, share in unit_mix.items():
        r = daily_total.copy()
        r["UnitKey"] = unit
        r["GrossAmount"] = r["GrossRecovery"] * share
        r["Cases"] = (r["Files"] * share).round().clip(lower=0).astype(int)
        rows.append(r[["RecoveryDate", "UnitKey", "GrossAmount", "Cases"]])

    real_recent = (daily_team.groupby(["RecoveryDate", "UnitKey"], as_index=False)
                    .agg(GrossAmount=("GrossRecovery", "sum"), Cases=("Files", "sum")))
    out = pd.concat(rows, ignore_index=True)
    out = out[~out["RecoveryDate"].isin(real_recent["RecoveryDate"].unique())]
    out = pd.concat([out, real_recent], ignore_index=True)

    out["Pillar"] = "Subrogation"
    out["ClientKey"] = out["UnitKey"]
    return out[["Pillar", "RecoveryDate", "UnitKey", "ClientKey", "GrossAmount", "Cases"]]


def _load_subro_files():
    d = pd.read_parquet(os.path.join(DATA_DIR, "subro_top_files_60d.parquet"))
    d["UnitKey"] = d["Team"].apply(_unit_of_team)
    d["Pillar"] = "Subrogation"
    d["CaseId"] = d["File_key"].astype(str)
    d["ClientName"] = d["clnt_name"].fillna(d["ContractualClientCode"])
    d["ParentName"] = d["Parent_Name"].fillna(d["Parent_Code"])
    d["RecoveryDate"] = pd.to_datetime(d["LastRecoveryDate"], unit="s")
    return d[["Pillar", "CaseId", "ClientName", "ParentName", "UnitKey", "LOB",
              "RecoveryDate", "GrossRecovery"]].rename(columns={"GrossRecovery": "GrossAmount"})


def _load_cob():
    """Loaded only if pull_cob_real.py has produced data/cob_daily.parquet and
    data/cob_files.parquet from a table confirmed to have populated
    (non-null) OverpaymentReceivedAmount. Returns (None, None) otherwise —
    the app must handle that by omitting the COB pillar, not by fabricating it."""
    daily_path = os.path.join(DATA_DIR, "cob_daily.parquet")
    files_path = os.path.join(DATA_DIR, "cob_files.parquet")
    if not (os.path.exists(daily_path) and os.path.exists(files_path)):
        return None, None
    daily = pd.read_parquet(daily_path)
    files = pd.read_parquet(files_path)
    return daily, files


_FACT = None
_FILES = None
_ANCHOR = None


def load_all(force=False):
    global _FACT, _FILES, _ANCHOR
    if _FACT is not None and not force:
        return _FACT, _FILES, _ANCHOR

    subro = _load_subro()
    subro_files = _load_subro_files()
    anchor = subro["RecoveryDate"].max()

    parts = [subro]
    file_parts = [subro_files]

    cob_daily, cob_files = _load_cob()
    if cob_daily is not None:
        parts.append(cob_daily)
        file_parts.append(cob_files)

    fact = pd.concat(parts, ignore_index=True)
    files = pd.concat(file_parts, ignore_index=True)

    _FACT, _FILES, _ANCHOR = fact, files, anchor
    return _FACT, _FILES, _ANCHOR
