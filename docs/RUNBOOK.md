# Runbook Reset & Perluasan Eksperimen
Komparasi PostgreSQL 17 JSONB vs MongoDB 8.0 BSON

## 0. Apa yang diperbaiki dari eksperimen sebelumnya

| Masalah lama | Perbaikan |
|---|---|
| P99 "pada 512 VU" sebenarnya agregat seluruh 29 menit run | Setiap checkpoint VU jadi scenario k6 terpisah + diberi tag `checkpoint`; ekstraksi p99 difilter per-tag lewat `extract_results.py` |
| Latensi negatif (clock drift) | Berhenti pakai custom `Date.now()` timer; pakai metrik bawaan k6 `http_req_duration` (satu clock, satu proses) |
| Setiap skenario dijalankan 3x tanpa reset (dead tuple numpuk lintas run) | `reset_environment.py` wajib dijalankan sebelum SETIAP skenario |
| Docker stats snapshot manual sesaat | `monitor_resources.sh` mencatat kontinu tiap 5 detik selama run, dirata-rata + stdev |
| Error/timeout hanya muncul sebagai WARN log, tidak dihitung formal | `check()` eksplisit `not timeout`, dihitung sebagai error_rate per checkpoint |
| Framing "JSONB vs BSON" | Lihat bagian 4 di bawah — direvisi jadi framing system-level |

## 1. Prasyarat sebelum mulai

```bash
cd ~/Riset_TA_Database
pip install psycopg2-binary pymongo --break-system-packages
docker compose up -d ta_postgres_17 ta_mongodb_8
```

Pastikan FastAPI bridge mendukung parameter `?mode=flat|nested` pada endpoint
`/read/postgres` dan `/read/mongo` (untuk skenario query variant). Jika belum,
tambahkan cabang query berdasarkan parameter ini di endpoint yang sudah ada —
tidak perlu endpoint baru.

## 2. Matriks 12 Skenario (4 asli + 8 tambahan)

| # | Operasi | Jenis Query | Sistem | Volume Data | Status |
|---|---|---|---|---|---|
| 1 | READ | nested (multikriteria) | PostgreSQL | full (150.346) | asli, diulang dengan skrip baru |
| 2 | READ | nested (multikriteria) | MongoDB | full (150.346) | asli, diulang dengan skrip baru |
| 3 | UPDATE | — | PostgreSQL | full (150.346) | asli, diulang dengan skrip baru |
| 4 | UPDATE | — | MongoDB | full (150.346) | asli, diulang dengan skrip baru |
| 5 | READ | flat (single-field) | PostgreSQL | full (150.346) | **baru** — baseline query |
| 6 | READ | flat (single-field) | MongoDB | full (150.346) | **baru** — baseline query |
| 7 | READ | nested | PostgreSQL | 50.000 | **baru** — volume sensitivity |
| 8 | READ | nested | MongoDB | 50.000 | **baru** — volume sensitivity |
| 9 | READ | nested | PostgreSQL | 100.000 | **baru** — volume sensitivity |
| 10 | READ | nested | MongoDB | 100.000 | **baru** — volume sensitivity |
| 11 | UPDATE | — | PostgreSQL | 50.000 | **baru** — dead tuple accumulation rate pada volume kecil |
| 12 | UPDATE | — | MongoDB | 50.000 | **baru** — write saturation pada volume kecil |

Total estimasi durasi: 12 skenario x (~22 menit test + reset ~1-3 menit + jeda 5 menit) ≈ **6-7 jam**. Sarankan dijalankan dalam 2 sesi (misalnya skenario 1-6 hari pertama, 7-12 hari kedua) supaya mesin tidak thermal-throttling akibat durasi maraton.

## 3. Prosedur eksekusi per skenario (WAJIB diikuti urutannya)

```bash
# Contoh untuk skenario #1: READ nested, PostgreSQL, full data

# 1) Reset ke kondisi bersih
python scripts/reset_environment.py --size full

# 2) Mulai monitoring resource di background
bash scripts/monitor_resources.sh raw_scn1_resources.csv &
MONITOR_PID=$!

# 3) Jalankan k6 dengan output NDJSON penuh (bukan cuma summary)
k6 run -e QUERY_MODE=nested -e DATA_SIZE=full \
  --out json=raw_scn1_read_postgres.ndjson \
  k6/test_read_postgres.js

# 4) Hentikan monitoring
kill $MONITOR_PID

# 5) Ekstraksi hasil bersih per checkpoint VU
python scripts/extract_results.py raw_scn1_read_postgres.ndjson \
  --label scn1_read_postgres_full_nested \
  --resources_csv raw_scn1_resources.csv

# 6) Untuk skenario UPDATE PostgreSQL saja: cek dead tuple ratio SETELAH run
python -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, database='yelp_db', user='admin', password='password123')
cur = conn.cursor()
cur.execute('''SELECT n_live_tup, n_dead_tup,
    ROUND(n_dead_tup::numeric/NULLIF(n_live_tup+n_dead_tup,0)*100,2)
    FROM pg_stat_user_tables WHERE relname='yelp_business';''')
print(cur.fetchone())
"

# 7) Jeda 5 menit sebelum skenario berikutnya (sesuai desain di Tabel 3.2)
sleep 300
```

Ulangi pola ini untuk skenario 2-12, ganti flag `-e QUERY_MODE=` dan
`-e DATA_SIZE=` serta script k6 yang dipanggil (`test_read_mongo.js`,
`test_update_postgres.js`, `test_update_mongo.js`), dan pastikan
`reset_environment.py --size <full|100000|50000>` dijalankan dengan ukuran
yang SESUAI skenario di langkah 1.

## 4. Checklist validitas sebelum data dianggap final

- [ ] Reset environment dijalankan sebelum SETIAP skenario (bukan hanya sebelum skenario pertama)
- [ ] Tidak ada nilai `min` negatif tersisa di data mentah (kalau masih ada, laporkan jumlahnya secara eksplisit — jangan disembunyikan)
- [ ] P95/P99 yang dilaporkan berasal dari checkpoint yang benar-benar terisolasi (`checkpoint=vu_256`, `checkpoint=vu_512`), dicek lewat `summary_*.csv`
- [ ] Resource usage (CPU/RAM) dilaporkan sebagai rata-rata ± stdev selama plateau, bukan snapshot satu titik
- [ ] Error rate / timeout rate dilaporkan sebagai angka eksplisit per checkpoint, termasuk checkpoint pertama kali error muncul
- [ ] Dead tuple ratio PostgreSQL dicatat SEBELUM (harus ~0% pasca reset) dan SESUDAH setiap skenario UPDATE

## 5. Update ke Bab 3 Proposal (rencana analisis & metode)

Ganti kalimat rencana analisis (3.4) yang lama dengan:

> "Ekstraksi metrik latensi dilakukan dari output K6 penuh (bukan hanya
> ringkasan akhir), dengan setiap titik data ditandai (tagged) sesuai
> checkpoint tingkat konkurensi tempat data tersebut dihasilkan. Nilai P95
> dan P99 dihitung secara terisolasi untuk setiap checkpoint (5, 50, 100,
> 200, 256, 400, dan 512 Virtual Users), sehingga metrik yang dilaporkan
> pada kondisi 256 VU dan 512 VU murni mencerminkan kondisi tersebut, bukan
> agregat dari seluruh durasi pengujian. Lingkungan basis data direset ke
> kondisi awal (truncate, re-ingest, rebuild index, VACUUM ANALYZE) sebelum
> setiap skenario dijalankan, untuk memastikan metrik akumulatif seperti
> rasio dead tuple murni mencerminkan operasi dari skenario yang
> bersangkutan."

---

## 6. Jawaban untuk komentar dosen (framing "JSONB vs BSON")

Tambahkan paragraf berikut ke **Bab 1 (setelah Latar Belakang paragraf
pertama)** dan **subbab baru 1.5.6 Batasan Interpretasi Hasil** (draft sudah
diberikan di percakapan sebelumnya) — dan tambahkan juga versi ringkas ini di
**Bab 3.1 Desain Penelitian** sebagai catatan metodologis eksplisit:

> "Perlu ditegaskan bahwa unit analisis dalam penelitian ini adalah sistem
> manajemen basis data secara utuh (PostgreSQL 17 dengan JSONB, expression
> index, dan driver asyncpg; serta MongoDB 8.0 dengan BSON, compound index,
> dan driver motor), yang diakses melalui lapisan API dan connection pool
> yang dibuat setara secara fungsional — bukan perbandingan format data
> JSONB dan BSON secara terisolasi dari komponen pendukungnya (mesin
> penyimpanan, strategi indexing, dan driver). Dengan demikian, hasil
> penelitian ini tidak dapat dan tidak dimaksudkan untuk disimpulkan sebagai
> 'JSONB lebih cepat daripada BSON' atau sebaliknya. Yang diukur dan
> dilaporkan adalah performa dua tumpukan teknologi (technology stack) yang
> berbeda secara arsitektural — mencakup mekanisme MVCC versus in-place
> update WiredTiger, strategi pengindeksan GIN/expression index versus
> compound B-Tree, serta karakteristik driver asinkron masing-masing — dalam
> kondisi beban kerja yang dibuat seekuivalen mungkin. Seluruh interpretasi
> dan kesimpulan pada penelitian ini secara konsisten merujuk pada 'sistem
> PostgreSQL' dan 'sistem MongoDB', bukan pada 'JSONB' dan 'BSON' sebagai
> entitas yang berdiri sendiri."

**Kenapa jawaban ini cukup untuk komentar dosen:** dosen tidak keberatan
dengan desain eksperimennya (dia bilang "ini tetap valid") — keberatannya
murni pada **klaim generalisasi** yang mungkin muncul di kesimpulan. Jadi
solusinya bukan mengubah eksperimen, tapi mengunci bahasa yang dipakai di
seluruh dokumen (judul boleh tetap pakai label "JSONB vs BSON" karena itu
konvensi penamaan umum di literatur pembanding, tapi setiap kesimpulan
substantif harus merujuk ke "sistem", bukan ke "format").

**Langkah tambahan disarankan:** lakukan pencarian kata `JSONB` dan `BSON`
di seluruh draft (terutama Bab 4/5 nanti saat menulis hasil) — setiap kali
kata itu muncul sebagai SUBJEK kalimat kesimpulan (misal "JSONB unggul..."),
ganti jadi "sistem PostgreSQL (dengan JSONB)..." supaya subjek kalimat
selalu sistem, bukan format data.
