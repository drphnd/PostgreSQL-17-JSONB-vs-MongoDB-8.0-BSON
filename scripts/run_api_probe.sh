#!/usr/bin/env bash
# Pemakaian: bash scripts/run_api_probe.sh postgres|mongo N
# Sama dengan run_scn1_rerun.sh / run_scn2_rerun.sh, tetapi hanya 256 dan 512 VU (SHORT_MODE=1)
# dan ditambah pencatatan CPU proses API + k6 + host. Berkas lama tidak ditimpa.
set -u
cd ~/Riset_TA_Database
DB="${1:?postgres|mongo}"; N="${2:?nomor run}"
RAW="probe_${DB}_run${N}.ndjson"; RES="probe_${DB}_resources_run${N}.csv"; APIC="probe_${DB}_api_cpu_run${N}.csv"; HB="hb_probe_${DB}_run${N}.log"
for f in "$RAW" "$RAW.gz" "$RES" "$APIC" "$HB"; do [ -s "$f" ] && { echo "ABORT: $f sudah ada"; exit 1; }; done
python3 scripts/reset_environment.py --size full || { echo "ABORT: reset gagal"; exit 1; }
curl -s -X POST http://localhost:8000/reload; echo
curl -s http://localhost:8000/health | grep -q pg_ids || { echo "ABORT: bukan app.main:app"; exit 1; }
CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/read/${DB}?mode=nested")
[ "$CODE" = "200" ] || { echo "ABORT: API mengembalikan $CODE"; exit 1; }
pkill -f hb.py 2>/dev/null
python3 scripts/hb.py > "$HB" & HB_PID=$!
bash scripts/monitor_resources.sh "$RES" & MON_PID=$!
python3 scripts/monitor_api.py "$APIC" 5 & API_PID=$!
echo "k6 mulai $(date)"
k6 run --quiet -e SHORT_MODE=1 -e REQUEST_TIMEOUT=60s -e QUERY_MODE=nested -e DATA_SIZE=full --out json="$RAW" "k6/test_read_${DB}.js"
echo "k6 selesai $(date)"
kill $MON_PID $HB_PID $API_PID 2>/dev/null
python3 scripts/extract_results.py "$RAW" --label "probe_${DB}_run${N}" --resources_csv "$RES"
python3 scripts/extract_decomposition.py "$RAW" --label "probe_${DB}_run${N}"
gzip -f "$RAW"
