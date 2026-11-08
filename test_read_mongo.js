/**
 * test_read_mongo.js
 * ==================
 * Skenario READ — MongoDB BSON
 * IDENTIK dengan test_read_postgres.js kecuali endpoint URL.
 * Ini yang membuat perbandingan apple-to-apple.
 *
 * Cara menjalankan (SETELAH PostgreSQL selesai, restart server dulu):
 *   k6 run test_read_mongo.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const mongoReadLatency = new Trend('mongo_read_latency', true);
const mongoReadErrors  = new Rate('mongo_read_error_rate');
const mongoReadTotal   = new Counter('mongo_read_total');

export const options = {
  // IDENTIK dengan test_read_postgres.js
  scenarios: {
    mongo_read_ramp: {
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
    'mongo_read_latency': ['p(99)<10000'],
    'mongo_read_error_rate': ['rate<0.05'],
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/read/mongo`, {
    timeout: '30s',
  });

  const success = check(res, {
    'status 200': (r) => r.status === 200,
    'response has count': (r) => {
      try {
        return JSON.parse(r.body).count !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  mongoReadLatency.add(res.timings.duration);
  mongoReadErrors.add(!success);
  mongoReadTotal.add(1);
}

export function handleSummary(data) {
  return {
    'result_read_mongo.json': JSON.stringify(data, null, 2),
  };
}
