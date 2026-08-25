"""Security regressions. Each of these was reachable on the live public deployment.

The backend has no authentication and is reachable by anyone with the URL, so "an
unauthenticated caller can do X" is the whole threat model here.
"""

import os
import shutil

import pytest
from fastapi.testclient import TestClient

import app.backend.main as backend
from app.backend.main import app, get_db

client = TestClient(app)


@pytest.fixture
def temp_flights():
    created = []
    yield created
    with get_db() as conn:
        for fid in created:
            shutil.rmtree(os.path.join("data", "flights", fid), ignore_errors=True)
            conn.execute("DELETE FROM flights WHERE id = ?", (fid,))
        conn.commit()


def test_fileless_post_cannot_reset_an_existing_flight(temp_flights):
    """`POST /flights` with only a flight_id used to run an unconditional
    `ON CONFLICT DO UPDATE SET status='pending'`. One unauthenticated request with
    flight_id=test downgraded the public demo, cleared its result, and left it serving
    202 forever — recoverable only by a restart."""
    before = client.get("/flights/test/status")
    if before.status_code != 200:
        pytest.skip("demo flight not provisioned in this environment")
    original = before.json()["status"]

    res = client.post("/flights", data={"flight_id": "test"})
    assert res.status_code == 400

    after = client.get("/flights/test/status").json()
    assert after["status"] == original, "a file-less POST changed an existing flight"
    assert client.get("/flights/test/result").status_code == 200


def test_cors_does_not_reflect_arbitrary_origins_with_credentials():
    """`allow_origins=["*"]` together with `allow_credentials=True` does not send `*`:
    Starlette reflects the caller's Origin and adds Allow-Credentials: true. Any page the
    user visited could then script this API and read the responses."""
    res = client.get("/flights", headers={"Origin": "https://evil.example"})
    headers = {k.lower(): v for k, v in res.headers.items()}

    allow_origin = headers.get("access-control-allow-origin")
    allow_credentials = headers.get("access-control-allow-credentials")

    assert not (allow_origin == "https://evil.example" and allow_credentials == "true"), (
        "backend reflects an arbitrary Origin with credentials enabled"
    )


def test_non_jpeg_uploads_are_rejected_and_reported(temp_flights):
    """The photos endpoint accepted any bytes under any name. It now keeps only JPEGs and
    says which files it refused — silently dropping them would leave the client believing
    it uploaded ten photos when seven arrived."""
    fid = "pytest_sec_types"
    temp_flights.append(fid)

    res = client.post(
        f"/flights/{fid}/photos",
        files=[
            ("files", ("good.jpg", b"jpeg-ish bytes", "image/jpeg")),
            ("files", ("payload.exe", b"MZ\x90\x00", "application/octet-stream")),
            ("files", ("shell.php", b"<?php ?>", "text/plain")),
        ],
    )
    assert res.status_code == 200
    body = res.json()
    assert body["filenames"] == ["good.jpg"]
    assert sorted(body["rejected"]) == ["payload.exe", "shell.php"]

    on_disk = os.listdir(os.path.join("data", "flights", fid, "photos"))
    assert on_disk == ["good.jpg"]


def test_oversized_upload_is_refused_and_leaves_no_partial_file(temp_flights, monkeypatch):
    """There was no size cap anywhere, so any caller could fill the disk of a public
    service. The refusal must also clean up, or a rejected upload still costs the space."""
    fid = "pytest_sec_size"
    temp_flights.append(fid)
    monkeypatch.setattr(backend, "MAX_PHOTO_BYTES", 1024 * 1024)

    ok = client.post(
        f"/flights/{fid}/photos",
        files=[("files", ("small.jpg", b"\x00" * (256 * 1024), "image/jpeg"))],
    )
    assert ok.status_code == 200

    too_big = client.post(
        f"/flights/{fid}/photos",
        files=[("files", ("huge.jpg", b"\x00" * (3 * 1024 * 1024), "image/jpeg"))],
    )
    assert too_big.status_code == 413

    on_disk = sorted(os.listdir(os.path.join("data", "flights", fid, "photos")))
    assert on_disk == ["small.jpg"], f"partial upload left behind: {on_disk}"


@pytest.mark.parametrize(
    "hostile_id",
    ["..", ".", "../..", "../../etc/passwd", "a/b", "a\\b", "....//x", ""],
)
def test_path_traversal_stays_blocked(hostile_id):
    """Regression guard: flight_id is interpolated into filesystem paths in several
    places, and the backend is public."""
    res = client.post(
        f"/flights/{hostile_id}/photos",
        files=[("files", ("a.jpg", b"x", "image/jpeg"))],
    )
    assert res.status_code in (400, 404, 405), res.status_code
    assert not os.path.exists(os.path.join("data", "photos"))


def test_database_path_is_overridable():
    """The suite imported get_db and wrote to the production database, leaving a phantom
    flight visible in the public API — first in the list, since it orders by updated_at."""
    assert backend.DB_PATH == os.environ.get("ARGUS_DB_PATH", "data/argus.db")
