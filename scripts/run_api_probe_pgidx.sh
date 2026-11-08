#!/usr/bin/env bash
# OPSI B (sensitivitas): PostgreSQL dengan indeks ekspresi GABUNGAN pada tiga atribut nested,
# setara dengan indeks gabungan MongoDB. Hanya 256 dan 512 VU (SHORT_MODE=1), dengan pencatatan CPU API.
# Pemakaian: bash scripts/run_api_probe_pgidx.sh N      (N = 31, 32, 33)
# Berkas lama tidak ditimpa; skrip berhenti jika output sudah ada atau rencana kueri tidak memakai indeks.
set -u
cd ~/Riset_TA_Database
N="${1:?nomor run, mis. 31}"; DB=postgres
RAW="pgidx_${DB}_run${N}.ndjson"; RES="pgidx_${DB}_resources_run${N}.csv"; APIC="pgidx_${DB}_api_cpu_run${N}.csv"; HB="hb_pgidx_${DB}_run${N}.log"
for f in "$RAW" "$RAW.gz" "$RES" "$APIC" "$HB"; do [ -s "$f" ] && { echo "ABORT: $f sudah ada"; exit 1; }; done

python3 scripts/reset_environment.py --size full || { echo "ABORT: reset gagal"; exit 1; }

# Indeks gabungan (reset_environment membuat ulang tiga indeks tunggal; indeks gabungan ditambahkan setelahnya)
PSQL="docker exec -i ta_postgres_17 psql -U admin -d yelp_db"
$PSQL -c "CREATE INDEX IF NOT EXISTS idx_composite_nested ON yelp_business ((document->'attributes'->>'RestaurantsPriceRange2'), (document->'attributes'->>'WiFi'), (document->'attributes'->>'OutdoorSeating'));" || { echo "ABORT: gagal membuat indeks"; exit 1; }
$PSQL -c "ANALYZE yelp_business;"

# Periksa rencana: harus memakai indeks gabungan, bukan Seq Scan
PLAN=$($PSQL -c "EXPLAIN SELECT business_id, document FROM yelp_business WHERE document->'attributes'->>'RestaurantsPriceRange2'='2' AND document->'attributes'->>'WiFi'='free' AND document->'attributes'->>'OutdoorSeating'='true' LIMIT 50;")
echo "$PLAN"
echo "$PLAN" | grep -q "idx_composite_nested" || { echo "ABORT: planner tidak memakai idx_composite_nested (jangan lanjut; beri tahu saya hasil EXPLAIN di atas)"; exit 1; }
echo "$PLAN" > "pgidx_plan_run${N}.txt"

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
python3 scripts/extract_results.py "$RAW" --label "pgidx_${DB}_run${N}" --resources_csv "$RES"
python3 scripts/extract_decomposition.py "$RAW" --label "pgidx_${DB}_run${N}"
gzip -f "$RAW"
