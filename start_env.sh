#!/usr/bin/env bash
# Menyalakan dan memverifikasi lingkungan. Pemakaian: bash start_env.sh   (NEED_GB=30 bisa diubah)
cd ~/Riset_TA_Database || exit 1
source env_ta/bin/activate
NEED_GB="${NEED_GB:-30}"
FREE_C=$(df -BG --output=avail /mnt/c 2>/dev/null | tail -1 | tr -dc '0-9')
echo "[0] ruang bebas drive C: ${FREE_C:-?} GB (minimum ${NEED_GB} GB)"
if [ -n "$FREE_C" ] && [ "$FREE_C" -lt "$NEED_GB" ]; then echo "ABORT: ruang C: kurang"; exit 1; fi
SCHEME=$(/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "powercfg /getactivescheme" 2>/dev/null | tr -d '\r')
echo "[0b] mode daya: ${SCHEME:-tidak terbaca}"
for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info >/dev/null 2>&1 || { echo "ABORT: Docker belum jalan"; exit 1; }
docker compose up -d
for i in $(seq 1 60); do docker exec ta_postgres_17 pg_isready -U admin -d yelp_db >/dev/null 2>&1 && break; sleep 2; done
for i in $(seq 1 60); do docker exec ta_mongodb_8 mongosh --quiet --eval 'db.runCommand({ping:1}).ok' 2>/dev/null | grep -q 1 && break; sleep 2; done
echo "[2] kelengkapan data"
PGN=$(docker exec ta_postgres_17 psql -U admin -d yelp_db -tAc "SELECT count(*) FROM yelp_business" 2>/dev/null)
MGN=$(docker exec ta_mongodb_8 mongosh --quiet --eval 'db.getSiblingDB("yelp_db").yelp_business.countDocuments({})' 2>/dev/null | tail -1)
echo "postgres=$PGN mongo=$MGN"
if [ "$PGN" != "150346" ] || [ "$MGN" != "150346" ]; then
  [ -f yelp_academic_dataset_business.json ] || { echo "ABORT: dataset Yelp tidak ada"; exit 1; }
  python3 scripts/reset_environment.py --size full || { echo "ABORT: reset gagal"; exit 1; }
fi
echo "[3] API (app.main:app)"
bash scripts/check_target.sh || { echo "ABORT: target database salah"; exit 1; }
pkill -f uvicorn 2>/dev/null; sleep 1
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > log_api.txt 2>&1 &
for i in $(seq 1 60); do curl -s http://localhost:8000/health | grep -q pg_ids && break; sleep 2; done
curl -s -X POST http://localhost:8000/reload; echo
echo "[4] cek akhir"
curl -s http://localhost:8000/health; echo
curl -s -o /dev/null -w "read mongo: %{http_code}\n"      "http://localhost:8000/read/mongo?mode=nested"
curl -s -o /dev/null -w "read postgres: %{http_code}\n"   "http://localhost:8000/read/postgres?mode=nested"
curl -s -o /dev/null -w "update mongo: %{http_code}\n"    -X PUT http://localhost:8000/update/mongo    -H "Content-Type: application/json" -d '{"index":100,"wifi_value":"free"}'
curl -s -o /dev/null -w "update postgres: %{http_code}\n" -X PUT http://localhost:8000/update/postgres -H "Content-Type: application/json" -d '{"index":100,"wifi_value":"free"}'
df -h . | tail -1
