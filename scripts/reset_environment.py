#!/usr/bin/env python3
"""
reset_environment.py

Mereset kedua basis data ke kondisi bersih sebelum SETIAP skenario dijalankan.
Ini krusial karena hasil sebelumnya diketahui tercemar akumulasi state
lintas-run (dead tuple PostgreSQL menumpuk dari 3x eksekusi berturut-turut
tanpa reset).

Yang dilakukan:
1. TRUNCATE tabel PostgreSQL / drop-recreate koleksi MongoDB
2. Re-ingest dataset dari file JSONL Yelp, dengan opsi ukuran subset
   (untuk skenario variasi volume data: 50000 / 100000 / full)
3. Rebuild index yang setara secara fungsional pada kedua sistem
4. VACUUM ANALYZE PostgreSQL (memastikan dead tuple mulai dari 0%)
5. Mencetak konfirmasi n_live_tup / n_dead_tup sebagai bukti kondisi awal bersih

Pemakaian:
  python reset_environment.py --size full
  python reset_environment.py --size 100000
  python reset_environment.py --size 50000
"""

import argparse
import ast
import json
import time
import psycopg2
from pymongo import MongoClient

PG_CONFIG = dict(host='localhost', port=5432, database='yelp_db',
                  user='admin', password='password123')
MONGO_URI = 'mongodb://localhost:27017'
DATASET_PATH = 'yelp_academic_dataset_business.json'
BATCH_SIZE = 5000


def clean_attribute_value(v):
    """
    Membersihkan nilai atribut yang tersimpan sebagai representasi string
    Python (artifak dataset asli Yelp), mis. "u'free'" -> 'free',
    "True" -> True (boolean asli), "{'garage': False}" -> dict asli.
    Nilai yang memang sudah berupa string/angka biasa (mis. "2" untuk
    RestaurantsPriceRange2) dibiarkan apa adanya -- tidak dipaksa konversi
    supaya tidak mengubah semantik data yang sebenarnya sudah benar.
    """
    if not isinstance(v, str):
        return v
    s = v.strip()

    if s in ('True', 'False', 'None'):
        return ast.literal_eval(s)

    # strip prefix u' / u" (unicode-literal repr dari Python 2)
    if s.startswith("u'") or s.startswith('u"'):
        s = s[1:]

    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return v

    if s.startswith('{') and s.endswith('}'):
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return v

    return v  # biarkan apa adanya, mis. "2", "Philadelphia", dst.


def clean_document(doc):
    attrs = doc.get('attributes')
    if isinstance(attrs, dict):
        doc['attributes'] = {k: clean_attribute_value(v) for k, v in attrs.items()}
    elif attrs is None:
        # PENTING: sebagian dokumen Yelp punya attributes: null (bukan {} kosong).
        # Kalau dibiarkan null, operasi $set MongoDB pada sub-field (mis. attributes.WiFi)
        # akan GAGAL dengan error "Cannot create field 'WiFi' in element {attributes: null}"
        # karena MongoDB tidak bisa membuat sub-path di dalam nilai null.
        # Default-kan ke dict kosong supaya endpoint update selalu bisa menulis ke sana.
        doc['attributes'] = {}
    return doc


def load_dataset(limit=None):
    docs = []
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            docs.append(clean_document(json.loads(line)))
    return docs


def reset_postgres(docs):
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()

    print('[Postgres] Truncating table...')
    cur.execute('TRUNCATE TABLE yelp_business;')
    conn.commit()

    print(f'[Postgres] Ingesting {len(docs)} documents...')
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        args = [(d['business_id'], json.dumps(d)) for d in batch]
        cur.executemany(
            'INSERT INTO yelp_business (business_id, document) VALUES (%s, %s) '
            'ON CONFLICT (business_id) DO NOTHING;', args
        )
        conn.commit()

    print('[Postgres] Rebuilding expression indexes...')
    cur.execute('DROP INDEX IF EXISTS idx_price_range;')
    cur.execute('DROP INDEX IF EXISTS idx_wifi;')
    cur.execute('DROP INDEX IF EXISTS idx_outdoor_seating;')
    cur.execute("CREATE INDEX idx_price_range ON yelp_business ((document->'attributes'->>'RestaurantsPriceRange2'));")
    cur.execute("CREATE INDEX idx_wifi ON yelp_business ((document->'attributes'->>'WiFi'));")
    cur.execute("CREATE INDEX idx_outdoor_seating ON yelp_business ((document->'attributes'->>'OutdoorSeating'));")
    conn.commit()

    print('[Postgres] Running VACUUM ANALYZE...')
    old_isolation = conn.isolation_level
    conn.set_isolation_level(0)  # VACUUM tidak bisa jalan di dalam transaksi
    cur.execute('VACUUM ANALYZE yelp_business;')
    conn.set_isolation_level(old_isolation)

    cur.execute('''
        SELECT n_live_tup, n_dead_tup,
               ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_pct
        FROM pg_stat_user_tables WHERE relname = 'yelp_business';
    ''')
    print('[Postgres] Kondisi awal (live, dead, dead_pct):', cur.fetchone())

    cur.close()
    conn.close()


def reset_mongo(docs):
    client = MongoClient(MONGO_URI)
    db = client['yelp_db']

    print('[MongoDB] Dropping collection...')
    db.yelp_business.drop()

    print(f'[MongoDB] Ingesting {len(docs)} documents...')
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        db.yelp_business.insert_many(batch, ordered=False)

    print('[MongoDB] Rebuilding indexes...')
    db.yelp_business.create_index('business_id', unique=True)
    db.yelp_business.create_index([
        ('attributes.RestaurantsPriceRange2', 1),
        ('attributes.WiFi', 1),
        ('attributes.OutdoorSeating', 1),
    ])

    count = db.yelp_business.count_documents({})
    print(f'[MongoDB] Kondisi awal: {count} dokumen tersimpan.')
    client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', default='full',
                         help="'full' (150346) atau angka spesifik, mis. 100000 / 50000")
    args = parser.parse_args()

    limit = None if args.size == 'full' else int(args.size)

    print(f'=== RESET ENVIRONMENT (size={args.size}) ===')
    t0 = time.time()
    docs = load_dataset(limit)
    print(f'Dataset dimuat: {len(docs)} dokumen dalam {time.time() - t0:.2f}s')

    reset_postgres(docs)
    reset_mongo(docs)

    print(f'=== RESET SELESAI dalam {time.time() - t0:.2f}s ===')


if __name__ == '__main__':
    main()
