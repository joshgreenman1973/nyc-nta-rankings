# Fact-check report: Every neighborhood, ranked

Conducted Aug. 3, 2026, against primary sources. All fixes described below are applied in this commit.

**Overall assessment:** The core data pipeline verified cleanly against independent recomputation — every population figure matched exactly and two independent point-in-polygon implementations agreed to the row. Three real issues were found and fixed: an inflated tree count (removed trees were included), a mislabeled tree metric, and imprecise station/top-coding descriptions.

## Verified ✅

- **All 197 NTA populations, exact match.** Independently rebuilt from the Census API (2020-2024 ACS tract-level B01003, all five county FIPS) summed through City Planning's tract-to-NTA equivalency file (hm78-6dwm, 2,327 tracts). 197 of 197 values identical to the board's.
- **Citywide consistency.** The 197 neighborhoods sum to 8,475,754 vs the official ACS citywide 8,483,844 (Census API B01003 for place 51000); the 8,090 gap is residents of excluded park/airport/institutional NTAs.
- **Point-in-polygon assignment.** A second, independent implementation (matplotlib.path vs shapely STRtree) reproduced felony counts exactly in three test NTAs across three boroughs: Midtown-Times Square 4,356; Greenpoint 650; Mariner's Harbor-Arlington-Graniteville 602.
- **Violent felony definition.** The four offense strings (murder & non-negl. manslaughter 309, rape 2,049, robbery 15,092, felony assault 29,841) sum to 47,291 — exactly the count used; a full scan of 2025 felony `ofns_desc` values confirms no variant spellings were missed. Total 2025 felony complaints with coordinates: 188,142, matching the server-side count.
- **Percentage bases.** Recomputed from raw estimates in DCP's workbooks: Greenpoint bachelor's-or-higher 65.97% vs published 66.0; unemployment 6.79% vs published 6.79 (correct civilian-labor-force base).
- **Wakefield-Woodlawn noise outlier is real.** 77,720 noise complaints for 49,552 residents; cross-checked by zip code (10466 + 10470: 80,047 in the same window). The board's prolific-caller caveat stands.
- **Crash coordinate loss.** 85,546 collisions in 2025, 82,704 with usable coordinates (3.3% lack them), matching the methodology's "about 3%."
- **Match rates.** Every dataset assigned 99%+ of coordinates to an NTA (lowest: collisions at 99.2%).
- **Citywide population context.** Vintage 2025 census estimate ~8.58M as of July 1, 2025 (DCP "Population Estimates and Trends," July 2026 release), ~1.2% above the ACS five-year 8.48M, as stated on the page.

## Fixed 🔶

1. **Tree count included removed trees (~10% inflation).** The forestry file keeps "Retired" points for trees that were removed (173,626 records). The original filter excluded only dead/stump conditions; corrected to `tpstructure = 'Full' AND tpcondition != 'Dead'`, dropping the count from 993,104 to 888,653 standing live trees. Leaders were re-ranked (Norwood remains #1).
2. **Tree metric mislabeled "street trees."** Forestry Tree Points covers all trees the Parks Department actively manages — street trees plus managed park trees — and excludes uninventoried natural woodland. Relabeled "Parks-managed trees per square mile" with an explanatory note.
3. **"Station complexes" was wrong.** The MTA dataset counts stations (496, incl. 21 Staten Island Railway), not complexes (445); Times Square-42nd Street is five stations. Notes on both pages now say so.
4. **Top-coding attribution imprecise.** The $200,000 / $3,500 / $2,000,000 caps arise from DCP computing medians on bracketed distributions with open-ended top brackets, not from a census-published median top-code (the bureau's own tract-level top-codes differ). Reworded on both pages; observed caps in the data (2 NTAs at $200,000; 5 at $3,500; 3 at $2,000,000) are consistent with the corrected description.
5. **Displayed land area wasn't precise enough to reproduce density.** Upper East Side-Yorkville showed 0.5 sq mi with density 160,485 (78,549 ÷ 0.489). Land area now displays three decimals.

## Not independently verifiable ❓

- **ACS medians and percentages beyond arithmetic checks.** DCP is the sole tabulator of ACS data at NTA geography (medians can't be rebuilt from public tract tables). Values were read directly from DCP's published workbooks; parsing was verified by the exact-match population test, which exercises the same code path.
- **Administrative undercounts** (evictions before marshal execution, unreported crashes/crimes) are inherent to the sources and disclosed in the methodology.
