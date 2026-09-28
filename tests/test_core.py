import datetime as dt
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from time_zone_database import TimeZoneDatabase, TimeZoneInfo


class FixedClock:
    """Deterministic clock returning the same naive UTC moment every call."""

    def __init__(self, year=2024, month=1, day=15, hour=12, minute=0, second=0):
        self._moment = dt.datetime(year, month, day, hour, minute, second)

    def __call__(self, tz=None):
        if tz is None:
            return self._moment
        return self._moment.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)


class TestTimeZoneDatabase(unittest.TestCase):
    def setUp(self):
        self.db = TimeZoneDatabase(now=FixedClock(2024, 1, 15, 12, 0, 0))

    def test_identifiers_sorted_and_nonempty(self):
        ids = self.db.identifiers()
        self.assertGreater(len(ids), 10)
        self.assertEqual(ids, sorted(ids))

    def test_all_identifiers_includes_aliases(self):
        all_ids = self.db.all_identifiers()
        self.assertIn("US/Eastern", all_ids)
        self.assertIn("America/New_York", all_ids)
        self.assertIn("Japan", all_ids)
        self.assertIn("Asia/Tokyo", all_ids)

    def test_regions_unique_and_sorted(self):
        regions = self.db.regions()
        self.assertEqual(regions, sorted(regions))
        self.assertIn("Africa", regions)
        self.assertIn("Asia", regions)
        self.assertIn("UTC", regions)
        # No duplicates
        self.assertEqual(len(regions), len(set(regions)))

    def test_by_region_returns_canonical_only(self):
        americas = self.db.by_region("America")
        self.assertIn("America/New_York", americas)
        self.assertIn("America/Argentina/Buenos_Aires", americas)
        # Aliases should NOT appear here
        self.assertNotIn("US/Eastern", americas)
        # Wrong region must not leak
        self.assertNotIn("Asia/Tokyo", americas)

    def test_by_region_case_sensitive(self):
        self.assertEqual(self.db.by_region("america"), [])

    def test_by_region_strips_whitespace(self):
        americas = self.db.by_region("  America  ")
        self.assertIn("America/New_York", americas)

    def test_is_known_canonical_and_alias(self):
        self.assertTrue(self.db.is_known("Asia/Tokyo"))
        self.assertTrue(self.db.is_known("Japan"))
        self.assertFalse(self.db.is_known("Asia/Nonexistent"))

    def test_is_canonical(self):
        self.assertTrue(self.db.is_canonical("Asia/Tokyo"))
        self.assertFalse(self.db.is_canonical("Japan"))
        self.assertFalse(self.db.is_canonical("Asia/Nonexistent"))

    def test_canonicalize(self):
        self.assertEqual(self.db.canonicalize("Japan"), "Asia/Tokyo")
        self.assertEqual(self.db.canonicalize("Asia/Tokyo"), "Asia/Tokyo")
        self.assertIsNone(self.db.canonicalize("Nowhere/Nowhere"))

    def test_get_canonical(self):
        info = self.db.get("Asia/Tokyo")
        self.assertIsInstance(info, TimeZoneInfo)
        self.assertEqual(info.identifier, "Asia/Tokyo")
        self.assertEqual(info.region, "Asia")
        self.assertEqual(info.location, "Tokyo")
        self.assertEqual(info.country_codes, ("JP",))
        self.assertIn("Japan", info.aliases)

    def test_get_resolves_alias(self):
        info = self.db.get("US/Eastern")
        self.assertEqual(info.identifier, "America/New_York")
        self.assertEqual(info.region, "America")

    def test_get_unknown_raises(self):
        with self.assertRaises(ZoneInfoNotFoundError):
            self.db.get("Mars/Olympus_Mons")

    def test_utc_offset_deterministic(self):
        info = self.db.get("Asia/Tokyo")
        self.assertEqual(info.current_utc_offset(), dt.timedelta(hours=9))
        self.assertEqual(info.current_utc_offset_seconds(), 9 * 3600)

    def test_utc_offset_negative(self):
        info = self.db.get("America/New_York")
        # FixedClock is Jan 15 2024 -> EST = UTC-5
        self.assertEqual(info.current_utc_offset(), dt.timedelta(hours=-5))
        self.assertEqual(info.current_utc_offset_seconds(), -5 * 3600)

    def test_utc_offset_zero(self):
        info = self.db.get("UTC")
        self.assertEqual(info.current_utc_offset(), dt.timedelta(0))
        self.assertEqual(info.current_utc_offset_seconds(), 0)

    def test_utc_offset_summer(self):
        summer_db = TimeZoneDatabase(now=FixedClock(2024, 7, 15, 12, 0, 0))
        info = summer_db.get("America/New_York")
        self.assertEqual(info.current_utc_offset(), dt.timedelta(hours=-4))

    def test_repr_and_equality(self):
        a = self.db.get("Asia/Tokyo")
        b = self.db.get("Japan")
        self.assertEqual(a, b)
        self.assertIn("Asia/Tokyo", repr(a))

    def test_hash_by_identifier(self):
        a = self.db.get("Asia/Tokyo")
        b = self.db.get("Japan")
        self.assertEqual(hash(a), hash(b))
        self.assertEqual(len({a, b}), 1)

    def test_len_matches_identifier_count(self):
        self.assertEqual(len(self.db), len(self.db.identifiers()))

    def test_contains(self):
        self.assertIn("Asia/Tokyo", self.db)
        self.assertIn("Japan", self.db)
        self.assertNotIn("Mars/Olympus_Mons", self.db)
        self.assertNotIn(12345, self.db)

    def test_iter_yields_all_canonical(self):
        infos = list(iter(self.db))
        ids = [i.identifier for i in infos]
        self.assertEqual(ids, self.db.identifiers())
        for info in infos:
            self.assertIsInstance(info, TimeZoneInfo)

    def test_multi_segment_region(self):
        info = self.db.get("America/Argentina/Buenos_Aires")
        self.assertEqual(info.region, "America")
        self.assertEqual(info.location, "Buenos Aires")

    def test_utc_has_no_country_codes(self):
        info = self.db.get("UTC")
        self.assertEqual(info.country_codes, ())
        self.assertIsNone(info.location)
        self.assertIn("Etc/UTC", info.aliases)
        self.assertIn("GMT", info.aliases)


if __name__ == "__main__":
    unittest.main()
