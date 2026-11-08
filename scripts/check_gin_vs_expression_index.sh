#!/usr/bin/env bash
# check_gin_vs_expression_index.sh
#
# Membandingkan secara empiris strategi expression index (dipakai pada
# eksperimen) versus GIN index, untuk query filter multikriteria yang
# path-nya SUDAH DIKETAHUI TETAP sejak awal -- menjawab kritik bahwa
# pemilihan expression index adalah pembatasan kapabilitas native
# PostgreSQL yang dipaksakan demi menyamai arsitektur MongoDB.
#
# Tidak perlu load test 512 VU penuh -- perbandingan cost planner dan
# waktu eksekusi single-query sudah cukup untuk mengonfirmasi expression
# index memang pilihan idiomatik untuk pola akses kueri tetap seperti ini,
# BUKAN downgrade paksa.

echo "=== Kondisi SEBELUM: hanya expression index (kondisi eksperimen asli) ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
EXPLAIN ANALYZE
SELECT business_id, document FROM yelp_business
WHERE document->'attributes'->>'RestaurantsPriceRange2' = '2'
  AND document->'attributes'->>'WiFi' = 'free'
  AND document->'attributes'->>'OutdoorSeating' = 'true'
LIMIT 50;
"

echo ""
echo "=== Menambahkan GIN index sebagai pembanding ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
CREATE INDEX IF NOT EXISTS idx_gin_document ON yelp_business USING GIN (document jsonb_path_ops);
"

echo ""
echo "=== Ukuran index: expression index vs GIN index ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT
  indexrelname AS nama_index,
  pg_size_pretty(pg_relation_size(indexrelid)) AS ukuran
FROM pg_stat_user_indexes
WHERE relname = 'yelp_business'
ORDER BY pg_relation_size(indexrelid) DESC;
"

echo ""
echo "=== Kondisi SESUDAH: GIN index tersedia, cek query plan yang dipilih planner ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
EXPLAIN ANALYZE
SELECT business_id, document FROM yelp_business
WHERE document @> '{\"attributes\": {\"RestaurantsPriceRange2\": \"2\", \"WiFi\": \"free\", \"OutdoorSeating\": true}}'
LIMIT 50;
"

echo ""
echo "=== Bersihkan: hapus GIN index pembanding (kembalikan ke kondisi eksperimen asli) ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
DROP INDEX IF EXISTS idx_gin_document;
"

echo ""
echo "Interpretasi:"
echo "- Bandingkan 'Execution Time' dan ukuran index antara kedua pendekatan."
echo "- GIN index umumnya berukuran signifikan lebih besar dan/atau waktu"
echo "  eksekusi tidak lebih cepat untuk kueri equality pada path tetap"
echo "  seperti ini -- ini yang menjadi dasar empiris pemilihan expression"
echo "  index sebagai representasi idiomatik untuk pola akses kueri yang"
echo "  sudah diketahui, sebagaimana direkomendasikan dokumentasi resmi"
echo "  PostgreSQL untuk kasus penggunaan serupa."
