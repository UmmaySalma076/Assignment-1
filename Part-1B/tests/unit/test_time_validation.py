from datetime import datetime

import pytest

from reminder_agent.domain.time import (
    TemporalValidationError,
    local_time_candidates,
    require_unambiguous_local_time,
    validate_zoned_datetime,
)


def test_valid_rfc3339_zone_offset_is_preserved():
    value = datetime.fromisoformat("2026-03-05T09:30:00-05:00")
    assert validate_zoned_datetime(value, "America/New_York").hour == 9


def test_zone_offset_mismatch_is_rejected():
    value = datetime.fromisoformat("2026-03-05T09:30:00+00:00")
    with pytest.raises(TemporalValidationError, match="offset"):
        validate_zoned_datetime(value, "America/New_York")


def test_dst_gap_has_no_local_candidates():
    wall = datetime(2026, 3, 8, 2, 30)
    assert local_time_candidates(wall, "America/New_York") == []
    with pytest.raises(TemporalValidationError, match="does not exist"):
        require_unambiguous_local_time(wall, "America/New_York")


def test_dst_fold_has_two_local_candidates():
    wall = datetime(2026, 11, 1, 1, 30)
    assert len(local_time_candidates(wall, "America/New_York")) == 2
    with pytest.raises(TemporalValidationError, match="ambiguous"):
        require_unambiguous_local_time(wall, "America/New_York")


def test_fixed_local_time_has_one_candidate():
    wall = datetime(2026, 3, 5, 9, 30)
    assert len(local_time_candidates(wall, "America/New_York")) == 1
