// test_mixed_mongo.js -- setara fungsional dengan test_mixed_postgres.js
//
// Menguji apakah WiredTiger MongoDB menunjukkan pola interferensi
// read-write yang berbeda dari PostgreSQL MVCC pada kondisi beban
// campuran, sebagai pembanding langsung terhadap test_mixed_postgres.js.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, DEFAULT_THRESHOLDS } from './config.js';
import { buildSequentialScenarios } from './build_scenarios.js';

const DATA_SIZE = __ENV.DATA_SIZE || 'full';
const READ_RATIO = parseFloat(__ENV.READ_RATIO || '0.8');
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '3s';

const poolWaitTrend = new Trend('pool_wait_ms', true);
const dbExecTrend = new Trend('db_exec_ms', true);

export const options = {
  scenarios: buildSequentialScenarios('mixedMongo'),
  thresholds: DEFAULT_THRESHOLDS,
  discardResponseBodies: true, // header tetap terbaca meski body di-discard -- mengurangi beban memori/IO
  tags: { db: 'mongodb', operation: 'mixed', data_size: DATA_SIZE },
};

export function mixedMongo() {
  const isRead = Math.random() < READ_RATIO;
  let res;

  if (isRead) {
    const url = `${BASE_URL}/read/mongo?mode=nested`;
    res = http.get(url, {
      timeout: REQUEST_TIMEOUT,
      tags: { db: 'mongodb', operation: 'mixed', op: 'read', data_size: DATA_SIZE },
    });
  } else {
    const randomId = Math.floor(Math.random() * 150346);
    const url = `${BASE_URL}/update/mongo`;
    const payload = JSON.stringify({ index: randomId, wifi_value: 'free' });
    res = http.put(url, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: REQUEST_TIMEOUT,
      tags: { db: 'mongodb', operation: 'mixed', op: 'update', data_size: DATA_SIZE },
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
