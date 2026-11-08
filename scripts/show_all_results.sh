#!/usr/bin/env bash
# show_all_results.sh
#
# Menampilkan SEMUA data hasil pengujian dari 22 skenario yang sudah
# dijalankan, terorganisir per kategori. Jalankan dari folder
# ~/Riset_TA_Database/

echo "############################################################"
echo "# 1. SKENARIO INTI (Tingkat 1-3) -- 12 skenario"
echo "############################################################"
for f in summary_scn1_read_postgres_full_nested.csv \
         summary_scn2_read_mongo_full_nested.csv \
         summary_scn3_update_postgres_full.csv \
         summary_scn4_update_mongo_full.csv \
         summary_scn5_read_postgres_full_flat.csv \
         summary_scn6_read_mongo_full_flat.csv \
         summary_scn7_read_postgres_50k_nested.csv \
         summary_scn8_read_postgres_100k_nested.csv \
         summary_scn8b_read_postgres_100k_nested_rerun.csv \
         summary_scn9_read_mongo_50k_nested.csv \
         summary_scn10_read_mongo_100k_nested.csv \
         summary_scn11_update_postgres_50k.csv \
         summary_scn12_update_mongo_50k.csv; do
  if [ -f "$f" ]; then
    echo ""
    echo "=== $f ==="
    column -s',' -t "$f"
  else
    echo ""
    echo "=== $f (TIDAK DITEMUKAN) ==="
  fi
done

echo ""
echo "############################################################"
echo "# 2. SENSITIVITY ANALYSIS (timeout 3 detik) -- 4 skenario"
echo "############################################################"
for f in summary_sens1_read_postgres_timeout3s.csv \
         summary_sens2_read_mongo_timeout3s.csv \
         summary_sens3_update_postgres_timeout3s.csv \
         summary_sens4_update_mongo_timeout3s.csv; do
  if [ -f "$f" ]; then
    echo ""
    echo "=== $f ==="
    column -s',' -t "$f"
  else
    echo ""
    echo "=== $f (TIDAK DITEMUKAN) ==="
  fi
done

echo ""
echo "############################################################"
echo "# 3. MIXED WORKLOAD -- 2 skenario"
echo "############################################################"
for f in summary_scn13_mixed_postgres_full.csv \
         summary_scn14_mixed_mongo_full.csv; do
  if [ -f "$f" ]; then
    echo ""
    echo "=== $f ==="
    column -s',' -t "$f"
  else
    echo ""
    echo "=== $f (TIDAK DITEMUKAN) ==="
  fi
done

echo ""
echo "############################################################"
echo "# 4. RESOURCE USAGE (CPU/RAM) RINGKASAN per skenario inti"
echo "############################################################"
for f in raw_scn1_resources.csv raw_scn2_resources.csv raw_scn3_resources.csv \
         raw_scn4_resources.csv raw_scn5_resources.csv raw_scn6_resources.csv \
         raw_scn7_resources.csv raw_scn8_resources.csv raw_scn9_resources.csv \
         raw_scn10_resources.csv raw_scn11_resources.csv raw_scn12_resources.csv; do
  if [ -f "$f" ]; then
    echo ""
    echo "=== $f (baris terakhir sebagai sample) ==="
    tail -3 "$f"
  fi
done

echo ""
echo "############################################################"
echo "# 5. STATUS DATABASE SAAT INI"
echo "############################################################"
echo "-- PostgreSQL: jumlah dokumen & dead tuple --"
docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT n_live_tup, n_dead_tup,
       ROUND(n_dead_tup::numeric/NULLIF(n_live_tup+n_dead_tup,0)*100,2) AS dead_pct,
       autovacuum_count
FROM pg_stat_user_tables WHERE relname = 'yelp_business';
" 2>/dev/null

echo ""
echo "-- MongoDB: jumlah dokumen --"
docker exec -it ta_mongodb_8 mongosh yelp_db --eval "db.yelp_business.countDocuments()" 2>/dev/null

echo ""
echo "############################################################"
echo "# SELESAI -- semua data di atas juga tersimpan di masing-"
echo "# masing file summary_*.csv untuk diproses lebih lanjut"
echo "############################################################"
