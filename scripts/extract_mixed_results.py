#!/usr/bin/env python3
"""
extract_mixed_results.py

Varian extract_results.py khusus untuk skenario mixed workload -- selain
mengelompokkan per checkpoint VU, script ini JUGA memisahkan berdasarkan
tag 'op' (read/update), sehingga latensi READ dan UPDATE yang tercampur
dalam satu run bisa diekstraksi terpisah dan dibandingkan langsung dengan
baseline skenario terisolasi (Skenario 1 untuk read, Skenario 3/4 untuk
update).

Pemakaian:
  python extract_mixed_results.py mixed_postgres.ndjson --label mixed_postgres
"""

import argparse
import json
import time
from collections import defaultdict


def percentile(sorted_data, p):
    if not sorted_data:
        return None
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ndjson_file')
    parser.add_argument('--label', default='mixed_result')
    args = parser.parse_args()

    # key: (checkpoint, op) -> list nilai
    durations = defaultdict(list)
    failed = defaultdict(int)
    total = defaultdict(int)
    negative_count = 0

    print(f'Memproses {args.ndjson_file} ...')
    t0 = time.time()
    lines_scanned = 0
    lines_matched = 0

    with open(args.ndjson_file, 'r') as f:
        for line in f:
            lines_scanned += 1
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
                print(f'  ... {lines_matched} data point diproses ({time.time()-t0:.1f}s)')

            tags = record['data'].get('tags', {})
            checkpoint = tags.get('checkpoint', 'unknown')
            op = tags.get('op', 'unknown')  # 'read' atau 'update'
            key = (checkpoint, op)
            value = record['data']['value']
            status = tags.get('status', '')

            is_failed = (status == '0') or (status.isdigit() and int(status) >= 400)
            if is_failed:
                failed[key] += 1
                total[key] += 1
                continue

            if value < 0:
                negative_count += 1
                continue

            durations[key].append(value)
            total[key] += 1

    print(f'\nSelesai: {lines_scanned} baris dipindai, {lines_matched} data point cocok, '
          f'{time.time()-t0:.1f}s\n')
    print(f'=== Ringkasan Mixed Workload: {args.label} ===')
    print(f'Total nilai negatif (dikecualikan): {negative_count}\n')

    header = f"{'checkpoint':<12}{'op':<8}{'count':>10}{'p50':>10}{'p95':>10}{'p99':>10}{'error_rate%':>13}"
    print(header)
    print('-' * len(header))

    CHECKPOINT_ORDER = ['vu_005', 'vu_050', 'vu_100', 'vu_200', 'vu_256', 'vu_400', 'vu_512']
    all_keys = set(total.keys()) | set(durations.keys())

    def sort_key(k):
        cp, op = k
        cp_idx = CHECKPOINT_ORDER.index(cp) if cp in CHECKPOINT_ORDER else 999
        return (cp_idx, op)

    rows = []
    for key in sorted(all_keys, key=sort_key):
        cp, op = key
        vals = sorted(durations.get(key, []))
        n = len(vals)
        err_rate = 100 * failed[key] / total[key] if total[key] else 0

        if n == 0:
            print(f"{cp:<12}{op:<8}{n:>10}{'--':>10}{'--':>10}{'--':>10}{err_rate:>13.2f}")
            rows.append([cp, op, n, '', '', '', err_rate])
            continue

        p50 = percentile(vals, 50)
        p95 = percentile(vals, 95)
        p99 = percentile(vals, 99)
        print(f"{cp:<12}{op:<8}{n:>10}{p50:>10.2f}{p95:>10.2f}{p99:>10.2f}{err_rate:>13.2f}")
        rows.append([cp, op, n, p50, p95, p99, err_rate])

    out_csv = f'summary_{args.label}.csv'
    with open(out_csv, 'w') as f:
        f.write('checkpoint,op,count,p50,p95,p99,error_rate_pct\n')
        for r in rows:
            f.write(','.join(str(x) for x in r) + '\n')
    print(f'\nDisimpan ke {out_csv}')
    print('\nLangkah selanjutnya: bandingkan kolom p99 pada baris op="read" di sini')
    print('dengan p99 Skenario 1 (PostgreSQL)/2 (MongoDB) pada checkpoint yang sama,')
    print('dan baris op="update" dengan Skenario 3/4, untuk mengukur interferensi')
    print('akibat beban campuran dibandingkan kondisi terisolasi.')


if __name__ == '__main__':
    main()
