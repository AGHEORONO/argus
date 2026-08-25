"""Keep the test suite out of the production database.

`tests/test_main.py` imported `get_db` directly and wrote to `data/argus.db`, so running
pytest created rows that appeared immediately in the live API — and first in the list,
since `/flights` orders by `updated_at DESC`. One of them had no imagery, which silently
degraded the zone grid in the frontend from raster-anchored to anomaly-anchored.
"""

import os
import tempfile

# Must be set before app.backend.main is imported, since DB_PATH is read at module level.
_TEST_DB = os.path.join(tempfile.gettempdir(), "argus_pytest.db")
os.environ.setdefault("ARGUS_DB_PATH", _TEST_DB)


def pytest_sessionstart(session):
    # A fresh database per run: leftover rows from a previous run are a source of tests
    # that pass only on the second attempt.
    if os.path.exists(_TEST_DB):
        try:
            os.remove(_TEST_DB)
        except OSError:
            pass
