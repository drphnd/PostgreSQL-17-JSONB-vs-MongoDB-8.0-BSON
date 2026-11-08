#!/usr/bin/env python3
"""
extract_decomposition.py
Memecah latensi per checkpoint menjadi: waktu tunggu pool (pool_wait_ms),
waktu eksekusi query di handler (db_exec_ms), dan sisanya (antrean/serialisasi/HTTP di luar handler).
Memakai metrik k6 yang SUDAH direkam skrip k6/test_read_*.js (Trend pool_wait_ms, db_exec_ms).
Pemakaian: python3 scripts/extract_decomposition.py FILE.ndjson[.gz] --label scn1_run11
Hasil: decomposition_<label>.csv
"""
import argparse, gzip, json
from collections import defaultdict

def pct(s, p):
    k = (len(s) - 1) * p / 100; f = int(k); c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)

ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--label', default='result'); ap.add_argument('--by-op', action='store_true', help='pisahkan read/update (hanya latensi total)')
a = ap.parse_args()
M = {'http_req_duration': 'lat', 'pool_wait_ms': 'pool', 'db_exec_ms': 'exec'}
vals = defaultdict(lambda: defaultdict(list))
op = gzip.open if a.file.endswith('.gz') else open
with op(a.file, 'rt') as f:
    for line in f:
        if '"type":"Point"' not in line:
            continue
        key = None
        for m, k in M.items():
            if '"metric":"%s"' % m in line:
                key = k; break
        if key is None:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = r['data'].get('tags', {})
        v = r['data']['value']
        cp = t.get('checkpoint') or t.get('scenario') or 'unknown'
        if a.by_op and t.get('op'):
            cp = cp + ':' + t['op']   # beban campuran: pisahkan read dan update
        if key == 'lat':
            st = t.get('status', '')
            if st == '0' or (st.isdigit() and int(st) >= 400) or v < 0:
                continue
        vals[cp][key].append(v)

cols = ['checkpoint', 'n_lat', 'n_hdr', 'mean_lat', 'mean_pool', 'mean_exec', 'mean_rest',
        'p50_lat', 'p99_lat', 'p50_pool', 'p99_pool', 'p50_exec', 'p99_exec']
rows = []
for cp in sorted(vals):
    d = vals[cp]
    lat, pool, ex = sorted(d['lat']), sorted(d['pool']), sorted(d['exec'])
    if not lat:
        continue
    mean = lambda x: sum(x) / len(x) if x else float('nan')
    ml, mp, me = mean(lat), mean(pool), mean(ex)
    p = lambda s, q: pct(s, q) if s else float('nan')
    rows.append([cp, len(lat), len(ex), ml, mp, me, ml - mp - me,
                 p(lat, 50), p(lat, 99), p(pool, 50), p(pool, 99), p(ex, 50), p(ex, 99)])
print(','.join(cols))
with open('decomposition_%s.csv' % a.label, 'w') as o:
    o.write(','.join(cols) + '\n')
    for r in rows:
        s = [r[0]] + ['%.2f' % x if isinstance(x, float) else str(x) for x in r[1:]]
        print(','.join(s)); o.write(','.join(s) + '\n')
print('Disimpan: decomposition_%s.csv' % a.label)
