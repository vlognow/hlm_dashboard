import json, time, studio_cob as studio
out = open('probe_dmg_2.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
t = time.time()
d = studio.q("""
SELECT TABLE_SCHEMA, TABLE_NAME, concat_ws(', ', collect_list(COLUMN_NAME)) cols, COUNT(*) n_cols
FROM `DMGMining.information_schema.columns`
WHERE TABLE_SCHEMA IN ('productionreport','RetroTerm','compliance','CenteneRetro','standardized','Audits','ClientPerformanceModel','POF','FrontrunnerTrack','AetnaRxCompliance')
GROUP BY TABLE_SCHEMA, TABLE_NAME ORDER BY TABLE_SCHEMA, TABLE_NAME LIMIT 400
""", timeout=1500, retries=1)
d.to_csv('dmg_small_schemas.csv', index=False)
w(f'rows={len(d)} ({time.time()-t:.0f}s)')
for _, r in d.iterrows():
    w(f"{r['TABLE_SCHEMA']}.{r['TABLE_NAME']} ({r['n_cols']}): {r['cols'][:220]}")
w('DONE'); out.close()
