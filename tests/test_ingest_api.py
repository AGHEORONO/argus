"""Tests for flight photos ingestion and validation API endpoints."""

import os
import shutil
import pytest
from fastapi.testclient import TestClient

from app.backend.main import app, get_db, init_db
from tests.photo_fixtures import make_photo_set


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


@pytest.fixture
def cleanup_flights():
    created_flight_ids = []
    yield created_flight_ids
    for fid in created_flight_ids:
        flight_dir = os.path.join("data", "flights", fid)
        if os.path.exists(flight_dir):
            shutil.rmtree(flight_dir, ignore_errors=True)
        with get_db() as conn:
            conn.execute("DELETE FROM flights WHERE id = ?", (fid,))
            conn.commit()


def test_upload_photos(tmp_path, cleanup_flights):
    """1. Upload photos -> 200, saved matches count, files exist on disk."""
    flight_id = "test_upload_flight_01"
    cleanup_flights.append(flight_id)

    files = [
        ("files", ("photo_01.jpg", b"fake_jpeg_content_1", "image/jpeg")),
        ("files", ("photo_02.jpg", b"fake_jpeg_content_2", "image/jpeg")),
        ("files", ("photo_03.jpg", b"fake_jpeg_content_3", "image/jpeg")),
    ]

    response = client.post(f"/flights/{flight_id}/photos", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["flight_id"] == flight_id
    assert data["saved"] == 3
    assert data["filenames"] == ["photo_01.jpg", "photo_02.jpg", "photo_03.jpg"]

    # Verify files on disk
    photos_dir = os.path.join("data", "flights", flight_id, "photos")
    for fname in ["photo_01.jpg", "photo_02.jpg", "photo_03.jpg"]:
        file_path = os.path.join(photos_dir, fname)
        assert os.path.isfile(file_path)
        with open(file_path, "rb") as f:
            assert f.read().startswith(b"fake_jpeg_content_")

    # Verify flight record created in database with pending status
    with get_db() as conn:
        cursor = conn.execute("SELECT status FROM flights WHERE id = ?", (flight_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "pending"


def test_validate_good_photo_set(tmp_path, cleanup_flights):
    """2. Validate on good photo set -> 200, accepted True."""
    flight_id = "test_good_flight_02"
    cleanup_flights.append(flight_id)

    photos = make_photo_set(str(tmp_path / "good"), n=6, sharp=True, gps=True, spacing_m=10.0)
    upload_files = []
    for p in photos:
        with open(p, "rb") as f:
            upload_files.append(("files", (os.path.basename(p), f.read(), "image/jpeg")))

    upload_res = client.post(f"/flights/{flight_id}/photos", files=upload_files)
    assert upload_res.status_code == 200
    assert upload_res.json()["saved"] == 6

    val_res = client.post(f"/flights/{flight_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert report["accepted"] is True
    assert report["reasons"] == []
    assert report["summary"]["total"] == 6
    assert len(report["photos"]) == 6


def test_validate_bad_photo_set(tmp_path, cleanup_flights):
    """3. Validate on bad photo set -> 200, accepted False, reasons non-empty."""
    flight_id = "test_bad_flight_03"
    cleanup_flights.append(flight_id)

    photos = make_photo_set(str(tmp_path / "bad"), n=6, sharp=False, gps=False)
    upload_files = []
    for p in photos:
        with open(p, "rb") as f:
            upload_files.append(("files", (os.path.basename(p), f.read(), "image/jpeg")))

    upload_res = client.post(f"/flights/{flight_id}/photos", files=upload_files)
    assert upload_res.status_code == 200

    val_res = client.post(f"/flights/{flight_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert report["accepted"] is False
    assert len(report["reasons"]) > 0


def test_get_validation_after_validate(tmp_path, cleanup_flights):
    """4. GET validation after validate -> returns exact same report."""
    flight_id = "test_val_persist_04"
    cleanup_flights.append(flight_id)

    photos = make_photo_set(str(tmp_path / "persist"), n=6, sharp=True, gps=True, spacing_m=10.0)
    upload_files = []
    for p in photos:
        with open(p, "rb") as f:
            upload_files.append(("files", (os.path.basename(p), f.read(), "image/jpeg")))

    client.post(f"/flights/{flight_id}/photos", files=upload_files)
    val_res = client.post(f"/flights/{flight_id}/validate")
    assert val_res.status_code == 200
    expected_report = val_res.json()

    get_res = client.get(f"/flights/{flight_id}/validation")
    assert get_res.status_code == 200
    assert get_res.json() == expected_report


def test_get_validation_before_validate(cleanup_flights):
    """5. GET validation before validate -> 404."""
    # Case A: flight does not exist at all
    res_nonexistent = client.get("/flights/non_existent_flight_05/validation")
    assert res_nonexistent.status_code == 404

    # Case B: flight exists (e.g. registered via POST /flights) but has not been validated
    flight_id = "test_unvalidated_flight_05"
    cleanup_flights.append(flight_id)

    res_create = client.post("/flights", data={"flight_id": flight_id})
    assert res_create.status_code == 200

    res_unvalidated = client.get(f"/flights/{flight_id}/validation")
    assert res_unvalidated.status_code == 404


def test_validate_flight_no_photos(cleanup_flights):
    """6. Validate on flight without photos -> 400 (or 404 if flight not found)."""
    flight_id = "test_empty_flight_06"
    cleanup_flights.append(flight_id)

    # Create flight entry with no photos uploaded
    res_create = client.post("/flights", data={"flight_id": flight_id})
    assert res_create.status_code == 200

    val_res = client.post(f"/flights/{flight_id}/validate")
    assert val_res.status_code == 400
    assert "No photos" in val_res.json()["detail"]

    # If flight does not exist at all -> 404
    val_res_404 = client.post("/flights/non_existent_flight_06b/validate")
    assert val_res_404.status_code == 404


def test_validate_with_override_query_param(tmp_path, cleanup_flights):
    """7. Validate with overridden query param -> different verdict on same set."""
    flight_id = "test_override_flight_07"
    cleanup_flights.append(flight_id)

    photos = make_photo_set(str(tmp_path / "override"), n=6, sharp=True, gps=True, spacing_m=10.0)
    upload_files = []
    for p in photos:
        with open(p, "rb") as f:
            upload_files.append(("files", (os.path.basename(p), f.read(), "image/jpeg")))

    client.post(f"/flights/{flight_id}/photos", files=upload_files)

    # Default thresholds -> accepted
    res_default = client.post(f"/flights/{flight_id}/validate")
    assert res_default.status_code == 200
    assert res_default.json()["accepted"] is True

    # With strict min_blur_score override -> rejected
    res_overridden = client.post(f"/flights/{flight_id}/validate?min_blur_score=999999.0")
    assert res_overridden.status_code == 200
    assert res_overridden.json()["accepted"] is False
    assert len(res_overridden.json()["reasons"]) > 0


def test_upload_sanitized_filename(cleanup_flights):
    """8. Filename with path traversal ('../evil.jpg') is sanitized, cannot write outside dir."""
    flight_id = "test_sanitize_flight_08"
    cleanup_flights.append(flight_id)

    files = [
        ("files", ("../../evil_traversal_1.jpg", b"evil_payload_1", "image/jpeg")),
        ("files", ("..\\..\\evil_traversal_2.jpg", b"evil_payload_2", "image/jpeg")),
        ("files", ("sub/folder/nested.jpg", b"nested_payload", "image/jpeg")),
    ]

    response = client.post(f"/flights/{flight_id}/photos", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["saved"] == 3

    photos_dir = os.path.join("data", "flights", flight_id, "photos")
    for fn in data["filenames"]:
        assert "/" not in fn
        assert "\\" not in fn
        assert not fn.startswith("..")
        assert os.path.exists(os.path.join(photos_dir, fn))

    # Verify no file escaped outside photos directory
    assert not os.path.exists("evil_traversal_1.jpg")
    assert not os.path.exists("evil_traversal_2.jpg")
    assert not os.path.exists("data/evil_traversal_1.jpg")
    assert not os.path.exists(os.path.join("data", "flights", "evil_traversal_1.jpg"))
