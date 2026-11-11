"""Threshold scan on the endpoint-window panel.

Fig. 2(b) and the paper's claim that tightening the quota is free both rest on
this scan, so it is computed here rather than inside the plotting script.

Usage:  py -3.13 src\\e9_threshold.py
"""
import csv
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(ROOT, 'data', 'e1_panel.csv')
OUT = os.path.join(ROOT, 'data', 'e9_threshold.json')

TAUS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]


def main():
    rows = list(csv.DictReader(io.open(PANEL, encoding='utf-8')))
    by_role = {}
    for r in rows:
        by_role.setdefault(r['role'], []).append(float(r['rho']))

    n = {k: len(v) for k, v in by_role.items()}
    out = {'windows_s': 300, 'roles': n, 'scan': []}
    for t in TAUS:
        fp = sum(1 for x in by_role['client'] if x > t) / n['client']
        cap = sum(1 for x in by_role['service'] if x > t) / n['service']
        out['scan'].append({'tau': t, 'false_alarm': fp, 'capture': cap,
                            'quota': t / (1.0 - t)})
    # the quota rho0 that corresponds to tau is rho0 = tau/(1-tau): rho=tau means
    # S/(S+R)=tau, i.e. S/R = tau/(1-tau).  Reported for cross-reference with E1.
    out['note'] = ('false_alarm is the share of subscriber cells above tau, '
                   'capture the share of service cells above tau')
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(out, indent=1))
    for s in out['scan']:
        print('tau=%.2f  false_alarm=%.4f  capture=%.3f' %
              (s['tau'], s['false_alarm'], s['capture']))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
