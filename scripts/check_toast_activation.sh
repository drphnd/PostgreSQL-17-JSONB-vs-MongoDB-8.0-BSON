#!/usr/bin/env bash
# check_toast_activation.sh
#
# Memverifikasi apakah mekanisme TOAST PostgreSQL aktif untuk dataset ini --
# menjawab kritik bahwa update pada field WiFi (satu field kecil) mungkin
# tidak merepresentasikan overhead penulisan ulang dokumen bersarang secara
# memadai. TOAST hanya aktif ketika ukuran baris melebihi ambang batas
# TOAST_TUPLE_THRESHOLD (default ~2 KB pada PostgreSQL). Jika dokumen Yelp
# secara konsisten berada di bawah ambang ini, maka TOAST TIDAK aktif, dan
# seluruh dokumen memang ditulis ulang secara utuh di halaman heap utama
# pada setiap UPDATE -- ini justru mengonfirmasi (bukan mengurangi) beban
# write amplification MVCC yang diklaim, karena tidak ada offloading
# sebagian data ke tabel TOAST terpisah yang bisa mengurangi ukuran
# penulisan ulang.

echo "=== Distribusi ukuran dokumen JSONB (bytes) ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT
  MIN(pg_column_size(document))    AS ukuran_min_bytes,
  ROUND(AVG(pg_column_size(document)))  AS ukuran_rata_rata_bytes,
  MAX(pg_column_size(document))    AS ukuran_maks_bytes,
  COUNT(*) FILTER (WHERE pg_column_size(document) > 2048) AS jumlah_dokumen_di_atas_toast_threshold
FROM yelp_business;
"

echo ""
echo "=== Ambang batas TOAST yang berlaku ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "SHOW block_size;"
echo "(TOAST_TUPLE_THRESHOLD default = block_size / 4, umumnya 2048 bytes untuk block_size 8192)"

echo ""
echo "=== Cek langsung: apakah ada tabel TOAST yang terpakai untuk yelp_business ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT
  c.relname AS nama_tabel,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS ukuran_total,
  pg_size_pretty(pg_relation_size(t.oid)) AS ukuran_tabel_toast
FROM pg_class c
LEFT JOIN pg_class t ON c.reltoastrelid = t.oid
WHERE c.relname = 'yelp_business';
"

echo ""
echo "Interpretasi:"
echo "- Jika 'jumlah_dokumen_di_atas_toast_threshold' = 0 atau mendekati 0,"
echo "  TOAST tidak aktif untuk mayoritas dokumen -- seluruh dokumen"
echo "  ditulis ulang utuh di halaman heap utama pada setiap UPDATE,"
echo "  MENGONFIRMASI (bukan melemahkan) klaim write amplification MVCC."
echo "- Jika 'ukuran_tabel_toast' menunjukkan nilai signifikan (bukan 0"
echo "  bytes/kosong), berarti sebagian dokumen memang di-TOAST, dan hal"
echo "  ini perlu didiskusikan sebagai nuansa tambahan pada Bab 4/5."
