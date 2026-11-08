/**
 * test_read_postgres.js
 * =====================
 * Skenario READ — PostgreSQL JSONB
 * Filter multikriteria pada atribut bersarang (depth-2)
 *
 * Cara menjalankan:
 *   k6 run test_read_postgres.js
 *
 * Desain ramping mengikuti BAB 1 rumusan masalah:
 * - Pengujian bertahap: 50 → 100 → 200 → 256 → 400 → 512 VU
 * - Total durasi: ~30 menit (sesuai komitmen BAB 1)
 * - Setiap plateau minimal 4 menit untuk menangkap sustained peak
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Metrik custom agar lebih mudah dibaca di laporan
const pgReadLatency = new Trend('pg_read_latency', true);
const pgReadErrors  = new Rate('pg_read_error_rate');
const pgReadTotal   = new Counter('pg_read_total');

export const options = {
  scenarios: {
    pg_read_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        // Warmup — biarkan JIT dan connection pool stabil
        { duration: '2m',  target: 50  },   // Naik ke 50 VU
        { duration: '3m',  target: 50  },   // Plateau 50 VU (low concurrency)

        { duration: '1m',  target: 100 },   // Naik ke 100 VU
        { duration: '3m',  target: 100 },   // Plateau 100 VU

        { duration: '1m',  target: 200 },   // Naik ke 200 VU
        { duration: '3m',  target: 200 },   // Plateau 200 VU

        { duration: '1m',  target: 256 },   // Naik ke 256 VU (high concurrency)
        { duration: '4m',  target: 256 },   // Plateau 256 VU — TITIK UKUR UTAMA RQ1

        { duration: '1m',  target: 400 },   // Naik ke 400 VU
        { duration: '3m',  target: 400 },   // Plateau 400 VU

        { duration: '1m',  target: 512 },   // Naik ke 512 VU (peak concurrency)
        { duration: '4m',  target: 512 },   // Plateau 512 VU — TITIK UKUR UTAMA RQ1

        { duration: '2m',  target: 0   },   // Cooldown
      ],
    },
  },

  // Tampilkan P95 dan P99 di summary — sesuai RQ1
  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max', 'count'],

  // Threshold: penelitian akan GAGAL (merah) jika P99 melebihi batas ini
  // Sesuaikan nilai ini setelah run pertama jika perlu
  thresholds: {
    'pg_read_latency': ['p(99)<10000'],  // P99 < 10 detik (longgar dulu)
    'pg_read_error_rate': ['rate<0.05'], // Error rate < 5%
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/read/postgres`, {
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

  // Catat ke metrik custom
  pgReadLatency.add(res.timings.duration);
  pgReadErrors.add(!success);
  pgReadTotal.add(1);
}

export function handleSummary(data) {
  // Cetak ringkasan ke file JSON agar bisa dibandingkan dengan MongoDB nanti
  return {
    'result_read_postgres.json': JSON.stringify(data, null, 2),
  };
}
