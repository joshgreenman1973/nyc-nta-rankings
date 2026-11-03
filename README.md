# Every neighborhood, ranked

All 197 of New York City's residential neighborhood tabulation areas (2020 NTAs), ranked 63 ways with verifiable government data. Live: https://joshgreenman1973.github.io/nyc-nta-rankings/

- `docs/` — the site (GitHub Pages): index.html, methodology.html, rankings.json
- `data/fetch.sh` — downloads point datasets from NYC Open Data, MTA subway stations from the state portal and Census Bureau jobs-by-workplace data (fails loud on empty fetches)
- `data/extract_acs.py` — reads Department of City Planning ACS 2020-2024 NTA workbooks
- `data/points.py` — point-in-polygon aggregation to 2020 NTAs; for 311 also counts distinct locations and the busiest location
- `data/build.py` — merges everything, plus jobs per NTA, into `docs/rankings.json`

Rebuild: `./data/fetch.sh && cd data && ../venv/bin/python extract_acs.py && ../venv/bin/python points.py && ../venv/bin/python build.py`

Sources: Census Bureau ACS via City Planning; NYC Open Data (NYPD, 311, collisions, evictions, restaurants, Parks forestry trees); MTA; Census Bureau LEHD workplace data (LODES 8, 2023). See docs/methodology.html for definitions and caveats.
