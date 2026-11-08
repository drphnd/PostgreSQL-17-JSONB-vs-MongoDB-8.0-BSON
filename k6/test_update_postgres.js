// test_update_postgres.js
// Perbaikan: timeout eksplisit diset (bukan default k6 60s yang menutupi
// pola kegagalan asli), dan setiap gagal request dicatat sebagai `check`
// gagal (bukan cuma WARN log yang sulit dihitung otomatis).

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, DEFAULT_THRESHOLDS } from './config.js';
import { buildSequentialScenarios } from './build_scenarios.js';

const DATA_SIZE = __ENV.DATA_SIZE || 'full';
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '3s'; // eksplisit, bukan default tersembunyi

const poolWaitTrend = new Trend('pool_wait_ms', true);
const dbExecTrend = new Trend('db_exec_ms', true);

export const options = {
  scenarios: buildSequentialScenarios('updatePostgres'),
  thresholds: DEFAULT_THRESHOLDS,
  discardResponseBodies: true, // header tetap terbaca meski body di-discard -- mengurangi beban memori/IO
  tags: { db: 'postgres', operation: 'update', data_size: DATA_SIZE },
};

// business_id dipilih pseudo-random dari rentang dataset supaya update
// tersebar (mendekati pola write nyata), bukan selalu menimpa baris yang sama.
export function updatePostgres() {
  const randomId = Math.floor(Math.random() * 150346);
  const url = `${BASE_URL}/update/postgres`;
  const payload = JSON.stringify({ index: randomId, wifi_value: 'free' });
  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: REQUEST_TIMEOUT,
    tags: { db: 'postgres', operation: 'update', data_size: DATA_SIZE },
  };
  const res = http.put(url, payload, params);
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
