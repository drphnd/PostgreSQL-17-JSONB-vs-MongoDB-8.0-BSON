# PANDUAN EKSEKUSI — Urutan Wajib
# =================================
# Ikuti langkah ini BERURUTAN. Jangan skip.
# Setiap langkah ada verifikasi output-nya.

# ============================================================
# LANGKAH 0 — Persiapan (Jalankan sekali di awal sesi)
# ============================================================

# Masuk ke WSL dan direktori riset
wsl
cd ~/Riset_TA_Database
source env_ta/bin/activate

# Matikan semua proses lama
pkill -f uvicorn 2>/dev/null
pkill -f "api_bridge" 2>/dev/null

# Verifikasi port 8000 kosong
ss -tlnp | grep 8000
# EXPECTED: tidak ada output


# ============================================================
# LANGKAH 1 — Install dependencies baru
# ============================================================

pip uninstall psycopg2-binary -y
pip install asyncpg "motor[srv]" fastapi "uvicorn[standard]"

# Verifikasi
python -c "import asyncpg, motor; print('[OK] Dependencies siap')"
# EXPECTED: [OK] Dependencies siap


# ============================================================
# LANGKAH 2 — Salin file dari output ke direktori riset
# (File ini sudah dibuat oleh Claude di sesi ini)
# Salin manual atau download dari chat, lalu:
# ============================================================

# Letakkan file-file berikut di ~/Riset_TA_Database/:
# - rebuild_indexes.py
# - api_bridge.py
# - test_read_postgres.js
# - test_read_mongo.js
# - test_update_postgres.js
# - test_update_mongo.js


# ============================================================
# LANGKAH 3 — Rebuild indeks (WAJIB, lakukan sekali)
# ============================================================

python rebuild_indexes.py

# EXPECTED OUTPUT:
# [PostgreSQL] Membangun ulang indeks...
#   -> Menghapus GIN index lama (idx_jsonb_doc)...
#   -> Membuat indeks untuk filter attributes.RestaurantsPriceRange2...
#      Selesai dalam X detik.
#   -> Membuat indeks untuk filter attributes.WiFi...
#   -> Membuat indeks untuk filter attributes.OutdoorSeating...
# [MongoDB] Membangun ulang indeks...
#   -> Menghapus indeks lama...
#   -> Membuat indeks business_id (unique)...
#   -> Membuat compound index untuk READ multikriteria...
# [VERIFIKASI] Memeriksa indeks yang aktif...
#   PostgreSQL indexes: (tampil 4 indeks: PK + 3 expression index)
#   MongoDB indexes:    (tampil 3 indeks: _id + business_id + compound)


# ============================================================
# LANGKAH 4 — Nyalakan API Bridge
# (Buka terminal baru / tab baru untuk ini — jangan ditutup)
# ============================================================

# Di TERMINAL 1:
cd ~/Riset_TA_Database
source env_ta/bin/activate

# PENTING: --workers 1 bukan 4. Ini menghilangkan variabel pool ganda.
uvicorn api_bridge:app --host 0.0.0.0 --port 8000 --workers 1

# EXPECTED: Muncul baris "[STARTUP] Selesai. 1000 ID di-cache."
# JANGAN TUTUP terminal ini selama pengujian berlangsung.


# ============================================================
# LANGKAH 5 — Verifikasi health sebelum K6 dijalankan
# ============================================================

# Di TERMINAL 2 (buka terminal baru):
cd ~/Riset_TA_Database
source env_ta/bin/activate

curl http://localhost:8000/health | python -m json.tool

# EXPECTED:
# {
#   "all_systems_ok": true,
#   "databases": {
#     "postgres": {"ok": true, "document_count": 150346},
#     "mongodb":  {"ok": true, "document_count": 150346}
#   }
# }
#
# JIKA all_systems_ok = false: JANGAN lanjutkan. Periksa Docker container.
# docker ps  (pastikan ta_postgres_17 dan ta_mongodb_8 berstatus Up)


# ============================================================
# LANGKAH 6 — Jalankan Load Test (30 menit per skenario)
# URUTAN PENTING: REST dulu 5 menit antar skenario
# ============================================================

# 6A. READ PostgreSQL
k6 run test_read_postgres.js
# Durasi: ~30 menit
# Output akan tersimpan ke: result_read_postgres.json

# [ISTIRAHAT 5 MENIT] — Biarkan database recovery dari sustained load
sleep 300

# 6B. READ MongoDB
k6 run test_read_mongo.js
# Durasi: ~30 menit
# Output: result_read_mongo.json

# [ISTIRAHAT 5 MENIT]
sleep 300

# 6C. UPDATE PostgreSQL
k6 run test_update_postgres.js
# Durasi: ~30 menit
# Output: result_update_postgres.json

# [ISTIRAHAT 5 MENIT]
sleep 300

# 6D. UPDATE MongoDB
k6 run test_update_mongo.js
# Durasi: ~30 menit
# Output: result_update_mongo.json


# ============================================================
# LANGKAH 7 — Setelah semua selesai
# ============================================================

# Cek semua file hasil ada:
ls -lh result_*.json
# EXPECTED: 4 file JSON masing-masing berisi data K6 summary

# Catatan untuk laporan:
# - Angka yang relevan: pg_read_latency.p99, mongo_read_latency.p99
#   pg_update_latency.p99, mongo_update_latency.p99
# - Throughput: http_reqs / duration
# - Error rate: http_req_failed


# ============================================================
# CATATAN METODOLOGIS UNTUK BAB 3
# ============================================================
# 
# Mengapa --workers 1:
#   Dengan multiple workers, setiap worker punya pool koneksi sendiri.
#   Ini menciptakan ketidakseimbangan antara PostgreSQL dan MongoDB
#   karena cara keduanya mengelola koneksi berbeda. Single worker
#   memastikan satu pool tunggal yang identik untuk keduanya.
#
# Mengapa MAX_POOL_SIZE = 50:
#   PostgreSQL default max_connections = 100. Dengan pool 50, ada
#   ruang untuk koneksi maintenance tanpa risiko "too many connections".
#   MongoDB tidak punya limit seperti ini, tapi kita batasi sama
#   untuk fairness.
#
# Mengapa asyncpg bukan psycopg2:
#   psycopg2 synchronous + FastAPI async = thread blocking.
#   asyncpg non-blocking = FastAPI bisa melayani request lain
#   sambil menunggu database. Ini setara dengan behavior motor (MongoDB).
#   Tanpa kesetaraan ini, yang Anda ukur adalah overhead driver,
#   bukan performa database.
