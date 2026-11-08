import sys, json, collections
fn = sys.argv[1]
by = collections.defaultdict(list)
import gzip
for line in (gzip.open(fn,'rt') if fn.endswith('.gz') else open(fn)):
    if '"http_req_duration"' not in line:
        continue
    try:
        o = json.loads(line)
    except ValueError:
        continue
    if o.get("type") != "Point" or o.get("metric") != "http_req_duration":
        continue
    d = o["data"]
    if d["value"] < 0:
        continue
    by[d["tags"].get("checkpoint")].append((d["time"][:19], d["value"]))

def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int((len(v) + 1) * p) - 1)]

print("checkpoint   n        >5s(%)  P99_mentah  P99_tanpa_stall  dibuang  detik_stall")
for cp in sorted(by, key=lambda c: int(c.split("_")[1])):
    pts = by[cp]
    vu = int(cp.split("_")[1])
    thr = max(3, 0.5 * vu)
    slow = collections.Counter(s for s, v in pts if v > 3000)
    stall = {s for s, c in slow.items() if c >= thr}
    keep = [v for s, v in pts if not (s in stall and v > 3000)]
    n = len(pts)
    print(f"{cp:<12} {n:<8} {100*sum(v>5000 for _,v in pts)/n:6.2f}  {pct([v for _,v in pts],.99):10.1f}  {pct(keep,.99):14.1f}  {n-len(keep):7}  {len(stall):6}")