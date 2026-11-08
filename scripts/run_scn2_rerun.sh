#!/usr/bin/env bash
# Pemakaian: bash scripts/run_scn2_rerun.sh 2     (angka = nomor run)
set -u
cd ~/Riset_TA_Database
N="${1:?beri nomor run, mis. 2}"
RAW="raw_scn2_read_mongo_run${N}.ndjson"
RES="raw_scn2_resources_run${N}.csv"
HB="hb_scn2_run${N}.log"
for f in "$RAW" "$RAW.gz" "$RES" "$HB"; do
  [ -e "$f" ] && [ -s "$f" ] && { echo "ABORT: $f sudah ada, tidak ditimpa"; exit 1; }
done

echo "[1] reset environment"
python3 scripts/reset_environment.py --size full || { echo "ABORT: reset gagal"; exit 1; }
curl -s -X POST http://localhost:8000/reload; echo

echo "[2] cek API"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/read/mongo?mode=nested")
[ "$CODE" = "200" ] || { echo "ABORT: API mengembalikan $CODE (harus 200). Nyalakan API dulu."; exit 1; }

echo "[3] heartbeat + sampler"
pkill -f hb.py 2>/dev/null
HBPY=$(ls hb.py scripts/hb.py 2>/dev/null | head -1)
if [ -n "$HBPY" ]; then python3 "$HBPY" > "$HB" & HB_PID=$!; fi
bash scripts/monitor_resources.sh "$RES" & MON_PID=$!

echo "[4] k6 mulai $(date)"
k6 run --quiet -e REQUEST_TIMEOUT=60s -e QUERY_MODE=nested -e DATA_SIZE=full --out json="$RAW" k6/test_read_mongo.js
echo "[4] k6 selesai $(date)"

kill $MON_PID ${HB_PID:-} 2>/dev/null
echo "[5] analisis"
python3 scripts/stall_p99.py "$RAW"
python3 scripts/extract_results.py "$RAW" --label "scn2_read_mongo_full_nested_run${N}" --resources_csv "$RES"
gzip -f "$RAW"
