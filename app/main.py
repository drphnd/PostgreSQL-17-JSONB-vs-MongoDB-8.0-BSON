# app/main.py
#
# Lapisan API asinkron (thin API bridge) sesuai subbab 3.3.2 proposal.
# Driver: asyncpg (PostgreSQL) dan motor (MongoDB), connection pool identik
# (min=10, max=50), dijalankan single worker (lihat perintah run di SETUP.md).
#
# Endpoint:
#   GET  /read/postgres?mode=nested|flat
#   GET  /read/mongo?mode=nested|flat
#   PUT  /update/postgres   body: {"index": int, "wifi_value": str}
#   PUT  /update/mongo      body: {"index": int, "wifi_value": str}
#   GET  /health

import random
import time
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

PG_DSN = "postgresql://admin:password123@localhost:5432/yelp_db"
MONGO_URI = "mongodb://localhost:27017"

# Nilai filter contoh -- disesuaikan dengan distribusi nilai riil di kolom
# attributes.WiFi / RestaurantsPriceRange2 / OutdoorSeating pada Yelp dataset,
# SETELAH data dibersihkan oleh reset_environment.py (WiFi jadi string bersih
# tanpa wrapper "u'...'", OutdoorSeating jadi boolean asli, bukan string "True").
# Kombinasi ini dipilih karena punya jumlah dokumen terbanyak (5.222 dokumen)
# yang punya ketiga atribut terisi sekaligus -- lihat query verifikasi di
# subbab 3.2.2.
NESTED_FILTER_PG = {
    "price_range": "2",
    "wifi": "free",
    "outdoor_seating_text": "true",  # PostgreSQL ->> mengekstrak boolean JSON jadi teks lowercase
}
NESTED_FILTER_MONGO = {
    "price_range": "2",
    "wifi": "free",
    "outdoor_seating": True,  # MongoDB simpan boolean asli, filter juga harus boolean
}
FLAT_FILTER = {
    "city": "Philadelphia",
    "min_stars": 4.0,
}


class UpdatePayload(BaseModel):
    index: int
    wifi_value: str = "free"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await asyncpg.create_pool(
        dsn=PG_DSN, min_size=10, max_size=50
    )
    app.state.mongo_client = AsyncIOMotorClient(
        MONGO_URI, minPoolSize=10, maxPoolSize=50
    )
    app.state.mongo_db = app.state.mongo_client["yelp_db"]

    # PENTING: pre-load daftar ID sekali di awal (bukan OFFSET per-request).
    # OFFSET/skip pada dataset besar adalah O(n) table/collection scan --
    # kalau dipakai per-request pada update, latency yang terukur akan
    # tercemar oleh cost pencarian baris, bukan murni cost jsonb_set/$set.
    # Dengan array ID di memori, pemilihan dokumen acak jadi O(1) pada kedua
    # sistem, sehingga perbandingan tetap apple-to-apple.
    async with app.state.pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT business_id FROM yelp_business;")
        app.state.pg_ids = [r["business_id"] for r in rows]

    mongo_ids_cursor = app.state.mongo_db.yelp_business.find({}, {"_id": 1})
    app.state.mongo_ids = [doc["_id"] async for doc in mongo_ids_cursor]

    yield
    await app.state.pg_pool.close()
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "pg_ids": len(app.state.pg_ids), "mongo_ids": len(app.state.mongo_ids)}


@app.post("/reload")
async def reload_ids():
    """
    WAJIB dipanggil setiap kali reset_environment.py selesai dijalankan
    (truncate + re-ingest), karena daftar ID di-cache di memori saat startup
    dan tidak otomatis tahu ada perubahan data di database.
    Contoh: curl -X POST http://localhost:8000/reload
    """
    async with app.state.pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT business_id FROM yelp_business;")
        app.state.pg_ids = [r["business_id"] for r in rows]

    mongo_ids_cursor = app.state.mongo_db.yelp_business.find({}, {"_id": 1})
    app.state.mongo_ids = [doc["_id"] async for doc in mongo_ids_cursor]

    return {"status": "reloaded", "pg_ids": len(app.state.pg_ids), "mongo_ids": len(app.state.mongo_ids)}


# ---------- READ ----------

@app.get("/read/postgres")
async def read_postgres(mode: str = "nested", response: Response = None):
    pool: asyncpg.Pool = app.state.pg_pool

    # Instrumentasi dekomposisi latensi -- menjawab kritik bahwa P99 yang
    # diukur K6 di level HTTP bisa tercemar waktu antre di connection pool,
    # bukan murni waktu eksekusi query di database engine.
    t0 = time.perf_counter()
    async with pool.acquire() as conn:
        t1 = time.perf_counter()  # koneksi berhasil didapat dari pool
        if mode == "flat":
            rows = await conn.fetch(
                """
                SELECT business_id, document FROM yelp_business
                WHERE document->>'city' = $1
                  AND (document->>'stars')::float >= $2
                LIMIT 50;
                """,
                FLAT_FILTER["city"], FLAT_FILTER["min_stars"],
            )
        else:  # nested
            rows = await conn.fetch(
                """
                SELECT business_id, document FROM yelp_business
                WHERE document->'attributes'->>'RestaurantsPriceRange2' = $1
                  AND document->'attributes'->>'WiFi' = $2
                  AND document->'attributes'->>'OutdoorSeating' = $3
                LIMIT 50;
                """,
                NESTED_FILTER_PG["price_range"], NESTED_FILTER_PG["wifi"], NESTED_FILTER_PG["outdoor_seating_text"],
            )
        t2 = time.perf_counter()  # query selesai dieksekusi

    pool_wait_ms = (t1 - t0) * 1000
    db_exec_ms = (t2 - t1) * 1000

    if response is not None:
        response.headers["X-Pool-Wait-Ms"] = f"{pool_wait_ms:.3f}"
        response.headers["X-DB-Exec-Ms"] = f"{db_exec_ms:.3f}"

    return {"mode": mode, "count": len(rows)}


@app.get("/read/mongo")
async def read_mongo(mode: str = "nested", response: Response = None):
    db = app.state.mongo_db

    t0 = time.perf_counter()
    # motor tidak punya "acquire koneksi eksplisit" seperti asyncpg -- ia
    # menyerahkan permintaan ke connection pool internal driver secara
    # implisit di titik ini. t0 tetap dicatat sebagai referensi awal, dan
    # t1 diambil tepat sebelum query dikirim, sehingga selisih t1-t0
    # merepresentasikan overhead penjadwalan/antrean driver.
    t1 = time.perf_counter()
    if mode == "flat":
        query = {"city": FLAT_FILTER["city"], "stars": {"$gte": FLAT_FILTER["min_stars"]}}
    else:  # nested
        query = {
            "attributes.RestaurantsPriceRange2": NESTED_FILTER_MONGO["price_range"],
            "attributes.WiFi": NESTED_FILTER_MONGO["wifi"],
            "attributes.OutdoorSeating": NESTED_FILTER_MONGO["outdoor_seating"],
        }
    docs = await db.yelp_business.find(query).to_list(length=50)
    t2 = time.perf_counter()

    pool_wait_ms = (t1 - t0) * 1000
    db_exec_ms = (t2 - t1) * 1000

    if response is not None:
        response.headers["X-Pool-Wait-Ms"] = f"{pool_wait_ms:.3f}"
        response.headers["X-DB-Exec-Ms"] = f"{db_exec_ms:.3f}"

    return {"mode": mode, "count": len(docs)}


# ---------- PARTIAL UPDATE ----------

@app.put("/update/postgres")
async def update_postgres(payload: UpdatePayload, response: Response = None):
    pool: asyncpg.Pool = app.state.pg_pool
    ids = app.state.pg_ids
    business_id = ids[payload.index % len(ids)]  # O(1), tidak pakai OFFSET

    t0 = time.perf_counter()
    async with pool.acquire() as conn:
        t1 = time.perf_counter()
        result = await conn.execute(
            """
            UPDATE yelp_business
            SET document = jsonb_set(document, '{attributes,WiFi}', to_jsonb($1::text))
            WHERE business_id = $2;
            """,
            payload.wifi_value, business_id,
        )
        t2 = time.perf_counter()

    if response is not None:
        response.headers["X-Pool-Wait-Ms"] = f"{(t1 - t0) * 1000:.3f}"
        response.headers["X-DB-Exec-Ms"] = f"{(t2 - t1) * 1000:.3f}"

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "updated"}


@app.put("/update/mongo")
async def update_mongo(payload: UpdatePayload, response: Response = None):
    db = app.state.mongo_db
    ids = app.state.mongo_ids
    doc_id = ids[payload.index % len(ids)]  # O(1), tidak pakai skip

    t0 = time.perf_counter()
    t1 = time.perf_counter()
    result = await db.yelp_business.update_one(
        {"_id": doc_id},
        {"$set": {"attributes.WiFi": payload.wifi_value}},
    )
    t2 = time.perf_counter()

    if response is not None:
        response.headers["X-Pool-Wait-Ms"] = f"{(t1 - t0) * 1000:.3f}"
        response.headers["X-DB-Exec-Ms"] = f"{(t2 - t1) * 1000:.3f}"

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "updated", "modified": result.modified_count}
