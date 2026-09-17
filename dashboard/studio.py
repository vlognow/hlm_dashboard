"""Thin helper: run SQL against the Studio project that fronts TRGDMGREP1.

Studio's custom-SQL endpoint is Spark-SQL flavoured: backtick-quote registered
table names (`Subro_SRS.dbo.files`), use LIMIT not TOP, rand() not NEWID().
Every call is slow (minutes), so callers should run in background jobs.
"""
import os, json, time
import pandas as pd
from machinify.session import Session

CONF = os.path.expanduser('~/~.mch.prod.yam')
PROJECT = '0010z'
_sess = None; _proj = None

def proj():
    global _sess, _proj
    if _proj is None:
        _sess = Session(conf=CONF)
        _proj = _sess.getProject(PROJECT)
    return _proj

def q(sql, timeout=1800, quiet=True, retries=2):
    """Run a SELECT and return a DataFrame (columns from response schema)."""
    last = None
    for attempt in range(retries + 1):
        try:
            resp = proj().sqlQuery(sql, quiet=quiet, timeout=timeout, raw=True)
            return _to_df(resp)
        except Exception as e:  # transient gateway errors are common
            last = e
            if attempt < retries:
                time.sleep(20 * (attempt + 1))
    raise last

def _to_df(resp):
    if hasattr(resp, 'to_dict'):
        resp = resp.to_dict()
    if isinstance(resp, str):
        resp = json.loads(resp)
    if isinstance(resp, dict) and 'schema' in resp:
        cols = [c['name'] for c in resp['schema']]
        rows = resp.get('rows') or resp.get('data') or []
        return pd.DataFrame(rows, columns=cols)
    raise ValueError(f'unexpected response shape: {str(resp)[:300]}')

def ep(col):
    """Studio returns dates as epoch seconds (or ms for timestamps). Convert."""
    s = pd.to_numeric(col, errors='coerce')
    # heuristic: > 1e11 means milliseconds
    ms = s.abs() > 1e11
    out = pd.to_datetime(s.where(~ms), unit='s', errors='coerce')
    out = out.fillna(pd.to_datetime(s.where(ms), unit='ms', errors='coerce'))
    return out
