"""Direct SQL Server access to the Rawlings COB servers from JupyterHub (no Studio).

Credentials live in ~/sql_access.txt (chmod 600, never committed). Format is free-form:
a token starting with 'use' (username label, any spelling) followed by the login,
and a token starting with 'pass' followed by the password. Domain logins use DOMAIN\\user.

    import act_conn
    df = act_conn.q("SELECT TOP 5 * FROM sys.tables")                # ACT on TRGACAP3
    df = act_conn.q("SELECT ...", db='SmartII')                       # other DBs on same server
    df = act_conn.q("SELECT ...", host=act_conn.HOSTS['PIDCOB'], db='DMGMining')
"""
import os, pymssql
import pandas as pd

HOSTS = {'TRGACAP3': '192.168.251.12', 'PIDCOB': '192.168.251.18', 'TRGDMGREP1': '192.168.251.19'}
CREDS = os.path.expanduser('~/sql_access.txt')

def creds(path=CREDS):
    toks = open(path).read().split()
    user = pwd = None
    for i, t in enumerate(toks):
        low = t.lower().rstrip(':=')
        if low.startswith('use') and user is None and i + 1 < len(toks):
            user = toks[i + 1]
        elif low.startswith('pass') and pwd is None and i + 1 < len(toks):
            pwd = toks[i + 1]
    if not user or not pwd:
        raise ValueError(f'could not parse username/password from {path}')
    return user, pwd

def connect(db='ACT', host=HOSTS['TRGACAP3'], login_timeout=60):
    user, pwd = creds()
    return pymssql.connect(server=host, user=user, password=pwd, database=db,
                           login_timeout=login_timeout, timeout=0)

def q(sql, db='ACT', host=HOSTS['TRGACAP3']):
    """Run a SELECT and return a DataFrame."""
    with connect(db=db, host=host) as c:
        return pd.read_sql(sql, c)
