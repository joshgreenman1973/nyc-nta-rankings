#!/usr/bin/env python3
"""Merge ACS metrics + point aggregates + geography into the app's rankings.json.

Only residential NTAs (ntatype 0) are ranked. Rates are per 1,000 residents
(evictions: per 1,000 renter-occupied units; trees: per square mile).
"""
import json, sys, datetime, csv, gzip

SQFT_PER_SQMI = 27878400.0

acs = json.load(open("acs.json"))
pts = json.load(open("points.json"))["counts"]
gj = json.load(open("raw/nta2020.geojson"))

# Jobs located in each NTA (Census LEHD LODES 8 workplace file, 2023, all jobs),
# for the optional "residents and workers" rate base. Blocks join to NTAs
# through City Planning's 2020 tract-to-NTA equivalency.
t2n = {r["geoid"]: r["ntacode"] for r in csv.DictReader(open("raw/tract_nta.csv"))}
JOBS = {}
for r in csv.DictReader(gzip.open("raw/ny_wac_2023.csv.gz", "rt")):
    g = r["w_geocode"]
    if g[:5] not in ("36005", "36047", "36061", "36081", "36085"):
        continue
    c = t2n.get(g[:11])
    assert c, f"block {g} has no NTA"
    JOBS[c] = JOBS.get(c, 0) + int(r["C000"])
assert sum(JOBS.values()) > 4_000_000, "jobs file looks short"

areas = []
for f in gj["features"]:
    p = f["properties"]
    if p["ntatype"] != "0":
        continue
    code = p["nta2020"]
    sqmi = float(p["shape_area"]) / SQFT_PER_SQMI
    assert 0.02 < sqmi < 15, f"{code}: implausible area {sqmi}"
    a = acs[code]
    c = pts.get(code, {})
    pop = a["population"]["v"]
    renters = a["_renter_units"]["v"]

    vals = {k: v for k, v in a.items() if not k.startswith("_")}
    vals["density"] = {"v": round(pop / sqmi) if pop else None, "m": None}
    vals["land_area"] = {"v": round(sqmi, 3), "m": None}

    def rate(metric, num_key, den, per=1000.0, nd=1):
        n = c.get(num_key, 0)
        vals[metric] = {"v": round(n / den * per, nd) if den else None, "m": None, "n": n}
        if num_key + "_locs" in c or num_key in ("complaints_311", "noise", "rodent", "illegal_parking"):
            vals[metric]["l"] = c.get(num_key + "_locs", 0)   # distinct locations
            vals[metric]["t"] = c.get(num_key + "_top", 0)    # complaints at the busiest one
    if pop and pop > 0:
        rate("felony_rate", "felonies", pop)
        rate("violent_rate", "violent_felonies", pop)
        rate("collision_rate", "collisions", pop)
        rate("injury_rate", "crash_injuries", pop)
        rate("complaints_rate", "complaints_311", pop, nd=0)
        rate("noise_rate", "noise", pop)
        rate("rodent_rate", "rodent", pop)
        rate("parking_rate", "illegal_parking", pop)
        rate("restaurant_rate", "restaurants", pop)
    else:
        for m in ("felony_rate","violent_rate","collision_rate","injury_rate","complaints_rate","noise_rate","rodent_rate","parking_rate","restaurant_rate"):
            vals[m] = {"v": None, "m": None, "n": c.get(m, 0)}
    vals["eviction_rate"] = {"v": round(c.get("evictions", 0) / renters * 1000, 1) if renters else None,
                             "m": None, "n": c.get("evictions", 0)}
    vals["tree_density"] = {"v": round(c.get("trees", 0) / sqmi), "m": None, "n": c.get("trees", 0)}
    vals["subway_stations"] = {"v": c.get("subway_stations", 0), "m": None}

    # round long ACS decimals for payload size + display
    for k, vm in vals.items():
        if vm["v"] is not None:
            if k in ("median_hh_income", "per_capita_income", "median_home_value", "median_rent", "population", "density"):
                vm["v"] = round(vm["v"])
            elif k == "land_area":
                pass  # keep 3 decimals so density arithmetic is reproducible
            elif isinstance(vm["v"], float):
                vm["v"] = round(vm["v"], 1)
        if vm.get("m") is not None:
            vm["m"] = round(vm["m"], 1) if vm["m"] < 100 else round(vm["m"])

    areas.append({"code": code, "name": p["ntaname"], "boro": p["boroname"],
                  "jobs": JOBS.get(code, 0), "values": vals})

assert len(areas) == 197, f"expected 197 residential NTAs, got {len(areas)}"

out = {
    "built": datetime.date.today().isoformat(),
    "areas": sorted(areas, key=lambda a: a["code"]),
}
json.dump(out, open("../docs/rankings.json", "w"), separators=(",", ":"))
n_metrics = len(areas[0]["values"])
print(f"wrote ../docs/rankings.json: {len(areas)} areas x {n_metrics} metrics", file=sys.stderr)
