// quick_verify_mongo_update.js
//
// Versi RINGAN khusus untuk verifikasi swap host (Fase 1c) -- BUKAN
// bagian dari data eksperimen utama. Alih-alih arsitektur 7-checkpoint
// 24 menit penuh (yang 2x memicu crash Bus error di titik ini), skrip
// ini hanya naik singkat ke 512 VU selama 2 menit, cukup untuk menjawab
// pertanyaan "apakah swap terpakai di beban puncak" tanpa volume
// tulis-disk sebesar skenario penuh.
//
// Jalankan:
//   k6 run -e DATA_SIZE=50000 quick_verify_mongo_update.js
// (TIDAK perlu --out json= -- cukup ringkasan akhir k6, karena kita
//  cuma butuh korelasi waktu dengan host_memory_verification.csv)

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = '3s';

export const options = {
  scenarios: {
    quick_peak: {
      executor: 'ramping-vus',
      exec: 'quickUpdate',
      startVUs: 0,
      stages: [
        { target: 512, duration: '30s' },  // ramp cepat ke puncak
        { target: 512, duration: '2m' },   // tahan 2 menit -- cukup untuk verifikasi memori
        { target: 0, duration: '20s' },    // cooldown singkat
      ],
      gracefulRampDown: '10s',
    },
  },
  discardResponseBodies: true,
};

export function quickUpdate() {
  const randomId = Math.floor(Math.random() * 50000);
  const url = `${BASE_URL}/update/mongo`;
  const payload = JSON.stringify({ index: randomId, wifi_value: 'free' });
  const res = http.put(url, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: REQUEST_TIMEOUT,
  });
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.05);
}
