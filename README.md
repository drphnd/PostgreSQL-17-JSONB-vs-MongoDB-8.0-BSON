# PostgreSQL 17 JSONB vs MongoDB 8.0 BSON: nested document benchmark

Supplementary material for: Pandiangan, D., & Tjahjono, L. M. "Comparative Benchmarking of PostgreSQL and MongoDB for Nested Document Workloads under High Concurrency" (Edumatic).

## Contents
- `docker-compose.yml`, `init_postgres.sql`: containers (2 CPU, 2 GB each) and schema
- `create_indexes.py`, `rebuild_indexes.py`, `ingest_data.py`: indexes and data loading
- `app/`, `api_bridge.py`: FastAPI service (asyncpg, motor)
- `k6/`, `test_*.js`: k6 load scripts (5, 50, 100, 200, 256, 400, 512 VU)
- `scripts/`, `start_env.sh`, `docs/`: run scripts and runbooks
- `data/`: aggregated k6 summaries and container resource logs (nested reads: runs 11-13; mixed 80:20: one run per system)

## Not included
- Yelp Open Dataset (business file): download from https://www.yelp.com/dataset (licence applies)
- Raw k6 output (several GB): available from the corresponding author on request

## Note on credentials
The `password123` strings are default credentials of local, throwaway Docker containers on localhost. Change them for any other use.

## Environment
WSL2, AMD Ryzen 7 7745HX, 16 GB RAM; k6 0.51.0; PostgreSQL 17.11; MongoDB 8.0.34.
