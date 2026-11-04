# Every neighborhood, ranked

All 197 of New York City's residential neighborhood tabulation areas (2020 NTAs), ranked 63 ways with verifiable government data. Live: https://joshgreenman1973.github.io/nyc-nta-rankings/

- `docs/` — the site (GitHub Pages): index.html, methodology.html, rankings.json, shapes.json
- `data/fetch.sh` — downloads every non-survey input: NYC Open Data point files (with record IDs), MTA subway stations, Census Bureau LODES jobs files (workplace and residence) and City Planning's tract-to-NTA equivalency. Fails loud on empty or short files and logs each run to `data/fetch.log`.
- `data/manifest.py` — writes `data/sources_manifest.json`: source, query scope, download time, size, row count and SHA-256 for every raw file.
- `data/extract_acs.py` — reads City Planning's ACS 2020-2024 NTA workbooks (`data/raw/*_nta.xlsx`, committed)
- `data/points.py` — point-in-polygon aggregation to 2020 NTAs. Asserts record IDs are unique; counts subway stations by distinct station ID; drops felonies at NYPD station-house points; records downloaded, usable, matched and ranked-area counts for every source.
- `data/build.py` — merges everything, plus LODES jobs per NTA, into `docs/rankings.json`

## Rebuild

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
./data/fetch.sh
cd data && ../venv/bin/python manifest.py && ../venv/bin/python extract_acs.py && ../venv/bin/python points.py && ../venv/bin/python build.py
```

The ACS workbooks and NTA boundaries are fetched once by hand (City Planning's download page needs a browser user agent) and are committed or archived. Open Data files change as agencies revise records, so a fresh fetch will not exactly reproduce an earlier build. The raw snapshot behind the current site is attached to the GitHub release named `data-<date>`; compare its files against `sources_manifest.json` checksums.

The companion [Everything map](https://github.com/joshgreenman1973/nyc-everything-map) bakes ranks from `docs/rankings.json` and parses the `M` metric table in `docs/index.html` (scripts/bake_rankings.py). Keep each M row on one line, with string literals or the `ACS` constant, or that bake breaks.

Sources: Census Bureau ACS via City Planning; NYC Open Data (NYPD, 311, collisions, evictions, restaurants, Parks forestry trees); MTA; Census Bureau LEHD LODES 8 (2023). See docs/methodology.html for definitions and caveats.
