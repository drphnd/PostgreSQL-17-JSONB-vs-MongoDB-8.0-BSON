#!/usr/bin/env python3
"""
monitor_api.py
Mencatat CPU proses API (uvicorn), proses k6, dan CPU total host setiap N detik.
Pemakaian: python3 scripts/monitor_api.py out.csv [interval_detik]   (hentikan dengan kill)
CPU per proses: 100% = satu core penuh. Satu worker uvicorn ~100% berarti event loop jenuh.
"""
import csv, sys, time
import psutil

out = sys.argv[1]; iv = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
def find():
    api, k6 = [], []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
            if ('python' in (p.info['name'] or '') or 'uvicorn' in (p.info['name'] or '')) and 'uvicorn' in cl and 'app.main' in cl: api.append(p)
            elif p.info['name'] == 'k6': k6.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return api, k6
def cpu(ps):
    t = 0.0
    for p in ps:
        try: t += p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return t
def rss(ps):
    t = 0.0
    for p in ps:
        try: t += p.memory_info().rss / 1048576
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return t
api, k6 = find(); cpu(api); cpu(k6); psutil.cpu_percent(None)
with open(out, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['timestamp', 'api_cpu_percent', 'api_rss_mib', 'k6_cpu_percent', 'host_cpu_percent'])
    while True:
        time.sleep(iv)
        if not api or any(not p.is_running() for p in api): api = find()[0]; cpu(api)
        if not k6 or any(not p.is_running() for p in k6): k6 = find()[1]; cpu(k6)
        w.writerow([time.strftime('%Y-%m-%dT%H:%M:%S'), '%.1f' % cpu(api), '%.1f' % rss(api), '%.1f' % cpu(k6), '%.1f' % psutil.cpu_percent(None)])
        f.flush()
