#!/usr/bin/env bash
# Pemakaian: bash scripts/run_mixed_rerun.sh postgres|mongo N
set -u
cd ~/Riset_TA_Database
DB="${1:?postgres|mongo}"; N="${2:?nomor run}"
RAW="mixed_${DB}_run${N}.ndjson"; RES="mixed_${DB}_resources_run${N}.csv"; HB="hb_mixed_${DB}_run${N}.log"
for f in "$RAW" "$RAW.gz" "$RES" "$HB"; do [ -s "$f" ] && { echo "ABORT: $f sudah ada"; exit 1; }; done
python3 scripts/reset_environment.py --size full || { echo "ABORT: reset gagal"; exit 1; }
curl -s -X POST http://localhost:8000/reload; echo
curl -s http://localhost:8000/health | grep -q pg_ids || { echo "ABORT: bukan app.main:app"; exit 1; }
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "http://localhost:8000/update/${DB}" -H "Content-Type: application/json" -d '{"index":100,"wifi_value":"free"}')
[ "$CODE" = "200" ] || { echo "ABORT: update $DB mengembalikan $CODE"; exit 1; }
curl -s -o /dev/null "http://localhost:8000/read/${DB}?mode=nested"
pkill -f hb.py 2>/dev/null
python3 scripts/hb.py > "$HB" & HB_PID=$!
bash scripts/monitor_resources.sh "$RES" & MON_PID=$!
k6 run --quiet -e REQUEST_TIMEOUT=60s -e DATA_SIZE=full -e READ_RATIO=0.8 --out json="$RAW" "k6/test_mixed_${DB}.js"
kill $MON_PID $HB_PID 2>/dev/null
python3 scripts/extract_mixed_results.py "$RAW" --label "scn_mixed_${DB}_run${N}"
python3 scripts/hb_gaps.py "$HB"
jq -r 'select(.type=="Point" and .metric=="http_reqs") | [.data.tags.name,.data.tags.status] | @tsv' "$RAW" | sort | uniq -c
gzip -f "$RAW"
