import json
import psycopg2
from psycopg2.extras import execute_values
from pymongo import MongoClient
import time

# Konfigurasi Koneksi sesuai dengan docker-compose.yml
PG_CREDS = {
    "host": "localhost",
    "port": "5432",
    "database": "yelp_db",
    "user": "admin",
    "password": "password123"
}
MONGO_URI = "mongodb://admin:password123@localhost:27017/"
FILE_PATH = "yelp_academic_dataset_business.json"
BATCH_SIZE = 5000 # Kita tembakkan 5.000 data sekaligus agar cepat

def main():
    print("Menghubungkan ke database...")
    
    # 1. Setup PostgreSQL
    pg_conn = psycopg2.connect(**PG_CREDS)
    pg_cursor = pg_conn.cursor()
    # Membuat tabel jika belum ada. Perhatikan tipe datanya adalah JSONB!
    pg_cursor.execute("""
        CREATE TABLE IF NOT EXISTS yelp_business (
            business_id VARCHAR(50) PRIMARY KEY,
            document JSONB
        );
        TRUNCATE TABLE yelp_business; -- Bersihkan tabel jika sudah ada isi dari tes sebelumnya
    """)
    pg_conn.commit()
    
    # 2. Setup MongoDB
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client["yelp_db"]
    mongo_collection = mongo_db["yelp_business"]
    mongo_collection.delete_many({}) # Bersihkan collection jika sudah ada isi

    print("Mulai membaca Yelp Dataset dan memompa ke Database (Batch Processing)...")
    start_time = time.time()
    
    pg_batch = []
    mongo_batch = []
    total_inserted = 0

    # Buka file secara Streaming (Line by Line)
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            doc = json.loads(line) # Ubah teks menjadi objek JSON Python
            
            # Persiapan format Postgres (Tuple: id, json_string)
            pg_batch.append((doc['business_id'], json.dumps(doc)))
            
            # Persiapan format Mongo (Langsung objek aslinya)
            mongo_batch.append(doc)
            
            # Jika sudah mencapai 5.000 data, tembakkan ke database!
            if len(pg_batch) >= BATCH_SIZE:
                # Tembak ke Postgres
                execute_values(pg_cursor, 
                               "INSERT INTO yelp_business (business_id, document) VALUES %s", 
                               pg_batch)
                pg_conn.commit()
                
                # Tembak ke Mongo
                mongo_collection.insert_many(mongo_batch)
                
                total_inserted += len(pg_batch)
                print(f"Berhasil memasukkan {total_inserted} dokumen bisnis...")
                
                # Kosongkan wadah batch untuk rombongan berikutnya
                pg_batch.clear()
                mongo_batch.clear()

    # Eksekusi sisa data yang kurang dari 5.000 di akhir file
    if pg_batch:
        execute_values(pg_cursor, "INSERT INTO yelp_business (business_id, document) VALUES %s", pg_batch)
        pg_conn.commit()
        mongo_collection.insert_many(mongo_batch)
        total_inserted += len(pg_batch)

    # Tutup semua koneksi
    pg_cursor.close()
    pg_conn.close()
    mongo_client.close()
    
    end_time = time.time()
    print(f"\n[SELESAI!] Total {total_inserted} dokumen berhasil di-ingest ke PostgreSQL dan MongoDB dalam waktu {end_time - start_time:.2f} detik.")

if __name__ == "__main__":
    main()
