"""
api_bridge.py — Versi Metodologis (Fair Async)
===============================================Perubahan dari versi sebelumnya:

1. psycopg2 (sync) → asyncpg (async): kedua driver sekarang non-blocking
2. pymongo → motor (async): konsisten dengan asyncpg
3. Pool size IDENTIK untuk kedua database (MAX_POOL_SIZE)
4. 1 worker uvicorn (jalankan dengan: uvicorn api_bridge:app --workers 1)
5. Operasi UPDATE menyentuh NESTED field (attributes.WiFi),
   bukan top-level field (stars) — sesuai RQ1 BAB 1

Cara menjalankan:
    uvicorn api_bridge:app --host 0.0.0.0 --port 8000 --workers 1
"""

from fastapi import FastAPI, HTTPException
import asyncpg
import motor.motor_asyncio
import random
import time

app = FastAPI(title="DB Benchmark Bridge")

# ============================================================
# KONFIGURASI — Pool size identik adalah kunci fairness
# ============================================================
MAX_POOL_SIZE = 50   # Sama untuk PostgreSQL dan MongoDB
MIN_POOL_SIZE = 10   # Sama untuk keduanya

PG_DSN = "postgresql://admin:password123@localhost:5432/yelp_db"
MONGO_URI = "mongodb://localhost:27017/"

# State global
pg_pool = None
mongo_col = None
valid_ids = []   # Cache 1000 ID untuk random lookup


# ============================================================
# STARTUP & SHUTDOWN
# ============================================================
@app.on_event("startup")
async def startup():
    global pg_pool, mongo_col, valid_ids

    print("[STARTUP] Menginisialisasi connection pools...")

    # PostgreSQL async pool
    pg_pool = await asyncpg.create_pool(
        dsn=PG_DSN,
        min_size=MIN_POOL_SIZE,
        max_size=MAX_POOL_SIZE,
        command_timeout=30
    )

    # MongoDB async client
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=MAX_POOL_SIZE,
        minPoolSize=MIN_POOL_SIZE,
        serverSelectionTimeoutMS=5000
    )
    mongo_col = mongo_client["yelp_db"]["yelp_business"]

    # Cache business_id dari PostgreSQL (sumber tunggal agar ID identik)
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT business_id FROM yelp_business LIMIT 1000;"
        )
        valid_ids = [r['business_id'] for r in rows]

    print(f"[STARTUP] Selesai. {len(valid_ids)} ID di-cache.")
    print(f"[STARTUP] PG pool: {MIN_POOL_SIZE}-{MAX_POOL_SIZE} koneksi")
    print(f"[STARTUP] Mongo pool: {MIN_POOL_SIZE}-{MAX_POOL_SIZE} koneksi")


@app.on_event("shutdown")
async def shutdown():
    if pg_pool:
        await pg_pool.close()
    print("[SHUTDOWN] Connection pools ditutup.")


# ============================================================
# READ ENDPOINTS
# Filter multikriteria pada atribut bersarang (depth-2)
# Sesuai BAB 1: attributes.RestaurantsPriceRange2, WiFi, OutdoorSeating
# ============================================================


@app.get("/read/postgres")
async def read_postgres():
    """
    READ PostgreSQL — Filter multikriteria pada nested JSONB attributes.
    """
    try:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    business_id,
                    document->>'name' AS name,
                    document->'attributes'->>'WiFi' AS wifi,
                    document->'attributes'->>'OutdoorSeating' AS outdoor,
                    document->'hours'->>'Monday' AS monday_hours
                FROM yelp_business
                WHERE
                    document->'attributes'->>'RestaurantsPriceRange2' = '2'
                    AND document->'attributes'->>'WiFi' = 'free'
                    AND document->'attributes'->>'OutdoorSeating' = 'true'
                LIMIT 10;
            """)
        return {"status": "ok", "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/read/mongo")
async def read_mongo():
    """
    READ MongoDB — Filter multikriteria yang setara.
    Menggunakan compound index:
    RestaurantsPriceRange2 + WiFi + OutdoorSeating
    """
    try:
        cursor = mongo_col.find(
            {
                "attributes.RestaurantsPriceRange2": "2",
                "attributes.WiFi": "free",
                "attributes.OutdoorSeating": True
            },
            {
                "business_id": 1,
                "name": 1,
                "attributes.WiFi": 1,
                "attributes.OutdoorSeating": 1,
                "hours.Monday": 1
            }
        ).limit(10)

        results = await cursor.to_list(length=10)

        return {
            "status": "ok",
            "count": len(results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# UPDATE ENDPOINTS
# Partial update pada NESTED field (depth-2) — sesuai RQ1 BAB 1
# BUKAN stars (top-level) — ini yang membedakan dari versi lama
# ============================================================

# Nilai valid untuk attributes.WiFi di dataset Yelp
WIFI_VALUES = ["u'free'", "u'paid'", "u'no'", "None"]

@app.put("/update/postgres")
async def update_postgres():
    """
    PARTIAL UPDATE PostgreSQL — jsonb_set pada attributes.WiFi (nested depth-2).
    Lookup menggunakan PRIMARY KEY index (business_id).
    """
    target_id = random.choice(valid_ids)
    new_wifi = random.choice(WIFI_VALUES)

    try:
        async with pg_pool.acquire() as conn:
            await conn.execute("""
                UPDATE yelp_business
                SET document = jsonb_set(
                    document,
                    '{attributes,WiFi}',
                    to_jsonb($1::text)
                )
                WHERE business_id = $2;
            """, new_wifi, target_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update/mongo")
async def update_mongo():
    """
    PARTIAL UPDATE MongoDB — $set pada attributes.WiFi (nested depth-2).
    Lookup menggunakan indeks business_id (unique).
    """
    target_id = random.choice(valid_ids)
    new_wifi = random.choice(WIFI_VALUES)

    try:
        await mongo_col.update_one(
            {"business_id": target_id},
            {"$set": {"attributes.WiFi": new_wifi}}
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/health")
async def health():
    """
    Verifikasi bahwa kedua database bisa dicapai sebelum load test.
    Jalankan ini dulu sebelum K6 dinyalakan.
    """
    status = {}

    # Test PostgreSQL
    try:
        async with pg_pool.acquire() as conn:
            result = await conn.fetchval("SELECT COUNT(*) FROM yelp_business;")
        status["postgres"] = {"ok": True, "document_count": result}
    except Exception as e:
        status["postgres"] = {"ok": False, "error": str(e)}

    # Test MongoDB
    try:
        count = await mongo_col.count_documents({})
        status["mongodb"] = {"ok": True, "document_count": count}
    except Exception as e:
        status["mongodb"] = {"ok": False, "error": str(e)}

    all_ok = all(v["ok"] for v in status.values())
    return {"all_systems_ok": all_ok, "databases": status}
