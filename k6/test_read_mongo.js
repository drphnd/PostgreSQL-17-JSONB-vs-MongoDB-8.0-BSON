// test_read_mongo.js -- setara fungsional dengan test_read_postgres.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, DEFAULT_THRESHOLDS } from './config.js';
import { buildSequentialScenarios } from './build_scenarios.js';

const QUERY_MODE = __ENV.QUERY_MODE || 'nested';
const DATA_SIZE = __ENV.DATA_SIZE || 'full';
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '3s';

const poolWaitTrend = new Trend('pool_wait_ms', true);
const dbExecTrend = new Trend('db_exec_ms', true);

export const options = {
  scenarios: buildSequentialScenarios('readMongo'),
  thresholds: DEFAULT_THRESHOLDS,
  discardResponseBodies: true, // header tetap terbaca meski body di-discard -- mengurangi beban memori/IO
  tags: { db: 'mongodb', operation: 'read', query_mode: QUERY_MODE, data_size: DATA_SIZE },
};

export function readMongo() {
  const url = `${BASE_URL}/read/mongo?mode=${QUERY_MODE}`;
  const res = http.get(url, {
    timeout: REQUEST_TIMEOUT,
    tags: { db: 'mongodb', operation: 'read', query_mode: QUERY_MODE, data_size: DATA_SIZE },
  });
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
