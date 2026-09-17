import studio_cob as studio, json

p = studio.proj()
out = open('probe_charts.txt', 'w')
def w(s): out.write(s+'\n'); out.flush()

for method_name in ['listCharts', 'listDashboards', 'listPredictions', 'listTasks', 'listModels']:
    try:
        m = getattr(p, method_name)
        items = m(quiet=True)
        items = list(items)
        w(f'== {method_name}: n={len(items)} ==')
        for it in items[:200]:
            s = str(it)
            w('   ' + s[:400])
    except AttributeError:
        w(f'== {method_name}: not available ==')
    except Exception as e:
        w(f'== {method_name}: ERR {str(e)[:300]} ==')
w('DONE')
out.close()
