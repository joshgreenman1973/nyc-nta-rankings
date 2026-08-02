#!/usr/bin/env python3
"""Point-in-polygon aggregation of NYC Open Data points into 2020 NTAs.

Outputs points.json: {nta_code: {metric: count}} plus _meta with match rates.
Fails loud if any input is missing or match rate is implausibly low.
"""
import csv, json, sys
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

csv.field_size_limit(10**8)

gj = json.load(open("raw/nta2020.geojson"))
polys, codes = [], []
for f in gj["features"]:
    polys.append(shape(f["geometry"]))
    codes.append(f["properties"]["nta2020"])
tree = STRtree(polys)
print(f"{len(polys)} NTA polygons", file=sys.stderr)

counts = {c: {} for c in codes}
meta = {}

def assign(lons, lats, weights, metric):
    """Add weighted counts of points to containing NTAs."""
    pts = shapely.points(np.asarray(lons), np.asarray(lats))
    res = tree.query(pts, predicate="intersects")  # [[pt_idx],[poly_idx]]
    for pi, gi in zip(res[0], res[1]):
        c = codes[gi]
        counts[c][metric] = counts[c].get(metric, 0) + weights[pi]
    matched = len(set(res[0]))
    return matched

def load_csv(path, latcol, loncol):
    lons, lats, rows = [], [], []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            try:
                la, lo = float(row[latcol]), float(row[loncol])
            except (ValueError, KeyError):
                continue
            if not (40.3 < la < 41.1 and -74.5 < lo < -73.4):
                continue
            lats.append(la); lons.append(lo); rows.append(row)
    return lons, lats, rows

def run(path, latcol, loncol, metric_fn, name, min_rate=0.90):
    lons, lats, rows = load_csv(path, latcol, loncol)
    total = len(rows)
    assert total > 0, f"{name}: no usable rows"
    # metric_fn(row) -> list of (metric, weight)
    per_metric = {}
    for i, row in enumerate(rows):
        for m, w in metric_fn(row):
            per_metric.setdefault(m, ([], [], []))
            per_metric[m][0].append(lons[i]); per_metric[m][1].append(lats[i]); per_metric[m][2].append(w)
    for m, (lo, la, w) in per_metric.items():
        matched = assign(lo, la, w, m)
        rate = matched / len(lo)
        print(f"{name}/{m}: {len(lo)} pts, {matched} matched ({rate:.1%})", file=sys.stderr)
        meta[m] = {"points": len(lo), "matched": matched}
        assert rate > min_rate, f"{name}/{m}: match rate too low"

ONE = lambda m: (lambda row: [(m, 1)])

VIOLENT = {"MURDER & NON-NEGL. MANSLAUGHTER", "RAPE", "ROBBERY", "FELONY ASSAULT"}
def crime_fn(row):
    out = []
    if row.get("law_cat_cd") == "FELONY":
        out.append(("felonies", 1))
        if row.get("ofns_desc") in VIOLENT:
            out.append(("violent_felonies", 1))
    return out

def coll_fn(row):
    out = [("collisions", 1)]
    try:
        inj = int(float(row.get("number_of_persons_injured") or 0)) + int(float(row.get("number_of_persons_killed") or 0))
    except ValueError:
        inj = 0
    if inj: out.append(("crash_injuries", inj))
    return out

def t311_fn(row):
    ct = row.get("complaint_type", "")
    out = [("complaints_311", 1)]
    if ct.startswith("Noise"): out.append(("noise", 1))
    if ct == "Rodent": out.append(("rodent", 1))
    if ct == "Illegal Parking": out.append(("illegal_parking", 1))
    return out

run("raw/nypd2025.csv", "latitude", "longitude", crime_fn, "crime")
run("raw/collisions2025.csv", "latitude", "longitude", coll_fn, "collisions")
run("raw/evictions2025.csv", "latitude", "longitude", ONE("evictions"), "evictions")
run("raw/restaurants.csv", "latitude", "longitude", ONE("restaurants"), "restaurants")
run("raw/subway_stations.csv", "gtfs_latitude", "gtfs_longitude", ONE("subway_stations"), "subway", min_rate=0.99)

# trees: WKT geometry column
tlons, tlats = [], []
with open("raw/trees.csv") as fh:
    for row in csv.DictReader(fh):
        g = row.get("geometry", "")
        if not g.startswith("POINT"): continue
        try:
            lo, la = g[g.index("(")+1:g.index(")")].split()
            lo, la = float(lo), float(la)
        except ValueError:
            continue
        if 40.3 < la < 41.1 and -74.5 < lo < -73.4:
            tlons.append(lo); tlats.append(la)
assert len(tlons) > 500000, "trees: too few points"
matched = assign(tlons, tlats, [1]*len(tlons), "trees")
print(f"trees: {len(tlons)} pts, {matched} matched ({matched/len(tlons):.1%})", file=sys.stderr)
meta["trees"] = {"points": len(tlons), "matched": matched}

run("raw/t311.csv", "latitude", "longitude", t311_fn, "t311", min_rate=0.85)

out = {"counts": counts, "_meta": meta}
json.dump(out, open("points.json", "w"))
print("wrote points.json", file=sys.stderr)
