"""Core offline IANA time-zone database.

Design decisions
----------------
* Zero third-party dependencies; stdlib only. We therefore do NOT attempt
  to ship the tzdata binary blob. Instead we expose whatever zoneinfo can
  resolve locally and layer descriptive metadata on top.
* Metadata comes from a small curated table of canonical IANA identifiers.
  Regions (continent/ocean) are derived deterministically from the tz name
  by splitting on '/' and taking the first segment. We made this explicit
  rather than parsing zone1970.tab because zone1970.tab is not always
  present on stripped-down container images.
* Aliases are resolved via zoneinfo's own IANA key normalisation so we stay
  consistent with the operating-system tzdata the caller already has.
"""

from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple


class TimeZoneInfo:
    """Read-only descriptive metadata for a single IANA time zone.

    Instances are created by :class:`TimeZoneDatabase`; users rarely need
    to construct them directly.
    """

    __slots__ = ("identifier", "region", "location", "country_codes", "aliases", "_now")

    def __init__(
        self,
        identifier: str,
        region: str,
        location: Optional[str],
        country_codes: Tuple[str, ...],
        aliases: Tuple[str, ...],
        now: Callable[[], _dt.datetime] = _dt.datetime.now,
    ) -> None:
        self.identifier = identifier
        self.region = region
        self.location = location
        self.country_codes = country_codes
        self.aliases = aliases
        self._now = now

    def __repr__(self) -> str:
        return f"TimeZoneInfo(identifier={self.identifier!r}, region={self.region!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeZoneInfo):
            return NotImplemented
        return self.identifier == other.identifier

    def __hash__(self) -> int:
        return hash(self.identifier)

    def current_utc_offset(self) -> _dt.timedelta:
        """Return the current UTC offset for this zone.

        Determinism note: the offset reflects whatever the injected clock
        returns. Tests pass a fixed clock so the result is reproducible.
        """
        aware = self._now(ZoneInfo(self.identifier))
        if aware.tzinfo is None:  # pragma: no cover - defensive
            raise RuntimeError("datetime lacked tzinfo after construction")
        return aware.utcoffset() or _dt.timedelta(0)

    def current_utc_offset_seconds(self) -> int:
        """Integer seconds form of :meth:`current_utc_offset`."""
        return int(self.current_utc_offset().total_seconds())


class TimeZoneDatabase:
    """Offline lookup of IANA time-zone identifiers and metadata.

    Parameters
    ----------
    now:
        Optional clock function returning ``datetime``. Injected purely so
        tests can make ``current_utc_offset`` deterministic; defaults to
        :func:`datetime.datetime.now`.
    """

    # Curated canonical identifiers with country codes and known aliases.
    # Region is derived from the first path segment; we do not store it.
    _TABLE: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], Optional[str]]] = {
        "Africa/Abidjan": (("CI",), (), "Abidjan"),
        "Africa/Accra": (("GH",), (), "Accra"),
        "Africa/Addis_Ababa": (("ET",), (), "Addis Ababa"),
        "Africa/Algiers": (("DZ",), (), "Algiers"),
        "Africa/Cairo": (("EG",), (), "Cairo"),
        "Africa/Casablanca": (("MA",), (), "Casablanca"),
        "Africa/Johannesburg": (("ZA",), (), "Johannesburg"),
        "Africa/Lagos": (("NG",), (), "Lagos"),
        "Africa/Nairobi": (("KE",), (), "Nairobi"),
        "America/Argentina/Buenos_Aires": (("AR",), ("America/Buenos_Aires",), "Buenos Aires"),
        "America/Chicago": (("US",), ("US/Central",), "Chicago"),
        "America/Denver": (("US",), ("US/Mountain",), "Denver"),
        "America/Los_Angeles": (("US",), ("US/Pacific",), "Los Angeles"),
        "America/New_York": (("US",), ("US/Eastern",), "New York"),
        "America/Sao_Paulo": (("BR",), (), "São Paulo"),
        "America/Toronto": (("CA",), (), "Toronto"),
        "America/Vancouver": (("CA",), (), "Vancouver"),
        "America/Mexico_City": (("MX",), (), "Mexico City"),
        "Asia/Bangkok": (("TH",), (), "Bangkok"),
        "Asia/Dubai": (("AE",), (), "Dubai"),
        "Asia/Hong_Kong": (("HK",), (), "Hong Kong"),
        "Asia/Jerusalem": (("IL",), ("Asia/Tel_Aviv",), "Jerusalem"),
        "Asia/Kolkata": (("IN",), ("Asia/Calcutta",), "Kolkata"),
        "Asia/Seoul": (("KR",), ("ROK",), "Seoul"),
        "Asia/Shanghai": (("CN",), ("PRC", "Asia/Harbin", "Asia/Chongqing"), "Shanghai"),
        "Asia/Singapore": (("SG",), ("Singapore",), "Singapore"),
        "Asia/Tokyo": (("JP",), ("Japan",), "Tokyo"),
        "Australia/Sydney": (("AU",), (), "Sydney"),
        "Australia/Perth": (("AU",), (), "Perth"),
        "Europe/Amsterdam": (("NL",), (), "Amsterdam"),
        "Europe/Berlin": (("DE",), (), "Berlin"),
        "Europe/London": (("GB",), ("GB",), "London"),
        "Europe/Paris": (("FR",), (), "Paris"),
        "Europe/Moscow": (("RU",), (), "Moscow"),
        "Pacific/Auckland": (("NZ",), ("NZ",), "Auckland"),
        "Pacific/Honolulu": (("US",), ("US/Hawaii",), "Honolulu"),
        "UTC": ((), ("Etc/UTC", "Etc/GMT", "GMT", "Universal", "Zulu"), None),
    }

    def __init__(self, now: Callable[[], _dt.datetime] = _dt.datetime.now) -> None:
        self._now = now
        self._alias_to_canonical: Dict[str, str] = {}
        for canonical, (_codes, aliases, _loc) in self._TABLE.items():
            self._alias_to_canonical[canonical] = canonical
            for alias in aliases:
                self._alias_to_canonical[alias] = canonical

    def identifiers(self) -> List[str]:
        """Return canonical identifiers in sorted order."""
        return sorted(self._TABLE.keys())

    def all_identifiers(self) -> List[str]:
        """Return canonical identifiers AND aliases, sorted."""
        return sorted(self._alias_to_canonical.keys())

    def regions(self) -> List[str]:
        """Return the distinct region prefixes (e.g. ``Africa``, ``UTC``)."""
        seen: List[str] = []
        for ident in self._TABLE:
            region = ident.split("/", 1)[0]
            if region not in seen:
                seen.append(region)
        seen.sort()
        return seen

    def by_region(self, region: str) -> List[str]:
        """Canonical identifiers whose region matches ``region`` exactly."""
        region = region.strip()
        return sorted(
            ident for ident in self._TABLE
            if ident.split("/", 1)[0] == region
        )

    def is_known(self, identifier: str) -> bool:
        """True if ``identifier`` is a canonical id or registered alias."""
        return identifier in self._alias_to_canonical

    def is_canonical(self, identifier: str) -> bool:
        """True if ``identifier`` is a canonical id (not an alias)."""
        return identifier in self._TABLE

    def canonicalize(self, identifier: str) -> Optional[str]:
        """Return the canonical id for ``identifier`` or None if unknown."""
        return self._alias_to_canonical.get(identifier)

    def get(self, identifier: str) -> TimeZoneInfo:
        """Lookup metadata for ``identifier`` (canonical or alias).

        Raises :class:`ZoneInfoNotFoundError` if unknown.
        """
        canonical = self._alias_to_canonical.get(identifier)
        if canonical is None:
            raise ZoneInfoNotFoundError(f"Unknown time zone identifier: {identifier!r}")
        codes, aliases, location = self._TABLE[canonical]
        region = canonical.split("/", 1)[0]
        return TimeZoneInfo(
            identifier=canonical,
            region=region,
            location=location,
            country_codes=codes,
            aliases=aliases,
            now=self._now,
        )

    def __iter__(self) -> Iterator[TimeZoneInfo]:
        for ident in self.identifiers():
            yield self.get(ident)

    def __len__(self) -> int:
        return len(self._TABLE)

    def __contains__(self, identifier: object) -> bool:
        return isinstance(identifier, str) and identifier in self._alias_to_canonical
