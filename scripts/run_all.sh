#!/usr/bin/env bash
cd ~/Riset_TA_Database
( while true; do echo "$(date +%T),$(free -m | awk "/Mem:/{print \$3\",\"\$7}"),$(free -m | awk "/Swap:/{print \$3}")" >> mem_run_all.csv; sleep 5; done ) &
curl -s http://localhost:8000/health | grep -q pg_ids || { echo "ABORT: API bukan app.main:app"; exit 1; }
for n in 8 9 10; do
  bash scripts/run_scn2_rerun.sh $n > log_scn2_run$n.txt 2>&1; python3 scripts/hb_gaps.py hb_scn2_run$n.log >> log_scn2_run$n.txt; sleep 300
  bash scripts/run_scn1_rerun.sh $n > log_scn1_run$n.txt 2>&1; python3 scripts/hb_gaps.py hb_scn1_run$n.log >> log_scn1_run$n.txt; sleep 300
done
bash scripts/run_mixed_rerun.sh postgres 2 > log_mixed_postgres_run2.txt 2>&1; sleep 300
bash scripts/run_mixed_rerun.sh mongo 2 > log_mixed_mongo_run2.txt 2>&1
echo SELESAI $(date) > SELESAI_RUN_ALL.txt
kill $(jobs -p) 2>/dev/null
