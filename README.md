# Time Zone Database

Offline lookup of IANA time-zone identifiers with descriptive metadata, using only the Python standard library.

## Usage

```python
from time_zone_database import TimeZoneDatabase, TimeZoneInfo

db = TimeZoneDatabase()
print(db.identifiers()[:3])            # ['Africa/Abidjan', 'Africa/Accra', 'Africa/Addis_Ababa']
print(db.regions())                    # ['Africa', 'America', 'Asia', 'Australia', 'Europe', 'Pacific', 'UTC']
info = db.get("US/Eastern")             # alias resolves to America/New_York
print(info.identifier, info.region, info.country_codes)
print(db.canonicalize("Japan"))         # Asia/Tokyo
print("Asia/Kolkata" in db)             # True
```

## Why this exists

Container images often lack the `zone1970.tab` file that tools like `pytz` bundle for zone metadata, yet they do ship `zoneinfo`-compatible tzdata. This library layers a small curated metadata table on top of whatever `zoneinfo` can resolve locally, so you can ask for region, country codes, canonical names, and aliases without a third-party package.

The trade-off: the metadata table is hand-maintained and finite. It covers the common IANA zones and their well-known aliases but is not a full mirror of the IANA database. If you need every zone ever defined, use `zoneinfo` directly and accept that you get no metadata.

## Edge cases

- **Aliases** such as `US/Eastern`, `Japan`, `PRC`, and `GMT` are accepted by `get`, `is_known`, and `canonicalize`; they resolve to their canonical IANA identifier.
- **`UTC`** is treated as its own region with no country codes and no city location.
- **`current_utc_offset`** reflects daylight-saving rules at the moment the injected clock returns. Pass a custom `now` callable to `TimeZoneDatabase` for deterministic offsets; the default uses `datetime.now`.
- **`by_region`** is case-sensitive and matches only the first path segment (`America`, not `America/Argentina`).

## Exports

- `TimeZoneDatabase` — the lookup class.
- `TimeZoneInfo` — per-zone metadata returned by `TimeZoneDatabase.get`.
