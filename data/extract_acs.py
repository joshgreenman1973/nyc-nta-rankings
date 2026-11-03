#!/usr/bin/env python3
"""Extract NTA-level metrics from DCP ACS 2020-2024 5-year profile workbooks.

Each variable in the workbooks has columns: <stem>E (estimate), <stem>M (MOE),
<stem>C (CV), <stem>P (percent), <stem>Z (MOE of percent).
Output: acs.json  {nta_code: {metric_id: {"v": value, "m": moe}}}
Fails loud if any expected column or NTA is missing.
"""
import json, sys
import openpyxl

RAW = "raw"

# metric_id -> (workbook, stem, use) where use is "E" (estimate) or "P" (percent)
METRICS = {
    # Demographic
    "population":      ("Dem", "Pop_1", "E"),
    "median_age":      ("Dem", "MdAge", "E"),
    "pct_under18":     ("Dem", "PopU181", "P"),
    "pct_65plus":      ("Dem", "Pop65pl1", "P"),
    "pct_hispanic":    ("Dem", "Hsp1", "P"),
    "pct_white_nh":    ("Dem", "WtNH", "P"),
    "pct_black_nh":    ("Dem", "BlNH", "P"),
    "pct_asian_nh":    ("Dem", "AsnNH", "P"),
    # Social
    "avg_hh_size":     ("Soc", "AvgHHSz", "E"),
    "pct_foreign_born":("Soc", "Fb1", "P"),
    "pct_lang_not_english": ("Soc", "LgOEng1", "P"),
    "pct_limited_english":  ("Soc", "LgOEnLEP1", "P"),
    "pct_bachelors":   ("Soc", "EA_BchDH", "P"),
    "pct_grad_degree": ("Soc", "EA_GrdPfD", "P"),
    "pct_no_hs":       ("Soc", "EA_LTHSGr", "P"),
    "pct_veterans":    ("Soc", "CvVet18pl", "P"),
    "pct_disability":  ("Soc", "CvNID", "P"),
    "pct_same_house":  ("Soc", "SmHs", "P"),
    "pct_internet":    ("Soc", "HHInt", "P"),
    # Economic
    "median_hh_income":("Econ", "MdHHInc", "E"),
    "per_capita_income":("Econ", "PerCapInc", "E"),
    "pct_poverty":     ("Econ", "PBwPv", "P"),
    "pct_child_poverty":("Econ", "PU18BwPv", "P"),
    "pct_hh_200k":     ("Econ", "HHI200pl", "P"),
    "pct_snap":        ("Econ", "Inc_SNAP", "P"),
    "unemployment":    ("Econ", "CvLFUEm2", "P"),
    "labor_force":     ("Econ", "LF", "P"),
    "pct_uninsured":   ("Econ", "NHIns", "P"),
    "pct_govt_workers":("Econ", "GvtWrkr", "P"),
    "pct_self_employed":("Econ", "SlfEmNInc", "P"),
    "mean_commute":    ("Econ", "MnTrvTm", "E"),
    "pct_transit":     ("Econ", "CW_PbTrns", "P"),
    "pct_walk_work":   ("Econ", "CW_Wlkd", "P"),
    "pct_wfh":         ("Econ", "CW_WrkdHm", "P"),
    "pct_drive_alone": ("Econ", "CW_DrvAln", "P"),
    # Housing
    "median_rent":     ("Hous", "MdGR", "E"),
    "median_home_value":("Hous", "MdVl", "E"),
    "pct_renters":     ("Hous", "ROcHU1", "P"),
    "pct_rent_burdened":("Hous", "GRPI30pl", "P"),
    "pct_severe_rent_burden":("Hous", "GRPI50pl", "P"),
    "pct_prewar":      ("Hous", "BltBf39", "P"),
    "pct_built_2010":  ("Hous", "Blt10Ltr", "P"),
    "pct_big_buildings":("Hous", "HU20plu", "P"),
    "pct_crowded":     ("Hous", "OcPR1pl", "P"),
    "pct_no_vehicle":  ("Hous", "NoVhclAv", "P"),
    "median_rooms":    ("Hous", "MdRms", "E"),
    "pct_vacant":      ("Hous", "VacHU", "P"),
    # denominators (not shown as ranking categories)
    "_occupied_units": ("Hous", "OcHU1", "E"),
    "_renter_units":   ("Hous", "ROcHU1", "E"),
}

# computed: pct_never_married, pct_single_family (below); density in build step.

def num(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "N/A", "*", "**", "***", "(X)"): return None
    try: return float(s)
    except ValueError: return None

books = {}
for wbname in ("Dem", "Soc", "Econ", "Hous"):
    wb = openpyxl.load_workbook(f"{RAW}/{wbname}_nta.xlsx", read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))
    idx = {h: i for i, h in enumerate(hdr)}
    data = {}
    for r in rows:
        if r[idx["GeoType"]] != "NTA2020": continue
        code = r[idx["GeoID"]]
        data[code] = r
    books[wbname] = (idx, data)
    print(f"{wbname}: {len(data)} NTAs, {len(hdr)} cols", file=sys.stderr)

codes = set(books["Dem"][1].keys())
for wbname in books:
    assert set(books[wbname][1].keys()) == codes, f"NTA mismatch in {wbname}"

out = {}
for code in sorted(codes):
    rec = {}
    for mid, (wbname, stem, use) in METRICS.items():
        idx, data = books[wbname]
        row = data[code]
        vcol, mcol = stem + use, stem + ("Z" if use == "P" else "M")
        assert vcol in idx, f"missing column {vcol} in {wbname}"
        v = num(row[idx[vcol]])
        m = num(row[idx[mcol]]) if mcol in idx else None
        # City Planning leaves the percent (and its MOE) blank when the estimate
        # is exactly zero. That is a real 0%, not a missing value.
        if v is None and use == "P" and num(row[idx[stem + "E"]]) == 0:
            v = 0.0
        rec[mid] = {"v": v, "m": m}
    # computed: % never married (both sexes, pop 15+)
    idx, data = books["Soc"]
    row = data[code]
    def g(c): return num(row[idx[c]])
    nm, m15, f15 = g("MS_MNvMrdE"), g("MS_M15plE"), g("MS_F15plE")
    fnm = g("MS_FNvMrdE")
    if None not in (nm, fnm, m15, f15) and (m15 + f15) > 0:
        rec["pct_never_married"] = {"v": round((nm + fnm) / (m15 + f15) * 100, 1), "m": None}
    else:
        rec["pct_never_married"] = {"v": None, "m": None}
    # computed: % single-family (1-unit detached + attached share of units)
    idx, data = books["Hous"]
    row = data[code]
    def h(c): return num(row[idx[c]])
    d, a = h("HU1uDP"), h("HU1uAP")
    if d is None and h("HU1uDE") == 0: d = 0.0   # blank percent = zero estimate
    if a is None and h("HU1uAE") == 0: a = 0.0
    rec["pct_single_family"] = {"v": round(d + a, 1) if None not in (d, a) else None, "m": None}
    out[code] = rec

json.dump(out, open("acs.json", "w"))
print(f"wrote acs.json: {len(out)} NTAs x {len(next(iter(out.values())))} metrics", file=sys.stderr)
