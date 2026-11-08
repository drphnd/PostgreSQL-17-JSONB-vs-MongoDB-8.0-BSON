-- init_postgres.sql
-- Dijalankan otomatis oleh container postgres saat pertama kali start
-- (docker-entrypoint-initdb.d). Untuk reset berikutnya, gunakan
-- scripts/reset_environment.py, bukan restart container.

CREATE TABLE IF NOT EXISTS yelp_business (
    business_id TEXT PRIMARY KEY,
    document JSONB NOT NULL
);

-- Expression index -- dibangun ulang otomatis juga oleh reset_environment.py,
-- tapi disiapkan di sini supaya container siap pakai sejak awal.
CREATE INDEX IF NOT EXISTS idx_price_range
    ON yelp_business ((document->'attributes'->>'RestaurantsPriceRange2'));
CREATE INDEX IF NOT EXISTS idx_wifi
    ON yelp_business ((document->'attributes'->>'WiFi'));
CREATE INDEX IF NOT EXISTS idx_outdoor_seating
    ON yelp_business ((document->'attributes'->>'OutdoorSeating'));

-- Index tambahan untuk mendukung skenario query FLAT (baseline/kontrol)
CREATE INDEX IF NOT EXISTS idx_city ON yelp_business ((document->>'city'));
CREATE INDEX IF NOT EXISTS idx_stars ON yelp_business (((document->>'stars')::float));
