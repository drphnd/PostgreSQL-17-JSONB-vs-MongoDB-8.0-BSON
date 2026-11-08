#!/usr/bin/env bash
cd ~/Riset_TA_Database
bash scripts/check_target.sh || exit 1
curl -s http://localhost:8000/health | grep -q pg_ids || { echo "ABORT: API bukan app.main:app"; exit 1; }
( while true; do echo "$(date +%T),$(free -m | awk "/Mem:/{print \$3\",\"\$7}"),$(free -m | awk "/Swap:/{print \$3}")" >> mem_run_all3.csv; sleep 5; done ) &
step() { grep -qs "jeda proses" log_$3.txt && { echo "lewati $3"; return; }; bash scripts/$1 $2 > log_$3.txt 2>&1; python3 scripts/hb_gaps.py hb_$3.log >> log_$3.txt; sleep 300; }
for n in 11 12 13; do
  step run_scn2_rerun.sh $n scn2_run$n
  step run_scn1_rerun.sh $n scn1_run$n
done
mixed() { grep -qs "jeda proses" log_mixed_$1_run3.txt && return; bash scripts/run_mixed_rerun.sh $1 3 > log_mixed_$1_run3.txt 2>&1; python3 scripts/hb_gaps.py hb_mixed_$1_run3.log >> log_mixed_$1_run3.txt; sleep 300; }
mixed postgres
mixed mongo
echo SELESAI $(date) > SELESAI_RUN_ALL3.txt
kill $(jobs -p) 2>/dev/null
