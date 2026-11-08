import psycopg2
from pymongo import MongoClient
import time

PG_CREDS = {
    "host": "localhost", "port": "5432",
    "database": "yelp_db", "user": "admin", "password": "password123"
}
MONGO_URI = "mongodb://admin:password123@localhost:27017/"

def main():
    print("Memulai proses pembuatan Indeks...")
    
    # 1. Indexing PostgreSQL (GIN Index)
    print("--> Membangun GIN Index di PostgreSQL (Ini mungkin memakan waktu)...")
    pg_conn = psycopg2.connect(**PG_CREDS)
    pg_conn.autocommit = True # Diperlukan untuk pembuatan indeks
    pg_cursor = pg_conn.cursor()
    
    start_pg = time.time()
    # Mengindeks seluruh dokumen JSONB agar pencarian nested field menjadi instan
    pg_cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsonb_doc ON yelp_business USING GIN (document);")
    end_pg = time.time()
    print(f"[OK] GIN Index PostgreSQL selesai dalam {end_pg - start_pg:.2f} detik.")
    pg_cursor.close()
    pg_conn.close()

    # 2. Indexing MongoDB (B-Tree Compound Index)
    print("--> Membangun B-Tree Index di MongoDB...")
    mongo_client = MongoClient(MONGO_URI)
    mongo_collection = mongo_client["yelp_db"]["yelp_business"]
    
    start_mongo = time.time()
    # Mengindeks field spesifik yang sering dicari dalam skenario aplikasi nyata
    mongo_collection.create_index([("city", 1), ("stars", -1), ("attributes.WiFi", 1)])
    end_mongo = time.time()
    print(f"[OK] B-Tree Index MongoDB selesai dalam {end_mongo - start_mongo:.2f} detik.")
    mongo_client.close()

    print("\n[SELESAI] Kedua database kini sudah dioptimasi dan siap untuk Load Testing!")

if __name__ == "__main__":
    main()
