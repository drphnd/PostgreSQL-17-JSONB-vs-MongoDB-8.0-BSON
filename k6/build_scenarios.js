// build_scenarios.js
// Membangun object `scenarios` k6 secara otomatis dari daftar CHECKPOINTS,
// dengan startTime berurutan (sequential), masing-masing sebagai
// constant-vus executor terpisah + ramp-up singkat sebelum plateau.
//
// Kenapa begini, bukan satu ramping-vus besar seperti sebelumnya:
// - Setiap checkpoint jadi unit pengukuran independen dan bersih
// - k6 otomatis menambahkan tag `scenario:<name>` pada SETIAP data point
//   metrik (termasuk http_req_duration), sehingga saat post-processing
//   kita bisa filter p95/p99 murni per level VU, bukan campuran seluruh run.

import { CHECKPOINTS, RAMP_UP } from './config.js';

// MODE SINGKAT -- diaktifkan lewat env var SHORT_MODE=1, dirancang untuk
// mengurangi risiko instabilitas WSL2 pada sisa pengujian dengan cara
// melewati checkpoint VU rendah (5-200) yang perilakunya sudah diketahui
// stabil dari data sebelumnya, dan hanya fokus ke DUA titik ukur utama
// RQ1 (256 dan 512 VU). Ini memangkas durasi total dari ~25 menit
// menjadi ~9 menit, dan volume data tulis (ndjson) sekitar 70% lebih
// kecil -- secara signifikan mengurangi jendela eksposur terhadap
// crash WSL2 yang berulang kali terjadi pada beban penuh.
const SHORT_MODE = __ENV.SHORT_MODE === '1';
const ACTIVE_CHECKPOINTS = SHORT_MODE
  ? CHECKPOINTS.filter((cp) => cp.name === 'vu_256' || cp.name === 'vu_512')
  : CHECKPOINTS;

export function buildSequentialScenarios(execName) {
  const scenarios = {};
  let cursorSeconds = 0;

  ACTIVE_CHECKPOINTS.forEach((cp) => {
    const rampSeconds = parseDuration(RAMP_UP);
    const plateauSeconds = parseDuration(cp.duration);

    scenarios[cp.name] = {
      executor: 'ramping-vus',
      exec: execName,
      startVUs: 0,
      startTime: `${cursorSeconds}s`,
      stages: [
        { target: cp.vus, duration: RAMP_UP },       // ramp naik ke target
        { target: cp.vus, duration: cp.duration },    // plateau -- ini yang diukur
      ],
      gracefulRampDown: '10s',
      tags: { checkpoint: cp.name, target_vu: String(cp.vus) },
    };

    cursorSeconds += rampSeconds + plateauSeconds + 10; // +10s graceful buffer
  });

  return scenarios;
}

function parseDuration(str) {
  // Konversi sederhana "3m" / "20s" -> detik
  const m = str.match(/^(\d+)([sm])$/);
  const val = parseInt(m[1], 10);
  return m[2] === 'm' ? val * 60 : val;
}
