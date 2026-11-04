#!/usr/bin/env python3
"""Point-in-polygon aggregation of NYC Open Data points into 2020 NTAs.

Outputs points.json: {"counts": {nta_code: {metric: count}}, "_meta": {...}}.
_meta records, for every source, how many records were downloaded, how many had
usable coordinates, how many fell in any NTA and how many in a residential
(ranked) NTA, plus anything deliberately excluded, so every coverage figure on
the methodology page is reproducible.
Fails loud if an input is missing, a record ID repeats or a match rate is low.
"""
import csv, json, sys
from collections import Counter
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

csv.field_size_limit(10**8)

gj = json.load(open("raw/nta2020.geojson"))
polys, codes, residential = [], [], set()
for f in gj["features"]:
    polys.append(shape(f["geometry"]))
    codes.append(f["properties"]["nta2020"])
    if f["properties"]["ntatype"] == "0":
        residential.add(f["properties"]["nta2020"])
tree = STRtree(polys)
print(f"{len(polys)} NTA polygons, {len(residential)} residential", file=sys.stderr)

counts = {c: {} for c in codes}
meta = {}

# 311 metrics also get the number of distinct reported locations and the size of
# the two busiest, so one heavily reported location can't silently decide a ranking.
PLACE_METRICS = {"complaints_311", "noise", "rodent", "illegal_parking"}

def locate(lons, lats):
    """Index of the containing NTA for each point, or -1. A point exactly on a
    shared boundary goes to one polygon only, never both."""
    pts = shapely.points(np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
    res = tree.query(pts, predicate="intersects")
    out = np.full(len(lons), -1)
    pi, first = np.unique(res[0], return_index=True)
    out[pi] = res[1][first]
    return out

def assign(where, lats, lons, weights, metric):
    """Add weighted counts of located points to their NTAs."""
    places = {} if metric in PLACE_METRICS else None
    for i, gi in enumerate(where):
        if gi < 0:
            continue
        c = codes[gi]
        counts[c][metric] = counts[c].get(metric, 0) + weights[i]
        if places is not None:
            key = (round(lats[i], 5), round(lons[i], 5))  # one geocoded point, to about a meter
            pc = places.setdefault(c, Counter())
            pc[key] += 1
    if places is not None:
        for c, pc in places.items():
            top = [n for _, n in pc.most_common(2)]
            counts[c][metric + "_locs"] = len(pc)
            counts[c][metric + "_top"] = top[0]
            counts[c][metric + "_top2"] = sum(top)

def load(path, latcol, loncol, idcols, geom=None, drop_exact=False):
    """Read a CSV; assert record IDs are unique; split usable-coordinate rows from the rest.
    drop_exact removes rows identical in every field first (returned as a count)."""
    rows = list(csv.DictReader(open(path)))
    dropped = 0
    if drop_exact:
        seen, uniq = set(), []
        for r in rows:
            k = tuple(r.values())
            if k in seen: dropped += 1; continue
            seen.add(k); uniq.append(r)
        rows = uniq
    ids = Counter(tuple(r[c] for c in idcols) for r in rows)
    dup = {k: v for k, v in ids.items() if v > 1}
    assert not dup, f"{path}: {len(dup)} repeated record IDs, e.g. {list(dup)[:3]}"
    keep, lats, lons = [], [], []
    for r in rows:
        try:
            if geom:
                g = r[geom]; lo, la = g[g.index("(")+1:g.index(")")].split()
                la, lo = float(la), float(lo)
            else:
                la, lo = float(r[latcol]), float(r[loncol])
        except (ValueError, KeyError):
            continue
        if not (40.3 < la < 41.1 and -74.5 < lo < -73.4):
            continue
        keep.append(r); lats.append(la); lons.append(lo)
    return rows, keep, lats, lons, dropped

def run(name, path, latcol, loncol, idcols, metric_fn, min_rate=0.90, geom=None, exclude=None, drop_exact=False):
    rows, keep, lats, lons, dropped = load(path, latcol, loncol, idcols, geom, drop_exact)
    assert keep, f"{name}: no usable rows"
    where = locate(lons, lats)
    m = {"downloaded": len(rows) + dropped, "exact_duplicates_dropped": dropped, "usable_coords": len(keep),
         "in_any_nta": int((where >= 0).sum()),
         "in_ranked_nta": int(sum(1 for g in where if g >= 0 and codes[g] in residential))}
    excluded = np.zeros(len(keep), dtype=bool)
    if exclude:
        excluded, m["excluded"] = exclude(keep, lats, lons)
    per_metric = {}
    for i, r in enumerate(keep):
        for met, w in metric_fn(r, excluded[i]):
            per_metric.setdefault(met, []).append((i, w))
    for met, items in per_metric.items():
        idx = [i for i, _ in items]
        assign(where[idx], [lats[i] for i in idx], [lons[i] for i in idx], [w for _, w in items], met)
        m.setdefault("metrics", {})[met] = {"records": len(items),
            "in_ranked_nta": int(sum(1 for i in idx if where[i] >= 0 and codes[where[i]] in residential))}
    rate = m["in_any_nta"] / m["usable_coords"]
    print(f"{name}: {m['downloaded']} downloaded, {m['usable_coords']} usable, "
          f"{m['in_any_nta']} in an NTA ({rate:.2%}), {m['in_ranked_nta']} in a ranked NTA", file=sys.stderr)
    assert rate > min_rate, f"{name}: match rate too low"
    meta[name] = m

# ---- crime ----------------------------------------------------------------
# NYPD places every rape and sex-crime complaint at the precinct station house, and
# also places there many other offenses it could not geocode (dataset footnotes 10-11).
# Those coordinates say nothing about where a crime happened, so every felony recorded
# at a station-house point is left out of the neighborhood counts. Station houses are
# identified as the points that hold the rape and sex-crime records.
SEX = {"RAPE", "SEX CRIMES"}
VIOLENT = {"MURDER & NON-NEGL. MANSLAUGHTER", "ROBBERY", "FELONY ASSAULT"}

def station_houses(keep, lats, lons):
    key = lambda i: (round(lats[i], 6), round(lons[i], 6))
    sex = [(key(i), r["addr_pct_cd"]) for i, r in enumerate(keep) if r["ofns_desc"] in SEX]
    sh = {k for k, _ in sex}
    by_pct = Counter(p for _, p in sex)
    pts_per_pct = Counter(p for k, p in set(sex))
    assert 70 <= len(sh) <= 90, f"expected about one station house per precinct, got {len(sh)}"
    ex = np.array([key(i) in sh for i in range(len(keep))])
    fel = [r for i, r in enumerate(keep) if ex[i] and r["law_cat_cd"] == "FELONY"]
    info = {"station_house_points": len(sh), "precincts": len(by_pct),
            "precincts_with_more_than_one_point": sum(1 for v in pts_per_pct.values() if v > 1),
            "felonies_at_station_houses": len(fel),
            "of_which_rape_or_sex_crimes": sum(1 for r in fel if r["ofns_desc"] in SEX),
            "of_which_murder_robbery_felony_assault": sum(1 for r in fel if r["ofns_desc"] in VIOLENT),
            "rape_and_sex_crime_felonies_anywhere": sum(1 for r in keep if r["law_cat_cd"] == "FELONY" and r["ofns_desc"] in SEX)}
    print(f"crime station houses: {info}", file=sys.stderr)
    return ex, info

def crime_fn(row, excluded):
    if excluded or row.get("law_cat_cd") != "FELONY":
        return []
    out = [("felonies", 1)]
    if row.get("ofns_desc") in VIOLENT:
        out.append(("violent_felonies", 1))
    return out

def coll_fn(row, _):
    out = [("collisions", 1)]
    try:
        inj = int(float(row.get("number_of_persons_injured") or 0)) + int(float(row.get("number_of_persons_killed") or 0))
    except ValueError:
        inj = 0
    if inj: out.append(("crash_injuries", inj))
    return out

def t311_fn(row, _):
    ct = row.get("complaint_type", "")
    out = [("complaints_311", 1)]
    if ct.startswith("Noise"): out.append(("noise", 1))
    if ct == "Rodent": out.append(("rodent", 1))
    if ct == "Illegal Parking": out.append(("illegal_parking", 1))
    return out

ONE = lambda m: (lambda row, _: [(m, 1)])

run("crime", "raw/nypd2025.csv", "latitude", "longitude", ["cmplnt_num"], crime_fn, exclude=station_houses)
run("collisions", "raw/collisions2025.csv", "latitude", "longitude", ["collision_id"], coll_fn)
# Evictions have no record ID. A row is an execution: case, docket and execution date.
# One row in the 2025 file repeats exactly and is dropped. 58 cases were executed twice
# on different dates (same unit, months apart); both executions count.
run("evictions", "raw/evictions2025.csv", "latitude", "longitude",
    ["court_index_number", "docket_number", "executed_date"], ONE("evictions"), drop_exact=True)
# Restaurants: one row per establishment. A CAMIS listed at two coordinates would repeat
# here and fail the uniqueness check rather than count twice.
run("restaurants", "raw/restaurants.csv", "latitude", "longitude", ["camis"], ONE("restaurants"))

# Subway: the MTA file has one row per GTFS stop. A few stations carry two stop IDs at
# the same coordinates (145 St, W 4 St-Wash Sq, Queensboro Plaza), so count distinct
# station_id values: keep the first row of each and confirm the duplicates sit together.
srows = list(csv.DictReader(open("raw/subway_stations.csv")))
first, dups = {}, []
for r in srows:
    s = r["station_id"]
    if s in first:
        f = first[s]
        assert (f["gtfs_latitude"], f["gtfs_longitude"]) == (r["gtfs_latitude"], r["gtfs_longitude"]), f"station {s} has two locations"
        dups.append(f"{s} {r['stop_name']} ({f['gtfs_stop_id']}, {r['gtfs_stop_id']})")
    else:
        first[s] = r
with open("raw/_stations_unique.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=srows[0].keys()); w.writeheader(); w.writerows(first.values())
run("subway", "raw/_stations_unique.csv", "gtfs_latitude", "gtfs_longitude", ["station_id"], ONE("subway_stations"), min_rate=0.99)
meta["subway"].update({"stop_rows": len(srows), "stations_with_two_stop_ids": dups})
print(f"subway: {len(srows)} stop rows, {len(first)} stations; doubled: {dups}", file=sys.stderr)

run("trees", "raw/trees.csv", None, None, ["objectid"], ONE("trees"), geom="geometry")
run("t311", "raw/t311.csv", "latitude", "longitude", ["unique_key"], t311_fn, min_rate=0.85)

json.dump({"counts": counts, "_meta": meta}, open("points.json", "w"), indent=0)
print("wrote points.json", file=sys.stderr)
