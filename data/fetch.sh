#!/bin/bash
# Fetch every non-ACS input: NYC Open Data point files (Socrata SODA 2.1 CSV export),
# MTA stations from the state portal, Census Bureau LODES jobs files and City Planning's
# tract-to-NTA equivalency. Every fetch must produce a non-trivial file or this script
# FAILS LOUD (exit 1). Each file keeps its record ID so points.py can assert uniqueness.
# Afterward run manifest.py, which records row counts, download times and checksums.
set -uo pipefail
cd "$(dirname "$0")/raw"
B="https://data.cityofnewyork.us/resource"
LOG=../fetch.log
echo "=== fetch run $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

fetch () { # name dataset select where group minbytes
  local name=$1 ds=$2 sel=$3 where=$4 group=$5 min=$6
  echo "[$(date +%H:%M:%S)] start $name" | tee -a "$LOG"
  local args=(-sG --retry 3 --retry-delay 10 -o "$name.csv" "$B/$ds.csv"
              --data-urlencode "\$select=$sel" --data-urlencode "\$limit=6000000")
  [ -n "$where" ] && args+=(--data-urlencode "\$where=$where")
  [ -n "$group" ] && args+=(--data-urlencode "\$group=$group")
  curl "${args[@]}" || { echo "FAIL curl $name" | tee -a "$LOG"; exit 1; }
  local sz=$(stat -f%z "$name.csv")
  if [ "$sz" -lt "$min" ]; then echo "FAIL $name too small: $sz bytes" | tee -a "$LOG"; head -c 300 "$name.csv"; exit 1; fi
  echo "[$(date +%H:%M:%S)] done $name: $sz bytes, $(wc -l < "$name.csv") lines" | tee -a "$LOG"
}

# Crime: precinct and offense are kept so station-house placements can be identified.
fetch nypd2025 qgea-i56i "cmplnt_num,addr_pct_cd,latitude,longitude,law_cat_cd,ofns_desc" "rpt_dt >= '2025-01-01T00:00:00' AND rpt_dt <= '2025-12-31T23:59:59'" "" 10000000 &
P1=$!
fetch collisions2025 h9gi-nx95 "collision_id,latitude,longitude,number_of_persons_injured,number_of_persons_killed" "crash_date >= '2025-01-01T00:00:00' AND crash_date <= '2025-12-31T23:59:59'" "" 1000000 &
P2=$!
fetch evictions2025 6z8x-wfk4 "court_index_number,docket_number,eviction_apt_num,executed_date,latitude,longitude" "executed_date >= '2025-01-01' AND executed_date <= '2025-12-31' AND residential_commercial_ind = 'Residential'" "" 100000 &
P3=$!
# Full structure = a standing tree (excludes Retired/removed points and stumps);
# condition != 'Dead' drops standing dead trees.
fetch trees hn5i-inap "objectid,geometry" "tpstructure = 'Full' AND tpcondition != 'Dead'" "" 20000000 &
P4=$!
# Restaurants: establishments (CAMIS) that have had at least one inspection. The file also
# lists permit applicants not yet inspected, with inspection_date 1900-01-01; those are left out.
fetch restaurants 43nn-pn8j "camis,latitude,longitude" "inspection_date > '1901-01-01T00:00:00'" "camis,latitude,longitude" 500000 &
P5=$!
fetch tract_nta hm78-6dwm "geoid,ntacode" "" "" 40000 &
P6=$!
FAILED=0
for p in $P1 $P2 $P3 $P4 $P5 $P6; do wait $p || FAILED=1; done
[ "$FAILED" = 1 ] && { echo "A FETCH FAILED"; exit 1; }

# Subway stations live on the state portal, not NYC's. One row per GTFS stop;
# points.py counts distinct station_id values.
echo "[$(date +%H:%M:%S)] start subway_stations" | tee -a "$LOG"
curl -sG --retry 3 -o subway_stations.csv "https://data.ny.gov/resource/39hk-dx4f.csv" \
  --data-urlencode '$select=station_id,gtfs_stop_id,stop_name,gtfs_latitude,gtfs_longitude,daytime_routes' \
  --data-urlencode '$limit=5000' || { echo "FAIL curl subway"; exit 1; }
[ "$(wc -l < subway_stations.csv)" -gt 400 ] || { echo "FAIL subway too small"; exit 1; }
echo "[$(date +%H:%M:%S)] done subway_stations: $(wc -l < subway_stations.csv) lines" | tee -a "$LOG"

# Census LEHD LODES 8, 2023, all jobs: by workplace block (WAC) and by home block (RAC),
# for the commuter-adjusted rate base.
for kind in wac rac; do
  curl -sf --retry 3 -o ny_${kind}_2023.csv.gz "https://lehd.ces.census.gov/data/lodes/LODES8/ny/$kind/ny_${kind}_S000_JT00_2023.csv.gz" \
    || { echo "FAIL curl lodes $kind"; exit 1; }
  [ "$(stat -f%z ny_${kind}_2023.csv.gz)" -gt 1000000 ] || { echo "FAIL lodes $kind too small"; exit 1; }
  echo "[$(date +%H:%M:%S)] done lodes $kind" | tee -a "$LOG"
done

# 311 is the monster (~3.9M rows), so it runs last, alone.
fetch t311 erm2-nwe9 "unique_key,latitude,longitude,complaint_type" "created_date >= '2025-08-01T00:00:00' AND created_date < '2026-08-01T00:00:00'" "" 100000000
echo "ALL FETCHES OK" | tee -a "$LOG"
