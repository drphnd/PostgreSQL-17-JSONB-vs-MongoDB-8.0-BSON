#!/usr/bin/env bash
cd ~/Riset_TA_Database
curl -s http://localhost:8000/health | grep -q pg_ids || { echo "ABORT: API bukan app.main:app"; exit 1; }
( while true; do echo "$(date +%T),$(free -m | awk "/Mem:/{print \$3\",\"\$7}"),$(free -m | awk "/Swap:/{print \$3}")" >> mem_run_all2.csv; sleep 5; done ) &
step() { grep -qs "jeda proses" log_$3.txt && { echo "lewati $3"; return; }; bash scripts/$1 $2 > log_$3.txt 2>&1; python3 scripts/hb_gaps.py hb_$3.log >> log_$3.txt; sleep 300; }
step run_scn1_rerun.sh 8  scn1_run8
step run_scn2_rerun.sh 9  scn2_run9
step run_scn1_rerun.sh 9  scn1_run9
step run_scn2_rerun.sh 10 scn2_run10
step run_scn1_rerun.sh 10 scn1_run10
grep -qs "jeda proses" log_mixed_postgres_run2.txt || { bash scripts/run_mixed_rerun.sh postgres 2 > log_mixed_postgres_run2.txt 2>&1; python3 scripts/hb_gaps.py hb_mixed_postgres_run2.log >> log_mixed_postgres_run2.txt; sleep 300; }
grep -qs "jeda proses" log_mixed_mongo_run2.txt || { bash scripts/run_mixed_rerun.sh mongo 2 > log_mixed_mongo_run2.txt 2>&1; python3 scripts/hb_gaps.py hb_mixed_mongo_run2.log >> log_mixed_mongo_run2.txt; }
echo SELESAI $(date) > SELESAI_RUN_ALL.txt
kill $(jobs -p) 2>/dev/null
