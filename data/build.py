#!/usr/bin/env python3
"""Merge ACS metrics + point aggregates + geography into the app's rankings.json.

Only residential NTAs (ntatype 0) are ranked. Rates are per 1,000 residents
(evictions: per 1,000 renter-occupied units; trees: per square mile). Rates are
stored to three decimals so the page ranks on (nearly) unrounded values; the
page rounds only for display.
"""
import json, sys, datetime, csv, gzip

SQFT_PER_SQMI = 27878400.0

acs = json.load(open("acs.json"))
pts = json.load(open("points.json"))["counts"]
gj = json.load(open("raw/nta2020.geojson"))

# Census LEHD LODES 8, 2023, all jobs, for the optional commuter-adjusted rate base:
# jobs located in each NTA (workplace file, WAC) and jobs held by people who live
# there (residence file, RAC). Blocks join to NTAs through City Planning's 2020
# tract-to-NTA equivalency.
t2n = {r["geoid"]: r["ntacode"] for r in csv.DictReader(open("raw/tract_nta.csv"))}
def lodes(path, col):
    out = {}
    for r in csv.DictReader(gzip.open(path, "rt")):
        g = r[col]
        if g[:5] not in ("36005", "36047", "36061", "36081", "36085"):
            continue
        c = t2n.get(g[:11])
        assert c, f"block {g} has no NTA"
        out[c] = out.get(c, 0) + int(r["C000"])
    return out
JOBS = lodes("raw/ny_wac_2023.csv.gz", "w_geocode")
RJOBS = lodes("raw/ny_rac_2023.csv.gz", "h_geocode")
assert sum(JOBS.values()) > 4_000_000, "jobs file looks short"
assert sum(RJOBS.values()) > 3_000_000, "residence jobs file looks short"
print(f"jobs located in the city {sum(JOBS.values()):,}; jobs held by city residents {sum(RJOBS.values()):,}", file=sys.stderr)

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
    # area is fixed, so the density margin is the population margin scaled by the same area
    pm = a["population"]["m"]
    vals["density"] = {"v": round(pop / sqmi, 1) if pop else None, "m": round(pm / sqmi) if pop and pm is not None else None}
    vals["land_area"] = {"v": round(sqmi, 3), "m": None}

    def rate(metric, num_key, den, per=1000.0, nd=3):
        n = c.get(num_key, 0)
        vals[metric] = {"v": round(n / den * per, nd) if den else None, "m": None, "n": n}
        if num_key + "_locs" in c or num_key in ("complaints_311", "noise", "rodent", "illegal_parking"):
            vals[metric]["l"] = c.get(num_key + "_locs", 0)   # distinct locations
            vals[metric]["t"] = c.get(num_key + "_top", 0)    # complaints at the busiest one
            vals[metric]["t2"] = c.get(num_key + "_top2", 0)  # at the two busiest
    if pop and pop > 0:
        rate("felony_rate", "felonies", pop)
        rate("violent_rate", "violent_felonies", pop)
        rate("collision_rate", "collisions", pop)
        rate("injury_rate", "crash_injuries", pop)
        rate("complaints_rate", "complaints_311", pop)
        rate("noise_rate", "noise", pop)
        rate("rodent_rate", "rodent", pop)
        rate("parking_rate", "illegal_parking", pop)
        rate("restaurant_rate", "restaurants", pop)
    else:
        for m in ("felony_rate","violent_rate","collision_rate","injury_rate","complaints_rate","noise_rate","rodent_rate","parking_rate","restaurant_rate"):
            vals[m] = {"v": None, "m": None, "n": c.get(m, 0)}
    vals["eviction_rate"] = {"v": round(c.get("evictions", 0) / renters * 1000, 3) if renters else None,
                             "m": None, "n": c.get("evictions", 0)}
    vals["tree_density"] = {"v": round(c.get("trees", 0) / sqmi, 1), "m": None, "n": c.get("trees", 0)}
    vals["subway_stations"] = {"v": c.get("subway_stations", 0), "m": None}

    # round long ACS decimals for payload size + display
    RATES = {"felony_rate","violent_rate","collision_rate","injury_rate","complaints_rate","noise_rate",
             "rodent_rate","parking_rate","restaurant_rate","eviction_rate","tree_density","density"}
    for k, vm in vals.items():
        if vm["v"] is not None:
            if k in ("median_hh_income", "per_capita_income", "median_home_value", "median_rent", "population"):
                vm["v"] = round(vm["v"])
            elif k == "land_area" or k in RATES:
                pass  # keep their precision: land area reproduces density; rates rank unrounded
            elif isinstance(vm["v"], float):
                vm["v"] = round(vm["v"], 1)
        if vm.get("m") is not None:
            vm["m"] = round(vm["m"], 1) if vm["m"] < 100 else round(vm["m"])

    areas.append({"code": code, "name": p["ntaname"], "boro": p["boroname"],
                  "jobs": JOBS.get(code, 0), "rjobs": RJOBS.get(code, 0), "values": vals})

assert len(areas) == 197, f"expected 197 residential NTAs, got {len(areas)}"

out = {
    "built": datetime.date.today().isoformat(),
    "sources": json.load(open("points.json"))["_meta"],
    "areas": sorted(areas, key=lambda a: a["code"]),
}
json.dump(out, open("../docs/rankings.json", "w"), separators=(",", ":"))
n_metrics = len(areas[0]["values"])
print(f"wrote ../docs/rankings.json: {len(areas)} areas x {n_metrics} metrics", file=sys.stderr)
