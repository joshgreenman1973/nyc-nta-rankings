#!/bin/bash
# Fetch point-level datasets from NYC Open Data (Socrata SODA 2.1 CSV export).
# Every fetch must produce a non-trivial file or this script FAILS LOUD (exit 1).
set -uo pipefail
cd "$(dirname "$0")/raw"
B="https://data.cityofnewyork.us/resource"

fetch () { # name dataset select where group minbytes
  local name=$1 ds=$2 sel=$3 where=$4 group=$5 min=$6
  echo "[$(date +%H:%M:%S)] start $name"
  local args=(-sG --retry 3 --retry-delay 10 -o "$name.csv" "$B/$ds.csv"
              --data-urlencode "\$select=$sel" --data-urlencode "\$limit=6000000")
  [ -n "$where" ] && args+=(--data-urlencode "\$where=$where")
  [ -n "$group" ] && args+=(--data-urlencode "\$group=$group")
  curl "${args[@]}" || { echo "FAIL curl $name"; exit 1; }
  local sz=$(stat -f%z "$name.csv")
  if [ "$sz" -lt "$min" ]; then echo "FAIL $name too small: $sz bytes"; head -c 300 "$name.csv"; exit 1; fi
  echo "[$(date +%H:%M:%S)] done $name: $sz bytes, $(wc -l < "$name.csv") lines"
}

fetch nypd2025 qgea-i56i "latitude,longitude,law_cat_cd,ofns_desc" "rpt_dt >= '2025-01-01T00:00:00' AND rpt_dt <= '2025-12-31T23:59:59'" "" 10000000 &
P1=$!
fetch collisions2025 h9gi-nx95 "latitude,longitude,number_of_persons_injured,number_of_persons_killed" "crash_date >= '2025-01-01T00:00:00' AND crash_date <= '2025-12-31T23:59:59'" "" 1000000 &
P2=$!
fetch evictions2025 6z8x-wfk4 "latitude,longitude" "executed_date >= '2025-01-01' AND executed_date <= '2025-12-31' AND residential_commercial_ind = 'Residential'" "" 100000 &
P3=$!
# Full structure = a standing tree (excludes Retired/removed points and stumps);
# condition != 'Dead' drops standing dead trees.
fetch trees hn5i-inap "geometry" "tpstructure = 'Full' AND tpcondition != 'Dead'" "" 20000000 &
P4=$!
FAILED=0
for p in $P1 $P2 $P3 $P4; do wait $p || FAILED=1; done
[ "$FAILED" = 1 ] && { echo "A FETCH FAILED"; exit 1; }

# 311 is the monster (~3.9M rows) — run last, alone.
fetch t311 erm2-nwe9 "latitude,longitude,complaint_type" "created_date >= '2025-08-01T00:00:00' AND created_date < '2026-08-01T00:00:00'" "" 100000000
echo "ALL FETCHES OK"
