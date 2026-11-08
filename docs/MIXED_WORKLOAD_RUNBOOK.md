# Runbook — Mixed Workload (Skenario 13-14)

Tujuan: menguji apakah kontensi lock antara operasi read dan write yang
berjalan KONKUREN (bukan terisolasi seperti Skenario 1-4) mengungkap
perbedaan arsitektural MVCC PostgreSQL vs WiredTiger MongoDB yang tidak
teramati pada desain eksperimen terisolasi.

Rasio beban: 80% read (nested) : 20% update -- pola OLTP umum.
Estimasi waktu: 2 skenario x (~25 menit test + reset + jeda) ≈ 1-1,5 jam.

Prasyarat: file `k6/test_mixed_postgres.js`, `k6/test_mixed_mongo.js`,
dan `scripts/extract_mixed_results.py` sudah ada di folder proyek.

---

## Skenario #13 — Mixed Workload, PostgreSQL, full data

```bash
python scripts/reset_environment.py --size full
curl -X POST http://localhost:8000/reload; echo

curl "http://localhost:8000/read/postgres?mode=nested"; echo
curl -s -X PUT http://localhost:8000/update/postgres \
  -H "Content-Type: application/json" \
  -d '{"index": 100, "wifi_value": "free"}'; echo

bash scripts/monitor_resources.sh mixed13_resources.csv &
MONITOR_PID=$!

k6 run -e DATA_SIZE=full -e READ_RATIO=0.8 \
  --out json=mixed13_postgres.ndjson \
  k6/test_mixed_postgres.js

kill $MONITOR_PID

python scripts/extract_mixed_results.py mixed13_postgres.ndjson \
  --label scn13_mixed_postgres_full

docker exec -it ta_postgres_17 psql -U admin -d yelp_db -c "
SELECT n_live_tup, n_dead_tup,
       ROUND(n_dead_tup::numeric/NULLIF(n_live_tup+n_dead_tup,0)*100,2) AS dead_pct,
       autovacuum_count
FROM pg_stat_user_tables WHERE relname = 'yelp_business';
"

sleep 300
```

---

## Skenario #14 — Mixed Workload, MongoDB, full data

```bash
python scripts/reset_environment.py --size full
curl -X POST http://localhost:8000/reload; echo

curl "http://localhost:8000/read/mongo?mode=nested"; echo
curl -s -X PUT http://localhost:8000/update/mongo \
  -H "Content-Type: application/json" \
  -d '{"index": 100, "wifi_value": "free"}'; echo

bash scripts/monitor_resources.sh mixed14_resources.csv &
MONITOR_PID=$!

k6 run -e DATA_SIZE=full -e READ_RATIO=0.8 \
  --out json=mixed14_mongo.ndjson \
  k6/test_mixed_mongo.js

kill $MONITOR_PID

python scripts/extract_mixed_results.py mixed14_mongo.ndjson \
  --label scn14_mixed_mongo_full
```

---

# SETELAH KEDUA SKENARIO SELESAI — Analisis Interferensi

## Bandingkan p99 mixed vs isolated pada checkpoint yang sama

Buka `summary_scn13_mixed_postgres_full.csv`, filter baris `op=read`,
bandingkan kolom `p99` dengan `summary_scn1_read_postgres_full_nested.csv`
pada checkpoint yang sama (mis. `vu_512`).

Lakukan hal serupa untuk:
- `op=update` di Skenario #13 vs `summary_scn3_update_postgres_full.csv`
- Skenario #14 (`op=read`) vs `summary_scn2_read_mongo_full_nested.csv`
- Skenario #14 (`op=update`) vs `summary_scn4_update_mongo_full.csv`

**Hitung rasio interferensi** untuk tiap kombinasi:
```
rasio_interferensi = p99_mixed / p99_isolated
```

## Interpretasi

- **Rasio mendekati 1.0**: kontensi lock read-write tidak memberikan
  dampak signifikan pada skala pengujian ini -- tetap temuan valid.
- **Rasio read PostgreSQL mendekati 1.0 tapi rasio read MongoDB > 1**
  (atau sebaliknya): bukti langsung perbedaan arsitektural MVCC
  (snapshot isolation, reader tidak pernah diblokir writer) vs mekanisme
  concurrency control WiredTiger.
- **Rasio update meningkat tajam pada salah satu sistem**: writer pada
  sistem tersebut lebih terganggu oleh keberadaan concurrent reader.

## Tulis subbab baru di Bab 4 — "4.X Analisis Beban Campuran (Mixed Workload)"

> "Untuk mengukur dampak kontensi lock antara operasi read dan write yang
> berjalan konkuren, dilakukan pengujian tambahan dengan beban campuran
> (80% read, 20% update) pada kedua sistem. Perbandingan latensi P99 pada
> kondisi checkpoint 512 VU antara skenario mixed workload dan skenario
> terisolasi menunjukkan rasio interferensi sebesar [X] untuk operasi read
> dan [Y] untuk operasi update pada PostgreSQL, serta [Z] dan [W] pada
> MongoDB."

## Update Bab 5

Karena skenario ini sekarang benar-benar dieksekusi, pindahkan poin mixed
workload dari daftar saran penelitian lanjutan menjadi bagian kontribusi
utama penelitian.
