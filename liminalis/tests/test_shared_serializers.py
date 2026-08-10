from datetime import UTC, date, datetime

from backend._shared.serializers import (
    compact_dict,
    date_key,
    domain_from_url,
    isoformat,
    parse_datetime,
    utc_timestamp_z,
)


def test_serializer_helpers_normalize_common_api_values() -> None:
    assert isoformat(date(2026, 6, 7)) == "2026-06-07"
    assert isoformat(datetime(2026, 6, 7, 1, 2, 3, tzinfo=UTC)).startswith("2026-06-07T01:02:03")
    assert domain_from_url("https://www.example.com/path") == "example.com"
    assert compact_dict({"a": 1, "b": None, "c": False}) == {"a": 1, "c": False}


def test_time_helpers_keep_utc_api_shape() -> None:
    value = datetime(2026, 6, 7, 1, 2, 3, tzinfo=UTC)

    assert utc_timestamp_z(value) == "2026-06-07T01:02:03Z"
    assert date_key(value) == "2026-06-07"
    assert parse_datetime("2026-06-07T01:02:03Z") == value
