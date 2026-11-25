# Fuel Window

[Open Fuel Window](https://coolcode.ca/fuelwindow/) compares regulated fuel prices in Nova Scotia and Prince Edward Island, calculates a fill or trip, and saves dated vehicle or heating-oil plans privately in the browser.

<!-- coolcode:guide -->
Fuel Window includes all six Nova Scotia pricing zones for self-serve regular gasoline and diesel; PEI adds self/full-serve regular, mid-grade, premium and diesel plus the after-tax furnace-oil maximum. Prices are official regulated limits, not live station quotes or forecasts. Editions and successful check dates are separate. Enter litres, distance and consumption to estimate a budget; optional saved plans retain their original source edition and can be exported/imported as JSON. Calculations and saved plans stay in your browser. Public sources are checked twice daily and an unavailable source retains its prior good prices with a visible warning.
<!-- /coolcode:guide -->

## Sources and meanings

- [Nova Scotia Energy Board prices and zone map](https://nserbt.ca/nseb/mandates/gasoline-diesel-pricing/gasoline-diesel-prices-zone-map): six zones, regular and ultra-low sulphur diesel, self-serve minimum/maximum cents per litre. [Official historical orders](https://nserbt.ca/nseb/mandates/gasoline-diesel-pricing/historical-prices) cover earlier periods.
- [PEI IRAC current petroleum prices](https://irac.pe.ca/petrol/current-petroleum-prices/): pump prices include taxes; furnace oil uses **Maximum Price (After Tax)**. Gasoline, diesel and furnace-oil adjustments normally take effect Tuesday and Friday at 00:01. Propane has a different schedule/tax basis and is excluded.
- Source `effective_date` is the date on the publisher's table. `checked_at` advances only after successful HTTP retrieval and complete validation. `last_attempt_at` records failed attempts separately. Money is CAD.
- IRAC arrow changes describe self-serve **minimums** or the furnace-oil **maximum**, labelled in the UI. Other price changes compare maximums between distinct editions actually collected. No historical change is inferred before an earlier capture exists.
- Maximum-only furnace oil has `min: null`, not zero. Station, delivery and service charges can differ. Trip fuel is `km × L/100 km / 100`; costs multiply litres by cents per litre / 100.

The initial capture contains 21 rows from November 24, 2026. Future counts derive from data. The collector keeps 120 distinct editions per source, with capture dates; saved personal plans retain selected evidence independently. HTML table adapters avoid downloading PDFs every refresh; historical PDF orders are linked for deeper history. We do not claim complete historical coverage.

## Privacy

The page fetches public JSON from its own path. Visitor inputs never go to fuel providers. Only clicking Save writes to `coolcode:fuelwindow:plans` in localStorage. Refreshes preserve saves; private browsing, storage restrictions or clearing site data may remove them. Export JSON backups. Import validates bounded size/schema/numbers; older coverage remains readable. Clear saved removes only this app's records. Shared CoolCode metrics/report controls retain their existing behaviour.

## Expand or customize

1. Edit `web/config.json` for default price ID, litres, distance, consumption, saved-plan limit (up to 100) and stale-check hours. Every published row becomes an option automatically; defaults do not limit coverage. Visitor vehicle names and valid numeric inputs are accepted within the displayed bounds.
2. Edit `config/sources.json` for official URL, adapter, expected row count, download/time limits and retained-edition limit. Add jurisdictions by implementing a parser in `scripts/refresh.py`, registering it in `ADAPTERS`, and adding fixtures/failure tests. Never reuse another source's date or treat a maximum as a range.
3. Run `python3 scripts/refresh.py`. Failed sources retain their old prices/check times with `status: retained`; initial failure without a capture aborts. Review `web/data/prices.json`. `--fixture-dir` is available for explicit offline experiments only.
4. Run the checks below, commit source/config/data to `main`, and verify Pages plus live data. Catalogue/coverage changes also follow the [CoolCode lifecycle](https://github.com/jsdyer/jsdyer.github.io/blob/main/docs/tool-lifecycle.md).

## Checks, schedule and operations

```sh
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 -m pip install -r tests/browser-requirements.txt
CHROMIUM_PATH=/usr/bin/google-chrome python3 tests/browser_smoke.py
```

Builds are offline, publishing only `web/` to ignored `dist/`. HTML, CSS, imports and JSON URLs share a content-derived version to avoid stale caches. Tests cover source fixtures, failure retention, cost calculations, coverage, safe imports, browser persistence and mobile layout.

`.github/workflows/pages.yml` checks sources at **07:19 and 19:19 UTC daily**, with `workflow_dispatch`. Push/PR builds use committed snapshots without network collection. Scheduled/manual runs validate, commit `web/data`, and deploy in the same workflow; they do not rely on a bot commit triggering another run. `.github/workflows/schedule-guard.yml` renews only the declared collector and itself. No API keys, Worker endpoint or repository secrets are needed.

Probe `/fuelwindow/data/prices.json`: inspect each `sources[].checked_at` (warn after 48 hours), `sources[].status`, `row_count` and `prices[].effective_date`. Top-level attempt time is not successful freshness. Register the workflow/guard with the central watchdog; a selected-repository GitHub App installation must include this repo.
