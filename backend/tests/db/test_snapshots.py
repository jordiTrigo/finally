from app.db import get_snapshots, record_snapshot


def test_no_snapshots_initially(db):
    assert get_snapshots() == []


def test_snapshots_are_returned_oldest_first(db):
    record_snapshot(10000.0)
    record_snapshot(10500.0)
    record_snapshot(9800.0)
    assert [s["total_value"] for s in get_snapshots()] == [10000.0, 10500.0, 9800.0]


def test_snapshot_carries_a_timestamp(db):
    record_snapshot(10000.0)
    assert get_snapshots()[0]["recorded_at"]
