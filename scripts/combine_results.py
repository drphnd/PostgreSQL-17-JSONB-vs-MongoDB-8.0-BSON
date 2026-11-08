#!/usr/bin/env python3
"""
combine_results.py

Menggabungkan seluruh file summary_scn*.csv menjadi satu tabel master,
dengan kolom tambahan yang mengidentifikasi metadata tiap skenario
(nomor skenario, sistem, operasi, jenis query, volume data) sehingga
mudah difilter/dipivot untuk membuat grafik dan tabel di Bab 4.

Pemakaian (dari folder ~/Riset_TA_Database):
  python scripts/combine_results.py

Output: hasil_final/master_table.csv
"""

import csv
import glob
import os

# Metadata tiap skenario -- disesuaikan manual karena nama file tidak
# 100% konsisten formatnya (beberapa pakai suffix _rerun, dsb).
# key: pattern yang dicari di nama file (tanpa 'summary_' dan '.csv')
SCENARIO_METADATA = {
    'scn1_read_postgres_full_nested':        {'no': 1,  'system': 'PostgreSQL', 'operation': 'READ',   'query_mode': 'nested', 'data_size': 150346},
    'scn2_read_mongo_full_nested':           {'no': 2,  'system': 'MongoDB',    'operation': 'READ',   'query_mode': 'nested', 'data_size': 150346},
    'scn3_update_postgres_full':             {'no': 3,  'system': 'PostgreSQL', 'operation': 'UPDATE', 'query_mode': '-',      'data_size': 150346},
    'scn4_update_mongo_full':                {'no': 4,  'system': 'MongoDB',    'operation': 'UPDATE', 'query_mode': '-',      'data_size': 150346},
    'scn5_read_postgres_full_flat':          {'no': 5,  'system': 'PostgreSQL', 'operation': 'READ',   'query_mode': 'flat',   'data_size': 150346},
    'scn6_read_mongo_full_flat':             {'no': 6,  'system': 'MongoDB',    'operation': 'READ',   'query_mode': 'flat',   'data_size': 150346},
    'scn7_read_postgres_50k_nested':         {'no': 7,  'system': 'PostgreSQL', 'operation': 'READ',   'query_mode': 'nested', 'data_size': 50000},
    'scn8_read_postgres_100k_nested':        {'no': 8,  'system': 'PostgreSQL', 'operation': 'READ',   'query_mode': 'nested', 'data_size': 100000},
    'scn8b_read_postgres_100k_nested_rerun': {'no': '8b','system': 'PostgreSQL','operation': 'READ',   'query_mode': 'nested', 'data_size': 100000},
    'scn9_read_mongo_50k_nested':            {'no': 9,  'system': 'MongoDB',    'operation': 'READ',   'query_mode': 'nested', 'data_size': 50000},
    'scn10_read_mongo_100k_nested':          {'no': 10, 'system': 'MongoDB',    'operation': 'READ',   'query_mode': 'nested', 'data_size': 100000},
    'scn11_update_postgres_50k':             {'no': 11, 'system': 'PostgreSQL', 'operation': 'UPDATE', 'query_mode': '-',      'data_size': 50000},
    'scn12_update_mongo_50k':                {'no': 12, 'system': 'MongoDB',    'operation': 'UPDATE', 'query_mode': '-',      'data_size': 50000},
}

CHECKPOINT_ORDER = ['vu_005', 'vu_050', 'vu_100', 'vu_200', 'vu_256', 'vu_400', 'vu_512']


def find_summary_files(search_dir='.'):
    pattern = os.path.join(search_dir, 'summary_*.csv')
    return sorted(glob.glob(pattern))


def label_from_filename(filepath):
    base = os.path.basename(filepath)
    label = base.replace('summary_', '').replace('.csv', '')
    return label


def main():
    files = find_summary_files('.')
    if not files:
        # Coba juga cari di hasil_final/ kalau dijalankan dari lokasi berbeda
        files = find_summary_files('hasil_final')

    if not files:
        print("Tidak ditemukan file summary_*.csv di direktori ini atau hasil_final/.")
        print("Jalankan script ini dari folder ~/Riset_TA_Database, atau dari folder hasil_final/.")
        return

    print(f"Ditemukan {len(files)} file summary:")
    for f in files:
        print(f"  - {f}")

    rows = []
    unmatched = []

    for filepath in files:
        label = label_from_filename(filepath)
        meta = SCENARIO_METADATA.get(label)
        if meta is None:
            unmatched.append(label)
            meta = {'no': '?', 'system': '?', 'operation': '?', 'query_mode': '?', 'data_size': '?'}

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                combined = {
                    'skenario_no': meta['no'],
                    'sistem': meta['system'],
                    'operasi': meta['operation'],
                    'jenis_query': meta['query_mode'],
                    'volume_data': meta['data_size'],
                    'checkpoint_vu': row['checkpoint'],
                    'count': row['count'],
                    'p50_ms': row['p50'],
                    'p95_ms': row['p95'],
                    'p99_ms': row['p99'],
                    'max_ms': row['max'],
                    'error_rate_pct': row['error_rate_pct'],
                    'source_file': label,
                }
                rows.append(combined)

    if unmatched:
        print("\nPERINGATAN: file berikut tidak dikenali metadatanya (kolom skenario diisi '?'):")
        for u in unmatched:
            print(f"  - {u}")
        print("Tambahkan entrinya secara manual ke SCENARIO_METADATA di script ini jika perlu.\n")

    # Urutkan: skenario_no, lalu urutan checkpoint VU logis
    def checkpoint_sort_key(cp):
        try:
            return CHECKPOINT_ORDER.index(cp)
        except ValueError:
            return 999

    rows.sort(key=lambda r: (str(r['skenario_no']), checkpoint_sort_key(r['checkpoint_vu'])))

    os.makedirs('hasil_final', exist_ok=True)
    output_path = os.path.join('hasil_final', 'master_table.csv')

    fieldnames = ['skenario_no', 'sistem', 'operasi', 'jenis_query', 'volume_data',
                  'checkpoint_vu', 'count', 'p50_ms', 'p95_ms', 'p99_ms', 'max_ms',
                  'error_rate_pct', 'source_file']

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nTabel master disimpan ke: {output_path}")
    print(f"Total baris: {len(rows)} (13 skenario x 7 checkpoint = idealnya 91 baris)")


if __name__ == '__main__':
    main()
