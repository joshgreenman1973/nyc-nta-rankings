#!/usr/bin/env python3
"""Merge ACS metrics + point aggregates + geography into the app's rankings.json.

Only residential NTAs (ntatype 0) are ranked. Rates are per 1,000 residents
(evictions: per 1,000 renter-occupied units; trees: per square mile).
"""
import json, sys, datetime

SQFT_PER_SQMI = 27878400.0

acs = json.load(open("acs.json"))
pts = json.load(open("points.json"))["counts"]
gj = json.load(open("raw/nta2020.geojson"))

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

    areas.append({"code": code, "name": p["ntaname"], "boro": p["boroname"], "values": vals})

assert len(areas) == 197, f"expected 197 residential NTAs, got {len(areas)}"

out = {
    "built": datetime.date.today().isoformat(),
    "areas": sorted(areas, key=lambda a: a["code"]),
}
json.dump(out, open("../docs/rankings.json", "w"), separators=(",", ":"))
n_metrics = len(areas[0]["values"])
print(f"wrote ../site/rankings.json: {len(areas)} areas x {n_metrics} metrics", file=sys.stderr)
