#!/usr/bin/env bash
# monitor_host_memory.sh
#
# Mencatat kondisi memori LEVEL HOST WSL2 (bukan container Docker) secara
# kontinu -- menjawab pertanyaan sidang: apakah degradasi performa di
# 512 VU murni saturasi internal DBMS, atau ikut tercampur swapping OS
# inang (WSL2) akibat batas memory=10GB/swap=6GB yang dikonfigurasi.
#
# Jalankan BERSAMAAN dengan SATU pengujian ulang terarah di kondisi
# terberat (512 VU, UPDATE MongoDB -- yang sebelumnya sempat memicu OOM),
# sebagai verifikasi tambahan. TIDAK perlu mengulang seluruh 12 skenario.
#
# Pemakaian:
#   ./monitor_host_memory.sh host_memory_verification.csv &
#   MEM_MONITOR_PID=$!
#   k6 run -e DATA_SIZE=50000 --out json=verify_update_mongo.ndjson k6/test_update_mongo.js
#   kill $MEM_MONITOR_PID

OUTPUT_FILE="${1:-host_memory.csv}"
INTERVAL_SECONDS="${2:-3}"

echo "timestamp,mem_total_mb,mem_used_mb,mem_available_mb,swap_total_mb,swap_used_mb" > "$OUTPUT_FILE"

while true; do
  TS=$(date +%Y-%m-%dT%H:%M:%S)
  read -r _ total used available <<< "$(free -m | awk '/^Mem:/ {print $1, $2, $3, $7}')"
  read -r _ swap_total swap_used <<< "$(free -m | awk '/^Swap:/ {print $1, $2, $3}')"
  echo "$TS,$total,$used,$available,$swap_total,$swap_used" >> "$OUTPUT_FILE"
  sleep "$INTERVAL_SECONDS"
done
