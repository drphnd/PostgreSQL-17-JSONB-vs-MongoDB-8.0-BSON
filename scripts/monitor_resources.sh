#!/usr/bin/env bash
# monitor_resources.sh
#
# Mencatat docker stats SECARA KONTINU (bukan snapshot manual sesaat seperti
# sebelumnya) ke file CSV, setiap 5 detik, selama skenario berjalan.
# Jalankan di background SEBELUM k6 run dimulai, matikan (kill) setelah selesai.
#
# Pemakaian:
#   ./monitor_resources.sh result_read_postgres_resources.csv &
#   MONITOR_PID=$!
#   k6 run ... test_read_postgres.js
#   kill $MONITOR_PID

OUTPUT_FILE="${1:-resources.csv}"
INTERVAL_SECONDS="${2:-5}"

echo "timestamp,container,cpu_percent,mem_usage_mib,mem_percent" > "$OUTPUT_FILE"

while true; do
  TS=$(date +%Y-%m-%dT%H:%M:%S)
  docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}" \
    | grep -E "ta_postgres_17|ta_mongodb_8" \
    | while IFS=',' read -r name cpu mem_usage mem_pct; do
        mem_mib=$(echo "$mem_usage" | cut -d'/' -f1 | sed 's/MiB//;s/GiB/*1024/' | bc 2>/dev/null)
        cpu_clean=$(echo "$cpu" | sed 's/%//')
        mem_pct_clean=$(echo "$mem_pct" | sed 's/%//')
        echo "$TS,$name,$cpu_clean,$mem_mib,$mem_pct_clean" >> "$OUTPUT_FILE"
      done
  sleep "$INTERVAL_SECONDS"
done
