// test_read_postgres.js
// Perbaikan dari versi sebelumnya:
// - TIDAK lagi pakai custom Trend + Date.now() manual (sumber clock drift / min negatif).
//   Latensi diambil murni dari metrik bawaan k6 `http_req_duration`, yang dihitung
//   di satu proses (k6) sehingga tidak rentan cross-clock drift.
// - Checkpoint VU dipisah per-scenario (lihat build_scenarios.js) supaya p95/p99
//   bisa diekstraksi bersih per level VU, bukan campuran seluruh 29 menit.
// - Mendukung QUERY_MODE=flat (single-field, baseline) atau nested (default,
//   multikriteria pada atribut bersarang) via environment variable.
//
// Jalankan:
//   k6 run -e QUERY_MODE=nested -e DATA_SIZE=full --out json=result_read_postgres_full.ndjson test_read_postgres.js
//   k6 run -e QUERY_MODE=flat   -e DATA_SIZE=full --out json=result_read_postgres_flat.ndjson  test_read_postgres.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, DEFAULT_THRESHOLDS } from './config.js';
import { buildSequentialScenarios } from './build_scenarios.js';

const QUERY_MODE = __ENV.QUERY_MODE || 'nested'; // 'nested' | 'flat'
const DATA_SIZE = __ENV.DATA_SIZE || 'full';     // 'full' | '100k' | '50k' -- hanya label untuk tagging hasil
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '3s';

// Metrik dekomposisi latensi -- menangkap header X-Pool-Wait-Ms dan
// X-DB-Exec-Ms yang dikirim FastAPI, untuk memisahkan waktu tunggu
// connection pool dari waktu eksekusi murni di database engine.
// Menjawab kritik bahwa http_req_duration K6 (level HTTP) berpotensi
// tercemar antrean pool, bukan murni performa DBMS.
const poolWaitTrend = new Trend('pool_wait_ms', true);
const dbExecTrend = new Trend('db_exec_ms', true);

export const options = {
  scenarios: buildSequentialScenarios('readPostgres'),
  thresholds: DEFAULT_THRESHOLDS,
  discardResponseBodies: true, // header tetap terbaca meski body di-discard -- mengurangi beban memori/IO
  tags: { db: 'postgres', operation: 'read', query_mode: QUERY_MODE, data_size: DATA_SIZE },
};

export function readPostgres() {
  const url = `${BASE_URL}/read/postgres?mode=${QUERY_MODE}`;
  const res = http.get(url, {
    timeout: REQUEST_TIMEOUT, // PENTING: timeout ketat (default 3s, bukan 60s
                               // default k6) supaya request yang terjebak
                               // antre di connection pool tercatat sebagai
                               // timeout/error_rate, bukan membengkakkan P99
                               // secara artifisial.
    tags: { db: 'postgres', operation: 'read', query_mode: QUERY_MODE, data_size: DATA_SIZE },
  });
  check(res, {
    'status 200': (r) => r.status === 200,
    'not timeout': (r) => r.status !== 0,
  });

  const poolWait = parseFloat(res.headers['X-Pool-Wait-Ms']);
  const dbExec = parseFloat(res.headers['X-Db-Exec-Ms']); // k6 menormalkan casing header
  if (!isNaN(poolWait)) poolWaitTrend.add(poolWait);
  if (!isNaN(dbExec)) dbExecTrend.add(dbExec);

  sleep(0.05); // jeda kecil supaya VU tidak spam murni back-to-back tanpa jeda realistis
}
