import json
import os
import sqlite3
import pytest
from app.backend.main import app, get_db, init_db, run_detection_job


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


def test_root():
    from app.backend.main import read_root
    res = read_root()
    assert res["status"] == "running"


def test_flight_lifecycle():
    flight_id = "test_unit_flight"
    before = "data/reference/before.tif"
    after = "data/reference/after.tif"

    if not os.path.exists(before) or not os.path.exists(after):
        pytest.skip("Reference files not found for unit test")

    # Run job directly to test function execution
    run_detection_job(flight_id, before, after, top_n=5)

    with get_db() as conn:
        cursor = conn.execute("SELECT status, result FROM flights WHERE id = ?", (flight_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "done"
        result = json.loads(row["result"])
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 5
