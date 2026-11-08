#!/usr/bin/env bash
ENG=$(docker info --format '{{.Name}}' 2>/dev/null)
[ "$ENG" = "docker-desktop" ] && { echo "ABORT: docker menuju Docker Desktop"; exit 1; }
PGIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ta_postgres_17)
MGID=$(docker exec ta_mongodb_8 hostname)
python3 - "$PGIP" "$MGID" <<'PY'
import sys, asyncio, asyncpg
from pymongo import MongoClient
pgip, mgid = sys.argv[1:3]
async def m():
    c = await asyncpg.connect("postgresql://admin:password123@localhost:5432/yelp_db")
    return await c.fetchval("select host(inet_server_addr())")
a = asyncio.run(m())
h = MongoClient("mongodb://localhost:27017").admin.command("serverStatus")["host"]
ok = (a == pgip and h == mgid)
print("PG api->", a, "container", pgip, "| Mongo api->", h, "container", mgid, "=>", "OK" if ok else "MISMATCH")
sys.exit(0 if ok else 1)
PY
