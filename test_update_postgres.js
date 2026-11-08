/**
 * test_update_postgres.js
 * =======================
 * Skenario PARTIAL UPDATE — PostgreSQL JSONB
 * Memperbarui attributes.WiFi (nested depth-2) menggunakan jsonb_set()
 *
 * Cara menjalankan:
 *   k6 run test_update_postgres.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const pgUpdateLatency = new Trend('pg_update_latency', true);
const pgUpdateErrors  = new Rate('pg_update_error_rate');
const pgUpdateTotal   = new Counter('pg_update_total');

export const options = {
  scenarios: {
    pg_update_ramp: {
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
        { duration: '4m',  target: 256 },   // High concurrency plateau
        { duration: '1m',  target: 400 },
        { duration: '3m',  target: 400 },
        { duration: '1m',  target: 512 },
        { duration: '4m',  target: 512 },   // Peak concurrency plateau
        { duration: '2m',  target: 0   },
      ],
    },
  },

  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max', 'count'],

  thresholds: {
    'pg_update_latency': ['p(99)<15000'],
    'pg_update_error_rate': ['rate<0.05'],
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  const res = http.put(`${BASE_URL}/update/postgres`, null, {
    timeout: '30s',
  });

  const success = check(res, {
    'status 200': (r) => r.status === 200,
  });

  pgUpdateLatency.add(res.timings.duration);
  pgUpdateErrors.add(!success);
  pgUpdateTotal.add(1);
}

export function handleSummary(data) {
  return {
    'result_update_postgres.json': JSON.stringify(data, null, 2),
  };
}
