#!/usr/bin/env python3
"""
extract_results.py

Mem-parsing output K6 dalam format NDJSON PENUH (bukan hanya summary akhir),
lalu mengelompokkan http_req_duration berdasarkan tag `checkpoint` (vu_005,
vu_050, ..., vu_512) yang otomatis ditempel k6 pada setiap scenario.

Ini yang memperbaiki masalah utama sebelumnya: p99 yang dilaporkan sekarang
BENAR-BENAR terisolasi per level VU, bukan agregat seluruh 29 menit run.

Pemakaian:
  k6 run --out json=raw_read_postgres.ndjson test_read_postgres.js
  python extract_results.py raw_read_postgres.ndjson --label read_postgres

Output: summary_<label>.csv berisi p50/p95/p99/min/max/count/error_rate per checkpoint,
serta ringkasan resource (jika file CSV monitor_resources.sh disediakan).
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict


def percentile(sorted_data, p):
    """Asumsikan input SUDAH terurut (sorted) -- dipanggil berulang per checkpoint
    tanpa sort ulang, penting untuk performa pada dataset jutaan baris."""
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ndjson_file')
    parser.add_argument('--label', default='result')
    parser.add_argument('--resources_csv', default=None,
                         help='Opsional: file CSV dari monitor_resources.sh untuk digabungkan')
    args = parser.parse_args()

    negative_count = 0
    lines_scanned = 0
    lines_matched = 0
    durations_by_checkpoint = defaultdict(list)
    failed_by_checkpoint = defaultdict(int)
    total_by_checkpoint = defaultdict(int)

    print(f'Memproses {args.ndjson_file} ... (bisa memakan waktu beberapa menit untuk file besar)')
    t0 = time.time()

    with open(args.ndjson_file, 'r') as f:
        for line in f:
            lines_scanned += 1

            # OPTIMASI: file NDJSON k6 mencatat SEMUA metrik (http_req_blocked,
            # connecting, sending, checks, iterations, vus, dst), bukan cuma
            # http_req_duration. Untuk file besar (jutaan baris), parsing JSON
            # penuh di SETIAP baris sangat lambat. Substring check dulu sebelum
            # json.loads() mempercepat drastis karena >90% baris langsung di-skip
            # tanpa parsing penuh.
            if '"metric":"http_req_duration"' not in line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get('type') != 'Point':
                continue

            lines_matched += 1
            if lines_matched % 200000 == 0:
                elapsed = time.time() - t0
                print(f'  ... {lines_matched} data point diproses ({elapsed:.1f}s berlalu)')

            tags = record['data'].get('tags', {})
            checkpoint = tags.get('checkpoint', 'unknown')
            value = record['data']['value']
            status = tags.get('status', '')

            # PENGERASAN PIPELINE: request yang gagal (status 0 = timeout/
            # connection error, atau status >= 400) dikecualikan dari
            # perhitungan P95/P99 latensi -- menjawab kritik bahwa request
            # gagal yang tercatat "cepat" (mis. langsung ditolak) berpotensi
            # mencemari persentil latensi secara palsu ke bawah. Error rate
            # tetap dihitung terpisah sebagai metrik independen.
            is_failed = (status == '0') or (status.isdigit() and int(status) >= 400)

            if is_failed:
                failed_by_checkpoint[checkpoint] += 1
                total_by_checkpoint[checkpoint] += 1
                continue  # TIDAK ikut masuk ke perhitungan latensi

            if value < 0:
                negative_count += 1
                continue  # tetap dikecualikan dari agregasi utama, tapi DIHITUNG dan dilaporkan eksplisit

            durations_by_checkpoint[checkpoint].append(value)
            total_by_checkpoint[checkpoint] += 1

    elapsed = time.time() - t0
    print(f'Selesai parsing: {lines_scanned} baris dipindai, {lines_matched} data point cocok, dalam {elapsed:.1f}s')

    print(f'\n=== Ringkasan: {args.label} ===')
    print(f'Total data point dengan nilai negatif (dikecualikan): {negative_count}\n')

    header = f"{'checkpoint':<12}{'count':>10}{'p50':>10}{'p95':>10}{'p99':>10}{'max':>10}{'error_rate%':>13}"
    print(header)
    print('-' * len(header))

    rows = []
    # PENTING: iterasi atas gabungan checkpoint dari total_by_checkpoint
    # (bukan hanya durations_by_checkpoint), supaya checkpoint dengan
    # error rate 100% (seluruh request gagal, tidak ada nilai durasi valid
    # sama sekali) TETAP muncul di laporan -- bukan hilang diam-diam.
    # Ini krusial khususnya untuk analisis sensitivitas timeout ketat, di
    # mana checkpoint beban tinggi berpotensi mengalami kegagalan masif.
    all_checkpoints = sorted(set(total_by_checkpoint.keys()) | set(durations_by_checkpoint.keys()))
    for cp in all_checkpoints:
        vals = sorted(durations_by_checkpoint.get(cp, []))
        n = len(vals)
        err_rate = 100 * failed_by_checkpoint[cp] / total_by_checkpoint[cp] if total_by_checkpoint[cp] else 0

        if n == 0:
            # Seluruh request pada checkpoint ini gagal -- tidak ada nilai
            # durasi valid untuk dihitung persentilnya.
            print(f"{cp:<12}{n:>10}{'--':>10}{'--':>10}{'--':>10}{'--':>10}{err_rate:>13.2f}")
            rows.append([cp, n, '', '', '', '', err_rate])
            continue

        p50 = percentile(vals, 50)
        p95 = percentile(vals, 95)
        p99 = percentile(vals, 99)
        vmax = vals[-1]
        print(f"{cp:<12}{n:>10}{p50:>10.2f}{p95:>10.2f}{p99:>10.2f}{vmax:>10.2f}{err_rate:>13.2f}")
        rows.append([cp, n, p50, p95, p99, vmax, err_rate])

    out_csv = f'summary_{args.label}.csv'
    with open(out_csv, 'w') as f:
        f.write('checkpoint,count,p50,p95,p99,max,error_rate_pct\n')
        for r in rows:
            f.write(','.join(str(x) for x in r) + '\n')
    print(f'\nDisimpan ke {out_csv}')

    if args.resources_csv:
        summarize_resources(args.resources_csv, args.label)


def summarize_resources(csv_path, label):
    import csv
    rows_by_container = defaultdict(list)
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cpu = float(row['cpu_percent'])
                mem = float(row['mem_usage_mib'])
            except (ValueError, TypeError):
                continue
            rows_by_container[row['container']].append((cpu, mem))

    print(f'\n=== Resource summary: {args.label if False else label} ===')
    for container, vals in rows_by_container.items():
        cpus = [v[0] for v in vals]
        mems = [v[1] for v in vals]
        print(f'{container}: CPU avg={statistics.mean(cpus):.2f}% '
              f'stdev={statistics.pstdev(cpus):.2f}% max={max(cpus):.2f}% | '
              f'MEM avg={statistics.mean(mems):.1f}MiB max={max(mems):.1f}MiB')


if __name__ == '__main__':
    main()
