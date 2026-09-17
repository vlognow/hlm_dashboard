"""Run sql/act_cob_discovery.sql against ACT on TRGACAP3 via pymssql and save every
result set plus PRINT messages to sql/act_discovery_output.txt.

    python run_act_discovery.py [path/to/other.sql] [--db ACT] [--host 192.168.251.12]
"""
import sys, os, argparse, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import act_conn

ap = argparse.ArgumentParser()
ap.add_argument('sql', nargs='?', default=os.path.join(os.path.dirname(__file__), 'sql', 'act_cob_discovery.sql'))
ap.add_argument('--db', default='ACT'); ap.add_argument('--host', default=act_conn.HOSTS['TRGACAP3'])
ap.add_argument('--out', default=None)
a = ap.parse_args()
out_path = a.out or os.path.splitext(a.sql)[0].replace('_cob_discovery', '_discovery') + '_output.txt'

sql = open(a.sql).read()
# strip a leading USE <db>; the connection already selects the database
sql = '\n'.join(l for l in sql.splitlines() if not l.strip().upper().startswith('USE '))

out = open(out_path, 'w')
def w(s=''): out.write(s + '\n'); out.flush()
def msg_handler(msgstate, severity, srvname, procname, line, msgtext):
    w(f'[msg] {msgtext.decode() if isinstance(msgtext, bytes) else msgtext}')

t0 = time.time()
conn = act_conn.connect(db=a.db, host=a.host)
conn._conn.set_msghandler(msg_handler)
cur = conn.cursor()
w(f'# {a.sql} on {a.host}/{a.db} at {time.strftime("%Y-%m-%d %H:%M:%S")}')
cur.execute(sql)
n = 0
while True:
    if cur.description:
        n += 1
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        w(f'\n## result set {n}: {len(df)} rows')
        with pd.option_context('display.max_rows', 5000, 'display.max_columns', 200, 'display.width', 400, 'display.max_colwidth', 120):
            w(df.to_string(index=False) if len(df) else '(empty)')
    if not cur.nextset():
        break
w(f'\n# done in {time.time()-t0:.0f}s, {n} result sets')
out.close()
print(f'wrote {out_path} ({n} result sets, {time.time()-t0:.0f}s)')
