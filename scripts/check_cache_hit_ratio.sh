#!/usr/bin/env bash
# check_cache_hit_ratio.sh
#
# Mengukur seberapa besar operasi baca selama pengujian benar-benar
# mengenai cache memori (bukan disk I/O) -- menjawab kritik bahwa dataset
# 150.346 dokumen mungkin muat seutuhnya di cache, sehingga eksperimen
# hanya menguji kecepatan RAM/CPU, bukan performa I/O disk yang
# sesungguhnya menjadi ujian arsitektural kedua sistem.
#
# Jalankan SETELAH salah satu skenario read (mis. Skenario #1) selesai,
# SEBELUM reset environment berikutnya -- statistik ini kumulatif sejak
# container terakhir kali restart/reset.

echo "=== PostgreSQL: Rasio Cache Hit (pg_statio_user_tables) ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT
  relname,
  heap_blks_read  AS blok_dibaca_dari_disk,
  heap_blks_hit   AS blok_dari_cache,
  ROUND(
    100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0), 2
  ) AS cache_hit_ratio_persen
FROM pg_statio_user_tables
WHERE relname = 'yelp_business';
"

echo ""
echo "=== PostgreSQL: shared_buffers terkonfigurasi ==="
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "SHOW shared_buffers;"

echo ""
echo "=== MongoDB: Statistik WiredTiger Cache ==="
docker exec -it ta_mongodb_8 mongosh yelp_db --eval "
const stats = db.serverStatus().wiredTiger.cache;
print('Cache terpakai (MB):', Math.round(stats['bytes currently in the cache'] / 1024 / 1024));
print('Cache maksimum dikonfigurasi (MB):', Math.round(stats['maximum bytes configured'] / 1024 / 1024));
print('Halaman dibaca dari disk ke cache:', stats['pages read into cache']);
print('Halaman ditemukan langsung di cache (tanpa I/O disk):', stats['pages requested from the cache']);
"

echo ""
echo "Interpretasi: cache_hit_ratio_persen mendekati 100% pada PostgreSQL,"
echo "atau 'pages read into cache' yang sangat kecil dibanding 'pages"
echo "requested from the cache' pada MongoDB, mengonfirmasi bahwa"
echo "pengujian didominasi akses cache memori -- bukan performa I/O disk."
