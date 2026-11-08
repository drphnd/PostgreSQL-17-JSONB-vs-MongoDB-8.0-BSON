// config.js
// Konfigurasi bersama untuk seluruh skrip pengujian K6.
// Perubahan penting dari versi sebelumnya:
// 1. Checkpoint VU dipisah jadi scenario k6 tersendiri (constant-vus),
//    bukan satu ramping-vus tunggal. K6 otomatis men-tag setiap metrik
//    dengan `scenario:<nama>` sehingga p95/p99 per level VU bisa
//    diekstraksi secara terisolasi, bukan tercampur dari seluruh durasi test.
// 2. Baseline VU sangat rendah (5 VU) ditambahkan sebagai true baseline.

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Setiap checkpoint: [nama_scenario, jumlah_VU, durasi_pengukuran]
// Durasi checkpoint utama (256, 512) dibuat lebih panjang (4 menit)
// sesuai kebutuhan "sustained peak load" yang sudah kamu klaim di Tabel 3.3.
export const CHECKPOINTS = [
  { name: 'vu_005', vus: 5,   duration: '1m' },
  { name: 'vu_050', vus: 50,  duration: '3m' },
  { name: 'vu_100', vus: 100, duration: '3m' },
  { name: 'vu_200', vus: 200, duration: '3m' },
  { name: 'vu_256', vus: 256, duration: '4m' },
  { name: 'vu_400', vus: 400, duration: '3m' },
  { name: 'vu_512', vus: 512, duration: '4m' },
];

// Jeda transisi antar checkpoint (graceful ramp singkat, bukan instan,
// supaya connection pool tidak dikejutkan oleh lonjakan VU seketika)
export const RAMP_UP = '20s';

// Threshold global -- dipakai untuk menandai kegagalan skenario secara jelas
// (bukan cuma warning log yang terserak seperti sebelumnya)
export const DEFAULT_THRESHOLDS = {
  http_req_failed: [{ threshold: 'rate<0.50', abortOnFail: false }],
};
