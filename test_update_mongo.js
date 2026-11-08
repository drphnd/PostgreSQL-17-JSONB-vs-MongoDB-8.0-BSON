/**
 * test_update_mongo.js
 * ====================
 * Skenario PARTIAL UPDATE — MongoDB BSON
 * Memperbarui attributes.WiFi (nested depth-2) menggunakan $set
 * IDENTIK dengan test_update_postgres.js kecuali endpoint URL.
 *
 * Cara menjalankan:
 *   k6 run test_update_mongo.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const mongoUpdateLatency = new Trend('mongo_update_latency', true);
const mongoUpdateErrors  = new Rate('mongo_update_error_rate');
const mongoUpdateTotal   = new Counter('mongo_update_total');

export const options = {
  scenarios: {
    mongo_update_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m',  target: 50  },
        { duration: '3m',  target: 50  },
        { duration: '1m',  target: 100 },
        { duration: '3m',  target: 100 },
        { duration: '1m',  target: 200 },
        { duration: '3m',  target: 200 },
        { duration: '1m',  target: 256 },
        { duration: '4m',  target: 256 },
        { duration: '1m',  target: 400 },
        { duration: '3m',  target: 400 },
        { duration: '1m',  target: 512 },
        { duration: '4m',  target: 512 },
        { duration: '2m',  target: 0   },
      ],
    },
  },

  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max', 'count'],

  thresholds: {
    'mongo_update_latency': ['p(99)<15000'],
    'mongo_update_error_rate': ['rate<0.05'],
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  const res = http.put(`${BASE_URL}/update/mongo`, null, {
    timeout: '30s',
  });

  const success = check(res, {
    'status 200': (r) => r.status === 200,
  });

  mongoUpdateLatency.add(res.timings.duration);
  mongoUpdateErrors.add(!success);
  mongoUpdateTotal.add(1);
}

export function handleSummary(data) {
  return {
    'result_update_mongo.json': JSON.stringify(data, null, 2),
  };
}
