# PostgreSQL 17 JSONB vs MongoDB 8.0 BSON: nested document benchmark

Supplementary material for: Pandiangan, D., & Tjahjono, L. M. "Comparative Benchmarking of PostgreSQL and MongoDB for Nested Document Workloads under High Concurrency" (Edumatic).

## Contents
- `docker-compose.yml`, `init_postgres.sql`: containers (2 CPU, 2 GB each) and schema
- `create_indexes.py`, `rebuild_indexes.py`, `ingest_data.py`: indexes and data loading
- `app/`, `api_bridge.py`: FastAPI service (asyncpg, motor)
- `k6/`, `test_*.js`: k6 load scripts (5, 50, 100, 200, 256, 400, 512 VU)
- `scripts/`, `start_env.sh`, `docs/`: run scripts and runbooks
- `data/`: aggregated k6 summaries and container resource logs (nested reads: runs 11-13; mixed 80:20: one run per system)

## Latency decomposition and API CPU
- `scripts/extract_decomposition.py`: splits latency into pool wait (`pool_wait_ms`), query call (`db_exec_ms`), and remainder, from the raw k6 output (`data/decomposition_*.csv`).
- `scripts/monitor_api.py`, `scripts/run_api_probe.sh`: three additional runs per system at 256 and 512 VU with CPU of the API process, k6, and host (`data/probe_runs21_23/`).

## Query plans and index statistics
- `data/query_plans/`: EXPLAIN ANALYZE (PostgreSQL) and explain with executionStats (MongoDB) for the nested-read query, index sizes, cumulative scan counts, and a plan with the index scan forced. PostgreSQL chose a sequential scan and did not use its three expression indexes; MongoDB used its compound index.
- `scripts/run_api_probe_pgidx.sh`: optional sensitivity run for PostgreSQL with a composite expression index (not part of the reported results).

## Sensitivity test: PostgreSQL with a composite index
- `data/pgidx_runs31_33/`: three additional PostgreSQL runs at 256 and 512 VU after adding a composite expression index on the three filtered attributes, so that the planner used an index plan (plan files included). Reported as a sensitivity analysis; the main results are unchanged.

## Not included
- Yelp Open Dataset (business file): download from https://www.yelp.com/dataset (licence applies)
- Raw k6 output (several GB): available from the corresponding author on request

## Note on credentials
The `password123` strings are default credentials of local, throwaway Docker containers on localhost. Change them for any other use.

## Environment
WSL2, AMD Ryzen 7 7745HX, 16 GB RAM; k6 0.51.0; PostgreSQL 17.11; MongoDB 8.0.34.
