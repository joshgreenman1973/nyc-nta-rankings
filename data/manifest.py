#!/usr/bin/env python3
"""Record what each raw input is: source, query, download time, size, row count and SHA-256.

Writes sources_manifest.json (committed). The raw files themselves are too big for git;
the exact snapshot used for a build is attached to a GitHub release of this repo (see
README), and the checksums here confirm a re-download matches it or show that it doesn't.
"""
import hashlib, json, os, datetime, gzip

RAW = "raw"
SOURCES = {
    "nypd2025.csv": ("NYPD complaint data historic", "https://data.cityofnewyork.us/d/qgea-i56i", "report date in calendar 2025"),
    "collisions2025.csv": ("Motor vehicle collisions - crashes", "https://data.cityofnewyork.us/d/h9gi-nx95", "crash date in calendar 2025"),
    "evictions2025.csv": ("Evictions", "https://data.cityofnewyork.us/d/6z8x-wfk4", "residential, executed in calendar 2025"),
    "restaurants.csv": ("DOHMH restaurant inspection results", "https://data.cityofnewyork.us/d/43nn-pn8j", "establishments with at least one inspection"),
    "trees.csv": ("Forestry tree points", "https://data.cityofnewyork.us/d/hn5i-inap", "structure Full, condition not Dead"),
    "t311.csv": ("311 service requests", "https://data.cityofnewyork.us/d/erm2-nwe9", "created Aug. 1, 2025-July 31, 2026"),
    "subway_stations.csv": ("MTA subway stations", "https://data.ny.gov/d/39hk-dx4f", "all rows (one per GTFS stop)"),
    "tract_nta.csv": ("2020 census tract to NTA equivalency", "https://data.cityofnewyork.us/d/hm78-6dwm", "all rows"),
    "nta2020.geojson": ("2020 neighborhood tabulation areas", "https://data.cityofnewyork.us/d/9nt8-h7nd", "clipped to shoreline"),
    "ny_wac_2023.csv.gz": ("LEHD LODES 8 workplace area characteristics, NY, 2023, all jobs", "https://lehd.ces.census.gov/data/lodes/LODES8/ny/wac/", "all rows"),
    "ny_rac_2023.csv.gz": ("LEHD LODES 8 residence area characteristics, NY, 2023, all jobs", "https://lehd.ces.census.gov/data/lodes/LODES8/ny/rac/", "all rows"),
    "Dem_nta.xlsx": ("City Planning ACS 2020-2024 NTA demographic profile", "https://www.nyc.gov/content/planning/pages/resources/datasets/american-community-survey", "workbook"),
    "Soc_nta.xlsx": ("City Planning ACS 2020-2024 NTA social profile", "same", "workbook"),
    "Econ_nta.xlsx": ("City Planning ACS 2020-2024 NTA economic profile", "same", "workbook"),
    "Hous_nta.xlsx": ("City Planning ACS 2020-2024 NTA housing profile", "same", "workbook"),
}
out = {}
for f, (name, url, scope) in SOURCES.items():
    p = os.path.join(RAW, f)
    assert os.path.exists(p), f"missing {p}"
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    rows = None
    if f.endswith(".csv"):
        rows = sum(1 for _ in open(p, "rb")) - 1
    elif f.endswith(".csv.gz"):
        rows = sum(1 for _ in gzip.open(p, "rb")) - 1
    out[f] = {"source": name, "url": url, "scope": scope,
              "downloaded_utc": datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
              "bytes": os.path.getsize(p), "rows": rows, "sha256": h}
json.dump(out, open("sources_manifest.json", "w"), indent=1)
print(f"wrote sources_manifest.json: {len(out)} files")
