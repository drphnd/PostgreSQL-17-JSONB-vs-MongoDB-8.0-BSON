"""
rebuild_indexes.py
==================
Membangun ulang indeks yang RELEVAN dengan operasi yang diuji di BAB 1:
- READ: filter multikriteria pada attributes.RestaurantsPriceRange2,
        attributes.WiFi, attributes.OutdoorSeating, hours.Monday
- UPDATE: partial update pada attributes.WiFi dan hours.Monday

Prinsip: Indeks yang diberikan ke kedua sistem harus mendukung
operasi yang SAMA, bukan indeks generik yang tidak berkaitan.
"""

import psycopg2
from pymongo import MongoClient
import time

PG_CREDS = {
    "host": "localhost", "port": "5432",
    "database": "yelp_db", "user": "admin", "password": "password123"
}
MONGO_URI = "mongodb://admin:password123@localhost:27017/"


def rebuild_postgres_indexes():
    print("\n[PostgreSQL] Membangun ulang indeks...")
    conn = psycopg2.connect(**PG_CREDS)
    conn.autocommit = True
    cur = conn.cursor()

    # Hapus indeks lama yang tidak relevan
    print("  -> Menghapus GIN index lama (idx_jsonb_doc)...")
    cur.execute("DROP INDEX IF EXISTS idx_jsonb_doc;")

    # INDEKS 1: Untuk operasi READ multikriteria pada nested attributes
    # Menggunakan ekspresi JSONB agar bisa dipakai oleh query filter
    print("  -> Membuat indeks untuk filter attributes.RestaurantsPriceRange2...")
    t = time.time()
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pg_price_range
        ON yelp_business ((document->'attributes'->>'RestaurantsPriceRange2'));
    """)
    print(f"     Selesai dalam {time.time()-t:.2f} detik.")

    print("  -> Membuat indeks untuk filter attributes.WiFi...")
    t = time.time()
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pg_wifi
        ON yelp_business ((document->'attributes'->>'WiFi'));
    """)
    print(f"     Selesai dalam {time.time()-t:.2f} detik.")

    print("  -> Membuat indeks untuk filter attributes.OutdoorSeating...")
    t = time.time()
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pg_outdoor
        ON yelp_business ((document->'attributes'->>'OutdoorSeating'));
    """)
    print(f"     Selesai dalam {time.time()-t:.2f} detik.")

    # CATATAN AKADEMIS:
    # PRIMARY KEY pada business_id sudah otomatis membuat B-Tree index.
    # Indeks GIN generik DIHAPUS karena tidak digunakan oleh query UPDATE
    # maupun READ yang kita definisikan — menyertakannya akan misleading
    # karena memberi kesan PostgreSQL "lebih siap" padahal indeks itu
    # tidak berkontribusi pada performa operasi yang diukur.

    cur.close()
    conn.close()
    print("[PostgreSQL] Semua indeks selesai dibangun.")


def rebuild_mongo_indexes():
    print("\n[MongoDB] Membangun ulang indeks...")
    client = MongoClient(MONGO_URI)
    col = client["yelp_db"]["yelp_business"]

    # Hapus semua indeks non-default dulu untuk mulai bersih
    print("  -> Menghapus indeks lama...")
    col.drop_indexes()

    # INDEKS 1: business_id — untuk operasi UPDATE (lookup by ID)
    print("  -> Membuat indeks business_id (unique)...")
    t = time.time()
    col.create_index("business_id", unique=True)
    print(f"     Selesai dalam {time.time()-t:.2f} detik.")

    # INDEKS 2: Filter multikriteria untuk operasi READ
    # Urutan field dalam compound index mengikuti selectivity (paling selektif dulu)
    print("  -> Membuat compound index untuk READ multikriteria...")
    t = time.time()
    col.create_index([
        ("attributes.RestaurantsPriceRange2", 1),
        ("attributes.WiFi", 1),
        ("attributes.OutdoorSeating", 1),
    ])
    print(f"     Selesai dalam {time.time()-t:.2f} detik.")

    # CATATAN AKADEMIS:
    # MongoDB compound index ini setara secara FUNGSIONAL dengan tiga
    # expression indexes PostgreSQL di atas — keduanya mendukung
    # filter multikriteria yang sama. Ini yang membuat perbandingan fair.

    client.close()
    print("[MongoDB] Semua indeks selesai dibangun.")


def verify_indexes():
    print("\n[VERIFIKASI] Memeriksa indeks yang aktif...")

    # PostgreSQL
    conn = psycopg2.connect(**PG_CREDS)
    cur = conn.cursor()
    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'yelp_business'
        ORDER BY indexname;
    """)
    rows = cur.fetchall()
    print("\n  PostgreSQL indexes:")
    for name, defn in rows:
        print(f"    [{name}]")
        print(f"      {defn}")
    cur.close()
    conn.close()

    # MongoDB
    client = MongoClient(MONGO_URI)
    col = client["yelp_db"]["yelp_business"]
    print("\n  MongoDB indexes:")
    for idx in col.list_indexes():
        print(f"    {dict(idx)}")
    client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("REBUILD INDEXES — Untuk Apple-to-Apple Comparison")
    print("=" * 60)
    rebuild_postgres_indexes()
    rebuild_mongo_indexes()
    verify_indexes()
    print("\n[SELESAI] Kedua database siap dengan indeks yang setara.")
