// test_mixed_postgres.js
//
// Skenario MIXED WORKLOAD -- menjawab kritik bahwa pengujian read dan
// update yang terisolasi (Skenario 1 & 3) menghilangkan kontensi lock
// dan interaksi snapshot isolation MVCC yang justru menjadi pembeda
// arsitektural utama PostgreSQL vs MongoDB pada kondisi produksi nyata.
//
// Setiap iterasi VU secara acak memilih READ (nested) atau UPDATE dengan
// proporsi READ_RATIO (default 0.8 -- pola OLTP umum: mayoritas baca,
// sebagian kecil tulis), bukan dua fungsi paralel terpisah, sehingga
// read dan write benar-benar tercampur dan berebut resource/lock secara
// alami dalam satu aliran request per VU.
//
// Jalankan:
//   k6 run -e DATA_SIZE=full -e READ_RATIO=0.8 \
//     --out json=mixed_postgres.ndjson k6/test_mixed_postgres.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, DEFAULT_THRESHOLDS } from './config.js';
import { buildSequentialScenarios } from './build_scenarios.js';

const DATA_SIZE = __ENV.DATA_SIZE || 'full';
const READ_RATIO = parseFloat(__ENV.READ_RATIO || '0.8'); // 80% read, 20% update
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '3s';

const poolWaitTrend = new Trend('pool_wait_ms', true);
const dbExecTrend = new Trend('db_exec_ms', true);

export const options = {
  scenarios: buildSequentialScenarios('mixedPostgres'),
  thresholds: DEFAULT_THRESHOLDS,
  discardResponseBodies: true, // header tetap terbaca meski body di-discard -- mengurangi beban memori/IO
  tags: { db: 'postgres', operation: 'mixed', data_size: DATA_SIZE },
};

export function mixedPostgres() {
  const isRead = Math.random() < READ_RATIO;
  let res;

  if (isRead) {
    const url = `${BASE_URL}/read/postgres?mode=nested`;
    res = http.get(url, {
      timeout: REQUEST_TIMEOUT,
      // PENTING: tag 'op' ditambahkan supaya extract_mixed_results.py bisa
      // memisahkan latensi READ dari UPDATE meski tercampur dalam satu run,
      // untuk dibandingkan dengan baseline Skenario 1 (read terisolasi).
      tags: { db: 'postgres', operation: 'mixed', op: 'read', data_size: DATA_SIZE },
    });
  } else {
    const randomId = Math.floor(Math.random() * 150346);
    const url = `${BASE_URL}/update/postgres`;
    const payload = JSON.stringify({ index: randomId, wifi_value: 'free' });
    res = http.put(url, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: REQUEST_TIMEOUT,
      // dibandingkan dengan baseline Skenario 3 (update terisolasi).
      tags: { db: 'postgres', operation: 'mixed', op: 'update', data_size: DATA_SIZE },
    });
  }

  check(res, {
    'status 200': (r) => r.status === 200,
    'not timeout': (r) => r.status !== 0,
  });

  const poolWait = parseFloat(res.headers['X-Pool-Wait-Ms']);
  const dbExec = parseFloat(res.headers['X-Db-Exec-Ms']);
  if (!isNaN(poolWait)) poolWaitTrend.add(poolWait);
  if (!isNaN(dbExec)) dbExecTrend.add(dbExec);

  sleep(0.05);
}
